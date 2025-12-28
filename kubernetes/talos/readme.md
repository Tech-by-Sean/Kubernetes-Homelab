## Proxmox VM Creation & Talos Linux Cluster

### Order of Operations

This is the **FIRST STEP** in setting up the Kubernetes homelab cluster.

**Prerequisites & Setup Order:**

1. **❌ Proxmox VMs & Talos Linux Cluster** - Base Kubernetes cluster (YOU ARE HERE)
2. ⬜ **MetalLB** - Load balancer for bare metal (`kubernetes/apps/metallb/`)
3. ⬜ **Traefik** - Ingress controller and reverse proxy (`kubernetes/apps/traefik/`)
4. ⬜ **CoreDNS Configuration** - DNS resolution for `.servers.local` domains (`kubernetes/apps/kube-system/coredns-config.yaml`)
5. ⬜ **Forgejo** - Self-hosted Git server (`http://forgejo.servers.local:3000`)
6. ⬜ **GitHub Mirror** - Forgejo configured to mirror to GitHub (backup)
7. ⬜ **ArgoCD** - GitOps continuous delivery
8. ⬜ **TrueNAS NFS Storage** - Direct NFS mounts via PV/PVC for persistent storage
9. ⬜ **Applications** - Media stack, monitoring, etc. (deployed via ArgoCD)

---

### Why Talos Linux?

Talos Linux is a modern, minimal, immutable Linux distribution designed specifically for Kubernetes. It provides:

**Key Benefits:**
- **Immutable Infrastructure:** OS is read-only, preventing configuration drift
- **API-Driven:** No SSH access - all configuration via declarative API
- **Minimal Attack Surface:** No shell, no package manager, only what Kubernetes needs
- **Easy Updates:** Seamless rolling updates without downtime
- **Production-Ready:** Battle-tested security and stability
- **Declarative Configuration:** Entire cluster configuration as code

**Why Proxmox?**
- **Virtualization Platform:** Industry-standard hypervisor for homelab
- **Resource Efficiency:** Run multiple VMs on a single physical host
- **Snapshot & Backup:** Easy VM snapshots and backups
- **High Availability:** Support for clustering and live migration
- **Web UI:** Easy management via web interface

---

### Architecture Overview

**Cluster Configuration:**

This homelab uses **3 control plane nodes + 2 worker nodes** for an optimal balance of high availability and resource efficiency.

**Why This Configuration?**
- ✅ **High Availability:** 3 control plane nodes provide true HA with etcd quorum
- ✅ **Fault Tolerance:** Cluster can tolerate 1 control plane failure and remain fully operational
- ✅ **Resource Efficient:** 2 workers sufficient for homelab workloads
- ✅ **Expandable:** Easy to add more worker nodes as needed

**Cluster Design (3+2 Configuration):**
```
Proxmox Host
├── Control Plane Nodes (VMs)
│   ├── talos-cp-01 (2 vCPU, 4GB RAM, 32GB disk)
│   ├── talos-cp-02 (2 vCPU, 4GB RAM, 32GB disk)
│   └── talos-cp-03 (2 vCPU, 4GB RAM, 32GB disk)
│
└── Worker Nodes (VMs)
    ├── talos-worker-01 (4 vCPU, 8GB RAM, 64GB disk)
    └── talos-worker-02 (4 vCPU, 8GB RAM, 64GB disk)

TrueNAS Server (External - 10.10.5.5)
└── Dataset: gluttonterra (6.71 TiB)
    └── k8s (Parent dataset for Kubernetes storage)
        ├── argocd/
        ├── jellyfin/
        ├── prowlarr/
        ├── qbittorrent/
        ├── radarr/
        ├── sonarr/
        └── ... (other application datasets)
```

**Resource Requirements (3+2 - This Configuration):**
- **Total vCPU:** 14 cores
- **Total RAM:** 28GB
- **Total Storage:** 224GB (local VM disks)
- **External Storage:** TrueNAS NFS shares from `gluttonterra/k8s` dataset

**Why 3 Control Plane Nodes?**
- **etcd Quorum:** Requires majority consensus (2/3 nodes = quorum maintained if 1 fails)
- **High Availability:** With 3 nodes, losing 1 node still allows cluster operations
- **Best Practice:** Industry standard for production-grade Kubernetes clusters

**Why 2 Worker Nodes (vs 3)?**
- **Homelab Workloads:** 2 workers provide enough capacity for typical homelab applications
- **Resource Savings:** Save 4 vCPU and 8GB RAM compared to 3 workers
- **Easy Expansion:** Can add worker-03, worker-04, etc. anytime without downtime

**Storage Architecture:**
- **Local Storage:** VM boot disks on Proxmox (ephemeral, cluster state)
- **Persistent Storage:** TrueNAS NFS shares from `gluttonterra/k8s` dataset
- **Dataset Structure:** Each application has its own child dataset under `k8s`
- **No CSI Driver:** Direct NFS mounts configured in PersistentVolume manifests
- **Worker Node Mounts:** NFS shares mount on worker nodes where pods are scheduled

**Network Requirements:**
- Static IP addresses for all nodes
- Network connectivity between all nodes
- Internet access for pulling container images
- DNS resolution (provided by your router or Technitium DNS)
- Network access to TrueNAS server for NFS mounts (10.10.5.5)

