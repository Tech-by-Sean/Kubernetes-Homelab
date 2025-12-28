# Jellyfin - Media Streaming Server

### Order of Operations

**Prerequisites & Setup Order:**

1. ✅ **Proxmox VMs & Talos Linux Cluster** - Base Kubernetes cluster
2. ✅ **MetalLB** - Load balancer for bare metal (`kubernetes/apps/metallb/`)
3. ✅ **Traefik** - Ingress controller and reverse proxy (`kubernetes/apps/traefik/`)
4. ✅ **CoreDNS Configuration** - DNS resolution for `.servers.local` domains (`kubernetes/apps/kube-system/coredns-config.yaml`)
5. ✅ **Forgejo** - Self-hosted Git server (`http://forgejo.servers.local:3000`)
6. ✅ **GitHub Mirror** - Forgejo configured to mirror to GitHub (backup)
7. ✅ **ArgoCD** - GitOps continuous delivery (`kubernetes/apps/argocd/`)
8. ✅ **TrueNAS NFS Storage** - Persistent storage configured
9. **❌ Jellyfin - Media Streaming Server** (YOU ARE HERE)
   - Other applications: Sonarr, Radarr, Prowlarr, qBittorrent, etc.

---

### Why Jellyfin?

Jellyfin is a free, open-source media server that lets you manage and stream your personal media collection.

**Key Features:**
- **No Subscriptions:** Completely free with no premium tiers
- **Privacy Focused:** No tracking, no phone-home
- **Format Support:** Wide codec and container support
- **Cross-Platform:** Web, mobile, TV apps, and more
- **Live TV & DVR:** Optional TV tuner integration
- **User Management:** Multiple users with watch history and preferences

**Why Use Jellyfin in Kubernetes?**
- Persistent storage on TrueNAS for media and config
- Easy scaling and updates via GitOps
- Ingress routing via Traefik with custom domain
- Centralized logging and monitoring

---

### Architecture Overview
```
User Request
    ↓
DNS (jellyfin.servers.local → 10.10.5.230)
    ↓
Traefik LoadBalancer (10.10.5.230)
    ↓
Traefik IngressRoute (routing rule)
    ↓
Jellyfin Service (ClusterIP)
    ↓
Jellyfin Pod
    ↓
TrueNAS NFS Shares (10.10.5.40)
├── Config:  /mnt/gluttonterra/k8s/jellyfin/config
├── Movies:  /mnt/gluttonterra/k8s/jellyfin/media/movies
└── Shows:   /mnt/gluttonterra/k8s/jellyfin/media/shows
```

---

### Prerequisites

Before deploying Jellyfin, ensure you have:

**Cluster Components:**
- [ ] Talos Kubernetes cluster running
- [ ] MetalLB installed and configured
- [ ] Traefik ingress controller deployed
- [ ] CoreDNS configured for `.servers.local` resolution
- [ ] ArgoCD installed (optional but recommended)

**Storage:**
- [ ] TrueNAS server accessible at 10.10.5.40
- [ ] NFS service enabled on TrueNAS
- [ ] Datasets created for Jellyfin

**Network:**
- [ ] DNS server accessible (Technitium at 10.10.5.2, 10.10.5.3)
- [ ] Traefik LoadBalancer IP noted (check: `kubectl get svc -n traefik`)

---

### File Structure

This deployment uses the following files from the repository:
```
kubernetes/apps/jellyfin/
├── readme.md                        # This file
├── jellyfin-config-pv-pvc.yaml     # Config storage (NFS)
├── jellyfin-movies-pv-pvc.yaml     # Movies library storage (NFS)
├── jellyfin-shows-pv-pvc.yaml      # TV shows library storage (NFS)
└── jellyfin-manifest.yaml          # Main deployment, service, and ingress
```

---

### Step 1: TrueNAS Dataset Setup

Create datasets for Jellyfin storage on TrueNAS.

#### 1.1 Create Datasets

Navigate to TrueNAS UI → **Storage** → **Datasets**

Create the following datasets under `gluttonterra/k8s/jellyfin`:
```
gluttonterra/k8s/jellyfin
├── config           # Jellyfin configuration and metadata
└── media
    ├── movies       # Movie library
    └── shows        # TV show library
```

