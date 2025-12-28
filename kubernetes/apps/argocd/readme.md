## ArgoCD - GitOps Continuous Delivery

### Why ArgoCD?

ArgoCD is a declarative, GitOps continuous delivery tool for Kubernetes. In this homelab, it serves as the **automated deployment engine** that keeps the cluster synchronized with Git.

**Key Benefits:**
- **GitOps Workflow:** Git repository is the single source of truth for cluster state
- **Automated Sync:** Automatically detects changes in Git and applies them to the cluster
- **Self-Healing:** Automatically corrects configuration drift when manual changes are made
- **Rollback:** Easy rollback to any previous Git commit
- **Visibility:** Visual UI showing application health, sync status, and resource topology
- **Multi-Environment:** Manage dev, staging, and production from a single interface

**How It Works in This Homelab:**
1. You commit Kubernetes manifests to Forgejo repository
2. ArgoCD detects the changes
3. ArgoCD automatically applies manifests to the cluster
4. Applications are deployed/updated without manual `kubectl apply`
5. ArgoCD continuously monitors and ensures cluster matches Git state

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
# Check ArgoCD namespace was created
kubectl get namespace argocd

# Check ArgoCD pods are running
kubectl get pods -n argocd

# Expected pods:
# argocd-server
# argocd-repo-server
# argocd-application-controller
# argocd-applicationset-controller
# argocd-dex-server
# argocd-redis
# argocd-notifications-controller
```

#### Access ArgoCD UI

**Option 1: Port Forward (Quick Access)**
```bash
kubectl port-forward svc/argocd-server -n argocd 8080:443
```
Then open: https://localhost:8080

**Option 2: Ingress (Recommended for Homelab)**
Access via configured ingress URL (e.g., https://argocd.servers.local)

#### Get Initial Admin Password
```bash
# Retrieve the initial password
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d; echo
```

**Login:**
- Username: `admin`
- Password: (output from above command)

**⚠️ Change the password immediately after first login!**

### Deployed Applications

This homelab uses ArgoCD to manage the following applications:

**Media Server Stack:**
- **Jellyfin** - Media streaming server (`kubernetes/apps/jellyfin/`)
- **Sonarr** - TV show management (`kubernetes/apps/sonarr/`)
- **Radarr** - Movie management (`kubernetes/apps/radarr/`)
- **Prowlarr** - Indexer manager (`kubernetes/apps/prowlarr/`)
- **qBittorrent** - Torrent client (`kubernetes/apps/qbittorrent/`)

**Reverse Proxy & Networking:**
- **Traefik** - Ingress controller and reverse proxy (`kubernetes/apps/traefik/`)
- **NGINX** - Web server (`kubernetes/apps/nginx/manifest/`)

**Infrastructure:**
- **CoreDNS Config** - DNS resolution for `.servers.local` domains (`kubernetes/apps/kube-system/`)
- **MetalLB** - Bare metal load balancer (`kubernetes/apps/metallb/`)
- **Metrics Server** - Resource metrics (`kubernetes/apps/metrics-server/`)
- **Longhorn** - Distributed block storage (`kubernetes/apps/longhorn/`)
- **Democratic CSI** - NFS storage provisioner (`kubernetes/apps/democratic-csi/`)

**Utilities:**
- **Unpackerr** - Automatic extraction of downloads (`kubernetes/apps/unpackerr/`)

### Configuration

#### Project Setup

ArgoCD uses **Projects** for access control and logical grouping. Each project needs permission to access your Git repositories.

**Add Forgejo Repository to a Project (GUI):**

1. ArgoCD UI → Settings (gear icon) → Projects
2. Select your project (e.g., `media`, `default`, `infrastructure`)
3. Scroll to "Source Repositories" section
4. Click "+ ADD SOURCE"
5. Enter: `http://forgejo.servers.local:3000/smokrane/Kubernetes-Homelab.git`
6. Click "SAVE"

**Common Projects in This Homelab:**
- `default` - Default ArgoCD project for general applications
- `media` - Media server applications (Jellyfin, Sonarr, Radarr, etc.)
- `infrastructure` - Core cluster services (Traefik, MetalLB, Longhorn, etc.)
- `argocd` - ArgoCD itself (if managing ArgoCD with ArgoCD)