---

### Prerequisites

Before starting, ensure you have:

**Hardware:**
- [ ] Proxmox VE 8.x installed and running
- [ ] Minimum: 14 vCPU, 28GB RAM, 224GB storage available
- [ ] Network switch/router with DHCP or ability to assign static IPs
- [ ] TrueNAS server accessible on network with sufficient storage

**Software:**
- [ ] `talosctl` CLI tool installed on your management machine (laptop/jumpbox)
- [ ] `kubectl` CLI tool installed
- [ ] SSH access to Proxmox host

**Network:**
- [ ] Available IP addresses for cluster nodes (e.g., 10.10.5.10-10.10.5.14)
- [ ] Network gateway configured (e.g., 10.10.5.1)
- [ ] DNS servers configured (e.g., 10.10.5.2, 10.10.5.3)
- [ ] TrueNAS server reachable from cluster at 10.10.5.5

**TrueNAS Storage Setup:**
- [ ] NFS service enabled on TrueNAS
- [ ] Main dataset created: `gluttonterra/k8s`
- [ ] Child datasets created for each application:
```
  gluttonterra/k8s/argocd
  gluttonterra/k8s/jellyfin
  gluttonterra/k8s/prowlarr
  gluttonterra/k8s/qbittorrent
  gluttonterra/k8s/radarr
  gluttonterra/k8s/sonarr
```
- [ ] NFS shares configured for `gluttonterra/k8s` and subdirectories
- [ ] NFS permissions set (allow Kubernetes subnet: 10.10.5.0/24)
- [ ] Authorized Networks configured in NFS share settings

**TrueNAS NFS Share Configuration Example:**
```
Dataset: gluttonterra/k8s
Path: /mnt/gluttonterra/k8s
Authorized Networks: 10.10.5.0/24
Authorized Hosts and IP Addresses: (empty for subnet-based)
Maproot User: root
Maproot Group: wheel
```

**Download Talos Linux ISO:**
```bash
# Download the latest Talos Linux ISO
wget https://github.com/siderolabs/talos/releases/download/v1.9.0/metal-amd64.iso

# Or get the latest release
TALOS_VERSION=$(curl -s https://api.github.com/repos/siderolabs/talos/releases/latest | grep tag_name | cut -d '"' -f 4)
wget https://github.com/siderolabs/talos/releases/download/${TALOS_VERSION}/metal-amd64.iso
```

**Install talosctl and kubectl:**
```bash
# Install talosctl (Linux/macOS)
curl -sL https://talos.dev/install | sh

# Install kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl
sudo mv kubectl /usr/local/bin/

# Verify installations
talosctl version
kubectl version --client
```

---

### Step 1: Upload Talos ISO to Proxmox

**Via Proxmox Web UI:**

1. Log into Proxmox web interface (e.g., `https://proxmox.local:8006`)
2. Click on your Proxmox node in the left sidebar
3. Click **"local (pve)"** → **"ISO Images"**
4. Click **"Upload"** button
5. Select the downloaded `metal-amd64.iso` file
6. Wait for upload to complete

**Via Command Line (SSH to Proxmox):**
```bash
# SSH to Proxmox host
ssh root@proxmox.local

# Download Talos ISO directly to Proxmox
cd /var/lib/vz/template/iso
wget https://github.com/siderolabs/talos/releases/download/v1.9.0/metal-amd64.iso
```

---

### Step 2: Create VMs in Proxmox

You'll create **5 VMs total**: 3 control plane nodes and 2 worker nodes.

#### Create Control Plane Node (talos-cp-01)

**Via Proxmox Web UI:**

1. Click **"Create VM"** button (top right)

2. **General Tab:**
   - **VM ID:** `100` (or next available)
   - **Name:** `talos-cp-01`
   - **Resource Pool:** (optional)

3. **OS Tab:**
   - **ISO Image:** Select `metal-amd64.iso`
   - **Guest OS Type:** Linux
   - **Kernel Version:** 6.x

4. **System Tab:**
   - **SCSI Controller:** VirtIO SCSI
   - **BIOS:** Default (SeaBIOS) or OVMF (UEFI)
   - **Machine:** q35
   - Leave other defaults

5. **Disks Tab:**
   - **Bus/Device:** SCSI 0
   - **Storage:** local-lvm (or your preferred storage)
   - **Disk size:** `32 GB`
   - **Cache:** Write back (unsafe)
   - **Discard:** ✅ Enable
   - **SSD emulation:** ✅ Enable (if using SSD storage)

6. **CPU Tab:**
   - **Sockets:** 1
   - **Cores:** 2
   - **Type:** host (or kvm64)

7. **Memory Tab:**
   - **Memory (MiB):** `4096` (4GB)
   - **Minimum memory:** `4096`
   - **Ballooning:** Disabled

8. **Network Tab:**
   - **Bridge:** vmbr0 (or your network bridge)
   - **Model:** VirtIO (paravirtualized)
   - **MAC address:** auto
   - **Firewall:** ✅ Enable (optional)