**Via TrueNAS UI:**
1. Click **Add Dataset**
2. Parent: `gluttonterra/k8s/jellyfin`
3. Name: `config`
4. Click **Submit**
5. Repeat for `media`, `media/movies`, `media/shows`

#### 1.2 Set Dataset Permissions

For each dataset (`config`, `media/movies`, `media/shows`):

1. Click dataset → **Edit Permissions**
2. Set:
   - **Owner:** `root`
   - **Group:** `root`
   - **Mode:** `0777` (or Owner/Group: `rwx`, Other: `r-x`)
   - ✅ **Apply permissions recursively**
3. Click **Save**

> **Why 0777?** Kubernetes pods run with varying UIDs/GIDs. Using 0777 ensures broad compatibility. For production, consider specific UID/GID mappings.

#### 1.3 Create NFS Shares

Navigate to **Shares** → **NFS**

Create shares for each dataset:

**Config Share:**
- Path: `/mnt/gluttonterra/k8s/jellyfin/config`
- Maproot User: `root`
- Maproot Group: `root`
- Networks: `10.10.5.0/24`

**Movies Share:**
- Path: `/mnt/gluttonterra/k8s/jellyfin/media/movies`
- Maproot User: `root`
- Maproot Group: `root`
- Networks: `10.10.5.0/24`

**Shows Share:**
- Path: `/mnt/gluttonterra/k8s/jellyfin/media/shows`
- Maproot User: `root`
- Maproot Group: `root`
- Networks: `10.10.5.0/24`

Click **Save** and **Enable Service** if prompted.

---

### Step 2: Traefik RBAC Configuration (One-Time Cluster Setup)

> **Note:** This is a **cluster-wide change**, not specific to Jellyfin. If you've already applied this for another application, skip this step.

Traefik needs proper RBAC permissions to discover and route to IngressRoute resources.

**Apply the Traefik RBAC configuration:**
```bash
# Apply Traefik RBAC from the traefik directory
kubectl apply -f kubernetes/apps/traefik/traefik-rbac.yaml

# Restart Traefik to pick up new permissions
kubectl rollout restart deployment traefik -n traefik

# Verify Traefik is running
kubectl get pods -n traefik
```

> **File location:** `kubernetes/apps/traefik/traefik-rbac.yaml`

---

### Step 3: Deploy Jellyfin Storage (PV/PVC)

Apply the persistent volume and persistent volume claim configurations for Jellyfin.
```bash
# Apply config storage
kubectl apply -f kubernetes/apps/jellyfin/jellyfin-config-pv-pvc.yaml

# Apply movies storage
kubectl apply -f kubernetes/apps/jellyfin/jellyfin-movies-pv-pvc.yaml

# Apply shows storage
kubectl apply -f kubernetes/apps/jellyfin/jellyfin-shows-pv-pvc.yaml

# Verify PVs are Available
kubectl get pv | grep jellyfin

# Expected output:
# jellyfin-config-pv    50Gi       RWO            Retain           Available             ...
# jellyfin-movies-pv    2Ti        RWX            Retain           Available             ...
# jellyfin-shows-pv     2Ti        RWX            Retain           Available             ...
```

> **Files:**
> - `kubernetes/apps/jellyfin/jellyfin-config-pv-pvc.yaml` - Config storage (50Gi)
> - `kubernetes/apps/jellyfin/jellyfin-movies-pv-pvc.yaml` - Movies storage (2Ti)
> - `kubernetes/apps/jellyfin/jellyfin-shows-pv-pvc.yaml` - Shows storage (2Ti)

**Storage Configuration Details:**

| Volume | Size | Access Mode | Purpose |
|--------|------|-------------|---------|
| jellyfin-config-pv | 50Gi | ReadWriteOnce | Jellyfin config, metadata, transcoding cache |
| jellyfin-movies-pv | 2Ti | ReadWriteMany | Movie library (shared with other apps) |
| jellyfin-shows-pv | 2Ti | ReadWriteMany | TV show library (shared with other apps) |

---

### Step 4: Deploy Jellyfin Application