#### Application Setup

Applications tell ArgoCD **what** to deploy and **where** to find the manifests.

**Example Application for Jellyfin:**
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

**Example Application for Traefik:**
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: traefik
  namespace: argocd
spec:
  project: infrastructure
  source:
    repoURL: http://forgejo.servers.local:3000/smokrane/Kubernetes-Homelab.git
    targetRevision: main
    path: kubernetes/apps/traefik
  destination:
    server: https://kubernetes.default.svc
    namespace: traefik
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
```

### Automated Sync vs Manual Sync

**Automated Sync** (Recommended for Homelab):
```yaml
syncPolicy:
  automated:
    prune: true      # Delete resources removed from Git
    selfHeal: true   # Revert manual changes
```
- ArgoCD automatically syncs changes from Git
- Cluster stays in sync with repository without manual intervention
- Self-healing prevents configuration drift

**Manual Sync:**
```yaml
syncPolicy: {}
```
- You must click "SYNC" in the UI or use CLI to deploy changes
- Useful for controlled deployments in production environments

### GitOps Workflow

**Standard Development Flow:**

1. **Make changes locally:**
```bash
   # Edit manifest files
   vim kubernetes/apps/jellyfin/jellyfin-manifest.yaml
```

2. **Commit and push to Forgejo:**
```bash
   git add .
   git commit -m "Update Jellyfin resource limits"
   git push origin main
```

3. **ArgoCD automatically deploys:**
   - Detects the change in Forgejo (polls every 3 minutes by default)
   - Compares cluster state with Git
   - Applies the changes
   - Updates application status in UI

4. **Verify in ArgoCD UI:**
   - Application shows "Synced" and "Healthy"
   - Changes are live in cluster

5. **GitHub mirror updated:**
   - Forgejo automatically mirrors to GitHub (every 8 hours)
   - GitHub serves as automatic backup

**That's it! No manual `kubectl apply` needed.**

### Monitoring and Troubleshooting

#### Check Application Status
```bash
# List all applications
kubectl get applications -n argocd

# Get details about specific application
kubectl describe application jellyfin -n argocd

# Check application status via ArgoCD CLI
argocd app list
argocd app get jellyfin
```

#### Common Issues and Solutions

**"Application repo is not permitted in project"**
- Add the Forgejo repository to the project's source repositories
- ArgoCD UI → Settings → Projects → [Your Project] → Source Repositories → Add Source
- Add: `http://forgejo.servers.local:3000/smokrane/Kubernetes-Homelab.git`

**"repository not accessible" or "failed to get repo"**
- Ensure CoreDNS is configured for `.servers.local` domains (see CoreDNS section)
- Verify Forgejo is running: `curl http://forgejo.servers.local:3000`
- Check argocd-repo-server logs: `kubectl logs -n argocd deployment/argocd-repo-server`
- Test DNS resolution from within cluster:
```bash
  kubectl run -it --rm debug --image=busybox --restart=Never -- nslookup forgejo.servers.local
```

**Application stuck in "Progressing" state**
- Click "REFRESH" in UI to force check
- Manually sync: Click "SYNC" → "SYNCHRONIZE"
- Check pod status: `kubectl get pods -n <namespace>`
- Review application events: `kubectl describe application <app-name> -n argocd`

**"OutOfSync" status**
- Someone made manual changes to the cluster (not through Git)
- If selfHeal is enabled, ArgoCD will auto-revert to Git state
- Otherwise, click "SYNC" to align cluster with Git
- Best practice: Always commit changes to Git, never use `kubectl apply` directly

**ApplicationSet Controller CrashLoopBackOff**
- Check logs: `kubectl logs -n argocd deployment/argocd-applicationset-controller`
- This component manages ApplicationSets (advanced feature)
- If not using ApplicationSets, crashes may be ignorable
- Restart deployment: `kubectl rollout restart deployment/argocd-applicationset-controller -n argocd`

