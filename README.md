# Kubernetes-Homelab
My Kubernetes home lab



## CoreDNS Configuration for External DNS Resolution

### Why This Is Needed

By default, CoreDNS in Kubernetes only resolves internal cluster DNS (`.cluster.local`) and forwards everything else to the node's DNS resolver. However, our on-premises services use `.local` domains (like `forgejo.servers.local`) which may not be properly resolved from within pods.

This configuration allows Kubernetes pods to resolve `.servers.local` domains by forwarding those queries to our Technitium DNS servers.

**Without this configuration:**
- ArgoCD cannot connect to `forgejo.servers.local`
- Pods cannot communicate with on-prem services using `.local` domains
- You'd need to use IP addresses instead of hostnames (not ideal for GitOps)

### Configuration

The CoreDNS ConfigMap is located at `kubernetes/apps/kube-system/coredns-config.yaml`

It forwards `.servers.local` DNS queries to our Technitium DNS servers at:
- Primary: `10.10.5.2`
- Secondary: `10.10.5.3`

### How to Apply

1. **Apply the ConfigMap:**
```bash
   kubectl apply -f kubernetes/apps/kube-system/coredns-config.yaml
```

2. **Restart CoreDNS to pick up changes:**
```bash
   kubectl rollout restart deployment coredns -n kube-system
```

3. **Verify CoreDNS pods are running:**
```bash
   kubectl get pods -n kube-system -l k8s-app=kube-dns
```

### Testing DNS Resolution

Test that pods can resolve `.servers.local` domains:
```bash
# Quick test
kubectl run test-dns --image=busybox -it --rm -- nslookup forgejo.servers.local

# Expected output should show:
# Server:    10.96.0.10
# Address:   10.96.0.10:53
# Name:      forgejo.servers.local
# Address:   <forgejo-ip-address>
```

### Troubleshooting

**If DNS resolution fails:**

1. Check CoreDNS logs:
```bash
   kubectl logs -n kube-system -l k8s-app=kube-dns
```

2. Verify Technitium DNS servers are reachable from cluster nodes:
```bash
   # From a node
   nslookup forgejo.servers.local 10.10.5.2
```

3. Verify the ConfigMap was applied:
```bash
   kubectl get configmap coredns -n kube-system -o yaml
```

**If you need to update DNS servers:**

Edit `kubernetes/apps/kube-system/coredns-config.yaml` and update the `forward` line:
```yaml
forward . 10.10.5.2 10.10.5.3
```

Then reapply and restart CoreDNS as shown above.

### Related Configuration

This DNS configuration is required for:
- ArgoCD to access Forgejo at `forgejo.servers.local:3000`
- Any applications that need to communicate with on-prem services
- GitOps workflows using local DNS names instead of IP addresses



## ArgoCD Project Permissions Configuration

### Why This Is Needed

ArgoCD uses **Projects** to provide logical grouping and access control for applications. Each project has a whitelist of allowed Git repositories. When you migrate from GitHub to Forgejo (or add any new Git repository), you must grant the project permission to use the new repository URL.

**Without this configuration:**
- Applications will fail with error: `application repo <url> is not permitted in project '<project-name>'`
- You cannot update applications to point to new repositories
- ArgoCD will reject any manifests from non-whitelisted repos

### Adding Repository to Project (GUI Method)

#### Step 1: Access Project Settings

1. **Log into ArgoCD UI** (usually at `https://argocd.yourdomain.com`)

2. **Click on "Settings"** (gear icon) in the left sidebar

3. **Click "Projects"**

4. **Find and click on your project** (e.g., `media`, `default`, etc.)

#### Step 2: Add Source Repository

1. **Scroll down to "Source Repositories"** section

2. **Click the "+ ADD SOURCE" button**

3. **Enter your Forgejo repository URL:**
```
   http://forgejo.servers.local:3000/smokrane/Kubernetes-Homelab.git
```

4. **Click "SAVE"**

#### Step 3: Verify and Update Applications

1. **Go to "Applications"** in the left sidebar

2. **Click on an application** you want to update (e.g., `jellyfin`)

3. **Click "EDIT"** or the "PARAMETERS" tab

4. **Update the "REPO URL"** field to:
```
   http://forgejo.servers.local:3000/smokrane/Kubernetes-Homelab.git
```

5. **Click "SAVE"**

6. The application should now sync successfully from Forgejo

### Screenshots Reference

The Project Settings page should show:
```
Source Repositories:
┌─────────────────────────────────────────────────────────────────────┐
│ http://forgejo.servers.local:3000/smokrane/Kubernetes-Homelab.git  │
│ https://github.com/Tech-by-Sean/Kubernetes-Homelab.git             │
└─────────────────────────────────────────────────────────────────────┘
```

### Updating Multiple Applications

If you have many applications to update:

1. **Repeat Step 3 for each application**, OR

2. **Use the bulk update approach:**
   - Export application manifests
   - Use find/replace to change GitHub URLs to Forgejo URLs
   - Reapply manifests

### Common Projects to Update

Typical projects in a homelab setup:
- `default` - Default ArgoCD project
- `media` - Media applications (Jellyfin, Sonarr, Radarr, etc.)
- `argocd` - ArgoCD itself (if self-managed)
- `infrastructure` - Core services (Traefik, MetalLB, etc.)

**Make sure to update permissions for ALL projects that use your Git repository!**

### Verification

After updating, verify the configuration:

1. **Check Project Details:**
   - Settings → Projects → [Your Project]
   - Confirm Forgejo URL is in "Source Repositories"

2. **Test Application Sync:**
   - Applications → [Your App] → "REFRESH" or "SYNC"
   - Should sync successfully without permission errors

3. **Check Application Status:**
   - Application should show "Healthy" and "Synced" status
   - No errors related to repository access

### Troubleshooting

**Error: "repository not accessible"**
- Ensure CoreDNS is configured (see CoreDNS section above)
- Verify ArgoCD repo-server can reach Forgejo
- Check that Forgejo is running and accessible

**Error: "application repo is not permitted"**
- You missed adding the repo to the project's source repositories
- Double-check the URL exactly matches (http vs https, trailing .git, etc.)

**Changes not taking effect:**
- Try refreshing the browser
- Log out and back into ArgoCD
- Restart ArgoCD pods if necessary:
```bash
  kubectl rollout restart deployment argocd-server -n argocd
```