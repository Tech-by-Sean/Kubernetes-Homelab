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
│   ├── talos-cp-01 (2 vCPU, 4GB RAM, 32GB disk) - 10.10.5.200
│   ├── talos-cp-02 (2 vCPU, 4GB RAM, 32GB disk) - 10.10.5.201
│   └── talos-cp-03 (2 vCPU, 4GB RAM, 32GB disk) - 10.10.5.202
│
└── Worker Nodes (VMs)
    ├── talos-worker-01 (4 vCPU, 8GB RAM, 64GB disk) - 10.10.5.203
    └── talos-worker-02 (4 vCPU, 8GB RAM, 64GB disk) - 10.10.5.204

TrueNAS Server (External - 10.10.5.40)
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
- Network access to TrueNAS server for NFS mounts (10.10.5.40)

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
- [ ] Available IP addresses for cluster nodes:
  - Control Plane: 10.10.5.200-202
  - Workers: 10.10.5.203-204
  - TrueNAS: 10.10.5.40
- [ ] Network gateway configured (e.g., 10.10.5.1)
- [ ] DNS servers configured (e.g., 10.10.5.2, 10.10.5.3)

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

### Step 1: Download Talos Installer Image

On your Proxmox host, download the Talos nocloud installer image:
```bash
# SSH to Proxmox host
ssh root@proxmox.local

# Navigate to images directory
cd /var/lib/vz/template/iso

# Download latest Talos nocloud image (v1.9.0)
wget https://github.com/siderolabs/talos/releases/download/v1.9.0/nocloud-amd64.raw.xz

# Extract the image
xz -d nocloud-amd64.raw.xz

# Verify download
ls -lh nocloud-amd64.raw
```

**Alternative: Download on your local machine and upload to Proxmox**
```bash
# Download on local machine
wget https://github.com/siderolabs/talos/releases/download/v1.9.0/nocloud-amd64.raw.xz
xz -d nocloud-amd64.raw.xz

# Upload to Proxmox (from local machine)
scp nocloud-amd64.raw root@proxmox.local:/var/lib/vz/template/iso/
```

---

### Step 2: Create VMs Using Talos Image

We'll create VMs using the Proxmox CLI, following the official Talos documentation approach.

#### Create Control Plane Nodes

**Create talos-cp-01 (VM ID 100):**
```bash
# SSH to Proxmox host
ssh root@proxmox.local

# Create VM with Talos disk
qm create 100 \
  --name talos-cp-01 \
  --memory 4096 \
  --cores 2 \
  --net0 virtio,bridge=vmbr0 \
  --scsihw virtio-scsi-pci \
  --ostype l26

# Import the Talos disk
qm importdisk 100 /var/lib/vz/template/iso/nocloud-amd64.raw local-lvm

# Attach the imported disk
qm set 100 --scsi0 local-lvm:vm-100-disk-0

# Set boot order
qm set 100 --boot order=scsi0

# Add serial console (recommended for troubleshooting)
qm set 100 --serial0 socket --vga serial0
```

**Create talos-cp-02 (VM ID 101):**
```bash
qm create 101 \
  --name talos-cp-02 \
  --memory 4096 \
  --cores 2 \
  --net0 virtio,bridge=vmbr0 \
  --scsihw virtio-scsi-pci \
  --ostype l26

qm importdisk 101 /var/lib/vz/template/iso/nocloud-amd64.raw local-lvm
qm set 101 --scsi0 local-lvm:vm-101-disk-0
qm set 101 --boot order=scsi0
qm set 101 --serial0 socket --vga serial0
```

**Create talos-cp-03 (VM ID 102):**
```bash
qm create 102 \
  --name talos-cp-03 \
  --memory 4096 \
  --cores 2 \
  --net0 virtio,bridge=vmbr0 \
  --scsihw virtio-scsi-pci \
  --ostype l26

qm importdisk 102 /var/lib/vz/template/iso/nocloud-amd64.raw local-lvm
qm set 102 --scsi0 local-lvm:vm-102-disk-0
qm set 102 --boot order=scsi0
qm set 102 --serial0 socket --vga serial0
```

#### Create Worker Nodes

