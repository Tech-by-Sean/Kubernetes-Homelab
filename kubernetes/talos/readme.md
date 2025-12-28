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
└── Dataset: gluttonterra/k8s (6.71 TiB)
    └── NFS shares for persistent application storage
```

**Resource Requirements (3+2):**
- **Total vCPU:** 14 cores
- **Total RAM:** 28GB
- **Total Storage:** 224GB (local VM disks)
- **External Storage:** TrueNAS NFS shares

**Network Configuration:**
- **Gateway:** 10.10.5.1
- **DNS Servers:** 10.10.5.2, 10.10.5.3
- **Control Plane VIP:** 10.10.5.200 (first control plane node)
- **TrueNAS:** 10.10.5.40

---

### Installation

#### Prerequisites

**Required Tools:**
```bash
# Install talosctl (macOS/Linux)
brew install siderolabs/tap/talosctl

# Or download manually
curl -sL https://talos.dev/install | sh

# Install kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl
sudo mv kubectl /usr/local/bin/

# Verify installations
talosctl version
kubectl version --client
```

**Network Requirements:**
- [ ] Proxmox VE 8.x installed
- [ ] Available IP addresses: 10.10.5.200-204
- [ ] TrueNAS server at 10.10.5.40 with NFS configured
- [ ] Network gateway: 10.10.5.1
- [ ] DNS servers: 10.10.5.2, 10.10.5.3

---

### Step 1: Download Talos ISO Image

Download the Talos metal ISO from the Image Factory:
```bash
# Create output directory
mkdir -p _out/

# Download Talos v1.9.5 metal ISO (amd64)
curl https://factory.talos.dev/image/376567988ad370138ad8b2698212367b8edcb69b5fd68c80be1f2ec7d603b4ba/v1.9.5/metal-amd64.iso -L -o _out/metal-amd64.iso
```

**Optional: QEMU Guest Agent Support**

For VM shutdown integration with Proxmox, use a custom ISO with QEMU guest agent:

1. Navigate to https://factory.talos.dev/
2. Select Talos version: **v1.9.5**
3. Check **siderolabs/qemu-guest-agent** extension
4. Click Submit

**Download the custom ISO:**
```bash
curl https://factory.talos.dev/image/ce4c980550dd2ab1b17bbf2b08801c7eb59418eafe8f279833297925d67c7515/v1.9.5/metal-amd64.iso -L -o _out/metal-amd64-qemu.iso
```

**Note the installer image URL for later:**
```
factory.talos.dev/installer/ce4c980550dd2ab1b17bbf2b08801c7eb59418eafe8f279833297925d67c7515:v1.9.5
```

---

### Step 2: Upload ISO to Proxmox

**Via Proxmox Web UI:**

1. Log into Proxmox web interface
2. Select **local** storage → **Content** section
3. Click **Upload** button
4. Select the downloaded ISO file
5. Wait for upload to complete

**Via Command Line:**
```bash
# SSH to Proxmox host
ssh root@proxmox.local

# Upload from your local machine
scp _out/metal-amd64.iso root@proxmox.local:/var/lib/vz/template/iso/
```

---

### Step 3: Create VMs

Before starting, familiarize yourself with Talos [system requirements](https://www.talos.dev/v1.9/introduction/system-requirements/).

#### Create Control Plane Node 1

**Via Proxmox Web UI:**

1. Click **Create VM** (top right)

2. **General Tab:**
   - VM ID: `100`
   - Name: `talos-cp-01`

3. **OS Tab:**
   - ISO Image: Select `metal-amd64.iso`
   - Guest OS Type: `Linux`
   - Kernel Version: `6.x`

4. **System Tab:**
   - Keep defaults

5. **Disks Tab:**
   - Keep defaults
   - Disk size: `32 GB` (or larger)

6. **CPU Tab:**
   - Cores: `2`
   - Type: `host` (recommended)
   
   > **Important:** As of Talos v1.0, the default `kvm64` CPU type may not work on Proxmox < 8.0.
   > If using Proxmox < 8.0, set CPU type to `host` or add this to `/etc/pve/qemu-server/100.conf`:
   > ```
   > args: -cpu kvm64,+cx16,+lahf_lm,+popcnt,+sse3,+ssse3,+sse4.1,+sse4.2
   > ```

7. **Memory Tab:**
   - Memory: `4096 MB` (4GB)
   - Ballooning: `Disabled`

8. **Network Tab:**
   - Bridge: `vmbr0`
   - Model: `VirtIO (paravirtualized)`

9. **Confirm Tab:**
   - ✅ **Start after created** (uncheck - we'll configure first)
   - Click **Finish**

#### Create Additional Nodes

**Control Plane Nodes:**
- `talos-cp-02` (VM ID: 101) - Same specs as cp-01
- `talos-cp-03` (VM ID: 102) - Same specs as cp-01

**Worker Nodes:**
- `talos-worker-01` (VM ID: 103) - 4 vCPU, 8GB RAM, 64GB disk
- `talos-worker-02` (VM ID: 104) - 4 vCPU, 8GB RAM, 64GB disk

**Quick CLI Creation:**
```bash
# SSH to Proxmox
ssh root@proxmox.local