Apply the main Jellyfin deployment, service, and ingress configuration.
```bash
# Apply Jellyfin manifest
kubectl apply -f kubernetes/apps/jellyfin/jellyfin-manifest.yaml

# Wait for deployment to complete
kubectl rollout status deployment/jellyfin -n media

# Verify all resources
kubectl get all -n media

# Check pod status
kubectl get pods -n media

# Expected output:
# NAME                        READY   STATUS    RESTARTS   AGE
# jellyfin-xxxxxxxxxx-xxxxx   1/1     Running   0          2m
```

> **File location:** `kubernetes/apps/jellyfin/jellyfin-manifest.yaml`

**This manifest creates:**
- Namespace: `media` (with privileged pod security)
- Deployment: Jellyfin container with resource limits
- Service: ClusterIP service on port 8096
- IngressRoute: Traefik routing for `jellyfin.servers.local`

**Verify PVCs are Bound:**
```bash
kubectl get pvc -n media

# Expected output:
# NAME                   STATUS   VOLUME               CAPACITY   ACCESS MODES
# jellyfin-config-pvc    Bound    jellyfin-config-pv   50Gi       RWO
# jellyfin-movies-pvc    Bound    jellyfin-movies-pv   2Ti        RWX
# jellyfin-shows-pvc     Bound    jellyfin-shows-pv    2Ti        RWX
```

---

### Step 5: DNS Configuration

Add a DNS A record for Jellyfin pointing to Traefik's LoadBalancer IP.

**Get Traefik LoadBalancer IP:**
```bash
kubectl get svc -n traefik

# Example output:
# NAME      TYPE           CLUSTER-IP      EXTERNAL-IP    PORT(S)
# traefik   LoadBalancer   10.43.100.50    10.10.5.230    80:30080/TCP,443:30443/TCP
```

Note the `EXTERNAL-IP` (example: `10.10.5.230`)

**Add DNS Record:**

In your DNS server (Technitium, pfSense, router, etc.):

| Record Type | Hostname | IP Address |
|-------------|----------|------------|
| A | jellyfin.servers.local | 10.10.5.230 |

**Verify DNS resolution:**
```bash
nslookup jellyfin.servers.local

# Should return: 10.10.5.230
```

---

### Step 6: Verify Deployment

**Check all resources:**
```bash
# Check namespace
kubectl get ns media

# Check pods
kubectl get pods -n media

# Check services
kubectl get svc -n media

# Check IngressRoute
kubectl get ingressroute -n media

# Check PVCs are bound
kubectl get pvc -n media

# Check pod logs
kubectl logs -n media -l app=jellyfin

# Test HTTP endpoint
curl -H "Host: jellyfin.servers.local" http://10.10.5.230
```

**Access Jellyfin:**

Open your browser and navigate to:
```
http://jellyfin.servers.local
```

You should see the Jellyfin setup wizard.

---

### Step 7: Initial Jellyfin Setup

**Via Web UI:**

1. Navigate to `http://jellyfin.servers.local`
2. Select your language
3. Create admin user account
4. Configure media libraries:
   - **Movies:** `/media/movies`
   - **TV Shows:** `/media/shows`
5. Configure metadata providers (TMDB, TVDB, etc.)
6. Complete setup wizard

**Add Media:**

Upload media to your TrueNAS shares:
- Movies: `/mnt/gluttonterra/k8s/jellyfin/media/movies`
- Shows: `/mnt/gluttonterra/k8s/jellyfin/media/shows`

Jellyfin will automatically scan and add them to your library.

---

### GitOps Deployment (ArgoCD)

If using ArgoCD, create an Application manifest:
```yaml
# argocd/applications/jellyfin.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: jellyfin
  namespace: argocd
spec:
  project: media
  source:
    repoURL: http://forgejo.servers.local:3000/smokrane/Kubernetes-Homelab.git
    targetRevision: main
    path: kubernetes/apps/jellyfin
  destination:
    server: https://kubernetes.default.svc
    namespace: media
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

**Apply via ArgoCD:**
```bash
kubectl apply -f argocd/applications/jellyfin.yaml

