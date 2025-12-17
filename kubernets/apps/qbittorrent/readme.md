# qBittorrent + Gluetun VPN Deployment Guide for Kubernetes

This guide covers deploying qBittorrent with Gluetun VPN sidecar on a Kubernetes cluster (Talos Linux) with TrueNAS NFS storage and Traefik ingress.

## Overview

**What is a sidecar?**
A sidecar is when multiple containers run in the same pod, sharing network and storage. In this setup:
- **Gluetun** creates a VPN tunnel and handles all networking
- **qBittorrent** routes all traffic through Gluetun's tunnel

This ensures all torrent traffic is anonymous. If the VPN drops, qBittorrent loses internet access (built-in kill switch).

```
Pod: qbittorrent
├── Container: gluetun     ← Creates VPN tunnel (Mullvad/WireGuard)
└── Container: qbittorrent ← All traffic forced through VPN
```

## Prerequisites

- Kubernetes cluster with Traefik ingress
- TrueNAS with NFS shares configured
- Mullvad VPN account (or other supported VPN)
- `media` namespace exists (created by Jellyfin manifest)

---

## Step 1: TrueNAS Setup

### 1.1 Create Datasets

Create these datasets in TrueNAS:

| Dataset | Purpose |
|---------|---------|
| `media-managment/qbittorrent/config` | qBittorrent configuration |
| `media-managment/media/downloads` | Downloaded files |

### 1.2 Create NFS Shares

For each dataset:
1. Go to **Shares** → **NFS** → **Add**
2. Set the path (e.g., `/mnt/master-storage/media-managment/qbittorrent/config`)
3. Maproot User: `root`
4. Maproot Group: `root`
5. Save

### 1.3 Set Permissions

For each dataset:
1. Go to **Datasets** → Select dataset
2. Edit Permissions:
   - Owner: `root`
   - Group: `root`
   - Mode: `0777`
   - Apply recursively
3. Save

---

## Step 2: Get Mullvad VPN Credentials

