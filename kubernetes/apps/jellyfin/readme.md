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
├── Config:  /mnt/master-storage/media-managment/jellyfin/config
├── Movies:  /mnt/master-storage/media-managment/jellyfin/media/movies
└── Shows:   /mnt/master-storage/media-managment/jellyfin/media/shows
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
- [ ] Datasets created under `master-storage/media-managment/jellyfin`

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

#### 1.1 Verify Dataset Structure

Your TrueNAS should have the following dataset structure:
```
master-storage/
└── media-managment/
    └── jellyfin/
        ├── config           # Jellyfin configuration and metadata
        └── media/
            ├── downloads    # Downloads directory (for qBittorrent)
            ├── movies       # Movie library
            └── shows        # TV show library
```

Based on your screenshot, these datasets already exist. If you need to create additional datasets:

**Via TrueNAS UI:**
1. Navigate to **Storage** → **Datasets**
2. Click **Add Dataset**
3. Parent: `master-storage/media-managment/jellyfin/media`
4. Name: (e.g., `anime`, `music`, etc.)
5. Click **Submit**

#### 1.2 Set Dataset Permissions

For each dataset (`config`, `media/movies`, `media/shows`):

1. Navigate to **Storage** → **Datasets**
2. Click the dataset → **Edit Permissions**
3. Set:
   - **Owner:** `root`
   - **Group:** `root`
   - **Access Mode:** Click **Use ACL Manager** or set Unix Permissions:
     - Owner: `Read`, `Write`, `Execute`
     - Group: `Read`, `Write`, `Execute`
     - Other: `Read`, `Execute`
   - ✅ **Apply permissions recursively**
4. Click **Save**

> **Note:** For simpler permission management, you can use `0777` (full permissions for all), but this is less secure. For production, consider specific UID/GID mappings.

#### 1.3 Create/Verify NFS Shares

Navigate to **Shares** → **NFS** → **Unix Shares (NFS)**

Verify or create NFS shares for each dataset:

