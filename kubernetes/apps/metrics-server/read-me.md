# 🚀 Kubernetes Metrics Server Deployment Guide (Talos Clusters)

This document outlines the **two essential phases** for successfully deploying the Kubernetes Metrics Server in a self-managed environment like Talos, including the mandatory infrastructure fix to ensure Kubelet certificate health and proper metric flow.

## 📝 Prerequisites

* Working `kubectl` access to the target Talos cluster.
* The Metrics Server manifest (`metrics-server.yaml`) must be pre-edited with the following performance/stability flags:
    * `--kubelet-insecure-tls`
    * `--kubelet-preferred-address-types=InternalIP`
    * `--metric-resolution=15s`

---

## 🔐 Phase 1: Deploy Kubelet TLS Infrastructure Fix

**⚠️ CRITICAL:** This step must be completed FIRST. The Metrics Server will not start without the Kubelet Serving Cert Approver in place to handle certificate signing requests.

### Step 1: Deploy Kubelet Serving Cert Approver

Deploy the controller using the manifest from the Homelab repository. This enables automatic approval of Kubelet Certificate Signing Requests (CSRs).

```bash
kubectl apply -f https://raw.githubusercontent.com/Tech-by-Sean/Kubernetes-Homelab/main/kubernets/apps/metrics-server/kubelet-cert-approver
```

### Step 2: Verify Cert Approver Deployment

Wait 30-60 seconds for the approver to be ready.

```bash
kubectl get pods -n kubelet-serving-cert-approver
```

---

## 📄 Phase 2: Deploy Metrics Server Application

This phase installs the Metrics Server pod using the custom, pre-configured manifest.

### Step 3: Apply the Metrics Server Manifest

Apply the manifest directly from the Homelab repository.

```bash
kubectl apply -f https://raw.githubusercontent.com/Tech-by-Sean/Kubernetes-Homelab/refs/heads/main/kubernets/apps/metrics-server/metrics-server.yaml
```

### Step 4: Verify Initial Pod Status

Check the status of the new pod in the `kube-system` namespace. It should now be `1/1` READY since the cert approver is handling certificates.

```bash
kubectl get pods -n kube-system -l k8s-app=metrics-server
```

---

## ✅ Phase 3: Final Verification and Health Check

### Step 5: Verify Metrics API Functionality

| Command | Expected Success Result |
|---------|------------------------|
| `kubectl get pods -n kube-system -l k8s-app=metrics-server` | Pod status must be `1/1 READY`. |
| `kubectl top nodes` | Must display CPU and Memory utilization figures for all nodes. |

**Success Note:** Once `kubectl top nodes` is working, cluster monitoring tools like k9s will be fully operational.

---

## 🗑️ Phase 4: Uninstall / Cleanup Procedure

To cleanly remove all components, use the following steps in reverse order.

### Step 6: Uninstall the Metrics Server

Remove the Metrics Server application components first.

```bash
kubectl delete -f https://raw.githubusercontent.com/Tech-by-Sean/Kubernetes-Homelab/refs/heads/main/kubernets/apps/metrics-server/metrics-server.yaml
```

### Step 7: Uninstall the Kubelet Serving Cert Approver

Remove the approver controller last.

```bash
kubectl delete namespace kubelet-serving-cert-approver 
#This will delete the namespace along with the pod.
```

### Step 8: Verification (Optional)

You can confirm the complete removal by checking the API service:

```bash
kubectl get apiservice v1beta1.metrics.k8s.io
# Expected Output: Error from server (NotFound): apiservices.apiregistration.k8s.io "v1beta1.metrics.k8s.io" not found
```

---