1. Log into [mullvad.net](https://mullvad.net)
2. Go to **Account** → **WireGuard configuration**
3. Generate a new key (or use existing)
4. Note down:
   - **Private key** (long base64 string)
   - **IPv4 address** (e.g., `10.66.212.225/32`)

---

## Step 3: Create Kubernetes Secret

Store your Mullvad private key securely:

```bash
kubectl create secret generic mullvad-vpn -n media \
  --from-literal=private-key=YOUR_WIREGUARD_PRIVATE_KEY
```

Replace `YOUR_WIREGUARD_PRIVATE_KEY` with your actual private key.

**Verify:**
```bash
kubectl get secret mullvad-vpn -n media
```

---

## Step 4: Storage Manifests

### 4.1 Config Storage

```yaml
# apps/qbittorrent/qbittorrent-config-pv-pvc.yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: qbittorrent-config-pv
spec:
  capacity:
    storage: 1Gi
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: ""
  nfs:
    server: 10.10.5.40
    path: /mnt/master-storage/media-managment/qbittorrent/config
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: qbittorrent-config
  namespace: media
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: ""
  volumeName: qbittorrent-config-pv
  resources:
    requests:
      storage: 1Gi
```

### 4.2 Downloads Storage

```yaml
# apps/qbittorrent/qbittorrent-downloads-pv-pvc.yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: qbittorrent-downloads-pv
spec:
  capacity:
    storage: 1Ti
  accessModes:
    - ReadWriteMany
  persistentVolumeReclaimPolicy: Retain
  storageClassName: ""
  nfs:
    server: 10.10.5.40
    path: /mnt/master-storage/media-managment/media/downloads
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: qbittorrent-downloads
  namespace: media
spec:
  accessModes:
    - ReadWriteMany
  storageClassName: ""
  volumeName: qbittorrent-downloads-pv
  resources:
    requests:
      storage: 1Ti
```

---

## Step 5: qBittorrent + Gluetun Manifest

```yaml
# apps/qbittorrent/qbittorrent-manifest.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: qbittorrent
  namespace: media
spec:
  replicas: 1
  selector:
    matchLabels:
      app: qbittorrent
  template:
    metadata:
      labels:
        app: qbittorrent
    spec:
      containers:
        # Gluetun VPN Container
        - name: gluetun
          image: qmcgaw/gluetun:latest
          securityContext:
            capabilities:
              add:
                - NET_ADMIN  # Required for VPN tunnel
          env:
            - name: VPN_SERVICE_PROVIDER
              value: "mullvad"
            - name: VPN_TYPE
              value: "wireguard"
            - name: WIREGUARD_PRIVATE_KEY
              valueFrom:
                secretKeyRef:
                  name: mullvad-vpn
                  key: private-key
            - name: WIREGUARD_ADDRESSES
              value: "10.66.212.225/32"  # Replace with your Mullvad address
            - name: SERVER_COUNTRIES
              value: "USA"  # Change to preferred country
            - name: FIREWALL_INPUT_PORTS
              value: "8080"  # Allow WebUI access
            - name: FIREWALL_OUTBOUND_SUBNETS
              value: "10.0.0.0/8"  # Allow access to local network/NFS
          ports:
            - containerPort: 8080
              name: webui
          volumeMounts:
            - name: gluetun-data
              mountPath: /gluetun
        
        # qBittorrent Container
        - name: qbittorrent
          image: linuxserver/qbittorrent:latest
          env:
            - name: PUID
              value: "1000"
            - name: PGID
              value: "1000"
            - name: TZ
              value: "America/New_York"  # Change to your timezone
            - name: WEBUI_PORT
              value: "8080"
          volumeMounts:
            - name: config
              mountPath: /config
            - name: downloads
              mountPath: /downloads
          resources:
            limits:
              memory: "2Gi"
              cpu: "1000m"
            requests:
              memory: "512Mi"
              cpu: "250m"
      
      volumes:
        - name: config
          persistentVolumeClaim:
            claimName: qbittorrent-config
        - name: downloads
          persistentVolumeClaim:
            claimName: qbittorrent-downloads
        - name: gluetun-data
          emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: qbittorrent
  namespace: media
spec:
  selector:
    app: qbittorrent
  ports:
    - port: 8080
      targetPort: 8080
  type: ClusterIP
---
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: qbittorrent
  namespace: media
spec:
  entryPoints:
    - web
  routes:
    - match: Host(`qbit.servers.local`)
      kind: Rule
      services:
        - name: qbittorrent
          port: 8080
```

---

## Step 6: Deploy

Apply manifests in order:

```bash
# Create the secret first (if not done already)
kubectl create secret generic mullvad-vpn -n media \
  --from-literal=private-key=YOUR_WIREGUARD_PRIVATE_KEY

# Apply storage
kubectl apply -f apps/qbittorrent/qbittorrent-config-pv-pvc.yaml
kubectl apply -f apps/qbittorrent/qbittorrent-downloads-pv-pvc.yaml

# Apply deployment
kubectl apply -f apps/qbittorrent/qbittorrent-manifest.yaml
```

---

## Step 7: DNS Configuration

Add A record in your DNS server (Technitium):

| Hostname | IP Address |
|----------|------------|
| qbit.servers.local | 10.10.5.230 |

The IP is Traefik's LoadBalancer IP:
```bash
kubectl get svc -n traefik
```

---

## Step 8: Verify Deployment

### 8.1 Check Pod Status

```bash
kubectl get pods -n media -l app=qbittorrent
```

Expected output:
```
NAME                           READY   STATUS    RESTARTS   AGE
qbittorrent-xxxxxxxxx-xxxxx   2/2     Running   0          5m
```

`2/2` means both containers (gluetun and qbittorrent) are running.

### 8.2 Check Gluetun VPN Connection

```bash
kubectl logs -n media -l app=qbittorrent -c gluetun | tail -20
```

Look for:
```
INFO [vpn] starting
INFO [wireguard] Connecting to x.x.x.x:51820
INFO [ip getter] Public IP address is x.x.x.x (Country, Region, City)
```

### 8.3 Check qBittorrent Logs

```bash
kubectl logs -n media -l app=qbittorrent -c qbittorrent | head -20
```

Look for the temporary password:
```
The WebUI administrator password was not set. A temporary password is provided for this session: XXXXXXXX
```

### 8.4 Test Internal Connectivity

```bash
kubectl run curl-test --image=curlimages/curl --rm -it --restart=Never \
  -- curl -s http://qbittorrent.media.svc.cluster.local:8080 | head -5
```

---

## Step 9: Access qBittorrent

1. Open browser: `http://qbit.servers.local`
2. Login:
   - Username: `admin`
   - Password: (from logs above)
3. Change password: **Tools** → **Options** → **Web UI** → **Authentication**

---

## Step 10: Verify VPN is Working

### Method 1: Check Public IP in Gluetun Logs

```bash
kubectl logs -n media -l app=qbittorrent -c gluetun | grep "Public IP"
```

Should show Mullvad's IP, not your real IP.

### Method 2: From qBittorrent Container

```bash
kubectl exec -n media -l app=qbittorrent -c qbittorrent -- curl -s ifconfig.me
```

Should return VPN IP address.

---

## Gluetun Configuration Options

### Change VPN Server Country

Edit `SERVER_COUNTRIES` in the manifest:

```yaml
- name: SERVER_COUNTRIES
  value: "USA"  # Options: USA, Canada, UK, Germany, etc.
```

### Use Specific Server City

```yaml
- name: SERVER_CITIES
  value: "New York"
```

### Kill Switch

Gluetun has a built-in kill switch. If VPN disconnects:
- All traffic is blocked
- qBittorrent cannot access internet
- Your real IP is never exposed

### Port Forwarding (for better speeds)

Mullvad doesn't support port forwarding anymore. If using a provider that does:

```yaml
- name: VPN_PORT_FORWARDING
  value: "on"
```

---

## Troubleshooting

### Pod stuck in ContainerCreating

Check NFS mount issues:
```bash
kubectl describe pod -n media -l app=qbittorrent
```

Fix: Verify NFS share permissions (0777, root:root)

### Gluetun won't connect

Check logs:
```bash
kubectl logs -n media -l app=qbittorrent -c gluetun
```

Common issues:
- Wrong private key in secret
- Wrong WIREGUARD_ADDRESSES
- Firewall blocking WireGuard (UDP 51820)

### qBittorrent file permission errors

```
QtLockedFile::lock(): file is not opened
```

Fix: Set TrueNAS dataset permissions to 0777 with root:root ownership.

### 404 from Traefik

Check IngressRoute exists:
```bash
kubectl get ingressroute -n media
```

Restart Traefik:
```bash
kubectl rollout restart deployment traefik -n traefik
```

### Browser forces HTTPS

Clear HSTS cache in browser, then access `http://qbit.servers.local`

---

## File Structure

```
apps/qbittorrent/
├── README.md
├── qbittorrent-config-pv-pvc.yaml
├── qbittorrent-downloads-pv-pvc.yaml
└── qbittorrent-manifest.yaml
```

---

## Useful Commands

| Command | Purpose |
|---------|---------|
| `kubectl get pods -n media -l app=qbittorrent` | Check pod status |
| `kubectl logs -n media -l app=qbittorrent -c gluetun` | View Gluetun logs |
| `kubectl logs -n media -l app=qbittorrent -c qbittorrent` | View qBittorrent logs |
| `kubectl logs -n media -l app=qbittorrent -c qbittorrent \| grep password` | Get temporary password |
| `kubectl exec -n media -l app=qbittorrent -c qbittorrent -- curl -s ifconfig.me` | Check VPN IP |
| `kubectl delete pod -n media -l app=qbittorrent` | Restart pod |
| `kubectl rollout restart deployment qbittorrent -n media` | Restart deployment |

---

## Security Notes

1. **Never commit secrets to Git** - Use `kubectl create secret` command
2. **VPN kill switch is automatic** - If VPN drops, traffic stops
3. **All torrent traffic is encrypted** - WireGuard encrypts everything
4. **Local network access** - `FIREWALL_OUTBOUND_SUBNETS` allows NFS but not internet without VPN

---

## Resources

- [Gluetun Documentation](https://github.com/qdm12/gluetun-wiki)
- [Mullvad WireGuard Setup](https://mullvad.net/en/help/wireguard/)
- [qBittorrent Documentation](https://github.com/qbittorrent/qBittorrent/wiki)
- [LinuxServer qBittorrent Image](https://docs.linuxserver.io/images/docker-qbittorrent/)