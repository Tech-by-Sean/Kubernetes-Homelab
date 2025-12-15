# Jellyfin Deployment Guide for Kubernetes (Talos + TrueNAS + Traefik)

## Prerequisites

- Kubernetes cluster (Talos Linux)
- TrueNAS with NFS shares
- Traefik ingress controller installed
- MetalLB for load balancing
- DNS server (e.g., Technitium)

---

## Step 1: TrueNAS Setup

### 1.1 Create Dataset

1. Go to **Datasets** → **Add Dataset**
2. Create: `master-storage/media-managment/jellyfin/config`
3. Set permissions:
   - Owner: `root`
   - Group: `root`
   - Mode: `0777` (Other needs Read/Write/Execute)
   - Apply recursively

### 1.2 Create NFS Share

1. Go to **Shares** → **NFS** → **Add**
2. Path: `/mnt/master-storage/media-managment/jellyfin/config`
3. Maproot User: `root`
4. Maproot Group: `root`
5. Save

---

## Step 2: Traefik RBAC Fix

> **Note:** This is a cluster-wide change, not specific to Jellyfin. Create this file in your `traefik/` folder and apply once per cluster. All apps using Traefik will benefit from this fix.

```yaml
# traefik/traefik-rbac.yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: traefik-ingress-controller
rules:
  - apiGroups: [""]
    resources: ["services", "endpoints", "secrets", "nodes"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["extensions", "networking.k8s.io"]
    resources: ["ingresses", "ingressclasses"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["extensions", "networking.k8s.io"]
    resources: ["ingresses/status"]
    verbs: ["update"]
  - apiGroups: ["traefik.io"]
    resources: ["*"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["discovery.k8s.io"]
    resources: ["endpointslices"]
    verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: traefik-ingress-controller
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: traefik-ingress-controller
subjects:
  - kind: ServiceAccount
    name: traefik-ingress-controller
    namespace: traefik
```

```bash
kubectl apply -f traefik-rbac.yaml
kubectl rollout restart deployment traefik -n traefik
```

---

## Step 3: Jellyfin Storage

Create the storage file first:

```yaml
# apps/jellyfin/jellyfin-storage.yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: jellyfin-config-pv
spec:
  capacity:
    storage: 10Gi
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: ""
  nfs:
    server: 10.10.5.40
    path: /mnt/master-storage/media-managment/jellyfin/config
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: jellyfin-config
  namespace: media
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: ""
  volumeName: jellyfin-config-pv
  resources:
    requests:
      storage: 10Gi
```

---

## Step 4: Jellyfin Manifest

```yaml
# apps/jellyfin/jellyfin-manifest.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: media
  labels:
    pod-security.kubernetes.io/enforce: privileged
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: jellyfin
  namespace: media
spec:
  replicas: 1
  selector:
    matchLabels:
      app: jellyfin
  template:
    metadata:
      labels:
        app: jellyfin
    spec:
      containers:
        - name: jellyfin
          image: jellyfin/jellyfin:latest
          ports:
            - containerPort: 8096
              name: http
          volumeMounts:
            - name: config
              mountPath: /config
          resources:
            limits:
              memory: "4Gi"
              cpu: "2000m"
            requests:
              memory: "1Gi"
              cpu: "500m"
      volumes:
        - name: config
          persistentVolumeClaim:
            claimName: jellyfin-config
---
apiVersion: v1
kind: Service
metadata:
  name: jellyfin
  namespace: media
spec:
  selector:
    app: jellyfin
  ports:
    - port: 8096
      targetPort: 8096
  type: ClusterIP
---
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: jellyfin
  namespace: media
spec:
  entryPoints:
    - web
  routes:
    - match: Host(`jellyfin.servers.local`)
      kind: Rule
      services:
        - name: jellyfin
          port: 8096
```

```bash
kubectl apply -f apps/jellyfin/jellyfin-storage.yaml
kubectl apply -f apps/jellyfin/jellyfin-manifest.yaml
```

---

## Step 5: DNS Configuration

Add A record in your DNS server:

| Hostname | IP Address |
|----------|------------|
| jellyfin.servers.local | 10.10.5.230 |

The IP is Traefik's LoadBalancer IP:
```bash
kubectl get svc -n traefik
```

---

## Step 6: Verify Deployment

```bash
# Check pod is running
kubectl get pods -n media

# Check service
kubectl get svc -n media

# Check IngressRoute
kubectl get ingressroute -n media

# Test routing
curl -H "Host: jellyfin.servers.local" http://10.10.5.230
```

Access Jellyfin at: `http://jellyfin.servers.local`

---

## Key Concepts

| Component | Purpose |
|-----------|---------|
| Namespace (`media`) | Isolates media apps; `privileged` label allows containers to run as root |
| PersistentVolume | Points to TrueNAS NFS share |
| PersistentVolumeClaim | Requests storage from PV |
| Deployment | Runs Jellyfin container |
| Service (ClusterIP) | Internal-only service; Traefik handles external access |
| IngressRoute | Traefik CRD that routes `jellyfin.servers.local` to the service |

---

## Troubleshooting

### Pod stuck in ContainerCreating
```bash
kubectl describe pod -n media -l app=jellyfin
```
Usually NFS mount issue. Check TrueNAS NFS share exists and permissions are correct.

### Pod in CrashLoopBackOff
```bash
kubectl logs -n media -l app=jellyfin
```
If "Permission denied" - fix TrueNAS dataset permissions (0777, root:root).

### 404 from Traefik
1. Check IngressRoute exists: `kubectl get ingressroute -n media`
2. Check Traefik logs: `kubectl logs -n traefik <pod-name>`
3. Verify RBAC is applied

### Can't resolve hostname
Check DNS record points to Traefik's IP (not Jellyfin's service IP).

---

## Adding Media Libraries Later

Create NFS shares for movies and shows datasets, then add PVs:

```yaml
# Add to manifest
---
apiVersion: v1
kind: PersistentVolume
metadata:
  name: jellyfin-movies-pv
spec:
  capacity:
    storage: 1Ti
  accessModes:
    - ReadWriteMany
  persistentVolumeReclaimPolicy: Retain
  storageClassName: ""
  nfs:
    server: 10.10.5.40
    path: /mnt/master-storage/media-managment/jellyfin/media/movies
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: jellyfin-movies
  namespace: media
spec:
  accessModes:
    - ReadWriteMany
  storageClassName: ""
  volumeName: jellyfin-movies-pv
  resources:
    requests:
      storage: 1Ti
---
apiVersion: v1
kind: PersistentVolume
metadata:
  name: jellyfin-shows-pv
spec:
  capacity:
    storage: 1Ti
  accessModes:
    - ReadWriteMany
  persistentVolumeReclaimPolicy: Retain
  storageClassName: ""
  nfs:
    server: 10.10.5.40
    path: /mnt/master-storage/media-managment/jellyfin/media/shows
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: jellyfin-shows
  namespace: media
spec:
  accessModes:
    - ReadWriteMany
  storageClassName: ""
  volumeName: jellyfin-shows-pv
  resources:
    requests:
      storage: 1Ti
```

Add volume mounts to deployment:
```yaml
volumeMounts:
  - name: config
    mountPath: /config
  - name: movies
    mountPath: /media/movies
  - name: shows
    mountPath: /media/shows
volumes:
  - name: config
    persistentVolumeClaim:
      claimName: jellyfin-config
  - name: movies
    persistentVolumeClaim:
      claimName: jellyfin-movies
  - name: shows
    persistentVolumeClaim:
      claimName: jellyfin-shows
```