**Create talos-worker-01 (VM ID 103):**
```bash
qm create 103 \
  --name talos-worker-01 \
  --memory 8192 \
  --cores 4 \
  --net0 virtio,bridge=vmbr0 \
  --scsihw virtio-scsi-pci \
  --ostype l26

qm importdisk 103 /var/lib/vz/template/iso/nocloud-amd64.raw local-lvm
qm set 103 --scsi0 local-lvm:vm-103-disk-0
qm set 103 --boot order=scsi0
qm set 103 --serial0 socket --vga serial0
```

**Create talos-worker-02 (VM ID 104):**
```bash
qm create 104 \
  --name talos-worker-02 \
  --memory 8192 \
  --cores 4 \
  --net0 virtio,bridge=vmbr0 \
  --scsihw virtio-scsi-pci \
  --ostype l26

qm importdisk 104 /var/lib/vz/template/iso/nocloud-amd64.raw local-lvm
qm set 104 --scsi0 local-lvm:vm-104-disk-0
qm set 104 --boot order=scsi0
qm set 104 --serial0 socket --vga serial0
```

**Note:** The disk size will be automatically set based on the imported image (approximately 1.2GB). Talos will use the entire disk available to it.

---

### Step 3: Start VMs and Get IP Addresses
```bash
# Start all VMs
for i in {100..104}; do qm start $i; done

# Wait about 30 seconds for VMs to boot
sleep 30
```

**Get IP addresses for each VM:**
```bash
# Check console output or use Proxmox UI
qm terminal 100

# Or check DHCP leases on your router
# Look for: talos-cp-01, talos-cp-02, talos-cp-03, talos-worker-01, talos-worker-02
```

**Document temporary DHCP IPs:**
```
talos-cp-01:     10.10.5.X (temporary DHCP)
talos-cp-02:     10.10.5.Y (temporary DHCP)
talos-cp-03:     10.10.5.Z (temporary DHCP)
talos-worker-01: 10.10.5.A (temporary DHCP)
talos-worker-02: 10.10.5.B (temporary DHCP)
```

---

### Step 4: Generate Talos Configuration

On your management machine (laptop/jumpbox):
```bash
# Create a directory for Talos configs
mkdir -p ~/talos-cluster
cd ~/talos-cluster

# Generate configuration files
# Use the FINAL static IP of your FIRST control plane node
talosctl gen config talos-homelab https://10.10.5.200:6443 \
  --output-dir . \
  --with-examples=false \
  --with-docs=false

# This creates:
# - controlplane.yaml (control plane node config)
# - worker.yaml (worker node config)
# - talosconfig (CLI configuration for managing cluster)
```

---

### Step 5: Configure Static IPs for Each Node

Create individual config files with static IP addresses for each node.

**Create controlplane-cp-01.yaml:**
```bash
cat > controlplane-cp-01.yaml << 'EOF'
version: v1alpha1
debug: false
persist: true
machine:
  type: controlplane
  token: <copy from controlplane.yaml>
  ca:
    crt: <copy from controlplane.yaml>
    key: <copy from controlplane.yaml>
  certSANs:
    - 10.10.5.200
  kubelet:
    image: ghcr.io/siderolabs/kubelet:v1.31.0
    defaultRuntimeSeccompProfileEnabled: true
    disableManifestsDirectory: true
  network:
    hostname: talos-cp-01
    interfaces:
      - interface: eth0
        addresses:
          - 10.10.5.200/24
        routes:
          - network: 0.0.0.0/0
            gateway: 10.10.5.1
    nameservers:
      - 10.10.5.2
      - 10.10.5.3
  install:
    disk: /dev/sda
    image: ghcr.io/siderolabs/installer:v1.9.0
    wipe: false
  time:
    disabled: false
    servers:
      - time.cloudflare.com
cluster:
  <copy entire cluster section from controlplane.yaml>
EOF
```

**Easier Method: Use sed to create configs from base template**
```bash
# Copy base files
cp controlplane.yaml controlplane-cp-01.yaml
cp controlplane.yaml controlplane-cp-02.yaml
cp controlplane.yaml controlplane-cp-03.yaml
cp worker.yaml worker-01.yaml
cp worker.yaml worker-02.yaml

# Edit each file to add the network configuration under 'machine:'
# Add this to each file (modify hostname and IP accordingly):
```