# Create control plane VMs
for i in {1..3}; do
  qm create $((99 + i)) \
    --name "talos-cp-0${i}" \
    --memory 4096 \
    --cores 2 \
    --cpu host \
    --net0 virtio,bridge=vmbr0 \
    --scsihw virtio-scsi-pci \
    --scsi0 local-lvm:32 \
    --ide2 local:iso/metal-amd64.iso,media=cdrom \
    --boot order=scsi0 \
    --ostype l26
done

# Create worker VMs
for i in {1..2}; do
  qm create $((102 + i)) \
    --name "talos-worker-0${i}" \
    --memory 8192 \
    --cores 4 \
    --cpu host \
    --net0 virtio,bridge=vmbr0 \
    --scsihw virtio-scsi-pci \
    --scsi0 local-lvm:64 \
    --ide2 local:iso/metal-amd64.iso,media=cdrom \
    --boot order=scsi0 \
    --ostype l26
done
```

> **Note:** Talos doesn't support memory hot plugging. Do not enable memory hotplug on Talos VMs.

---

### Step 4: Start Control Plane Node

Start the first control plane VM. It will boot into **maintenance mode**.
```bash
# Via Proxmox CLI
qm start 100

# Or via Web UI: Select VM → Start
```

#### Get IP Address

**With DHCP:**

Once in maintenance mode, the console will display the IP address:
```
[talos] task starting {"component":"controller-runtime","task":"network-setup"}
[talos] network link up {"component":"controller-runtime","link":"eth0"}
[talos] acquired IP address {"component":"controller-runtime","address":"10.10.5.X/24"}
```

Note this IP as `$CONTROL_PLANE_IP` (temporary DHCP IP).

**Without DHCP:**

Press `e` at the GRUB menu and add IP configuration to the kernel line:
```bash
linux /boot/vmlinuz ... talos.platform=metal ip=10.10.5.200::10.10.5.1:255.255.255.0::eth0:off
```

Format: `ip=<client-ip>::<gateway>:<netmask>::<device>:off`

Press `Ctrl-x` or `F10` to boot.

---

### Step 5: Generate Machine Configurations

From your management machine:
```bash
# Set the control plane IP (use the desired static IP or VIP)
export CONTROL_PLANE_IP=10.10.5.200

# Generate configurations
talosctl gen config talos-homelab https://$CONTROL_PLANE_IP:6443 --output-dir _out
```

This creates:
- `_out/controlplane.yaml` - **Single** control plane configuration (used for ALL 3 control plane nodes)
- `_out/worker.yaml` - **Single** worker configuration (used for ALL 2 worker nodes)
- `_out/talosconfig` - Talosctl client configuration

**Optional: Custom Installer with QEMU Guest Agent**

If using the custom ISO with QEMU guest agent:
```bash
talosctl gen config talos-homelab https://$CONTROL_PLANE_IP:6443 \
  --output-dir _out \
  --install-image factory.talos.dev/installer/ce4c980550dd2ab1b17bbf2b08801c7eb59418eafe8f279833297925d67c7515:v1.9.5
```

Then in Proxmox UI:
- Select each VM → **Options**
- Enable **QEMU Guest Agent**

#### Verify Disk Configuration (Important!)

By default, Talos will install to `/dev/sda`. Check if your disk is named differently:
```bash
# Check available disks (use the temp DHCP IP from Step 4)
talosctl get disks --insecure --nodes <temp-dhcp-ip>

