## ArgoCD - GitOps Continuous Delivery

### Order of Operations

This section shows where ArgoCD fits in the overall Kubernetes cluster setup process.

**Prerequisites & Setup Order:**

1. ✅ **Talos Linux Cluster** - Base Kubernetes cluster installed
2. ✅ **MetalLB** - Load balancer for bare metal (`kubernetes/apps/metallb/`)
3. ✅ **Traefik** - Ingress controller and reverse proxy (`kubernetes/apps/traefik/`)
4. ✅ **CoreDNS Configuration** - DNS resolution for `.servers.local` domains (`kubernetes/apps/kube-system/coredns-config.yaml`)
5. ✅ **Forgejo** - Self-hosted Git server (`http://forgejo.servers.local:3000`)
6. ✅ **GitHub Mirror** - Forgejo configured to mirror to GitHub (backup)
7. **❌ ArgoCD** - GitOps continuous delivery (YOU ARE HERE)
8. ⬜ **Storage Solutions** - Longhorn, Democratic CSI (can be deployed via ArgoCD)
9. ⬜ **Applications** - Media stack, monitoring, etc. (deployed via ArgoCD)

**Why This Order Matters:**

- **MetalLB** must be installed first to provide LoadBalancer IPs for services
- **Traefik** must be running to provide ingress access to ArgoCD UI (`https://argocd.servers.local`)
- **CoreDNS** must be configured to resolve `.servers.local` domains (required for ArgoCD to access Forgejo)
- **Forgejo** must be accessible for ArgoCD to pull manifests from the Git repository

**Before proceeding, verify these prerequisites:**
```bash
# 1. Check MetalLB is running
kubectl get pods -n metallb-system

# 2. Check Traefik is running and has an external IP
kubectl get svc -n traefik traefik

# 3. Verify CoreDNS configuration
kubectl get configmap coredns -n kube-system

# 4. Test Forgejo is accessible from within the cluster
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- curl -I http://forgejo.servers.local:3000

# 5. Verify DNS resolution works
kubectl run -it --rm debug --image=busybox --restart=Never -- nslookup forgejo.servers.local
```

**If any of these checks fail, do not proceed with ArgoCD installation. Fix the prerequisites first.**

---

### Why ArgoCD?

ArgoCD is a declarative, GitOps continuous delivery tool for Kubernetes. In this homelab, it serves as the **automated deployment engine** that keeps the cluster synchronized with Git.

**Key Benefits:**
- **GitOps Workflow:** Git repository is the single source of truth for cluster state
- **Automated Sync:** Automatically detects changes in Git and applies them to the cluster
- **Self-Healing:** Automatically corrects configuration drift when manual changes are made
- **Rollback:** Easy rollback to any previous Git commit
- **Visibility:** Visual UI showing application health, sync status, and resource topology

**How It Works in This Homelab:**
1. You commit Kubernetes manifests to Forgejo repository
2. ArgoCD detects the changes
3. ArgoCD automatically applies manifests to the cluster
4. Applications are deployed/updated without manual `kubectl apply`

### Installation

ArgoCD is deployed via the manifest located at:
```
kubernetes/apps/argocd/argocd-manifest.yaml
```

#### Apply ArgoCD Installation
```bash
# Apply the ArgoCD manifest
kubectl apply -f kubernetes/apps/argocd/argocd-manifest.yaml

# Or apply directly from Forgejo
kubectl apply -f http://forgejo.servers.local:3000/smokrane/Kubernetes-Homelab/raw/branch/main/kubernetes/apps/argocd/argocd-manifest.yaml
```

#### Verify Installation
```bash
# Check ArgoCD pods are running
kubectl get pods -n argocd

# Expected pods should all be Running:
# argocd-server
# argocd-repo-server
# argocd-application-controller
# argocd-applicationset-controller
# argocd-dex-server
# argocd-redis
# argocd-notifications-controller
```

### Access ArgoCD UI

ArgoCD is accessible via Traefik ingress at:
```
https://argocd.servers.local
```

**Get Initial Admin Password:**
```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d; echo
```

**Login:**
- URL: `https://argocd.servers.local`
- Username: `admin`
- Password: (output from above command)

**⚠️ Change the password immediately after first login!**

### Deploying Applications from Forgejo

#### Step 1: Add Forgejo Repository to ArgoCD Project

Before creating applications, you must grant the ArgoCD project permission to access your Forgejo repository.

1. **Open ArgoCD UI** at `https://argocd.servers.local`
2. **Click Settings** (gear icon ⚙️) → **Projects**
3. **Click on your project** (e.g., `default`, `media`, `infrastructure`)
4. **Scroll to "Source Repositories"** section
5. **Click "+ ADD SOURCE"**
6. **Enter Forgejo repository URL:**
```
   http://forgejo.servers.local:3000/smokrane/Kubernetes-Homelab.git
```
7. **Click "SAVE"**