**Add to controlplane-cp-01.yaml (after `machine:` section):**
```yaml
  network:
    hostname: talos-cp-01
    interfaces:
      - interface: eth0
        addresses:
          - 10.10.5.200/24
        routes:
          - network: 0.0.0.0/0
            gateway: 10.10.5.1
    nameservers:
      - 10.10.5.2
      - 10.10.5.3
  time:
    disabled: false
    servers:
      - time.cloudflare.com
```

**Add to controlplane-cp-02.yaml:**
```yaml
  network:
    hostname: talos-cp-02
    interfaces:
      - interface: eth0
        addresses:
          - 10.10.5.201/24
        routes:
          - network: 0.0.0.0/0
            gateway: 10.10.5.1
    nameservers:
      - 10.10.5.2
      - 10.10.5.3
  time:
    disabled: false
    servers:
      - time.cloudflare.com
```

**Add to controlplane-cp-03.yaml:**
```yaml
  network:
    hostname: talos-cp-03
    interfaces:
      - interface: eth0
        addresses:
          - 10.10.5.202/24
        routes:
          - network: 0.0.0.0/0
            gateway: 10.10.5.1
    nameservers:
      - 10.10.5.2
      - 10.10.5.3
  time:
    disabled: false
    servers:
      - time.cloudflare.com
```

**Add to worker-01.yaml:**
```yaml
  network:
    hostname: talos-worker-01
    interfaces:
      - interface: eth0
        addresses:
          - 10.10.5.203/24
        routes:
          - network: 0.0.0.0/0
            gateway: 10.10.5.1
    nameservers:
      - 10.10.5.2
      - 10.10.5.3
  time:
    disabled: false
    servers:
      - time.cloudflare.com
```

**Add to worker-02.yaml:**
```yaml
  network:
    hostname: talos-worker-02
    interfaces:
      - interface: eth0
        addresses:
          - 10.10.5.204/24
        routes:
          - network: 0.0.0.0/0
            gateway: 10.10.5.1
    nameservers:
      - 10.10.5.2
      - 10.10.5.3
  time:
    disabled: false
    servers:
      - time.cloudflare.com
```

---

### Step 6: Apply Configuration to Nodes

Apply the configuration to each node using their **temporary DHCP IPs** from Step 3:
```bash
# Apply configs using TEMPORARY IPs
# Replace X, Y, Z, A, B with the actual temporary DHCP IPs from Step 3

# Configure control plane nodes
talosctl apply-config --insecure \
  --nodes 10.10.5.X \
  --file controlplane-cp-01.yaml

talosctl apply-config --insecure \
  --nodes 10.10.5.Y \
  --file controlplane-cp-02.yaml

talosctl apply-config --insecure \
  --nodes 10.10.5.Z \
  --file controlplane-cp-03.yaml

# Configure worker nodes
talosctl apply-config --insecure \
  --nodes 10.10.5.A \
  --file worker-01.yaml

talosctl apply-config --insecure \
  --nodes 10.10.5.B \
  --file worker-02.yaml
```

**Wait for nodes to apply configuration and reboot (2-3 minutes).**

After configuration is applied, nodes will:
1. Install Talos to disk (`/dev/sda`)
2. Configure static networking
3. Reboot
4. Come up with static IPs: 10.10.5.200-204

**Verify nodes are accessible at new static IPs:**
```bash
# Ping each node
ping -c 3 10.10.5.200
ping -c 3 10.10.5.201
ping -c 3 10.10.5.202
ping -c 3 10.10.5.203
ping -c 3 10.10.5.204
```

---

### Step 7: Bootstrap the Cluster

Bootstrap the first control plane node to initialize the Kubernetes cluster:
```bash
# Set talosctl endpoint and nodes (using STATIC IPs now)
export TALOSCONFIG=~/talos-cluster/talosconfig
talosctl config endpoint 10.10.5.200 10.10.5.201 10.10.5.202
talosctl config node 10.10.5.200

# Bootstrap the cluster (only run once on ONE control plane node)
talosctl bootstrap --nodes 10.10.5.200
```

**⚠️ CRITICAL:** Only run `bootstrap` **ONCE** on **ONE** control plane node (talos-cp-01 at 10.10.5.200). Running it multiple times or on multiple nodes will break the cluster.

**Wait for bootstrap to complete (5-10 minutes).**