# If disk is /dev/vda instead of /dev/sda, edit the config files:
```

**Edit `_out/controlplane.yaml` and `_out/worker.yaml`** if needed:
```yaml
machine:
  install:
    disk: /dev/vda  # Change from /dev/sda if needed
    image: ghcr.io/siderolabs/installer:v1.9.5
    wipe: false
```

#### Configure Network Settings (Optional)

Add DNS and time servers to your configs. Edit both `_out/controlplane.yaml` and `_out/worker.yaml`:
```yaml
machine:
  network:
    nameservers:
      - 10.10.5.2
      - 10.10.5.3
  time:
    disabled: false
    servers:
      - time.cloudflare.com
```

**For Static IPs (Optional):**

If you want static IPs instead of DHCP, you have two options:

**Option A: DHCP with Reservations (Recommended for Homelab)**
- Don't modify the network config
- Reserve MAC addresses in your router/DHCP server:
  - talos-cp-01 → 10.10.5.200
  - talos-cp-02 → 10.10.5.201
  - talos-cp-03 → 10.10.5.202
  - talos-worker-01 → 10.10.5.203
  - talos-worker-02 → 10.10.5.204

**Option B: Config Patches (Advanced)**

Create patch files for each node with static IPs:
```bash
# Example patch for cp-01
cat > _out/cp-01-patch.yaml <<EOF
machine:
  network:
    hostname: talos-cp-01
    interfaces:
      - interface: eth0
        dhcp: false
        addresses:
          - 10.10.5.200/24
        routes:
          - network: 0.0.0.0/0
            gateway: 10.10.5.1
EOF
```

Then apply with patch:
```bash
talosctl apply-config --insecure \
  --nodes <temp-dhcp-ip> \
  --file _out/controlplane.yaml \
  --config-patch @_out/cp-01-patch.yaml
```

**This guide will use Option A (DHCP with reservations) for simplicity.**

---

### Step 6: Apply Configuration to Control Plane Node 1

Apply the `controlplane.yaml` to the first control plane node using its **temporary DHCP IP** from Step 4:
```bash
# Example: temp DHCP IP is 10.10.5.150
talosctl apply-config --insecure \
  --nodes 10.10.5.150 \
  --file _out/controlplane.yaml
```

**What happens:**
1. Talos installs to disk (`/dev/sda` or `/dev/vda`)
2. VM reboots
3. VM gets new IP from DHCP (or static IP if configured)
4. Kubernetes control plane begins initializing

**Reserve this node's IP as 10.10.5.200 in your router/DHCP server.**

> **Note:** VM will show as "Booting" in Proxmox until bootstrap is completed later.

---

### Step 7: Apply Configuration to Control Plane Nodes 2 & 3

**Start the remaining control plane VMs:**
```bash
# Via Proxmox CLI
qm start 101  # talos-cp-02
qm start 102  # talos-cp-03

# Or via Web UI: Select each VM → Start
```

**Wait for each to boot into maintenance mode and note their temporary IPs.**

**Apply the SAME `controlplane.yaml` to each:**
```bash
# Example temp IPs: cp-02 = 10.10.5.151, cp-03 = 10.10.5.152

# Apply to cp-02
talosctl apply-config --insecure \
  --nodes 10.10.5.151 \
  --file _out/controlplane.yaml

# Apply to cp-03
talosctl apply-config --insecure \
  --nodes 10.10.5.152 \
  --file _out/controlplane.yaml
```

**Reserve their IPs in your router/DHCP server:**
- talos-cp-02 → 10.10.5.201
- talos-cp-03 → 10.10.5.202

> **Note:** Using the same `controlplane.yaml` for all control plane nodes is correct. Each node gets a unique identity automatically.

---

### Step 8: Apply Configuration to Worker Nodes

**Start the worker VMs:**
```bash
# Via Proxmox CLI
qm start 103  # talos-worker-01
qm start 104  # talos-worker-02

# Or via Web UI: Select each VM → Start
```

**Wait for each to boot into maintenance mode and note their temporary IPs.**

**Apply the SAME `worker.yaml` to each:**
```bash
# Example temp IPs: worker-01 = 10.10.5.153, worker-02 = 10.10.5.154

# Apply to worker-01
talosctl apply-config --insecure \
  --nodes 10.10.5.153 \
  --file _out/worker.yaml

