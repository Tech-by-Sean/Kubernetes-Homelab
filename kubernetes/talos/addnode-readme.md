---

### Adding Nodes to an Existing Cluster

Once your cluster is running, you can easily add more control plane or worker nodes. The process is straightforward because you use the **same configuration files** that you used during initial setup.

---

#### Adding a Control Plane Node

**When to add:**
- Want higher availability (5 control planes can tolerate 2 failures)
- Need more control plane capacity
- Replacing a failed control plane node

**Step-by-Step Process:**

**1. Create the VM in Proxmox**

Via Web UI:
- Click **Create VM**
- VM ID: `106` (next available)
- Name: `talos-cp-04`
- OS: Select `metal-amd64.iso`
- CPU: 2 cores, type `host`
- Memory: 4096 MB
- Disk: 32 GB
- Network: Bridge `vmbr0`, Model `VirtIO`
- Finish (don't start yet)

Via CLI:
```bash
# SSH to Proxmox
ssh root@proxmox.local

# Create the VM
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
```

**2. Start the VM**
```bash
# Via CLI
qm start 106

# Or via Web UI: Select VM → Start
```

**3. Wait for Maintenance Mode**

Watch the console until you see:
```
[talos] task starting {"component":"controller-runtime","task":"network-setup"}
[talos] acquired IP address {"component":"controller-runtime","address":"10.10.5.156/24"}
```

Note the temporary DHCP IP (example: `10.10.5.156`)

**4. Apply the SAME controlplane.yaml**
```bash
# Use the ORIGINAL controlplane.yaml from your _out directory
cd ~/talos-cluster  # Or wherever you stored your configs

# Apply config using temporary DHCP IP
talosctl apply-config --insecure \
  --nodes 10.10.5.156 \
  --file _out/controlplane.yaml
```

**What happens:**
- Talos installs to disk
- VM reboots
- VM requests new DHCP IP

**5. Reserve Static IP in Router**

In your router/DHCP server, reserve the MAC address to IP:
- MAC: (get from Proxmox VM → Hardware → Network Device)
- IP: `10.10.5.206`

Or wait for DHCP to assign an IP and then reserve it.

**6. Update Talosctl Endpoints**
```bash
# Add the new control plane to endpoints
talosctl config endpoint 10.10.5.200 10.10.5.201 10.10.5.202 10.10.5.206
```

**7. Verify Node Joined**
```bash
# Check nodes (wait 2-3 minutes)
kubectl get nodes

# Should show:
# NAME              STATUS   ROLES           AGE
# talos-cp-01       Ready    control-plane   2d
# talos-cp-02       Ready    control-plane   2d
# talos-cp-03       Ready    control-plane   2d
# talos-cp-04       Ready    control-plane   1m    ← New node!

# Check etcd members (should show 4)
talosctl etcd members --nodes 10.10.5.200

# Expected output:
# NODE           MEMBER         HOSTNAME        PEER URLS
# 10.10.5.200    talos-cp-01    talos-cp-01     https://10.10.5.200:2380
# 10.10.5.200    talos-cp-02    talos-cp-02     https://10.10.5.201:2380
# 10.10.5.200    talos-cp-03    talos-cp-03     https://10.10.5.202:2380
# 10.10.5.200    talos-cp-04    talos-cp-04     https://10.10.5.206:2380  ← New!
```

**8. Verify etcd Health**
```bash
talosctl health --nodes 10.10.5.200,10.10.5.201,10.10.5.202,10.10.5.206

# All checks should pass
```

**That's it! Your 4th control plane node is now part of the cluster.**

---

#### Adding a Worker Node

**When to add:**
- Need more capacity for workloads
- Experiencing resource constraints
- Want better workload distribution

**Step-by-Step Process:**

**1. Create the VM in Proxmox**

Via Web UI:
- Click **Create VM**
- VM ID: `105` (next available)
- Name: `talos-worker-03`
- OS: Select `metal-amd64.iso`
- CPU: 4 cores, type `host`
- Memory: 8192 MB (8GB)
- Disk: 64 GB
- Network: Bridge `vmbr0`, Model `VirtIO`
- Finish (don't start yet)

Via CLI:
```bash
# SSH to Proxmox
ssh root@proxmox.local

# Create the VM
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
```

**2. Start the VM**
```bash
# Via CLI
qm start 105

# Or via Web UI: Select VM → Start
```

**3. Wait for Maintenance Mode**

Watch the console until you see:
```
[talos] task starting {"component":"controller-runtime","task":"network-setup"}
[talos] acquired IP address {"component":"controller-runtime","address":"10.10.5.157/24"}
```

Note the temporary DHCP IP (example: `10.10.5.157`)

**4. Apply the SAME worker.yaml**
```bash
# Use the ORIGINAL worker.yaml from your _out directory
cd ~/talos-cluster  # Or wherever you stored your configs

# Apply config using temporary DHCP IP
talosctl apply-config --insecure \
  --nodes 10.10.5.157 \
  --file _out/worker.yaml
```

**What happens:**
- Talos installs to disk
- VM reboots
- VM requests new DHCP IP
- Node joins the cluster automatically

**5. Reserve Static IP in Router**

In your router/DHCP server, reserve the MAC address to IP:
- MAC: (get from Proxmox VM → Hardware → Network Device)
- IP: `10.10.5.205`

Or wait for DHCP to assign an IP and then reserve it.

**6. Verify Node Joined**
```bash
# Check nodes (wait 2-3 minutes)
kubectl get nodes

# Should show:
# NAME              STATUS   ROLES           AGE
# talos-cp-01       Ready    control-plane   2d
# talos-cp-02       Ready    control-plane   2d
# talos-cp-03       Ready    control-plane   2d
# talos-worker-01   Ready    <none>          2d
# talos-worker-02   Ready    <none>          2d
# talos-worker-03   Ready    <none>          1m    ← New node!

# Check node details
kubectl describe node talos-worker-03

# Verify it can schedule pods
kubectl get nodes -o wide
```

**7. Test Workload Scheduling**
```bash
# Run a test pod
kubectl run test-nginx --image=nginx --replicas=1

# Check where it scheduled
kubectl get pods -o wide

# Should show running on one of the worker nodes

# Clean up
kubectl delete pod test-nginx
```

**That's it! Your 3rd worker node is now part of the cluster and ready to accept workloads.**

---

#### Adding Multiple Nodes at Once

You can add multiple nodes simultaneously:

**Example: Adding 2 workers and 1 control plane**
```bash
# Create all VMs first
qm create 105 --name "talos-worker-03" --memory 8192 --cores 4 --cpu host \
  --net0 virtio,bridge=vmbr0 --scsihw virtio-scsi-pci --scsi0 local-lvm:64 \
  --ide2 local:iso/metal-amd64.iso,media=cdrom --boot order=scsi0 --ostype l26

qm create 106 --name "talos-worker-04" --memory 8192 --cores 4 --cpu host \
  --net0 virtio,bridge=vmbr0 --scsihw virtio-scsi-pci --scsi0 local-lvm:64 \
  --ide2 local:iso/metal-amd64.iso,media=cdrom --boot order=scsi0 --ostype l26

qm create 107 --name "talos-cp-04" --memory 4096 --cores 2 --cpu host \
  --net0 virtio,bridge=vmbr0 --scsihw virtio-scsi-pci --scsi0 local-lvm:32 \
  --ide2 local:iso/metal-amd64.iso,media=cdrom --boot order=scsi0 --ostype l26

# Start all at once
for i in {105..107}; do qm start $i; done

# Wait for all to reach maintenance mode
# Get their temp IPs from consoles

# Apply configs (use appropriate temp IPs)
talosctl apply-config --insecure --nodes 10.10.5.157 --file _out/worker.yaml
talosctl apply-config --insecure --nodes 10.10.5.158 --file _out/worker.yaml
talosctl apply-config --insecure --nodes 10.10.5.159 --file _out/controlplane.yaml

# Reserve IPs in router
# Update talosctl endpoints if added control plane
# Verify all joined
kubectl get nodes
```

---

#### Replacing a Failed Node

**If a control plane or worker node fails permanently:**

**1. Remove the old node from the cluster**
```bash
# Drain the node (if it's still responding)
kubectl drain talos-worker-02 --ignore-daemonsets --delete-emptydir-data

# Delete from Kubernetes
kubectl delete node talos-worker-02

# If it was a control plane, remove from etcd
talosctl etcd remove-member talos-cp-02 --nodes 10.10.5.200

# Delete the VM in Proxmox
qm stop 104
qm destroy 104
```

**2. Create a new VM with the SAME VM ID and name**
```bash
# Recreate with same ID and name
qm create 104 \
  --name "talos-worker-02" \
  --memory 8192 \
  --cores 4 \
  --cpu host \
  --net0 virtio,bridge=vmbr0 \
  --scsihw virtio-scsi-pci \
  --scsi0 local-lvm:64 \
  --ide2 local:iso/metal-amd64.iso,media=cdrom \
  --boot order=scsi0 \
  --ostype l26

qm start 104
```

**3. Apply the same config and reserve same IP**
```bash
# Apply worker.yaml (or controlplane.yaml)
talosctl apply-config --insecure \
  --nodes <temp-ip> \
  --file _out/worker.yaml

# Reserve the SAME IP it had before (10.10.5.204)
```

**4. Verify replacement**
```bash
kubectl get nodes
# Should show the new node with the same name
```

---

#### Important Notes

**About Configuration Files:**

✅ **Always use the ORIGINAL config files** from your initial cluster setup
- Don't generate new configs with `talosctl gen config`
- The original `controlplane.yaml` and `worker.yaml` contain the cluster secrets
- Generating new configs creates a new cluster identity (won't join existing cluster)

**About Node Identity:**

- Each node automatically gets a unique identity when the config is applied
- You don't need to modify the config for each node
- Hostnames are auto-generated (or you can use config patches for custom names)

**About DHCP vs Static IPs:**

- Using DHCP with reservations is the easiest approach
- Reserve by MAC address in your router/DHCP server
- Alternatively, use config patches for inline static IPs (more complex)

**About etcd Quorum:**

| Control Planes | Quorum Required | Failures Tolerated |
|----------------|-----------------|-------------------|
| 1              | 1               | 0                 |
| 2              | 2               | 0 (not HA)        |
| 3              | 2               | 1 ✅ Recommended   |
| 4              | 3               | 1                 |
| 5              | 3               | 2 ✅ Production    |

- 3 control planes = tolerate 1 failure (ideal for homelab)
- 5 control planes = tolerate 2 failures (ideal for production)
- 4 or 6 control planes = no additional fault tolerance (avoid)

**About Worker Nodes:**

- Add as many as you need for capacity
- No quorum concerns (unlike control planes)
- Common homelab setups: 2-4 workers

---

#### Quick Reference Commands

**Add Control Plane Node:**
```bash
# Create VM (ID 106, 2 CPU, 4GB RAM, 32GB disk)
qm create 106 --name "talos-cp-04" --memory 4096 --cores 2 --cpu host \
  --net0 virtio,bridge=vmbr0 --scsihw virtio-scsi-pci --scsi0 local-lvm:32 \
  --ide2 local:iso/metal-amd64.iso,media=cdrom --boot order=scsi0 --ostype l26
qm start 106

# Apply config (use temp DHCP IP)
talosctl apply-config --insecure --nodes <temp-ip> --file _out/controlplane.yaml

# Update endpoints
talosctl config endpoint 10.10.5.200 10.10.5.201 10.10.5.202 10.10.5.206

# Verify
kubectl get nodes
talosctl etcd members
```

**Add Worker Node:**
```bash
# Create VM (ID 105, 4 CPU, 8GB RAM, 64GB disk)
qm create 105 --name "talos-worker-03" --memory 8192 --cores 4 --cpu host \
  --net0 virtio,bridge=vmbr0 --scsihw virtio-scsi-pci --scsi0 local-lvm:64 \
  --ide2 local:iso/metal-amd64.iso,media=cdrom --boot order=scsi0 --ostype l26
qm start 105

# Apply config (use temp DHCP IP)
talosctl apply-config --insecure --nodes <temp-ip> --file _out/worker.yaml

# Verify
kubectl get nodes
```

**Remove Node:**
```bash
# Drain (if still accessible)
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data

# Delete from Kubernetes
kubectl delete node <node-name>

# If control plane, remove from etcd
talosctl etcd remove-member <member-name> --nodes 10.10.5.200

# Stop and destroy VM
qm stop <vmid>
qm destroy <vmid>
```

---