<<<<<<< HEAD:kubernets/apps/metrics-server/read-me.md
# Deploying Metrics Server on Talos Kubernetes for k9s integration
=======
# Deploying Metrics Server on Talos Kubernetes for k9s intergration
>>>>>>> 279a26d (header update):kubernets/apps/metrics-server/read-me

This guide covers deploying the Kubernetes Metrics Server in a Talos cluster, ensuring secure kubelet certificate handling.

Note: The manifest intentionally puts the metrics server in the kube-system namespace as a standard. This follows official documentation standards.
---

## Table of Contents

1. [Enable Kubelet Certificate Rotation](#step-1-enable-kubelet-certificate-rotation-in-talos-configuration)
2. [Deploy Metrics Server](#step-2-deploy-the-kubernetes-metrics-server)
3. [Verify Metrics Server](#step-3-test-with-kubectl-top-and-k9s)

---

## 🚀 Step 1: Enable Kubelet Certificate Rotation in Talos Configuration

For the Metrics Server to securely collect metrics from the kubelets, the kubelets need trusted certificates. The recommended approach in Talos is to enable kubelet certificate rotation.

### 1. Retrieve Current Talos Machine Configuration

```bash
# For a control plane node
talosctl get mc $NODE_IP -o yaml > controlplane.yaml
# OR
# For a worker node
talosctl get mc $NODE_IP -o yaml > worker.yaml
```

### 2. Edit Configuration

Add the following to your YAML under `machine.kubelet.extraArgs:`  
You may also wish to deploy a kubelet certificate approver.

```yaml
# ... other configuration above
machine:
  kubelet:
    extraArgs:
      # Enable automatic kubelet serving certificate rotation
      rotate-server-certificates: true 
# ... other configuration below
```

### 3. Apply the Modified Configuration
Apply and reboot for changes to take effect:
```bash
talosctl apply-config --nodes $NODE_IP --file controlplane.yaml
talosctl apply-config --nodes $NODE_IP --file worker.yaml # Repeat for each worker node
```
> **Note:** For new clusters, include this snippet when generating the initial configuration.

---

## 📦 Step 2: Deploy the Kubernetes Metrics Server

With the kubelet configured, deploy the Metrics Server using the official manifest:

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

### Verify Deployment

Check Metrics Server pod status:
```bash
kubectl get pods -n kube-system -l k8s-app=metrics-server
# Wait for pod status to be Running
```

Check for registered metrics API:
```bash
kubectl get apiservices | grep metrics.k8s.io
```
Expected output should show `True` under the AVAILABLE column:  
`v1beta1.metrics.k8s.io   kube-system/metrics-server   True    <age>`

---

## 🖥️ Step 3: Test with kubectl top and k9s

### Test with kubectl top
Ensure metrics are being collected:
```bash
kubectl top nodes
kubectl top pods -A
```
You should see CPU & memory usage for nodes and pods.

### Test with k9s

```bash
k9s
```
You should see CPU and memory utilization in pod/node views and in pulses view (`:pulses`).

---

## 📝 References

- [Talos Documentation](https://www.talos.dev/)
- [Metrics Server Documentation](https://github.com/kubernetes-sigs/metrics-server)