**Config Share:**
1. Click **Add** (if doesn't exist)
2. **Path:** `/mnt/master-storage/media-managment/jellyfin/config`
3. Click **Submit**
4. Click the share → **Edit**
5. **Advanced Options:**
   - **Maproot User:** `root`
   - **Maproot Group:** `root`
   - **Authorized Networks:** `10.10.5.0/24`
6. Click **Save**

**Movies Share:**
1. **Path:** `/mnt/master-storage/media-managment/jellyfin/media/movies`
2. **Maproot User:** `root`
3. **Maproot Group:** `root`
4. **Authorized Networks:** `10.10.5.0/24`

**Shows Share:**
1. **Path:** `/mnt/master-storage/media-managment/jellyfin/media/shows`
2. **Maproot User:** `root`
3. **Maproot Group:** `root`
4. **Authorized Networks:** `10.10.5.0/24`

**Enable NFS Service:**
- Navigate to **System Settings** → **Services**
- Find **NFS** and toggle **Running**
- Click the **Configure** icon (⚙️) and ensure:
  - ✅ **Enable NFSv4**
  - ✅ **NFSv3 ownership model for NFSv4**
  - Click **Save**

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
> - `kubernetes/apps/jellyfin/jellyfin-config-pv-pvc.yaml` - Config storage (50Gi, RWO)
> - `kubernetes/apps/jellyfin/jellyfin-movies-pv-pvc.yaml` - Movies storage (2Ti, RWX)
> - `kubernetes/apps/jellyfin/jellyfin-shows-pv-pvc.yaml` - Shows storage (2Ti, RWX)

**Storage Configuration Details:**

| Volume | Size | Access Mode | NFS Path | Purpose |
|--------|------|-------------|----------|---------|
| jellyfin-config-pv | 50Gi | ReadWriteOnce | `/mnt/master-storage/media-managment/jellyfin/config` | Jellyfin config, metadata, cache |
| jellyfin-movies-pv | 2Ti | ReadWriteMany | `/mnt/master-storage/media-managment/jellyfin/media/movies` | Movie library (shared) |
| jellyfin-shows-pv | 2Ti | ReadWriteMany | `/mnt/master-storage/media-managment/jellyfin/media/shows` | TV show library (shared) |

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
- **Namespace:** `media` (with privileged pod security)
- **Deployment:** Jellyfin container with resource limits and health probes
- **Service:** ClusterIP service on port 8096
- **IngressRoute:** Traefik routing for `jellyfin.servers.local`

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

### Step 7: Verify NFS Mounts

Verify that the NFS shares are properly mounted inside the Jellyfin pod:
```bash
# Check mounts
kubectl exec -n media -l app=jellyfin -- df -h

# Expected output showing NFS mounts:
# Filesystem                                                          Size  Used Avail Use% Mounted on
# 10.10.5.40:/mnt/master-storage/media-managment/jellyfin/config     8.9T  1.6T  7.3T  18% /config
# 10.10.5.40:/mnt/master-storage/media-managment/jellyfin/media/movies  8.9T  1.6T  7.3T  18% /media/movies
# 10.10.5.40:/mnt/master-storage/media-managment/jellyfin/media/shows   8.9T  1.6T  7.3T  18% /media/shows

# Check mount details
kubectl exec -n media -l app=jellyfin -- mount | grep nfs

# List directory contents
kubectl exec -n media -l app=jellyfin -- ls -la /config
kubectl exec -n media -l app=jellyfin -- ls -la /media/movies
kubectl exec -n media -l app=jellyfin -- ls -la /media/shows
```

---

### Step 8: Initial Jellyfin Setup

**Via Web UI:**

1. Navigate to `http://jellyfin.servers.local`
2. **Welcome Screen:** Select your preferred language → Click **Next**
3. **Create Admin User:**
   - Username: (e.g., `admin`)
   - Password: (create a strong password)
   - Click **Next**
4. **Setup Media Libraries:**
   - Click **Add Media Library**
   - **Content type:** Movies
   - **Display name:** Movies
   - **Folders:** Click **+** and enter `/media/movies`
   - Click **OK**
   - Repeat for TV Shows (`/media/shows`)
   - Click **Next**
5. **Preferred Metadata Language:** Select your language → Click **Next**
6. **Remote Access:** Configure as needed → Click **Next**
7. **Finish:** Click **Finish**

**Add Media Files:**

Upload or copy media files to your TrueNAS shares:
- **Movies:** `/mnt/master-storage/media-managment/jellyfin/media/movies/`
- **TV Shows:** `/mnt/master-storage/media-managment/jellyfin/media/shows/`

Jellyfin will automatically scan and add them to your library.

**Trigger Manual Scan:**
- Dashboard → Libraries → Click **Scan All Libraries**

---

### GitOps Deployment (ArgoCD)

If using ArgoCD, create an Application manifest:

**Create `kubernetes/argocd/applications/jellyfin.yaml`:**
```yaml
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
kubectl apply -f kubernetes/argocd/applications/jellyfin.yaml

# Or via ArgoCD UI:
# - Applications → New App
# - Application Name: jellyfin
# - Project: media
# - Repository: http://forgejo.servers.local:3000/smokrane/Kubernetes-Homelab.git
# - Path: kubernetes/apps/jellyfin
# - Destination: media namespace
# - Sync Policy: Automatic
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
# 1. NFS mount issue - check TrueNAS NFS service is running
# 2. PVC not bound - check PV exists and matches PVC
# 3. Permissions issue - verify dataset permissions
# 4. Network issue - verify worker nodes can reach 10.10.5.40
```

**Check NFS mount:**
```bash
# From inside the pod
kubectl exec -n media -l app=jellyfin -- df -h | grep nfs

# Should show NFS mounts:
# 10.10.5.40:/mnt/master-storage/media-managment/jellyfin/config on /config
# 10.10.5.40:/mnt/master-storage/media-managment/jellyfin/media/movies on /media/movies
# 10.10.5.40:/mnt/master-storage/media-managment/jellyfin/media/shows on /media/shows
```

**Pod in CrashLoopBackOff:**
```bash
kubectl logs -n media -l app=jellyfin --tail=50

# Common issues:
# - Permission denied → Fix TrueNAS dataset permissions
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
# Via TrueNAS UI: Storage → Datasets → Click dataset → Edit Permissions
# Should allow root:root with appropriate read/write/execute

# Check NFS share settings
# Via TrueNAS UI: Shares → NFS
# Should allow: 10.10.5.0/24, Maproot=root

# Test NFS mount from a debug pod
kubectl run -it --rm nfs-test --image=busybox --restart=Never -- \
  sh -c "mount -t nfs 10.10.5.40:/mnt/master-storage/media-managment/jellyfin/config /mnt && ls -la /mnt"
```

**PVC stuck in Pending:**
```bash
kubectl describe pvc -n media jellyfin-config-pvc

# Check:
# 1. PV exists: kubectl get pv jellyfin-config-pv
# 2. volumeName matches in PVC spec
# 3. Access modes match between PV and PVC
# 4. Storage class is "" (empty string)
# 5. NFS server is reachable from worker nodes
```

**Jellyfin shows empty library:**
```bash
# Check if media directories are mounted
kubectl exec -n media -l app=jellyfin -- ls -la /media/movies
kubectl exec -n media -l app=jellyfin -- ls -la /media/shows

# Check if files exist on TrueNAS
# Via TrueNAS shell or file browser:
# ls -la /mnt/master-storage/media-managment/jellyfin/media/movies
# ls -la /mnt/master-storage/media-managment/jellyfin/media/shows

# Trigger library scan in Jellyfin UI
# Dashboard → Libraries → Scan All Libraries
```

**Test NFS connectivity from worker node:**
```bash
# Find which worker node the pod is on
kubectl get pod -n media -l app=jellyfin -o wide

# Test NFS mount from that worker node
# On Talos, use talosctl:
talosctl -n <worker-node-ip> read /proc/mounts | grep nfs
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
# Jellyfin config is stored on TrueNAS at:
# /mnt/master-storage/media-managment/jellyfin/config

# Take a TrueNAS snapshot
# TrueNAS UI → Storage → Datasets → jellyfin/config → Add Snapshot
# Or create automated snapshot task:
# Storage → Periodic Snapshot Tasks → Add
# Dataset: master-storage/media-managment/jellyfin/config
# Schedule: Daily, Keep 7 snapshots
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
- Movies: `/mnt/master-storage/media-managment/jellyfin/media/movies` (shared with Radarr)
- Shows: `/mnt/master-storage/media-managment/jellyfin/media/shows` (shared with Sonarr)
- Downloads: `/mnt/master-storage/media-managment/jellyfin/media/downloads` (shared with qBittorrent)

**Recommended Setup:**
1. qBittorrent downloads to `/media/downloads`
2. Sonarr/Radarr moves completed downloads to `/media/shows` or `/media/movies`
3. Jellyfin scans and adds to library automatically

---

### Related Configuration

- **Namespace:** `media` (shared with Sonarr, Radarr, Prowlarr, qBittorrent)
- **TrueNAS Dataset:** `master-storage/media-managment/jellyfin`
- **Traefik Configuration:** `kubernetes/apps/traefik/`
- **ArgoCD Project:** `media` (if using GitOps)
- **DNS Records:** Managed in Technitium (10.10.5.2, 10.10.5.3)

---

### Next Steps

Once Jellyfin is running:

1. ✅ Configure media libraries in Jellyfin UI
2. ⬜ Deploy qBittorrent for downloads
3. ⬜ Deploy Prowlarr for indexer management
4. ⬜ Deploy Sonarr for TV show management
5. ⬜ Deploy Radarr for movie management
6. ⬜ Configure automation pipeline:
```
   Prowlarr (indexers) → Sonarr/Radarr (management) → 
   qBittorrent (download) → Jellyfin (streaming)
```

---

### Quick Reference

**Access Jellyfin:**
```
URL: http://jellyfin.servers.local
```

**Repository Structure:**
```
kubernetes/apps/jellyfin/
├── readme.md                      # This file
├── jellyfin-config-pv-pvc.yaml   # Config storage (NFS)
├── jellyfin-movies-pv-pvc.yaml   # Movies storage (NFS)
├── jellyfin-shows-pv-pvc.yaml    # Shows storage (NFS)
└── jellyfin-manifest.yaml        # Deployment, Service, IngressRoute
```

**Common Commands:**
```bash
# Check status
kubectl get pods -n media
kubectl get pvc -n media
kubectl get ingressroute -n media

# View logs
kubectl logs -n media -l app=jellyfin -f

# Check NFS mounts
kubectl exec -n media -l app=jellyfin -- df -h | grep nfs

# Restart
kubectl rollout restart deployment/jellyfin -n media

# Access shell
kubectl exec -n media -it deployment/jellyfin -- /bin/bash
```

**TrueNAS Paths:**
```
NFS Server: 10.10.5.40

Config:    /mnt/master-storage/media-managment/jellyfin/config
Movies:    /mnt/master-storage/media-managment/jellyfin/media/movies
Shows:     /mnt/master-storage/media-managment/jellyfin/media/shows
Downloads: /mnt/master-storage/media-managment/jellyfin/media/downloads
```

**Network:**
```
Traefik LoadBalancer: 10.10.5.230
TrueNAS NFS Server:   10.10.5.40
DNS Servers:          10.10.5.2, 10.10.5.3
Kubernetes API:       https://10.10.5.200:6443
```

**PV/PVC Mapping:**
```
jellyfin-config-pv  → jellyfin-config-pvc  → /config (50Gi, RWO)
jellyfin-movies-pv  → jellyfin-movies-pvc  → /media/movies (2Ti, RWX)
jellyfin-shows-pv   → jellyfin-shows-pvc   → /media/shows (2Ti, RWX)
```