# Apply to worker-02
talosctl apply-config --insecure \
  --nodes 10.10.5.154 \
  --file _out/worker.yaml
```

**Reserve their IPs in your router/DHCP server:**
- talos-worker-01 → 10.10.5.203
- talos-worker-02 → 10.10.5.204

> **Note:** Additional workers can be added by repeating this process with the same `worker.yaml`.

---

### Step 9: Configure Talosctl

Configure talosctl to communicate with your cluster (use the **final static IPs** after DHCP reservation):
```bash
# Export talosconfig
export TALOSCONFIG="_out/talosconfig"

# Set endpoints (all control plane nodes with their final IPs)
talosctl config endpoint 10.10.5.200 10.10.5.201 10.10.5.202

# Set default node (first control plane)
talosctl config node 10.10.5.200
```

**Verify connectivity:**
```bash
# Should show services running
talosctl services

# Should show node info
talosctl version
```

---

### Step 10: Bootstrap Etcd

Bootstrap the Kubernetes cluster on the first control plane node:
```bash
talosctl bootstrap
```

**What happens:**
- etcd cluster initializes across all 3 control plane nodes
- Kubernetes control plane components start
- API server becomes available

**This command should only be run ONCE on ONE control plane node.**

**Monitor bootstrap progress:**
```bash
# Watch logs
talosctl dmesg --follow

# Check services
talosctl services

# Check etcd members (should show all 3 control planes)
talosctl etcd members
```

**Wait 5-10 minutes for bootstrap to complete.**

---

### Step 11: Retrieve Kubeconfig

Once bootstrap completes, retrieve the admin kubeconfig:
```bash
# Generate kubeconfig in current directory
talosctl kubeconfig .

# This creates ./kubeconfig file
export KUBECONFIG=$(pwd)/kubeconfig

# Or merge into default kubeconfig
talosctl kubeconfig ~/.kube/config

# Verify cluster access
kubectl get nodes
```

**Expected output:**
```
NAME              STATUS   ROLES           AGE   VERSION
talos-cp-01       Ready    control-plane   5m    v1.31.0
talos-cp-02       Ready    control-plane   5m    v1.31.0
talos-cp-03       Ready    control-plane   5m    v1.31.0
talos-worker-01   Ready    <none>          5m    v1.31.0
talos-worker-02   Ready    <none>          5m    v1.31.0
```

**If nodes show "NotReady", wait a few more minutes for the CNI to initialize.**

---

### Step 12: Verify Cluster Health
```bash
# Check all nodes
kubectl get nodes -o wide

# Check all pods
kubectl get pods -A

# Check etcd health
talosctl etcd members

# Expected output (3 control plane members):
# NODE           MEMBER         ID              HOSTNAME        PEER URLS
# 10.10.5.200    talos-cp-01    123456789...    talos-cp-01     https://10.10.5.200:2380
# 10.10.5.200    talos-cp-02    234567890...    talos-cp-02     https://10.10.5.201:2380
# 10.10.5.200    talos-cp-03    345678901...    talos-cp-03     https://10.10.5.202:2380

# Check cluster health
talosctl health --nodes 10.10.5.200,10.10.5.201,10.10.5.202
```

---

### Step 13: Verify TrueNAS NFS Connectivity

Verify worker nodes can access TrueNAS NFS shares:
```bash
# Test connectivity to TrueNAS
kubectl run -it --rm nfs-test --image=busybox --restart=Never -- ping -c 3 10.10.5.40

# Test NFS mount
kubectl run -it --rm nfs-mount-test --image=busybox --restart=Never -- \
  sh -c "mkdir -p /mnt/test && mount -t nfs 10.10.5.40:/mnt/gluttonterra/k8s /mnt/test && ls -la /mnt/test && umount /mnt/test"
```

**Expected output:** List of application datasets (argocd, jellyfin, prowlarr, qbittorrent, radarr, sonarr)

**If mount fails:**
- Verify NFS service is running on TrueNAS
- Check NFS share permissions allow 10.10.5.0/24 subnet
- Ensure firewall allows NFS traffic (ports 111, 2049)

---

### Using the Cluster

#### Talosctl Commands
```bash
# View containers (system namespace)
talosctl containers

# View containers (k8s namespace)
talosctl containers -k

# View logs
talosctl logs kubelet

# Check etcd members
talosctl etcd members