# Or via ArgoCD UI:
# - Applications → New App
# - Repository: http://forgejo.servers.local:3000/smokrane/Kubernetes-Homelab.git
# - Path: kubernetes/apps/jellyfin
# - Destination: media namespace
```

---

### Key Concepts

| Component | Purpose |
|-----------|---------|
| **Namespace** (`media`) | Isolates media apps; `privileged` label allows containers to run as root if needed |
| **PersistentVolume** | Points to TrueNAS NFS share (server: 10.10.5.40) |
| **PersistentVolumeClaim** | Requests storage from PV; binds pod to storage |
| **Deployment** | Runs Jellyfin container with resource limits and health checks |
| **Service** (ClusterIP) | Internal-only service; Traefik handles external access |
| **IngressRoute** | Traefik CRD that routes `jellyfin.servers.local` to the service |

**Storage Flow:**
```
Pod → PVC → PV → NFS Mount → TrueNAS Dataset
```

**Traffic Flow:**
```
User → DNS → Traefik LoadBalancer → IngressRoute → Service → Pod
```

---

### Troubleshooting

**Pod stuck in ContainerCreating:**
```bash
kubectl describe pod -n media -l app=jellyfin

# Common causes:
# 1. NFS mount issue
# 2. PVC not bound
# 3. Permissions issue on TrueNAS
```

**Check NFS mount:**
```bash
# From inside the pod
kubectl exec -n media -it <pod-name> -- df -h

# Should show NFS mounts:
# 10.10.5.40:/mnt/gluttonterra/k8s/jellyfin/config  on /config
# 10.10.5.40:/mnt/gluttonterra/k8s/jellyfin/media/movies on /media/movies
```

**Pod in CrashLoopBackOff:**
```bash
kubectl logs -n media -l app=jellyfin --tail=50

# Common issues:
# - Permission denied → Fix TrueNAS dataset permissions (0777, root:root)
# - Missing config → First boot should auto-generate
# - Port already in use → Check for conflicting services
```

**404 from Traefik:**
```bash
# Check IngressRoute exists
kubectl get ingressroute -n media

# Check Traefik can see the route
kubectl logs -n traefik deployment/traefik | grep jellyfin

# Verify RBAC is applied
kubectl get clusterrole traefik-ingress-controller

# If missing, apply traefik-rbac.yaml
kubectl apply -f kubernetes/apps/traefik/traefik-rbac.yaml
kubectl rollout restart deployment traefik -n traefik
```

**Can't resolve hostname:**
```bash
# Check DNS record
nslookup jellyfin.servers.local

# Should return Traefik's LoadBalancer IP (10.10.5.230), NOT the pod IP

# If returns wrong IP, update DNS record
# If no resolution, add A record to DNS server
```

**NFS Permission Denied:**
```bash
# Check TrueNAS dataset permissions
# Should be: Owner=root, Group=root, Mode=0777

# Check NFS share settings
# Should allow: 10.10.5.0/24, Maproot=root

# Test NFS mount from a debug pod
kubectl run -it --rm nfs-test --image=busybox --restart=Never -- \
  sh -c "mount -t nfs 10.10.5.40:/mnt/gluttonterra/k8s/jellyfin/config /mnt && ls -la /mnt"
```

**PVC stuck in Pending:**
```bash
kubectl describe pvc -n media jellyfin-config-pvc

# Check:
# 1. PV exists: kubectl get pv jellyfin-config-pv
# 2. volumeName matches in PVC
# 3. Access modes match
# 4. Storage class is "" (empty string)
```

**Jellyfin shows empty library:**
```bash
# Check if media directories are mounted
kubectl exec -n media deployment/jellyfin -- ls -la /media/movies
kubectl exec -n media deployment/jellyfin -- ls -la /media/shows

# Trigger library scan in Jellyfin UI
# Dashboard → Libraries → Scan All Libraries

# Or trigger via API
kubectl exec -n media deployment/jellyfin -- curl -X POST http://localhost:8096/Library/Refresh
```

---

### Maintenance

**Update Jellyfin:**
```bash
# Update image tag in jellyfin-manifest.yaml
# Change: image: jellyfin/jellyfin:latest
# To: image: jellyfin/jellyfin:10.9.0

# Apply changes
kubectl apply -f kubernetes/apps/jellyfin/jellyfin-manifest.yaml

# Or if using ArgoCD, commit to Git and ArgoCD will auto-sync
git add kubernetes/apps/jellyfin/jellyfin-manifest.yaml
git commit -m "Update Jellyfin to 10.9.0"
git push