**Repeat this for all projects that will deploy applications.**

#### Step 2: Create Application in ArgoCD (GUI Method)

**Example: Deploying Jellyfin**

1. **Open ArgoCD UI** at `https://argocd.servers.local`

2. **Click "+ NEW APP"** button (top left)

3. **Fill in Application Details:**

   **GENERAL:**
   - **Application Name:** `jellyfin`
   - **Project Name:** `media` (or `default`)
   - **Sync Policy:** Select `Automatic`
     - ✅ Check **PRUNE RESOURCES** (delete resources when removed from Git)
     - ✅ Check **SELF HEAL** (revert manual changes)

   **SOURCE:**
   - **Repository URL:** `http://forgejo.servers.local:3000/smokrane/Kubernetes-Homelab.git`
   - **Revision:** `main` (or `HEAD`)
   - **Path:** `kubernetes/apps/jellyfin`

   **DESTINATION:**
   - **Cluster URL:** `https://kubernetes.default.svc` (in-cluster)
   - **Namespace:** `media`

   **SYNC OPTIONS:**
   - ✅ Check **AUTO-CREATE NAMESPACE** (if namespace doesn't exist)

4. **Click "CREATE"** at the top

5. **ArgoCD will automatically:**
   - Clone the repository from Forgejo
   - Read manifests from `kubernetes/apps/jellyfin/`
   - Deploy resources to the `media` namespace
   - Begin syncing automatically

6. **Monitor Deployment:**
   - Application card will show sync status
   - Click on the application to see detailed resource tree
   - Status should show **"Synced"** and **"Healthy"**

#### Step 3: Verify Application Deployment
```bash
# Check pods are running
kubectl get pods -n media

# Check application status
kubectl get application jellyfin -n argocd
```

### GitOps Workflow

Once your application is set up in ArgoCD:

1. **Make changes to manifests locally:**
```bash
   vim kubernetes/apps/jellyfin/jellyfin-manifest.yaml
```

2. **Commit and push to Forgejo:**
```bash
   git add .
   git commit -m "Update Jellyfin image version"
   git push origin main
```

3. **ArgoCD automatically deploys:**
   - Detects changes in Forgejo (within 3 minutes)
   - Applies updates to the cluster
   - Updates application status in UI at `https://argocd.servers.local`

**That's it! No manual `kubectl apply` needed.**

### Application Examples

**Common Applications in This Homelab:**

| Application | Project | Path | Namespace |
|------------|---------|------|-----------|
| Jellyfin | media | `kubernetes/apps/jellyfin` | media |
| Sonarr | media | `kubernetes/apps/sonarr` | media |
| Radarr | media | `kubernetes/apps/radarr` | media |
| Prowlarr | media | `kubernetes/apps/prowlarr` | media |
| qBittorrent | media | `kubernetes/apps/qbittorrent` | media |
| Traefik | infrastructure | `kubernetes/apps/traefik` | traefik |
| Longhorn | infrastructure | `kubernetes/apps/longhorn` | longhorn-system |

Use the same process above to deploy any of these applications - just change the application name, path, and namespace accordingly.

### Troubleshooting

**"Application repo is not permitted in project"**
- You forgot to add Forgejo repository to the project
- Go to: Settings → Projects → [Your Project] → Source Repositories
- Add: `http://forgejo.servers.local:3000/smokrane/Kubernetes-Homelab.git`

**"Repository not accessible"**
- Ensure CoreDNS is configured for `.servers.local` domains
- Verify Forgejo is running: `kubectl get pods -n forgejo`
- Check repo-server logs: `kubectl logs -n argocd deployment/argocd-repo-server`

**Application stuck "Progressing"**
- Click "REFRESH" button in ArgoCD UI
- Check pod status: `kubectl get pods -n <namespace>`
- View application events in ArgoCD UI

**Can't access https://argocd.servers.local**
- Verify Traefik is running: `kubectl get pods -n traefik`
- Check DNS resolves: `nslookup argocd.servers.local`
- Check ingress: `kubectl get ingress -n argocd`

### Related Configuration

- **ArgoCD Manifest:** `kubernetes/apps/argocd/argocd-manifest.yaml`
- **ArgoCD UI:** `https://argocd.servers.local`
- **Git Repository:** `http://forgejo.servers.local:3000/smokrane/Kubernetes-Homelab`
- **CoreDNS Configuration:** `kubernetes/apps/kube-system/coredns-config.yaml`
- **Traefik Ingress:** `kubernetes/apps/traefik/`