# Health check
talosctl health

# Reboot a node
talosctl reboot --nodes 10.10.5.203

# Upgrade Talos
talosctl upgrade --nodes 10.10.5.200 \
  --image ghcr.io/siderolabs/installer:v1.9.5
```

#### Kubectl Commands
```bash
# View all pods
kubectl get pods -A

# View nodes
kubectl get nodes -o wide

# Cluster info
kubectl cluster-info

# Describe a node
kubectl describe node talos-cp-01

# Check events
kubectl get events -A --sort-by='.lastTimestamp'
```

---

### Adding Additional Nodes

#### Add Another Worker Node
```bash
# Create VM in Proxmox (VM ID 105)
qm create 105 \
  --name "talos-worker-03" \
  --memory 8192 \
  --cores 4 \
  --cpu host \
  --net0 virtio,bridge=vmbr0 \
  --scsihw virtio-scsi-pci \
  --scsi0 local-lvm:64 \
  --ide2 local:iso/metal-amd64.iso,media=cdrom \
  --boot order=scsi0 \
  --ostype l26

# Start the VM
qm start 105

# Wait for maintenance mode, get temp IP (example: 10.10.5.155)

# Apply the SAME worker.yaml
talosctl apply-config --insecure \
  --nodes 10.10.5.155 \
  --file _out/worker.yaml

# Reserve IP as 10.10.5.205 in router

# Verify node joined
kubectl get nodes
```

#### Add Another Control Plane Node
```bash
# Create VM in Proxmox (VM ID 106)
qm create 106 \
  --name "talos-cp-04" \
  --memory 4096 \
  --cores 2 \
  --cpu host \
  --net0 virtio,bridge=vmbr0 \
  --scsihw virtio-scsi-pci \
  --scsi0 local-lvm:32 \
  --ide2 local:iso/metal-amd64.iso,media=cdrom \
  --boot order=scsi0 \
  --ostype l26

# Start and apply config (same as worker process)
qm start 106

# Apply the SAME controlplane.yaml
talosctl apply-config --insecure \
  --nodes <temp-ip> \
  --file _out/controlplane.yaml

# Update talosctl endpoints
talosctl config endpoint 10.10.5.200 10.10.5.201 10.10.5.202 10.10.5.206
```

---

### Cleanup

To remove the cluster:

**Via Proxmox Web UI:**
1. Stop all VMs
2. Right-click each VM → **Remove**
3. Confirm deletion

**Via CLI:**
```bash
# Stop all VMs
for i in {100..104}; do qm stop $i; done

# Delete all VMs
for i in {100..104}; do qm destroy $i; done

# Remove ISO if no longer needed
rm /var/lib/vz/template/iso/metal-amd64.iso
```

---

### Troubleshooting

**VM won't boot after config apply:**
```bash
# Check if VM is actually running
qm status 100

# View console
qm terminal 100

# Check boot order
qm config 100 | grep boot
```

**Can't connect to node after applying config:**
```bash
# Node may still be installing to disk - wait 2-3 minutes
# Check DHCP leases on router for new IP
# Try pinging the expected static IP
ping 10.10.5.200
```

**Node stuck "NotReady":**
```bash
# Check kubelet logs
talosctl logs kubelet --nodes 10.10.5.200

# Check CNI pods
kubectl get pods -n kube-system | grep -E 'flannel|calico|cilium'

# Wait a few more minutes - CNI takes time to initialize
```

**etcd unhealthy:**
```bash
# Check etcd status on each control plane
talosctl etcd status --nodes 10.10.5.200
talosctl etcd status --nodes 10.10.5.201
talosctl etcd status --nodes 10.10.5.202

# Check etcd members
talosctl etcd members --nodes 10.10.5.200

# Verify all 3 members are listed
```

**Bootstrap fails:**
```bash
# Check if already bootstrapped
talosctl etcd members --nodes 10.10.5.200

# If showing members, cluster is already bootstrapped
# If empty, try bootstrap again
talosctl bootstrap
```

**Wrong disk detected:**
```bash
# Check available disks
talosctl get disks --insecure --nodes <node-ip>

# Update controlplane.yaml and worker.yaml:
# Change machine.install.disk from /dev/sda to /dev/vda (or correct disk)
# Re-apply configs
```

**NFS mount fails:**
```bash
# Test from cluster
kubectl run -it --rm debug --image=busybox --restart=Never -- ping 10.10.5.40