# Watch rollout
kubectl rollout status deployment/jellyfin -n media
```

**Backup Configuration:**
```bash
# Jellyfin config is stored on TrueNAS
# Take a TrueNAS snapshot of the dataset
# TrueNAS UI → Storage → Snapshots → Add Snapshot
# Dataset: gluttonterra/k8s/jellyfin/config
```

**View Logs:**
```bash
# Real-time logs
kubectl logs -n media -l app=jellyfin -f

# Last 100 lines
kubectl logs -n media -l app=jellyfin --tail=100

# Previous container (if crashed)
kubectl logs -n media -l app=jellyfin --previous
```

**Restart Jellyfin:**
```bash
# Graceful restart
kubectl rollout restart deployment/jellyfin -n media

# Force delete pod (will recreate)
kubectl delete pod -n media -l app=jellyfin
```

**Scale Replicas:**

> **Note:** Jellyfin doesn't support multiple replicas (shared database would conflict). Always keep replicas: 1

---

### Resource Requirements

**Minimum:**
- CPU: 500m (0.5 cores)
- Memory: 1Gi

**Recommended:**
- CPU: 2 cores
- Memory: 4Gi

**For 4K Transcoding:**
- CPU: 4+ cores (or hardware transcoding GPU)
- Memory: 8Gi

**Adjust in `jellyfin-manifest.yaml`:**
```yaml
resources:
  limits:
    memory: "8Gi"
    cpu: "4000m"
  requests:
    memory: "2Gi"
    cpu: "1000m"
```

---

### Integration with Other Apps

**Sonarr/Radarr Integration:**
- Sonarr and Radarr will download to the same NFS shares
- Jellyfin automatically detects new media
- Configure library auto-scan in Jellyfin settings

**Shared Storage:**
- Movies: `/mnt/gluttonterra/k8s/jellyfin/media/movies` (shared with Radarr)
- Shows: `/mnt/gluttonterra/k8s/jellyfin/media/shows` (shared with Sonarr)

---

### Related Configuration

- **Namespace:** `media` (shared with Sonarr, Radarr, Prowlarr, qBittorrent)
- **TrueNAS Datasets:** `gluttonterra/k8s/jellyfin/*`
- **Traefik Configuration:** `kubernetes/apps/traefik/`
- **ArgoCD Project:** `media` (if using GitOps)
- **DNS Records:** Managed in Technitium (10.10.5.2, 10.10.5.3)

---

### Next Steps

Once Jellyfin is running:

1. ✅ Configure media libraries in Jellyfin UI
2. ⬜ Deploy Sonarr for TV show management
3. ⬜ Deploy Radarr for movie management
4. ⬜ Deploy Prowlarr for indexer management
5. ⬜ Deploy qBittorrent for downloads
6. ⬜ Configure automation pipeline (Prowlarr → Sonarr/Radarr → qBittorrent → Jellyfin)

---

### Quick Reference

**Access Jellyfin:**
```
URL: http://jellyfin.servers.local
```

**Important Files:**
```
kubernetes/apps/jellyfin/
├── readme.md
├── jellyfin-config-pv-pvc.yaml
├── jellyfin-movies-pv-pvc.yaml
├── jellyfin-shows-pv-pvc.yaml
└── jellyfin-manifest.yaml
```

**Common Commands:**
```bash
# Check status
kubectl get pods -n media
kubectl get pvc -n media
kubectl get ingressroute -n media

# View logs
kubectl logs -n media -l app=jellyfin -f

# Restart
kubectl rollout restart deployment/jellyfin -n media

# Access shell
kubectl exec -n media -it deployment/jellyfin -- /bin/bash
```

**TrueNAS Paths:**
```
Config:  /mnt/gluttonterra/k8s/jellyfin/config
Movies:  /mnt/gluttonterra/k8s/jellyfin/media/movies
Shows:   /mnt/gluttonterra/k8s/jellyfin/media/shows
```

**Network:**
```
Traefik LoadBalancer: 10.10.5.230
TrueNAS NFS Server:   10.10.5.40
DNS Servers:          10.10.5.2, 10.10.5.3
```