**Monitor bootstrap progress:**
```bash
# Watch logs
talosctl dmesg --follow --nodes 10.10.5.200

# Check services
talosctl service --nodes 10.10.5.200
```

---

### Step 8: Retrieve kubeconfig

Once the cluster is bootstrapped, get the kubeconfig:
```bash
# Generate kubeconfig
talosctl kubeconfig --nodes 10.10.5.200 \
  --force \
  --merge=false \
  ~/talos-cluster/kubeconfig

# Set KUBECONFIG environment variable
export KUBECONFIG=~/talos-cluster/kubeconfig

# Or merge into default kubeconfig
talosctl kubeconfig --nodes 10.10.5.200 --force
```

---

### Step 9: Verify Cluster
```bash
# Check cluster info
kubectl cluster-info

# Check all nodes are Ready
kubectl get nodes -o wide

# Expected output (3+2 configuration):
# NAME              STATUS   ROLES           AGE   VERSION   INTERNAL-IP
# talos-cp-01       Ready    control-plane   10m   v1.31.0   10.10.5.200
# talos-cp-02       Ready    control-plane   10m   v1.31.0   10.10.5.201
# talos-cp-03       Ready    control-plane   10m   v1.31.0   10.10.5.202
# talos-worker-01   Ready    <none>          10m   v1.31.0   10.10.5.203
# talos-worker-02   Ready    <none>          10m   v1.31.0   10.10.5.204

# Check system pods
kubectl get pods -A

# All pods should be Running
```

**If nodes show "NotReady":**
- Wait a few more minutes for CNI (network plugin) to initialize
- Check logs: `talosctl logs --nodes 10.10.5.200 kubelet`

**Verify etcd cluster health:**
```bash
# Should show 3 members
talosctl etcd members --nodes 10.10.5.200

# Expected output:
# NODE           MEMBER              ID                HOSTNAME        PEER URLS
# 10.10.5.200    talos-cp-01         xxxxxxxxxxxx      talos-cp-01     https://10.10.5.200:2380
# 10.10.5.200    talos-cp-02         xxxxxxxxxxxx      talos-cp-02     https://10.10.5.201:2380
# 10.10.5.200    talos-cp-03         xxxxxxxxxxxx      talos-cp-03     https://10.10.5.202:2380
```

**Check etcd health:**
```bash
talosctl health --nodes 10.10.5.200,10.10.5.201,10.10.5.202
```

---

### Step 10: Verify TrueNAS NFS Connectivity

Before proceeding with application deployments, verify that worker nodes can access TrueNAS NFS shares:
```bash
# Test network connectivity to TrueNAS
kubectl run -it --rm nfs-test --image=busybox --restart=Never -- ping -c 3 10.10.5.40

# Test NFS mount to the main k8s dataset
kubectl run -it --rm nfs-mount-test --image=busybox --restart=Never -- \
  sh -c "mkdir -p /mnt/test && mount -t nfs 10.10.5.40:/mnt/gluttonterra/k8s /mnt/test && ls -la /mnt/test && umount /mnt/test"

# Expected output should show your application subdirectories:
# drwxr-xr-x    2 root     root          4096 Dec 28 12:00 argocd
# drwxr-xr-x    2 root     root          4096 Dec 28 12:00 jellyfin
# drwxr-xr-x    2 root     root          4096 Dec 28 12:00 prowlarr
# drwxr-xr-x    2 root     root          4096 Dec 28 12:00 qbittorrent
# drwxr-xr-x    2 root     root          4096 Dec 28 12:00 radarr
# drwxr-xr-x    2 root     root          4096 Dec 28 12:00 sonarr
```

**If NFS mount fails:**
- Verify NFS service is running on TrueNAS (10.10.5.40)
- Check NFS share is configured for `gluttonterra/k8s`
- Ensure authorized networks include 10.10.5.0/24
- Verify firewall rules allow NFS traffic (ports 111, 2049)
- Check TrueNAS dataset permissions

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
    server: 10.10.5.40
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

---

### Expanding the Cluster (Adding Nodes)

Your cluster is fully operational with 3 control plane + 2 worker nodes. However, you can easily expand it as needed.

#### Adding Another Worker Node

