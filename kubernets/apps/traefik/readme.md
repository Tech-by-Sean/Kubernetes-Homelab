# Traefik Deployment Guide

This guide walks you through deploying Traefik as an ingress controller in your Kubernetes cluster with MetalLB for load balancing.

## Prerequisites

- Kubernetes cluster up and running
- `kubectl` configured to access your cluster
- MetalLB installed and configured with an IP address pool

## Deployment Steps

### Step 1: Create the Traefik Namespace

```bash
kubectl create namespace traefik
```

### Step 2: Apply Gateway API CRDs

Deploy the Gateway API Custom Resource Definitions:

```bash
kubectl apply -f https://raw.githubusercontent.com/Tech-by-Sean/Kubernetes-Homelab/refs/heads/main/kubernets/apps/traefik/gateway-api-crd.yaml
```

### Step 3: Apply Traefik CRDs

Deploy the Traefik-specific Custom Resource Definitions:

```bash
kubectl apply -f https://raw.githubusercontent.com/Tech-by-Sean/Kubernetes-Homelab/refs/heads/main/kubernets/apps/traefik/traefik-crds.yaml
```

### Step 4: Apply Traefik RBAC

Deploy the necessary RBAC (Role-Based Access Control) resources:

```bash
kubectl apply -f https://raw.githubusercontent.com/Tech-by-Sean/Kubernetes-Homelab/refs/heads/main/kubernets/apps/traefik/traefik-rbac.yaml
```

### Step 5: Deploy Traefik

Deploy the Traefik controller, service account, and LoadBalancer service:

```bash
kubectl apply -f https://raw.githubusercontent.com/Tech-by-Sean/Kubernetes-Homelab/refs/heads/main/kubernets/apps/traefik/traefik-deployment.yaml
```

## Verification

### Check Pod Status

Verify that the Traefik pod is running:

```bash
kubectl get pods -n traefik
```

Expected output:
```
NAME                       READY   STATUS    RESTARTS   AGE
traefik-xxxxxxxxxx-xxxxx   1/1     Running   0          1m
```

### Check Service and External IP

Verify that MetalLB has assigned an external IP to the Traefik service:

```bash
kubectl get svc -n traefik
```

Expected output:
```
NAME      TYPE           CLUSTER-IP      EXTERNAL-IP   PORT(S)                                     AGE
traefik   LoadBalancer   10.108.94.101   10.10.5.230   80:xxxxx/TCP,443:xxxxx/TCP,8080:xxxxx/TCP   1m
```

### Access Traefik Dashboard

Once the external IP is assigned, access the Traefik dashboard:

```
http://<EXTERNAL-IP>:8080/dashboard/
```

**Note:** Don't forget the trailing slash!

### Test HTTP Access

Test that Traefik is responding on port 80:

```bash
curl http://<EXTERNAL-IP>
```

You should receive a `404 page not found` response, which confirms Traefik is running but has no routes configured yet.

## What's Deployed

- **Gateway API CRDs**: Standard Kubernetes Gateway API resources (v1.3.0)
- **Traefik CRDs**: Traefik-specific custom resources (IngressRoute, Middleware, etc.)
- **RBAC**: ClusterRole and ClusterRoleBinding for Traefik
- **Service Account**: `traefik-ingress-controller` in the `traefik` namespace
- **Deployment**: Traefik v3.2 controller
- **LoadBalancer Service**: Exposes Traefik on ports 80 (HTTP), 443 (HTTPS), and 8080 (Dashboard)

## Exposed Ports

- **80**: HTTP traffic
- **443**: HTTPS traffic  
- **8080**: Traefik dashboard (insecure mode for testing)

## Next Steps

- Create IngressRoutes to expose your applications
- Configure TLS certificates with cert-manager
- Secure the Traefik dashboard
- Set up middleware for authentication, rate limiting, etc.

## Troubleshooting

### Pod not starting

Check pod logs:
```bash
kubectl logs -n traefik -l app=traefik
```

### External IP stuck on `<pending>`

Check MetalLB status:
```bash
kubectl get pods -n metallb-system
kubectl logs -n metallb-system -l app=metallb -l component=controller
```

Verify your MetalLB IP address pool:
```bash
kubectl get ipaddresspool -n metallb-system
```

### Dashboard not accessible

Ensure you're using the correct URL format with the trailing slash:
```
http://<EXTERNAL-IP>:8080/dashboard/
```