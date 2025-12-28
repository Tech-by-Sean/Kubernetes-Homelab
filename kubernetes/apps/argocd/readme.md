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

ArgoCD is deployed via Kubernetes manifests located in:
```
kubernetes/apps/argocd/
```

#### Deployment Structure
```
kubernetes/apps/argocd/
├── namespace.yaml           # ArgoCD namespace
├── install.yaml             # ArgoCD core installation
├── argocd-cmd-params.yaml   # Configuration parameters
└── ingress.yaml             # Traefik ingress (optional)
```

#### Apply ArgoCD Installation
```bash
# From the repository root
kubectl apply -f kubernetes/apps/argocd/namespace.yaml
kubectl apply -f kubernetes/apps/argocd/install.yaml
kubectl apply -f kubernetes/apps/argocd/argocd-cmd-params.yaml

# Optional: If using Traefik ingress
kubectl apply -f kubernetes/apps/argocd/ingress.yaml
```

#### Verify Installation
```bash
# Check ArgoCD pods are running
kubectl get pods -n argocd

# Expected output:
# argocd-server
# argocd-repo-server
# argocd-application-controller
# argocd-dex-server
# argocd-redis
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

### Configuration

#### Project Setup

ArgoCD uses **Projects** for access control and logical grouping. Each project needs permission to access your Git repositories.

**Add Forgejo Repository to a Project (GUI):**

1. ArgoCD UI → Settings → Projects
2. Select your project (e.g., `media`, `default`)
3. Scroll to "Source Repositories"
4. Click "+ ADD SOURCE"
5. Add: `http://forgejo.servers.local:3000/smokrane/Kubernetes-Homelab.git`
6. Click "SAVE"

See **ArgoCD Project Permissions Configuration** section below for detailed steps.

#### Application Setup

Applications tell ArgoCD **what** to deploy and **where** to find the manifests.

**Example Application Manifest:**
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
    targetRevision: HEAD
    path: kubernetes/apps/media/jellyfin
  destination:
    server: https://kubernetes.default.svc
    namespace: media
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

### Automated Sync vs Manual Sync

**Automated Sync** (Recommended):
```yaml
syncPolicy:
  automated:
    prune: true      # Delete resources removed from Git
    selfHeal: true   # Revert manual changes
```
- ArgoCD automatically syncs changes from Git
- Cluster stays in sync with repository without manual intervention

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
   vim kubernetes/apps/media/jellyfin/deployment.yaml
```

2. **Commit and push to Forgejo:**
```bash
   git add .
   git commit -m "Update Jellyfin to v10.9.0"
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

**That's it! No manual `kubectl apply` needed.**

### Monitoring and Troubleshooting

#### Check Application Status
```bash
# List all applications
kubectl get applications -n argocd

# Get details about specific application
kubectl describe application jellyfin -n argocd
```

#### Common Issues and Solutions

**"Application repo is not permitted in project"**
- Add the repository to the project's source repositories (see Configuration section above)

**"repository not accessible"**
- Ensure CoreDNS is configured for `.servers.local` domains (see CoreDNS section)
- Verify Forgejo is running: `curl http://forgejo.servers.local:3000`
- Check argocd-repo-server logs: `kubectl logs -n argocd deployment/argocd-repo-server`

**Application stuck in "Progressing" state**
- Click "REFRESH" in UI to force check
- Manually sync: Click "SYNC" → "SYNCHRONIZE"
- Check pod status: `kubectl get pods -n <namespace>`

**"OutOfSync" status**
- Someone made manual changes to the cluster
- If selfHeal is enabled, ArgoCD will auto-revert
- Otherwise, click "SYNC" to align with Git

#### View Logs
```bash
# ArgoCD application controller
kubectl logs -n argocd deployment/argocd-application-controller

# ArgoCD repo server (Git sync issues)
kubectl logs -n argocd deployment/argocd-repo-server

# ArgoCD server (UI/API issues)
kubectl logs -n argocd deployment/argocd-server
```

### Best Practices

1. **Use Automated Sync:** Let ArgoCD handle deployments automatically
2. **Enable Self-Heal:** Prevent configuration drift from manual changes
3. **Enable Prune:** Clean up deleted resources automatically
4. **Use Projects:** Organize applications by purpose (media, infrastructure, etc.)
5. **Never `kubectl apply` directly:** Always commit changes to Git instead
6. **Monitor Sync Status:** Regularly check ArgoCD UI for application health
7. **Use Namespace Isolation:** Deploy applications to dedicated namespaces

### Related Configuration

- **Git Repository:** Forgejo at `http://forgejo.servers.local:3000`
- **CoreDNS:** Required for resolving `.servers.local` domains (see CoreDNS section)
- **Application Manifests:** Located in `kubernetes/apps/*/` directories
- **GitHub Mirror:** Automatic backup to GitHub (every 8 hours)

---

## ArgoCD Project Permissions Configuration

[... insert the GUI-focused project permissions section from previous response ...]