**Step 1: Create VM in Proxmox**
```bash
# SSH to Proxmox host
ssh root@proxmox.local

# Create new worker VM
qm create 105 \
  --name talos-worker-03 \
  --memory 8192 \
  --cores 4 \
  --net0 virtio,bridge=vmbr0 \
  --scsihw virtio-scsi-pci \
  --ostype l26

# Import Talos disk
qm importdisk 105 /var/lib/vz/template/iso/nocloud-amd64.raw local-lvm
qm set 105 --scsi0 local-lvm:vm-105-disk-0
qm set 105 --boot order=scsi0
qm set 105 --serial0 socket --vga serial0

# Start the VM
qm start 105
```

**Step 2: Create config with static IP (10.10.5.205)**
```bash
# On your management machine
cd ~/talos-cluster
cp worker.yaml worker-03.yaml

# Edit worker-03.yaml to add network configuration
```

**Add to worker-03.yaml:**
```yaml
  network:
    hostname: talos-worker-03
    interfaces:
      - interface: eth0
        addresses:
          - 10.10.5.205/24
        routes:
          - network: 0.0.0.0/0
            gateway: 10.10.5.1
    nameservers:
      - 10.10.5.2
      - 10.10.5.3
  time:
    disabled: false
    servers:
      - time.cloudflare.com
```

**Step 3: Apply configuration**
```bash
# Get temporary DHCP IP from Proxmox console
# Apply config
talosctl apply-config --insecure \
  --nodes <temporary-dhcp-ip> \
  --file worker-03.yaml
```

**Step 4: Verify node joined**
```bash
# Wait 2-3 minutes
kubectl get nodes

# Should show new worker at 10.10.5.205
```

---

### Cluster Management Commands

**Common talosctl commands:**
```bash
# Check node health
talosctl health --nodes 10.10.5.200,10.10.5.201,10.10.5.202

# View logs
talosctl logs --nodes 10.10.5.200 --tail

# Check service status
talosctl service --nodes 10.10.5.200

# Reboot a node
talosctl reboot --nodes 10.10.5.203

# Upgrade Talos version
talosctl upgrade --nodes 10.10.5.200 \
  --image ghcr.io/siderolabs/installer:v1.9.0

# Edit machine config
talosctl edit mc --nodes 10.10.5.200

# Get etcd status
talosctl etcd status --nodes 10.10.5.200
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

**Issue: VMs won't boot after disk import**
```bash
# Verify disk was imported correctly
qm config 100

# Should show scsi0 disk
# If not, re-import:
qm importdisk 100 /var/lib/vz/template/iso/nocloud-amd64.raw local-lvm
qm set 100 --scsi0 local-lvm:vm-100-disk-0
```

**Issue: Can't connect to node after config apply**
```bash
# Node may still be on DHCP IP
# Check Proxmox console or router DHCP leases

# Or wait 2-3 minutes for installation to complete
# Then try static IP
talosctl health --nodes 10.10.5.200
```

**Issue: Nodes stuck in "NotReady"**
```bash
# Check CNI pods
kubectl get pods -n kube-system | grep -E 'flannel|calico|cilium'

# Check kubelet logs
talosctl logs --nodes 10.10.5.200 kubelet

# Check for network issues
talosctl logs --nodes 10.10.5.200 -k | grep -i network
```

**Issue: etcd not healthy**
```bash
# Check etcd member list
talosctl etcd members --nodes 10.10.5.200

# Check etcd status on each control plane
talosctl etcd status --nodes 10.10.5.200
talosctl etcd status --nodes 10.10.5.201
talosctl etcd status --nodes 10.10.5.202

# Verify all 3 members are listed and healthy
```

**Issue: Cannot mount TrueNAS NFS shares**
```bash
# Verify network connectivity to TrueNAS
kubectl run -it --rm debug --image=busybox --restart=Never -- ping -c 3 10.10.5.40

# Test NFS mount from a pod
kubectl run -it --rm nfs-test --image=busybox --restart=Never -- \
  sh -c "mount -t nfs 10.10.5.40:/mnt/gluttonterra/k8s /mnt && ls -la /mnt"

# Check TrueNAS configuration
# - Authorized networks: 10.10.5.0/24
# - Maproot user: root
# - Maproot group: wheel
```

**Issue: Disk space full on Talos nodes**
```bash
# Talos disk is sized based on imported image (~1.2GB)
# To increase disk size:

# 1. Resize disk in Proxmox
qm resize 100 scsi0 +30G

