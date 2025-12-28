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