# Check TrueNAS NFS service
# Verify authorized networks: 10.10.5.0/24
# Check firewall allows NFS (ports 111, 2049)
```

**QEMU Guest Agent not working:**
```bash
# Verify QEMU agent is enabled in Proxmox
qm config 100 | grep agent

# Should show: agent: 1

# If not, enable it
qm set 100 --agent 1

# Verify custom installer image was used in config
grep "install:" _out/controlplane.yaml
# Should show: factory.talos.dev/installer/ce4c980...
```

---

### Next Steps

✅ **Talos Linux Cluster - Complete!**

**Your cluster now has:**
- ✅ 3 control plane nodes at 10.10.5.200-202 (HA with etcd quorum)
- ✅ 2 worker nodes at 10.10.5.203-204
- ✅ etcd cluster established across control planes
- ✅ Kubernetes API accessible at https://10.10.5.200:6443
- ✅ Static IP addressing via DHCP reservations
- ✅ NFS connectivity to TrueNAS verified

**Proceed to:**
2. ⬜ **MetalLB Installation** - Deploy load balancer for bare metal services
   - Required for exposing services outside the cluster
   - Provides LoadBalancer IP addresses for Traefik and applications

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
# Backup all generated configs
mkdir -p ~/backups/talos-cluster-$(date +%Y%m%d)
cp _out/* ~/backups/talos-cluster-$(date +%Y%m%d)/

# Store in multiple locations (external drive, cloud, etc.)
```

**Snapshot VMs in Proxmox:**
```bash
# Take snapshots after successful setup
for i in {100..104}; do
  qm snapshot $i initial-setup --description "Initial cluster setup - $(date)"
done
```

**Backup etcd:**
```bash
# Take regular etcd backups
talosctl etcd snapshot --nodes 10.10.5.200 ~/backups/etcd-backup-$(date +%Y%m%d).db

# Automate with cron
echo "0 2 * * * talosctl etcd snapshot --nodes 10.10.5.200 ~/backups/etcd-backup-\$(date +\%Y\%m\%d).db" | crontab -
```

**Backup TrueNAS Datasets:**

Configure TrueNAS snapshot tasks for `gluttonterra/k8s`:
1. Storage → Snapshots → Add Periodic Snapshot Task
2. Dataset: `gluttonterra/k8s`
3. Recursive: ✅ Enabled
4. Configure retention (hourly: 24, daily: 7, weekly: 4, monthly: 12)

---

### Related Documentation

- **Talos Proxmox Guide:** https://docs.siderolabs.com/talos/v1.9/platform-specific-installations/virtualized-platforms/proxmox
- **Talos Documentation:** https://www.talos.dev/
- **Kubernetes Documentation:** https://kubernetes.io/docs/
- **TrueNAS Documentation:** https://www.truenas.com/docs/
- **Next Step:** MetalLB Installation (`kubernetes/apps/metallb/readme.md`)

---

### Quick Reference

**Cluster Configuration:**
```
Control Plane: 10.10.5.200-202 (3 nodes, 2 vCPU, 4GB RAM each)
Workers:       10.10.5.203-204 (2 nodes, 4 vCPU, 8GB RAM each)
TrueNAS:       10.10.5.40
Gateway:       10.10.5.1
DNS:           10.10.5.2, 10.10.5.3
API Server:    https://10.10.5.200:6443
```

**Configuration Files:**
```
_out/controlplane.yaml  - Single file for ALL 3 control plane nodes
_out/worker.yaml        - Single file for ALL 2 worker nodes
_out/talosconfig        - Talosctl client configuration
```

**Essential Commands:**
```bash
# Check cluster health
kubectl get nodes
talosctl health

# Get kubeconfig
talosctl kubeconfig .

# Bootstrap (one time only, on first control plane)
talosctl bootstrap

# View logs
talosctl logs kubelet

# Check etcd
talosctl etcd members

# Apply same config to new node
talosctl apply-config --insecure --nodes <ip> --file _out/worker.yaml
```

**TrueNAS NFS Paths:**
```
Server: 10.10.5.40
Base:   /mnt/gluttonterra/k8s
Apps:   /mnt/gluttonterra/k8s/{argocd,jellyfin,prowlarr,qbittorrent,radarr,sonarr}
```