9. **Confirm Tab:**
   - Review settings
   - ✅ **Start after created** (uncheck this - we'll configure first)
   - Click **"Finish"**

#### Repeat for Remaining Nodes

**Control Plane Nodes:**
- `talos-cp-01` (VM ID: 100) - 2 vCPU, 4GB RAM, 32GB disk ✅ Created above
- `talos-cp-02` (VM ID: 101) - 2 vCPU, 4GB RAM, 32GB disk
- `talos-cp-03` (VM ID: 102) - 2 vCPU, 4GB RAM, 32GB disk

**Worker Nodes:**
- `talos-worker-01` (VM ID: 103) - 4 vCPU, 8GB RAM, 64GB disk
- `talos-worker-02` (VM ID: 104) - 4 vCPU, 8GB RAM, 64GB disk

**Quick VM Creation via CLI:**
```bash
# SSH to Proxmox host
ssh root@proxmox.local

# Create 3 control plane VMs
for i in {1..3}; do
  qm create $((99 + i)) \
    --name "talos-cp-0${i}" \
    --memory 4096 \
    --cores 2 \
    --net0 virtio,bridge=vmbr0 \
    --scsihw virtio-scsi-pci \
    --scsi0 local-lvm:32 \
    --ide2 local:iso/metal-amd64.iso,media=cdrom \
    --boot order=scsi0 \
    --ostype l26
done

# Create 2 worker VMs
for i in {1..2}; do
  qm create $((102 + i)) \
    --name "talos-worker-0${i}" \
    --memory 8192 \
    --cores 4 \
    --net0 virtio,bridge=vmbr0 \
    --scsihw virtio-scsi-pci \
    --scsi0 local-lvm:64 \
    --ide2 local:iso/metal-amd64.iso,media=cdrom \
    --boot order=scsi0 \
    --ostype l26
done
```

---

### Step 3: Boot VMs and Get IP Addresses

1. **Start all VMs:**
```bash
   # Via Proxmox CLI
   for i in {100..104}; do qm start $i; done
```

   Or via web UI: Select each VM → Click **"Start"** button

2. **Get IP addresses assigned to each VM:**
   
   **Option 1: Via Proxmox Console**
   - Click on VM → **Console**
   - Talos will boot and display its IP address
   - Record the IP for each node

   **Option 2: Check DHCP leases on your router**
   - Look for devices named `talos-cp-01`, `talos-worker-01`, etc.

   **Option 3: Scan network**
```bash
   nmap -sn 10.10.5.0/24
```

3. **Document the IP addresses:**
   
   **3+2 Configuration:**
```
   talos-cp-01:     10.10.5.10
   talos-cp-02:     10.10.5.11
   talos-cp-03:     10.10.5.12
   talos-worker-01: 10.10.5.13
   talos-worker-02: 10.10.5.14
   TrueNAS:         10.10.5.5
```

**Optional: Configure Static IPs in Router/DHCP**
- Reserve these IP addresses to prevent DHCP from reassigning them
- Or configure static IPs in Talos configuration (next step)

---

### Step 4: Generate Talos Configuration

On your management machine (laptop/jumpbox):
```bash
# Create a directory for Talos configs
mkdir -p ~/talos-cluster
cd ~/talos-cluster

# Generate configuration files
# Use the IP of your FIRST control plane node
talosctl gen config talos-homelab https://10.10.5.10:6443 \
  --output-dir .

# This creates:
# - controlplane.yaml (control plane node config)
# - worker.yaml (worker node config)
# - talosconfig (CLI configuration for managing cluster)
```

**Customize Configuration (Recommended):**

Edit `controlplane.yaml` and `worker.yaml` to add:
- Static IP addresses
- DNS servers
- NTP servers
- Custom settings

**Example: Add static IP to controlplane.yaml:**
```yaml
machine:
  network:
    hostname: talos-cp-01
    interfaces:
      - interface: eth0
        addresses:
          - 10.10.5.10/24
        routes:
          - network: 0.0.0.0/0
            gateway: 10.10.5.1
    nameservers:
      - 10.10.5.2
      - 10.10.5.3
  time:
    servers:
      - time.cloudflare.com
```

**Create separate config files for each node (optional but recommended):**

You can create individual configs for better organization:
```bash
# Copy base configs
cp controlplane.yaml controlplane-cp-01.yaml
cp controlplane.yaml controlplane-cp-02.yaml
cp controlplane.yaml controlplane-cp-03.yaml
cp worker.yaml worker-01.yaml
cp worker.yaml worker-02.yaml

# Edit each file with appropriate hostname and IP
# controlplane-cp-01.yaml → hostname: talos-cp-01, IP: 10.10.5.10
# controlplane-cp-02.yaml → hostname: talos-cp-02, IP: 10.10.5.11
# controlplane-cp-03.yaml → hostname: talos-cp-03, IP: 10.10.5.12
# worker-01.yaml → hostname: talos-worker-01, IP: 10.10.5.13
# worker-02.yaml → hostname: talos-worker-02, IP: 10.10.5.14
```

---

### Step 5: Apply Configuration to Nodes

Apply the configuration to each node:
```bash
# Configure control plane nodes
talosctl apply-config --insecure \
  --nodes 10.10.5.10 \
  --file controlplane.yaml

talosctl apply-config --insecure \
  --nodes 10.10.5.11 \
  --file controlplane.yaml

talosctl apply-config --insecure \
  --nodes 10.10.5.12 \
  --file controlplane.yaml

# Configure worker nodes
talosctl apply-config --insecure \
  --nodes 10.10.5.13 \
  --file worker.yaml

talosctl apply-config --insecure \
  --nodes 10.10.5.14 \
  --file worker.yaml
```

**Or if using individual config files:**
```bash
talosctl apply-config --insecure --nodes 10.10.5.10 --file controlplane-cp-01.yaml
talosctl apply-config --insecure --nodes 10.10.5.11 --file controlplane-cp-02.yaml
talosctl apply-config --insecure --nodes 10.10.5.12 --file controlplane-cp-03.yaml
talosctl apply-config --insecure --nodes 10.10.5.13 --file worker-01.yaml
talosctl apply-config --insecure --nodes 10.10.5.14 --file worker-02.yaml
```

**Note:** The `--insecure` flag is used during initial setup. After bootstrapping, Talos will use certificates for authentication.

**Wait for nodes to reboot and apply configuration (2-5 minutes).**

---

### Step 6: Bootstrap the Cluster

Bootstrap the first control plane node to initialize the Kubernetes cluster:
```bash
# Set talosctl endpoint and nodes
export TALOSCONFIG=~/talos-cluster/talosconfig
talosctl config endpoint 10.10.5.10 10.10.5.11 10.10.5.12
talosctl config node 10.10.5.10

# Bootstrap the cluster (only run once on ONE control plane node)
talosctl bootstrap --nodes 10.10.5.10
```

**⚠️ CRITICAL:** Only run `bootstrap` **ONCE** on **ONE** control plane node (talos-cp-01). Running it multiple times or on multiple nodes will break the cluster.

**Wait for bootstrap to complete (5-10 minutes).**

**Monitor bootstrap progress:**
```bash
talosctl dmesg --follow --nodes 10.10.5.10
```

---

### Step 7: Retrieve kubeconfig

Once the cluster is bootstrapped, get the kubeconfig:
```bash
# Generate kubeconfig
talosctl kubeconfig --nodes 10.10.5.10 \
  --force \
  --merge=false \
  ~/talos-cluster/kubeconfig

# Set KUBECONFIG environment variable
export KUBECONFIG=~/talos-cluster/kubeconfig

# Or merge into default kubeconfig
talosctl kubeconfig --nodes 10.10.5.10 --force
```

---

### Step 8: Verify Cluster
```bash
# Check cluster info
kubectl cluster-info

# Check all nodes are Ready
kubectl get nodes -o wide

# Expected output (3+2 configuration):
# NAME              STATUS   ROLES           AGE   VERSION
# talos-cp-01       Ready    control-plane   10m   v1.31.0
# talos-cp-02       Ready    control-plane   10m   v1.31.0
# talos-cp-03       Ready    control-plane   10m   v1.31.0
# talos-worker-01   Ready    <none>          10m   v1.31.0
# talos-worker-02   Ready    <none>          10m   v1.31.0

# Check system pods
kubectl get pods -A

# All pods should be Running (kube-system, kube-public, kube-node-lease)
```

**If nodes show "NotReady":**
- Wait a few more minutes for CNI (network plugin) to initialize
- Check logs: `talosctl logs --nodes 10.10.5.10`

**Verify etcd cluster health:**
```bash
# Should show 3 members
talosctl etcd members --nodes 10.10.5.10

# Expected output:
# NODE          MEMBER              ID                HOSTNAME        PEER URLS
# 10.10.5.10    talos-cp-01         xxxxxxxxxxxx      talos-cp-01     https://10.10.5.10:2380
# 10.10.5.10    talos-cp-02         xxxxxxxxxxxx      talos-cp-02     https://10.10.5.11:2380
# 10.10.5.10    talos-cp-03         xxxxxxxxxxxx      talos-cp-03     https://10.10.5.12:2380
```

**Check etcd health:**
```bash
talosctl health --nodes 10.10.5.10,10.10.5.11,10.10.5.12
```

---

### Step 9: Verify TrueNAS NFS Connectivity

Before proceeding with application deployments, verify that worker nodes can access TrueNAS NFS shares:
```bash
# Test network connectivity to TrueNAS
kubectl run -it --rm nfs-test --image=busybox --restart=Never -- ping -c 3 10.10.5.5

# Test NFS mount to the main k8s dataset
kubectl run -it --rm nfs-mount-test --image=busybox --restart=Never -- \
  sh -c "mkdir -p /mnt/test && mount -t nfs 10.10.5.5:/mnt/gluttonterra/k8s /mnt/test && ls -la /mnt/test && umount /mnt/test"

# Expected output should show your application subdirectories:
# drwxr-xr-x    2 root     root          4096 Dec 28 12:00 argocd
# drwxr-xr-x    2 root     root          4096 Dec 28 12:00 jellyfin
# drwxr-xr-x    2 root     root          4096 Dec 28 12:00 prowlarr
# drwxr-xr-x    2 root     root          4096 Dec 28 12:00 qbittorrent
# drwxr-xr-x    2 root     root          4096 Dec 28 12:00 radarr
# drwxr-xr-x    2 root     root          4096 Dec 28 12:00 sonarr
```

**If NFS mount fails:**
- Verify NFS service is running on TrueNAS
- Check NFS share is configured for `gluttonterra/k8s`
- Ensure authorized networks include 10.10.5.0/24
- Verify firewall rules allow NFS traffic (ports 111, 2049)
- Check TrueNAS dataset permissions

**Test individual application dataset:**
```bash
# Test mounting specific application dataset (e.g., Jellyfin)
kubectl run -it --rm nfs-jellyfin-test --image=busybox --restart=Never -- \
  sh -c "mount -t nfs 10.10.5.5:/mnt/gluttonterra/k8s/jellyfin /mnt && ls -la /mnt"
```

---

### TrueNAS Dataset Structure for Applications

Each application in your Kubernetes cluster will have its own dataset under `gluttonterra/k8s`:

**Dataset Hierarchy:**
```
gluttonterra (pool)
└── k8s (parent dataset - 6.71 TiB available)
    ├── argocd/           → NFS path: /mnt/gluttonterra/k8s/argocd
    ├── jellyfin/         → NFS path: /mnt/gluttonterra/k8s/jellyfin
    ├── prowlarr/         → NFS path: /mnt/gluttonterra/k8s/prowlarr
    ├── qbittorrent/      → NFS path: /mnt/gluttonterra/k8s/qbittorrent
    ├── radarr/           → NFS path: /mnt/gluttonterra/k8s/radarr
    └── sonarr/           → NFS path: /mnt/gluttonterra/k8s/sonarr
```

**Application PV/PVC Configuration Pattern:**

Each application will use this pattern in their manifests:
```yaml
# Example for Jellyfin config storage
apiVersion: v1
kind: PersistentVolume
metadata:
  name: jellyfin-config-pv
spec:
  capacity:
    storage: 50Gi
  accessModes:
    - ReadWriteMany
  nfs:
    server: 10.10.5.5
    path: /mnt/gluttonterra/k8s/jellyfin
  mountOptions:
    - nfsvers=4
    - hard
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: jellyfin-config-pvc
  namespace: media
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 50Gi
  volumeName: jellyfin-config-pv
```

**Benefits of This Structure:**
- ✅ **Organized:** Each app has dedicated storage
- ✅ **Isolated:** Datasets can have independent quotas, snapshots, permissions
- ✅ **Scalable:** Easy to add new application datasets
- ✅ **Manageable:** TrueNAS snapshots/backups per application
- ✅ **Flexible:** Different NFS mount options per application if needed

---

### Expanding the Cluster (Adding Nodes)

Your cluster is fully operational with 3 control plane + 2 worker nodes. However, you can easily expand it as your resource availability or workload demands increase.

#### Adding Another Worker Node (Recommended for Load Distribution)

**When to add a worker:**
- Running many applications and need more capacity
- Want better workload distribution
- Experiencing resource constraints on existing workers

**Step 1: Create VM in Proxmox**
```bash
# Via Proxmox CLI
qm create 105 \
  --name "talos-worker-03" \
  --memory 8192 \
  --cores 4 \
  --net0 virtio,bridge=vmbr0 \
  --scsihw virtio-scsi-pci \
  --scsi0 local-lvm:64 \
  --ide2 local:iso/metal-amd64.iso,media=cdrom \
  --boot order=scsi0 \
  --ostype l26

# Start the VM
qm start 105
```

**Or via Proxmox Web UI:**
- Follow same steps as Step 2 above
- Name: `talos-worker-03`
- VM ID: `105`
- 4 vCPU, 8GB RAM, 64GB disk

**Step 2: Get IP Address**

Boot the VM and note its IP address (e.g., `10.10.5.15`)

**Step 3: Apply Configuration**
```bash
# Use the same worker.yaml from initial setup
talosctl apply-config --insecure \
  --nodes 10.10.5.15 \
  --file worker.yaml

# Or create a custom config:
# cp worker.yaml worker-03.yaml
# Edit worker-03.yaml with hostname: talos-worker-03, IP: 10.10.5.15
# talosctl apply-config --insecure --nodes 10.10.5.15 --file worker-03.yaml
```

**Step 4: Verify Node Joined**
```bash
# Wait 2-3 minutes, then check
kubectl get nodes

# Should now show:
# NAME              STATUS   ROLES           AGE   VERSION
# talos-cp-01       Ready    control-plane   1h    v1.31.0
# talos-cp-02       Ready    control-plane   1h    v1.31.0
# talos-cp-03       Ready    control-plane   1h    v1.31.0
# talos-worker-01   Ready    <none>          1h    v1.31.0
# talos-worker-02   Ready    <none>          1h    v1.31.0
# talos-worker-03   Ready    <none>          2m    v1.31.0  ← New node!
```

**That's it! The new worker is ready to accept workloads and can mount TrueNAS NFS shares.**

#### Adding Another Control Plane Node (For Extra Redundancy)

**When to add a control plane:**
- Want even higher availability (can tolerate 2 node failures)
- Running critical production workloads
- Have extra resources available

**⚠️ Note:** Going from 3 to 4 control plane nodes does **NOT** increase fault tolerance. You'd need 5 nodes to tolerate 2 failures. However, it does provide extra capacity for control plane operations.

**Step 1: Create VM in Proxmox**
```bash
# Via Proxmox CLI
qm create 106 \
  --name "talos-cp-04" \
  --memory 4096 \
  --cores 2 \
  --net0 virtio,bridge=vmbr0 \
  --scsihw virtio-scsi-pci \
  --scsi0 local-lvm:32 \
  --ide2 local:iso/metal-amd64.iso,media=cdrom \
  --boot order=scsi0 \
  --ostype l26

# Start the VM
qm start 106
```

**Step 2: Get IP Address**

Boot the VM and note its IP address (e.g., `10.10.5.16`)

**Step 3: Apply Configuration**
```bash
# Use the same controlplane.yaml from initial setup
talosctl apply-config --insecure \
  --nodes 10.10.5.16 \
  --file controlplane.yaml
```

**Step 4: Update talosctl Endpoints**
```bash
# Add the new control plane node to your endpoints
talosctl config endpoint 10.10.5.10 10.10.5.11 10.10.5.12 10.10.5.16
```

**Step 5: Verify Node Joined**
```bash
# Check nodes
kubectl get nodes

# Check etcd members (should show 4 now)
talosctl etcd members --nodes 10.10.5.10
```

**Congratulations! You now have 4 control plane nodes.**

#### Scaling Summary

**Current Cluster (3+2):**
- ✅ Highly available (tolerates 1 control plane failure)
- ✅ Sufficient capacity for homelab workloads
- ✅ Resource efficient

**Add Worker-03 (3+3):**
- ✅ Better workload distribution
- ✅ More capacity for applications
- Cost: +4 vCPU, +8GB RAM, +64GB storage

**Add CP-04 (4+2 or 4+3):**
- ✅ Extra control plane capacity
- ⚠️ Same fault tolerance as 3 nodes (need 5 for 2-node tolerance)
- Cost: +2 vCPU, +4GB RAM, +32GB storage

**Recommendation:** Add workers before adding a 4th control plane unless you plan to scale to 5 control planes.

---

### Cluster Management Commands

**Common talosctl commands:**
```bash
# Check node health
talosctl health --nodes 10.10.5.10,10.10.5.11,10.10.5.12

# View logs
talosctl logs --nodes 10.10.5.10 --tail

# Check service status
talosctl service --nodes 10.10.5.10

# Reboot a node
talosctl reboot --nodes 10.10.5.13

# Upgrade Talos version
talosctl upgrade --nodes 10.10.5.10 \
  --image ghcr.io/siderolabs/installer:v1.9.0

# Edit machine config
talosctl edit mc --nodes 10.10.5.10

# Get etcd status
talosctl etcd status --nodes 10.10.5.10
```

**Common kubectl commands:**
```bash
# View all resources
kubectl get all -A

# Describe a node
kubectl describe node talos-cp-01

# Check cluster events
kubectl get events -A --sort-by='.lastTimestamp'

# Drain a node for maintenance
kubectl drain talos-worker-01 --ignore-daemonsets --delete-emptydir-data

# Uncordon node after maintenance
kubectl uncordon talos-worker-01

# Delete a node (before removing VM)
kubectl delete node talos-worker-03
```

---

### Understanding High Availability (3 Control Plane Nodes)

**What Happens if One Control Plane Node Fails:**

With 3 control plane nodes:
- **etcd requires majority quorum:** 3 nodes = need 2 votes for consensus
- **If 1 node fails:** 2 remaining nodes maintain quorum (2/3 = majority)
- **Cluster remains fully operational:** All operations continue normally
- **Zero downtime:** Users don't notice anything

**What You Can Do During a Failure:**
- ✅ Create new resources
- ✅ Update existing resources
- ✅ Delete resources
- ✅ Scale deployments
- ✅ Apply manifests
- ✅ All kubectl operations work

**Recovery:**
- Restore the failed control plane node when convenient
- No urgency - cluster runs fine on 2 control planes
- Once restored, it automatically rejoins the etcd cluster

**This is why 3 control plane nodes is the sweet spot for homelab!**

---

### Troubleshooting

**Issue: Nodes stuck in "NotReady"**
```bash
# Check CNI pods
kubectl get pods -n kube-system | grep -E 'flannel|calico|cilium'

# Check kubelet logs
talosctl logs --nodes 10.10.5.10 kubelet

# Check for network issues
talosctl logs --nodes 10.10.5.10 -k | grep -i network
```

**Issue: Cannot connect to cluster**
```bash
# Verify talosctl can reach nodes
talosctl health --nodes 10.10.5.10

# Check API server is running
talosctl service kube-apiserver --nodes 10.10.5.10

# Regenerate kubeconfig
talosctl kubeconfig --nodes 10.10.5.10 --force
```

**Issue: Bootstrap fails**
```bash
# Check bootstrap logs
talosctl dmesg --nodes 10.10.5.10

# Reset and try again (ONLY IF CLUSTER NOT YET CREATED)
talosctl reset --nodes 10.10.5.10 --graceful=false
# Then re-apply config and bootstrap
```

**Issue: etcd not healthy**
```bash
# Check etcd member list
talosctl etcd members --nodes 10.10.5.10

# Check etcd status on each control plane
talosctl etcd status --nodes 10.10.5.10
talosctl etcd status --nodes 10.10.5.11
talosctl etcd status --nodes 10.10.5.12

# Verify all 3 members are listed and healthy
```

**Issue: Network connectivity problems**
- Verify Proxmox network bridge (vmbr0) is configured correctly
- Check firewall rules on Proxmox host
- Ensure VMs can reach gateway and internet
- Verify DNS resolution works: `talosctl get addresses --nodes 10.10.5.10`

**Issue: New node won't join**
```bash
# Check node can reach existing cluster
# From new node, ping control plane IPs
talosctl logs --nodes 10.10.5.15 -k | grep -i "failed to"

# Verify configuration was applied
talosctl get machineconfig --nodes 10.10.5.15

# Check if API server is reachable from new node
talosctl logs --nodes 10.10.5.15 kubelet
```

**Issue: Cannot mount TrueNAS NFS shares**
```bash
# Verify network connectivity to TrueNAS
kubectl run -it --rm debug --image=busybox --restart=Never -- ping -c 3 10.10.5.5

# Test NFS mount from a pod
kubectl run -it --rm nfs-test --image=busybox --restart=Never -- \
  sh -c "mount -t nfs 10.10.5.5:/mnt/gluttonterra/k8s /mnt && ls -la /mnt"

# Check if NFS packages are available (Talos includes NFS client)
talosctl logs --nodes 10.10.5.13 -k | grep -i nfs

# Verify NFS share configuration on TrueNAS
# - Dataset: gluttonterra/k8s
# - Path: /mnt/gluttonterra/k8s
# - Authorized networks: 10.10.5.0/24
# - Maproot user: root
# - Maproot group: wheel
```

**Issue: PersistentVolume stuck in "Pending"**
```bash
# Check PV status
kubectl get pv
kubectl describe pv <pv-name>

# Check PVC status
kubectl get pvc -n <namespace>
kubectl describe pvc <pvc-name> -n <namespace>

# Common causes:
# - Incorrect NFS server IP in PV manifest (should be 10.10.5.5)
# - Wrong NFS path in PV manifest (should be /mnt/gluttonterra/k8s/<app>)
# - NFS share not accessible from worker nodes
# - Missing storage class (use empty string "" for no storage class)
```

**Issue: Permission denied when writing to NFS mount**
```bash
# Check TrueNAS dataset permissions
# On TrueNAS:
# - Maproot User should be: root
# - Maproot Group should be: wheel
# - Or configure specific UID/GID for applications

# Test write access
kubectl run -it --rm nfs-write-test --image=busybox --restart=Never -- \
  sh -c "mount -t nfs 10.10.5.5:/mnt/gluttonterra/k8s/jellyfin /mnt && touch /mnt/test.txt && ls -la /mnt/test.txt && rm /mnt/test.txt"
```

---

### Next Steps

Once your cluster is up and running with all nodes showing "Ready":

✅ **Talos Linux Cluster - Complete!**

**Your cluster now has:**
- ✅ 3 control plane nodes (high availability)
- ✅ 2 worker nodes (sufficient for homelab)
- ✅ etcd quorum established
- ✅ Kubernetes API accessible
- ✅ All system pods running
- ✅ NFS connectivity to TrueNAS `gluttonterra/k8s` verified

**Proceed to:**
2. ⬜ **MetalLB Installation** - Deploy load balancer for bare metal services
   - Required for exposing services outside the cluster
   - Provides LoadBalancer IP addresses for Traefik, applications, etc.

**After MetalLB, you'll install:**
3. ⬜ Traefik (ingress controller)
4. ⬜ CoreDNS configuration
5. ⬜ Forgejo (Git server)
6. ⬜ ArgoCD (GitOps)
7. ⬜ Applications with NFS-backed PersistentVolumes
   - Each app will mount its respective dataset from `gluttonterra/k8s/<app-name>`
   - Jellyfin: `/mnt/gluttonterra/k8s/jellyfin`
   - Sonarr: `/mnt/gluttonterra/k8s/sonarr`
   - Radarr: `/mnt/gluttonterra/k8s/radarr`
   - etc.

---

### Backup & Disaster Recovery

**Backup Configuration Files:**
```bash
# Always backup these files!
mkdir -p ~/backups/talos-cluster-$(date +%Y%m%d)
cp ~/talos-cluster/talosconfig ~/backups/talos-cluster-$(date +%Y%m%d)/
cp ~/talos-cluster/controlplane.yaml ~/backups/talos-cluster-$(date +%Y%m%d)/
cp ~/talos-cluster/worker.yaml ~/backups/talos-cluster-$(date +%Y%m%d)/
cp ~/talos-cluster/kubeconfig ~/backups/talos-cluster-$(date +%Y%m%d)/

# Store backups in multiple locations (external drive, cloud, etc.)
```

**Snapshot VMs in Proxmox:**
```bash
# Take snapshots of all nodes after successful setup
for i in {100..104}; do
  qm snapshot $i initial-setup --description "Initial cluster setup - $(date)"
done
```

Or via Proxmox UI:
- Select VM → Snapshots → Take Snapshot
- Name: `initial-setup`
- Description: `Cluster bootstrapped and verified`

**Export etcd Backup:**
```bash
# Take regular etcd backups (automate this with a cron job)
talosctl etcd snapshot --nodes 10.10.5.10 ~/backups/etcd-backup-$(date +%Y%m%d).db

# Restore from backup (if needed)
# talosctl etcd snapshot restore --nodes 10.10.5.10 ~/backups/etcd-backup-YYYYMMDD.db
```

**Backup Application Data on TrueNAS:**

Configure TrueNAS snapshot tasks for the `gluttonterra/k8s` dataset:

**Recommended TrueNAS Snapshot Schedule:**
```
Dataset: gluttonterra/k8s
Recursive: Yes (includes all child datasets)
Schedule:
  - Hourly snapshots: Keep 24
  - Daily snapshots: Keep 7
  - Weekly snapshots: Keep 4
  - Monthly snapshots: Keep 12
```

**Configure via TrueNAS UI:**
1. Storage → Snapshots → Add Periodic Snapshot Task
2. Dataset: `gluttonterra/k8s`
3. Recursive: ✅ Enabled
4. Schedule: Configure retention as above
5. Naming: `auto-%Y-%m-%d_%H-%M`

**Automated Backup Script (Recommended):**
```bash
#!/bin/bash
# Save as ~/bin/backup-talos-cluster.sh

BACKUP_DIR=~/backups/talos-cluster-$(date +%Y%m%d)
mkdir -p $BACKUP_DIR

# Backup configs
cp ~/talos-cluster/* $BACKUP_DIR/

# Backup etcd
talosctl etcd snapshot --nodes 10.10.5.10 $BACKUP_DIR/etcd-backup.db

# Backup all Kubernetes resources
kubectl get all -A -o yaml > $BACKUP_DIR/all-resources.yaml

# Backup PV/PVC definitions
kubectl get pv -o yaml > $BACKUP_DIR/persistent-volumes.yaml
kubectl get pvc -A -o yaml > $BACKUP_DIR/persistent-volume-claims.yaml

echo "Backup completed: $BACKUP_DIR"
echo "Note: Application data backed up via TrueNAS snapshots on gluttonterra/k8s"
```

**Schedule weekly backups:**
```bash
# Add to crontab
crontab -e

# Add this line (runs every Sunday at 2 AM)
0 2 * * 0 ~/bin/backup-talos-cluster.sh
```

---

### Related Documentation

- **Talos Documentation:** https://www.talos.dev/
- **Kubernetes Documentation:** https://kubernetes.io/docs/
- **Kubernetes NFS Volumes:** https://kubernetes.io/docs/concepts/storage/volumes/#nfs
- **Proxmox Documentation:** https://pve.proxmox.com/pve-docs/
- **TrueNAS Documentation:** https://www.truenas.com/docs/
- **Next Step:** MetalLB Installation (`kubernetes/apps/metallb/readme.md`)

---

### Quick Reference

**Node Information:**
```
Control Plane Nodes (3):
├── talos-cp-01:     10.10.5.10  (2 vCPU, 4GB RAM, 32GB disk)
├── talos-cp-02:     10.10.5.11  (2 vCPU, 4GB RAM, 32GB disk)
└── talos-cp-03:     10.10.5.12  (2 vCPU, 4GB RAM, 32GB disk)

Worker Nodes (2):
├── talos-worker-01: 10.10.5.13  (4 vCPU, 8GB RAM, 64GB disk)
└── talos-worker-02: 10.10.5.14  (4 vCPU, 8GB RAM, 64GB disk)

Total Resources: 14 vCPU, 28GB RAM, 224GB storage

External Storage:
└── TrueNAS Server: 10.10.5.5
    └── Dataset: gluttonterra/k8s (6.71 TiB available)
        ├── /mnt/gluttonterra/k8s/argocd
        ├── /mnt/gluttonterra/k8s/jellyfin
        ├── /mnt/gluttonterra/k8s/prowlarr
        ├── /mnt/gluttonterra/k8s/qbittorrent
        ├── /mnt/gluttonterra/k8s/radarr
        └── /mnt/gluttonterra/k8s/sonarr
```

**Essential Commands:**
```bash
# Check cluster health
kubectl get nodes
talosctl health --nodes 10.10.5.10,10.10.5.11,10.10.5.12

# View all pods
kubectl get pods -A

# Check etcd
talosctl etcd members --nodes 10.10.5.10

# Update kubeconfig
talosctl kubeconfig --nodes 10.10.5.10 --force

# Test NFS connectivity to k8s dataset
kubectl run -it --rm nfs-test --image=busybox --restart=Never -- \
  mount -t nfs 10.10.5.5:/mnt/gluttonterra/k8s /mnt
```

**Example PV/PVC for Jellyfin:**
```yaml
# PersistentVolume
apiVersion: v1
kind: PersistentVolume
metadata:
  name: jellyfin-config-pv
spec:
  capacity:
    storage: 100Gi
  accessModes:
    - ReadWriteMany
  nfs:
    server: 10.10.5.5
    path: /mnt/gluttonterra/k8s/jellyfin
  mountOptions:
    - nfsvers=4
    - hard
---
# PersistentVolumeClaim
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: jellyfin-config-pvc
  namespace: media
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 100Gi
  volumeName: jellyfin-config-pv
```