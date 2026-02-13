# Talos Cluster Config Generation Guide

> **Cluster:** `talos-proxmox-cluster`
> **Endpoint:** `https://10.10.5.100:6443`
> **Platform:** XCP-ng | **Disk:** `/dev/xvda` | **Interface:** `enX0` | **MTU:** `9000`
> **Talos:** `v1.12.2` | **Kubernetes:** `v1.34.1`

---

## ⚠️ SAVE YOUR `secrets.yaml` FILE

> **Without `secrets.yaml`, you CANNOT generate new node configs.**
>
> The `talosctl gen config` command **requires** this file. No secrets file = no new nodes.
>
> This file contains every certificate, token, and encryption secret that ties nodes to your cluster. If you lose it, you're stuck manually extracting certs from running nodes, decoding escaped YAML, stripping incompatible Kubernetes objects, and debugging certificate parsing errors — **a process that can take hours.**
>
> **Save it. Back it up. Do not lose it.**
>
> Store it in at least two places: password manager, encrypted USB, private git repo — pick two or more.
>
> If you lose it while you still have a running control plane, you can recover it (see the last section), but that process is painful and should be a **last resort**, not the plan.

---

## Step 1 — Generate a Config

Every command below **requires** `--with-secrets secrets.yaml`. Without it, Talos generates configs with **new random secrets** that won't match your cluster.

**Worker node:**

```bash
talosctl gen config talos-proxmox-cluster https://10.10.5.100:6443 \
  --with-secrets secrets.yaml \
  --output-types worker \
  --output worker.yaml
```

**Control plane node:**

```bash
talosctl gen config talos-proxmox-cluster https://10.10.5.100:6443 \
  --with-secrets secrets.yaml \
  --output-types controlplane \
  --output controlplane.yaml
```

**Both at once:**

```bash
talosctl gen config talos-proxmox-cluster https://10.10.5.100:6443 \
  --with-secrets secrets.yaml
```

This creates `controlplane.yaml`, `worker.yaml`, and `talosconfig` in the current directory.

---

## Step 2 — Customize the Config

The generated config uses generic defaults. At minimum, you **must** change the install disk or the install will fail.

### Install disk (required)

```yaml
machine:
  install:
    disk: /dev/xvda
```

### Installer image version (required)

Match the version running on your cluster:

```yaml
machine:
  install:
    image: ghcr.io/siderolabs/installer:v1.12.2
```

> **Tip:** Check your cluster version with `talosctl -n 10.10.5.100 version`

### Network (optional — can patch later)

```yaml
machine:
  network:
    hostname: talos-worker-xo-2
    interfaces:
      - interface: enX0
        mtu: 9000
        dhcp: true
```

### Extensions (optional — if needed for GPU, etc.)

```yaml
machine:
  install:
    extensions:
      - image: ghcr.io/siderolabs/nvidia-container-toolkit:...
```

---

## Step 3 — Boot and Apply

**1.** Create a VM in XCP-ng and boot from the Talos ISO. It will enter maintenance mode and grab a DHCP address.

**2.** Apply the config:

```bash
talosctl apply-config --insecure --nodes <new-node-ip> --file worker.yaml
```

> The `--insecure` flag is required because the node isn't part of the cluster yet.

**3.** Wait for it to join, then verify:

```bash
kubectl get nodes
```

---

## Troubleshooting

**Node stuck booting from a bad config?**

Reset it back to maintenance mode, fix your config, and re-apply:

```bash
talosctl reset --insecure --nodes <node-ip> --graceful=false
```

**Old node still showing in Kubernetes?**

```bash
kubectl delete node <old-node-name>
```

---

## Quick Reference

| Task | Command |
|---|---|
| Generate worker config | `talosctl gen config talos-proxmox-cluster https://10.10.5.100:6443 --with-secrets secrets.yaml --output-types worker --output worker.yaml` |
| Generate CP config | `talosctl gen config talos-proxmox-cluster https://10.10.5.100:6443 --with-secrets secrets.yaml --output-types controlplane --output controlplane.yaml` |
| Apply config to new node | `talosctl apply-config --insecure --nodes <ip> --file <config>.yaml` |
| Reset a stuck node | `talosctl reset --insecure --nodes <ip> --graceful=false` |
| Check cluster nodes | `kubectl get nodes` |
| Remove stale node | `kubectl delete node <name>` |

---

## Last Resort — Recovering `secrets.yaml`

> **You should never need this section if you saved your `secrets.yaml`.** This process is fragile and error-prone. It exists only as an emergency fallback.

The machine config from `talosctl get mc` comes back as a double-escaped string with embedded Kubernetes objects that crash the parser. The python script below handles both issues.

**Step 1 — Extract and clean the control plane config:**

```bash
talosctl -n 10.10.5.100 get mc v1alpha1 -o json | python3 -c "
import sys, json, yaml
data = json.loads(sys.stdin.read())
spec = data['spec']
config = yaml.safe_load(spec)
if isinstance(config, str):
    config = yaml.safe_load(config)
if 'apiServer' in config.get('cluster', {}):
    config['cluster']['apiServer'].pop('auditPolicy', None)
    config['cluster']['apiServer'].pop('admissionControl', None)
print(yaml.dump(config, default_flow_style=False, width=10000))
" > controlplane-clean.yaml
```

**Step 2 — Generate secrets from the cleaned config:**

```bash
talosctl gen secrets --from-controlplane-config controlplane-clean.yaml -o secrets.yaml
```

**Step 3 — Save it this time.**