#### View Logs
```bash
# ArgoCD application controller
kubectl logs -n argocd deployment/argocd-application-controller

# ArgoCD repo server (Git sync issues)
kubectl logs -n argocd deployment/argocd-repo-server

# ArgoCD server (UI/API issues)
kubectl logs -n argocd deployment/argocd-server

# ArgoCD applicationset controller
kubectl logs -n argocd deployment/argocd-applicationset-controller
```

### Best Practices

1. **Use Automated Sync:** Let ArgoCD handle deployments automatically
2. **Enable Self-Heal:** Prevent configuration drift from manual changes
3. **Enable Prune:** Clean up deleted resources automatically
4. **Use Projects:** Organize applications by purpose (media, infrastructure, etc.)
5. **Never `kubectl apply` directly:** Always commit changes to Git instead
6. **Monitor Sync Status:** Regularly check ArgoCD UI for application health
7. **Use Namespace Isolation:** Deploy applications to dedicated namespaces
8. **Document READMEs:** Each application directory should have a readme.md explaining its purpose
9. **Use Consistent Naming:** Follow naming convention: `<app-name>-manifest.yaml`

### Related Configuration

- **ArgoCD Manifest:** `kubernetes/apps/argocd/argocd-manifest.yaml`
- **Git Repository (Primary):** Forgejo at `http://forgejo.servers.local:3000/smokrane/Kubernetes-Homelab`
- **Git Repository (Mirror):** GitHub at `https://github.com/Tech-by-Sean/Kubernetes-Homelab`
- **CoreDNS Configuration:** `kubernetes/apps/kube-system/coredns-config.yaml` (required for `.servers.local` resolution)
- **Application Manifests:** Located in `kubernetes/apps/*/` directories
- **Application READMEs:** Individual readme.md files in each app directory

### Application Directory Structure

Each application follows this structure:
```
kubernetes/apps/<app-name>/
├── <app-name>-manifest.yaml    # Main deployment manifest
├── <app-name>-config-pv-pvc.yaml  # Config storage (if needed)
├── <app-name>-data-pv-pvc.yaml    # Data storage (if needed)
└── readme.md                      # Application documentation
```

**Examples:**
- `kubernetes/apps/jellyfin/jellyfin-manifest.yaml`
- `kubernetes/apps/traefik/traefik-deployment.yaml`
- `kubernetes/apps/qbittorrent/qbittorrent-manifest.yaml`

---

## ArgoCD Project Permissions Configuration

### Why This Is Needed

ArgoCD uses **Projects** to provide logical grouping and access control for applications. Each project has a whitelist of allowed Git repositories. When you migrate from GitHub to Forgejo (or add any new Git repository), you must grant the project permission to use the new repository URL.

**Without this configuration:**
- Applications will fail with error: `application repo <url> is not permitted in project '<project-name>'`
- You cannot create or update applications to point to new repositories
- ArgoCD will reject any manifests from non-whitelisted repos

### Adding Repository to Project (GUI Method)

#### Step 1: Access Project Settings

1. **Log into ArgoCD UI** (e.g., `https://argocd.servers.local` or via port-forward)

2. **Click on "Settings"** (gear icon ⚙️) in the left sidebar

3. **Click "Projects"**

4. **Find and click on your project** 
   - Common projects: `default`, `media`, `infrastructure`, `argocd`

#### Step 2: Add Source Repository

1. **Scroll down to "Source Repositories"** section

2. **Click the "+ ADD SOURCE" button**

3. **Enter your Forgejo repository URL:**
```
   http://forgejo.servers.local:3000/smokrane/Kubernetes-Homelab.git
```

4. **Click "SAVE"**

#### Step 3: Verify the Configuration

The "Source Repositories" section should now show:
```
Source Repositories:
┌─────────────────────────────────────────────────────────────────────┐
│ http://forgejo.servers.local:3000/smokrane/Kubernetes-Homelab.git  │
│ https://github.com/Tech-by-Sean/Kubernetes-Homelab.git             │
└─────────────────────────────────────────────────────────────────────┘
```

**Note:** Keep both repositories listed if you want flexibility to use either Forgejo (primary) or GitHub (backup mirror).

#### Step 4: Update Applications to Use Forgejo

1. **Go to "Applications"** in the left sidebar

