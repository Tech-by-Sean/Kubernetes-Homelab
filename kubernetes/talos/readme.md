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
# Set the control plane IP (temporary or desired static IP)
export CONTROL_PLANE_IP=10.10.5.200

# Generate configurations
talosctl gen config talos-homelab https://$CONTROL_PLANE_IP:6443 --output-dir _out
```

This creates:
- `_out/controlplane.yaml` - Control plane configuration
- `_out/worker.yaml` - Worker configuration
- `_out/talosconfig` - Talosctl client configuration

**Optional: Custom Installer with QEMU Guest Agent**

If using the custom ISO with QEMU guest agent:
```bash
talosctl gen config talos-homelab https://$CONTROL_PLANE_IP:6443 \
  --output-dir _out \
  --install-image factory.talos.dev/installer/ce4c980550dd2ab1b17bbf2b08801c7eb59418eafe8f279833297925d67c7515:v1.9.5
```

Then in Proxmox UI:
- Select VM → **Options**
- Enable **QEMU Guest Agent**

#### Configure Static IPs

Edit each configuration file to add static networking.

**Edit `_out/controlplane.yaml`** (for talos-cp-01):
```yaml
machine:
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

**Create separate configs for each node:**
```bash
cd _out

# Copy base configs
cp controlplane.yaml controlplane-cp-01.yaml
cp controlplane.yaml controlplane-cp-02.yaml
cp controlplane.yaml controlplane-cp-03.yaml
cp worker.yaml worker-01.yaml
cp worker.yaml worker-02.yaml

# Edit each file with appropriate hostname and IP:
# - controlplane-cp-01.yaml: hostname=talos-cp-01, IP=10.10.5.200
# - controlplane-cp-02.yaml: hostname=talos-cp-02, IP=10.10.5.201
# - controlplane-cp-03.yaml: hostname=talos-cp-03, IP=10.10.5.202
# - worker-01.yaml: hostname=talos-worker-01, IP=10.10.5.203
# - worker-02.yaml: hostname=talos-worker-02, IP=10.10.5.204
```

---

### Step 6: Apply Configuration to Control Plane

Apply the configuration using the **temporary DHCP IP**:
```bash
# Apply config to first control plane node
talosctl apply-config --insecure \
  --nodes $CONTROL_PLANE_IP \
  --file _out/controlplane-cp-01.yaml
```

**What happens:**
1. Talos installs to disk (`/dev/sda`)
2. VM reboots
3. VM comes up with static IP (10.10.5.200)
4. Kubernetes control plane initializes

> **Note:** VM will show as "Booting" until bootstrap is completed in a later step.

**Verify disk location:**
```bash
# Check available disks
talosctl get disks --insecure --nodes $CONTROL_PLANE_IP

# If disk is /dev/vda instead of /dev/sda, update the config files:
# Edit machine.install.disk in controlplane.yaml to: /dev/vda
```

---

### Step 7: Create Additional Control Plane Nodes

Repeat the process for control plane nodes 2 and 3:
```bash
# Start VMs
qm start 101
qm start 102

# Wait for maintenance mode, get IPs
# Let's say: CP-02 = 10.10.5.X, CP-03 = 10.10.5.Y

# Apply configs
talosctl apply-config --insecure \
  --nodes 10.10.5.X \
  --file _out/controlplane-cp-02.yaml

talosctl apply-config --insecure \
  --nodes 10.10.5.Y \
  --file _out/controlplane-cp-03.yaml
```

> **Note:** This process creates an HA control plane for fault tolerance.

---

### Step 8: Create Worker Nodes

Start worker VMs and apply configurations:
```bash
# Start worker VMs
qm start 103
qm start 104

# Wait for maintenance mode, get IPs
# Let's say: Worker-01 = 10.10.5.A, Worker-02 = 10.10.5.B

# Apply configs
talosctl apply-config --insecure \
  --nodes 10.10.5.A \
  --file _out/worker-01.yaml

talosctl apply-config --insecure \
  --nodes 10.10.5.B \
  --file _out/worker-02.yaml
```

> **Note:** Additional workers can be added by repeating this process.

---

### Step 9: Configure Talosctl

Configure talosctl to communicate with your cluster:
```bash
# Export talosconfig
export TALOSCONFIG="_out/talosconfig"

# Set endpoints (all control plane nodes)
talosctl config endpoint 10.10.5.200 10.10.5.201 10.10.5.202

# Set default node (first control plane)
talosctl config node 10.10.5.200
```

---

### Step 10: Bootstrap Etcd

Bootstrap the Kubernetes cluster:
```bash
talosctl bootstrap
```

**What happens:**
- etcd cluster initializes on control plane nodes
- Kubernetes control plane starts
- API server becomes available

**Monitor bootstrap:**
```bash
# Watch logs
talosctl dmesg --follow

# Check services
talosctl services
```

---

### Step 11: Retrieve Kubeconfig

Once bootstrap completes, retrieve the admin kubeconfig:
```bash
# Generate kubeconfig
talosctl kubeconfig .

# This creates ./kubeconfig file
export KUBECONFIG=$(pwd)/kubeconfig

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
```

#### Kubectl Commands
```bash
# View all pods
kubectl get pods -A

# View nodes
kubectl get nodes -o wide

# Cluster info
kubectl cluster-info
```

---

### TrueNAS NFS Storage Verification

Verify worker nodes can access TrueNAS NFS shares:
```bash
# Test connectivity
kubectl run -it --rm nfs-test --image=busybox --restart=Never -- ping -c 3 10.10.5.40

# Test NFS mount
kubectl run -it --rm nfs-mount-test --image=busybox --restart=Never -- \
  sh -c "mount -t nfs 10.10.5.40:/mnt/gluttonterra/k8s /mnt && ls -la /mnt"
```

**Expected output:** List of application datasets (argocd, jellyfin, sonarr, etc.)

---

### Cleanup

To remove the cluster:

1. **Stop VMs** in Proxmox UI
2. **Delete VMs** (right-click → Remove)
3. **Remove ISO** from local storage if no longer needed

---

### Troubleshooting

**VM won't boot:**
- Check CPU type is set to `host` or has required CPU flags
- Verify ISO is correctly attached

**Can't apply config:**
- Verify VM has network connectivity
- Check firewall rules allow traffic to port 50000
- Ensure using `--insecure` flag during initial config

**Node stuck "NotReady":**
```bash
# Check kubelet logs
talosctl logs kubelet

# Check CNI pods
kubectl get pods -n kube-system
```

**etcd unhealthy:**
```bash
# Check etcd status
talosctl etcd status

# Check etcd members
talosctl etcd members
```

---

### Next Steps

✅ **Talos Linux Cluster - Complete!**

**Your cluster now has:**
- ✅ 3 control plane nodes (HA)
- ✅ 2 worker nodes
- ✅ etcd quorum established
- ✅ Kubernetes API accessible
- ✅ Static IP configuration

**Proceed to:**
2. ⬜ **MetalLB Installation** - Load balancer for bare metal services

---

### Related Documentation

- **Talos Proxmox Guide:** https://docs.siderolabs.com/talos/v1.9/platform-specific-installations/virtualized-platforms/proxmox
- **Talos Documentation:** https://www.talos.dev/
- **Kubernetes Documentation:** https://kubernetes.io/docs/
- **TrueNAS Documentation:** https://www.truenas.com/docs/

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

**Essential Commands:**
```bash
# Check cluster health
kubectl get nodes
talosctl health

# Get kubeconfig
talosctl kubeconfig .

# Bootstrap (one time only)
talosctl bootstrap

# View logs
talosctl logs kubelet
```