# 2. Talos will auto-detect and expand partition on next boot
talosctl reboot --nodes 10.10.5.200
```

---

### Next Steps

Once your cluster is up and running with all nodes showing "Ready":

✅ **Talos Linux Cluster - Complete!**

**Your cluster now has:**
- ✅ 3 control plane nodes (high availability) at 10.10.5.200-202
- ✅ 2 worker nodes (sufficient for homelab) at 10.10.5.203-204
- ✅ etcd quorum established
- ✅ Kubernetes API accessible at 10.10.5.200:6443
- ✅ All system pods running
- ✅ Static IP addresses configured
- ✅ NFS connectivity to TrueNAS (10.10.5.40) verified

**Proceed to:**
2. ⬜ **MetalLB Installation** - Deploy load balancer for bare metal services

**After MetalLB, you'll install:**
3. ⬜ Traefik (ingress controller)
4. ⬜ CoreDNS configuration
5. ⬜ Forgejo (Git server)
6. ⬜ ArgoCD (GitOps)
7. ⬜ Applications with NFS-backed PersistentVolumes

---

### Backup & Disaster Recovery

**Backup Configuration Files:**
```bash
# Always backup these files!
mkdir -p ~/backups/talos-cluster-$(date +%Y%m%d)
cp ~/talos-cluster/*.yaml ~/backups/talos-cluster-$(date +%Y%m%d)/
cp ~/talos-cluster/talosconfig ~/backups/talos-cluster-$(date +%Y%m%d)/

# Store backups in multiple locations
```

**Snapshot VMs in Proxmox:**
```bash
# Take snapshots of all nodes after successful setup
for i in {100..104}; do
  qm snapshot $i initial-setup --description "Initial cluster setup - $(date)"
done
```

**Export etcd Backup:**
```bash
# Take regular etcd backups
talosctl etcd snapshot --nodes 10.10.5.200 ~/backups/etcd-backup-$(date +%Y%m%d).db
```

**TrueNAS Snapshots:**
Configure TrueNAS snapshot tasks for `gluttonterra/k8s` dataset with recursive enabled.

---

### Related Documentation

- **Talos Documentation:** https://www.talos.dev/
- **Talos Proxmox Guide:** https://docs.siderolabs.com/talos/v1.9/platform-specific-installations/virtualized-platforms/proxmox
- **Kubernetes Documentation:** https://kubernetes.io/docs/
- **Proxmox Documentation:** https://pve.proxmox.com/pve-docs/
- **TrueNAS Documentation:** https://www.truenas.com/docs/
- **Next Step:** MetalLB Installation (`kubernetes/apps/metallb/readme.md`)

---

### Quick Reference

**Node Information:**
```
Control Plane Nodes (3):
├── talos-cp-01:     10.10.5.200  (2 vCPU, 4GB RAM, 32GB disk)
├── talos-cp-02:     10.10.5.201  (2 vCPU, 4GB RAM, 32GB disk)
└── talos-cp-03:     10.10.5.202  (2 vCPU, 4GB RAM, 32GB disk)

Worker Nodes (2):
├── talos-worker-01: 10.10.5.203  (4 vCPU, 8GB RAM, 64GB disk)
└── talos-worker-02: 10.10.5.204  (4 vCPU, 8GB RAM, 64GB disk)

External Storage:
└── TrueNAS Server: 10.10.5.40
    └── Dataset: gluttonterra/k8s (6.71 TiB available)

Network:
├── Gateway: 10.10.5.1
├── DNS: 10.10.5.2, 10.10.5.3
└── Kubernetes API: https://10.10.5.200:6443
```

**Essential Commands:**
```bash
# Check cluster health
kubectl get nodes
talosctl health --nodes 10.10.5.200,10.10.5.201,10.10.5.202

# Update kubeconfig
talosctl kubeconfig --nodes 10.10.5.200 --force

# Test NFS connectivity
kubectl run -it --rm nfs-test --image=busybox --restart=Never -- \
  mount -t nfs 10.10.5.40:/mnt/gluttonterra/k8s /mnt
```

**Talos Image Download:**
```bash
# On Proxmox host
cd /var/lib/vz/template/iso
wget https://github.com/siderolabs/talos/releases/download/v1.9.0/nocloud-amd64.raw.xz
xz -d nocloud-amd64.raw.xz
```