2. **Click on an application** you want to update (e.g., `jellyfin`)

3. **Click "APP DETAILS"** at the top

4. **Click "EDIT"** button

5. **Update the "REPO URL"** field from:
```
   https://github.com/Tech-by-Sean/Kubernetes-Homelab.git
```
   To:
```
   http://forgejo.servers.local:3000/smokrane/Kubernetes-Homelab.git
```

6. **Click "SAVE"**

7. **Click "REFRESH"** to force ArgoCD to check the new repository

8. The application should now sync successfully from Forgejo

### Updating Multiple Applications

If you have many applications to update from GitHub to Forgejo:

**Option 1: GUI (Repetitive but Safe)**
- Repeat Step 4 above for each application

**Option 2: Edit Application Manifests (Bulk Update)**
```bash
# Use find/replace in your manifests
find kubernetes/apps -name "*-manifest.yaml" -type f \
  -exec sed -i 's|https://github.com/Tech-by-Sean/Kubernetes-Homelab.git|http://forgejo.servers.local:3000/smokrane/Kubernetes-Homelab.git|g' {} +

# Commit and push changes
git add .
git commit -m "Migrate all ArgoCD apps from GitHub to Forgejo"
git push origin main

# ArgoCD will automatically update applications
```

**Option 3: ArgoCD CLI (Advanced)**
```bash
# List all applications
argocd app list

# Update a specific application
argocd app set jellyfin \
  --repo http://forgejo.servers.local:3000/smokrane/Kubernetes-Homelab.git

# Sync the application
argocd app sync jellyfin
```

### Projects to Update

Make sure to add the Forgejo repository to **all projects** that deploy applications:

- ✅ `default` - Default project for general applications
- ✅ `media` - Jellyfin, Sonarr, Radarr, Prowlarr, qBittorrent, Unpackerr
- ✅ `infrastructure` - Traefik, MetalLB, Longhorn, Democratic CSI, NGINX
- ✅ `argocd` - ArgoCD self-management (if applicable)

### Verification Checklist

After updating repository permissions:

- [ ] Project shows Forgejo URL in "Source Repositories"
- [ ] Applications updated to use Forgejo repository URL
- [ ] Applications show "Synced" status (not "OutOfSync")
- [ ] Applications show "Healthy" status (not "Degraded")
- [ ] No errors in application details: `kubectl describe application <app> -n argocd`
- [ ] ArgoCD can fetch from Forgejo: Check repo-server logs

**Test the GitOps flow:**
```bash
# Make a small change to a manifest
echo "# Test change" >> kubernetes/apps/jellyfin/readme.md

# Commit and push
git add .
git commit -m "Test ArgoCD sync from Forgejo"
git push origin main

# Watch ArgoCD detect and sync (within 3 minutes)
argocd app get jellyfin --refresh
```

### Troubleshooting

**Error: "repository not accessible"**
- Ensure CoreDNS is configured for `.servers.local` domains (see CoreDNS Configuration section)
- Verify ArgoCD repo-server can reach Forgejo:
```bash
  kubectl exec -n argocd deployment/argocd-repo-server -- curl -I http://forgejo.servers.local:3000
```
- Check that Forgejo is running: `kubectl get pods -n forgejo`
- Check Forgejo service: `kubectl get svc -n forgejo`

**Error: "application repo is not permitted in project"**
- You missed adding the Forgejo repo to the project's source repositories
- Double-check the exact URL matches (http vs https, port number, trailing `.git`)
- Verify in UI: Settings → Projects → [Project Name] → Source Repositories

**Changes not taking effect:**
- Clear browser cache and refresh
- Log out and back into ArgoCD
- Force refresh the application: Click "REFRESH" button
- Restart ArgoCD components if necessary:
```bash
  kubectl rollout restart deployment argocd-server -n argocd
  kubectl rollout restart deployment argocd-repo-server -n argocd
```

**Application shows "Unknown" health status:**
- This is normal immediately after changing repository URL
- Click "REFRESH" to force health check
- Wait 1-2 minutes for ArgoCD to re-evaluate
- If persists, check pod status: `kubectl get pods -n <namespace>`