# Immich Kubernetes Deployment Guide

Production-ready Immich deployment on Kubernetes with NFS-backed storage.

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Storage Design](#storage-design)
- [Prerequisites](#prerequisites)
- [TrueNAS Configuration](#truenas-configuration)
- [Kubernetes Deployment](#kubernetes-deployment)
- [Backup & Restore](#backup--restore)
- [Troubleshooting](#troubleshooting)
- [Maintenance](#maintenance)

---

## Overview

This deployment configuration provides a production-ready Immich installation with:
- **Separated storage** for data and configuration
- **Security hardened** containers (non-root, capability dropping)
- **NFS-backed persistence** on TrueNAS
- **Traefik ingress** with HTTP/HTTPS support
- **Pod startup time**: ~63 seconds
- **Kubernetes 1.24+** compatible

---

## Architecture

```
┌─────────────────────────────────────────────┐
│           Kubernetes Cluster                │
│                                             │
│  ┌──────────────┐  ┌──────────────┐       │
│  │ immich-server│  │ immich-ml    │       │
│  │   (v2.4.1)   │  │ (face recog) │       │
│  └──────┬───────┘  └──────────────┘       │
│         │                                   │
│  ┌──────┴───────┐  ┌──────────────┐       │
│  │ PostgreSQL   │  │ Redis        │       │
│  │ (pgvecto-rs) │  │ (cache)      │       │
│  └──────┬───────┘  └──────────────┘       │
└─────────┼──────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────┐
│         TrueNAS NFS Storage                 │
│         (10.10.5.40)                        │
│                                             │
│  /mnt/master-storage/immich-photos/         │
│  ├── data/          (Photos/Videos)        │
│  │   └── library/   (User uploads)         │
│  └── config/        (System data)          │
│      ├── database/  (PostgreSQL)           │
│      ├── redis/     (Cache persist)        │
│      └── model-cache/ (ML models)          │
└─────────────────────────────────────────────┘
```

---

## Storage Design

### Why Separate Data and Config?

This deployment uses **two distinct NFS shares** for different purposes:

#### 1. **Data PV/PVC** (`immich-data`)
**Purpose**: Store user-uploaded photos and videos

**Characteristics:**
- **Large capacity**: 1000Gi (1TB+)
- **High I/O**: Optimized for media file access
- **Frequent writes**: New uploads constantly
- **Critical**: Contains irreplaceable user data

**ZFS Optimizations:**
```bash
recordsize=128K      # Optimal for photos/videos
compression=lz4      # Fast compression, good ratio for media
atime=off           # Don't track access times (performance)
```

**NFS Mount Options:**
```yaml
- nfsvers=4         # NFSv4 protocol
- hard              # Don't give up on mount
- intr              # Allow interruption
- noatime           # Performance: skip access time updates
- nodiratime        # Performance: skip dir access time updates
```

**Backup Strategy:**
- Snapshot frequency: Every 12 hours
- Retention: 7-14 days
- Replication: Daily to backup location
- User data is **irreplaceable** - protect accordingly

#### 2. **Config PV/PVC** (`immich-config`)
**Purpose**: Store system configuration and metadata

**Characteristics:**
- **Smaller capacity**: 50Gi (typically uses <10GB)
- **Random I/O**: Database operations
- **Frequent updates**: Metadata changes
- **Important**: Can be restored from backup

**ZFS Optimizations:**
```bash
recordsize=16K       # Optimal for database small blocks
compression=lz4      # Fast compression
```

**NFS Mount Options:**
```yaml
- nfsvers=4         # NFSv4 protocol
- hard              # Don't give up on mount
- intr              # Allow interruption
```

**What's Stored:**
- **PostgreSQL database**: User accounts, albums, sharing, metadata
- **Redis data**: Session cache, job queues
- **ML model cache**: Downloaded face recognition models (~2GB)

**Backup Strategy:**
- Snapshot frequency: Every 4-6 hours
- Retention: 30+ days (easier to recover from config issues)
- Database dumps: Daily SQL exports

### Benefits of This Separation

| Benefit | Explanation |
|---------|-------------|
| **Different backup schedules** | Photos backed up daily, config every 4 hours |
| **Independent scaling** | Grow photo storage without affecting config |
| **Performance tuning** | Different ZFS recordsize for each workload |
| **Easier migrations** | Move photos independently of database |
| **Better organization** | Clear separation of concerns |
| **Selective restore** | Restore config without touching photos |
| **Cost optimization** | Use different storage tiers if needed |

### Storage Usage Examples

**Typical Usage:**
```
immich-data (photos):        76 GB  (grows continuously)
immich-config (database):   100 MB  (grows slowly)
immich-config (redis):        5 MB  (ephemeral)
immich-config (ml-cache):   2.5 GB  (one-time download)
```

**Why This Matters:**
- You can snapshot config frequently (small) without impacting storage
- Photo backups can be slower (large) without affecting system operation
- Database can be optimized separately from media storage
- Easier to troubleshoot when issues are isolated to one storage type

---

## Prerequisites

### TrueNAS Requirements
- **Version**: TrueNAS SCALE or CORE
- **IP Address**: `10.10.5.40` (update in manifests)
- **Pool**: `master-storage` (or your pool name)
- **NFS Service**: Enabled
- **Network**: Accessible from Kubernetes nodes

### Kubernetes Cluster
- **Version**: 1.24 or newer
- **Ingress**: Traefik controller installed
- **kubectl**: Configured with cluster admin access
- **NFS Client**: Installed on all worker nodes

**Install NFS client on nodes:**
```bash
# Ubuntu/Debian
apt-get install -y nfs-common

# RHEL/CentOS/Rocky
yum install -y nfs-utils

# Verify
showmount -e 10.10.5.40
```

### DNS Configuration
Configure these DNS records (or use `/etc/hosts`):
- `immich.servers.local` → Traefik ingress IP (internal)
- `immich.techbysean.com` → Traefik ingress IP (external)

---

## TrueNAS Configuration

### 1. Create ZFS Datasets

```bash
# SSH to TrueNAS
ssh root@10.10.5.40

# Create parent dataset
zfs create master-storage/immich-photos

# Create data dataset (for photos/videos)
zfs create master-storage/immich-photos/data
zfs set recordsize=128K master-storage/immich-photos/data
zfs set compression=lz4 master-storage/immich-photos/data
zfs set atime=off master-storage/immich-photos/data

# Create config dataset (for database/cache)
zfs create master-storage/immich-photos/config
zfs set recordsize=16K master-storage/immich-photos/config
zfs set compression=lz4 master-storage/immich-photos/config

# Create subdirectories
mkdir -p /mnt/master-storage/immich-photos/data/library
mkdir -p /mnt/master-storage/immich-photos/config/database
mkdir -p /mnt/master-storage/immich-photos/config/redis
mkdir -p /mnt/master-storage/immich-photos/config/model-cache

# Set ownership (Immich runs as UID/GID 999)
chown -R 999:999 /mnt/master-storage/immich-photos/data
chown -R 999:999 /mnt/master-storage/immich-photos/config
chmod -R 755 /mnt/master-storage/immich-photos

# Verify
ls -lan /mnt/master-storage/immich-photos/
```

### 2. Configure NFS Shares

**Via TrueNAS Web UI:**

#### Data Share
1. Navigate to **Sharing → Unix Shares (NFS) → Add**
2. Configure:
   - **Path**: `/mnt/master-storage/immich-photos/data`
   - **Description**: `Immich Photo Data`
   - **Authorized Networks**: `10.10.5.0/24` (your Kubernetes subnet)
   - **Mapall User**: `root`
   - **Mapall Group**: `root`
   - **Enable NFSv4**: ✓
3. Click **Save**

#### Config Share
1. Navigate to **Sharing → Unix Shares (NFS) → Add**
2. Configure:
   - **Path**: `/mnt/master-storage/immich-photos/config`
   - **Description**: `Immich Configuration`
   - **Authorized Networks**: `10.10.5.0/24`
   - **Mapall User**: `root`
   - **Mapall Group**: `root`
   - **Enable NFSv4**: ✓
3. Click **Save**

#### Enable NFS Service
1. Navigate to **System → Services**
2. Find **NFS**
3. Toggle to **Running**
4. Enable **Start Automatically**

### 3. Verify NFS Exports

```bash
# From any machine with NFS client
showmount -e 10.10.5.40

# Expected output:
# Export list for 10.10.5.40:
# /mnt/master-storage/immich-photos/data   10.10.5.0/24
# /mnt/master-storage/immich-photos/config 10.10.5.0/24

# Test mount
mkdir -p /tmp/test-nfs
mount -t nfs 10.10.5.40:/mnt/master-storage/immich-photos/data /tmp/test-nfs
ls -la /tmp/test-nfs
umount /tmp/test-nfs
```

---

## Kubernetes Deployment

### Deployment Files

Create two YAML files in your working directory:

```
immich-k8s/
├── 01-immich-storage.yaml
└── 02-immich-application.yaml
```

### 01-immich-storage.yaml

**Storage layer with separated data and config:**

```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: immich-data-pv
spec:
  capacity:
    storage: 1000Gi  # Adjust based on photo library size
  accessModes:
    - ReadWriteMany
  persistentVolumeReclaimPolicy: Retain
  storageClassName: nfs-immich-data
  nfs:
    server: 10.10.5.40  # Your TrueNAS IP
    path: /mnt/master-storage/immich-photos/data
  mountOptions:
    - nfsvers=4
    - hard
    - intr
    - noatime
    - nodiratime

---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: immich-data-pvc
  namespace: immich
spec:
  accessModes:
    - ReadWriteMany
  storageClassName: nfs-immich-data
  resources:
    requests:
      storage: 1000Gi
  volumeName: immich-data-pv

---
apiVersion: v1
kind: PersistentVolume
metadata:
  name: immich-config-pv
spec:
  capacity:
    storage: 50Gi  # Config is much smaller
  accessModes:
    - ReadWriteMany
  persistentVolumeReclaimPolicy: Retain
  storageClassName: nfs-immich-config
  nfs:
    server: 10.10.5.40  # Your TrueNAS IP
    path: /mnt/master-storage/immich-photos/config
  mountOptions:
    - nfsvers=4
    - hard
    - intr

---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: immich-config-pvc
  namespace: immich
spec:
  accessModes:
    - ReadWriteMany
  storageClassName: nfs-immich-config
  resources:
    requests:
      storage: 50Gi
  volumeName: immich-config-pv
```

### 02-immich-application.yaml

**Complete application stack with security hardening:**

```yaml
---
# Namespace
apiVersion: v1
kind: Namespace
metadata:
  name: immich

---
# ConfigMap for environment variables
apiVersion: v1
kind: ConfigMap
metadata:
  name: immich-config
  namespace: immich
data:
  DB_HOSTNAME: "immich-postgresql"
  DB_USERNAME: "postgres"
  DB_DATABASE_NAME: "immich"
  REDIS_HOSTNAME: "immich-redis"
  UPLOAD_LOCATION: "/usr/src/app/upload"

---
# Secret for sensitive data
apiVersion: v1
kind: Secret
metadata:
  name: immich-secrets
  namespace: immich
type: Opaque
stringData:
  DB_PASSWORD: "ChangeThisPassword123!"  # CHANGE THIS!

---
# PostgreSQL Deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: immich-postgresql
  namespace: immich
  labels:
    app: immich-postgresql
spec:
  replicas: 1
  strategy:
    type: Recreate
  selector:
    matchLabels:
      app: immich-postgresql
  template:
    metadata:
      labels:
        app: immich-postgresql
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 999
        runAsGroup: 999
        fsGroup: 999
        seccompProfile:
          type: RuntimeDefault
      containers:
      - name: postgresql
        image: tensorchord/pgvecto-rs:pg14-v0.2.0
        securityContext:
          allowPrivilegeEscalation: false
          capabilities:
            drop:
              - ALL
          readOnlyRootFilesystem: false
        env:
        - name: POSTGRES_USER
          valueFrom:
            configMapKeyRef:
              name: immich-config
              key: DB_USERNAME
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: immich-secrets
              key: DB_PASSWORD
        - name: POSTGRES_DB
          valueFrom:
            configMapKeyRef:
              name: immich-config
              key: DB_DATABASE_NAME
        - name: PGDATA
          value: /var/lib/postgresql/data/pgdata
        ports:
        - containerPort: 5432
          name: postgresql
          protocol: TCP
        volumeMounts:
        - name: config-storage
          mountPath: /var/lib/postgresql/data
          subPath: database
        resources:
          requests:
            cpu: 250m
            memory: 512Mi
          limits:
            cpu: 2000m
            memory: 4Gi
        livenessProbe:
          exec:
            command:
            - /bin/sh
            - -c
            - pg_isready -U postgres
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        readinessProbe:
          exec:
            command:
            - /bin/sh
            - -c
            - pg_isready -U postgres
          initialDelaySeconds: 5
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 3
      volumes:
      - name: config-storage
        persistentVolumeClaim:
          claimName: immich-config-pvc

---
# PostgreSQL Service
apiVersion: v1
kind: Service
metadata:
  name: immich-postgresql
  namespace: immich
  labels:
    app: immich-postgresql
spec:
  selector:
    app: immich-postgresql
  ports:
  - port: 5432
    targetPort: 5432
    protocol: TCP
    name: postgresql
  type: ClusterIP

---
# Redis Deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: immich-redis
  namespace: immich
  labels:
    app: immich-redis
spec:
  replicas: 1
  selector:
    matchLabels:
      app: immich-redis
  template:
    metadata:
      labels:
        app: immich-redis
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 999
        runAsGroup: 999
        fsGroup: 999
        seccompProfile:
          type: RuntimeDefault
      containers:
      - name: redis
        image: redis:6.2-alpine
        securityContext:
          allowPrivilegeEscalation: false
          capabilities:
            drop:
              - ALL
          readOnlyRootFilesystem: false
        command:
        - redis-server
        - --save
        - "60"
        - "1"
        - --dir
        - /data
        ports:
        - containerPort: 6379
          name: redis
          protocol: TCP
        volumeMounts:
        - name: config-storage
          mountPath: /data
          subPath: redis
        resources:
          requests:
            cpu: 50m
            memory: 64Mi
          limits:
            cpu: 500m
            memory: 256Mi
        livenessProbe:
          tcpSocket:
            port: 6379
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          exec:
            command:
            - redis-cli
            - ping
          initialDelaySeconds: 5
          periodSeconds: 5
      volumes:
      - name: config-storage
        persistentVolumeClaim:
          claimName: immich-config-pvc

---
# Redis Service
apiVersion: v1
kind: Service
metadata:
  name: immich-redis
  namespace: immich
  labels:
    app: immich-redis
spec:
  selector:
    app: immich-redis
  ports:
  - port: 6379
    targetPort: 6379
    protocol: TCP
    name: redis
  type: ClusterIP

---
# Immich Server Deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: immich-server
  namespace: immich
  labels:
    app: immich-server
spec:
  replicas: 1
  selector:
    matchLabels:
      app: immich-server
  template:
    metadata:
      labels:
        app: immich-server
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 999
        runAsGroup: 999
        fsGroup: 999
        seccompProfile:
          type: RuntimeDefault
      containers:
      - name: immich-server
        image: ghcr.io/immich-app/immich-server:release
        securityContext:
          allowPrivilegeEscalation: false
          capabilities:
            drop:
              - ALL
          readOnlyRootFilesystem: false
        envFrom:
        - configMapRef:
            name: immich-config
        env:
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: immich-secrets
              key: DB_PASSWORD
        ports:
        - containerPort: 2283
          name: http
          protocol: TCP
        volumeMounts:
        - name: data-storage
          mountPath: /usr/src/app/upload
        resources:
          requests:
            cpu: 250m
            memory: 512Mi
          limits:
            cpu: 2000m
            memory: 4Gi
        livenessProbe:
          httpGet:
            path: /api/server/ping
            port: 2283
          initialDelaySeconds: 120
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 6
        readinessProbe:
          httpGet:
            path: /api/server/ping
            port: 2283
          initialDelaySeconds: 60
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
      volumes:
      - name: data-storage
        persistentVolumeClaim:
          claimName: immich-data-pvc

---
# Immich Machine Learning Deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: immich-machine-learning
  namespace: immich
  labels:
    app: immich-machine-learning
spec:
  replicas: 1
  selector:
    matchLabels:
      app: immich-machine-learning
  template:
    metadata:
      labels:
        app: immich-machine-learning
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 999
        runAsGroup: 999
        fsGroup: 999
        seccompProfile:
          type: RuntimeDefault
      containers:
      - name: immich-machine-learning
        image: ghcr.io/immich-app/immich-machine-learning:release
        securityContext:
          allowPrivilegeEscalation: false
          capabilities:
            drop:
              - ALL
          readOnlyRootFilesystem: false
        envFrom:
        - configMapRef:
            name: immich-config
        env:
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: immich-secrets
              key: DB_PASSWORD
        ports:
        - containerPort: 3003
          name: http
          protocol: TCP
        volumeMounts:
        - name: data-storage
          mountPath: /usr/src/app/upload
        - name: config-storage
          mountPath: /cache
          subPath: model-cache
        resources:
          requests:
            cpu: 250m
            memory: 1Gi
          limits:
            cpu: 2000m
            memory: 4Gi
        # Uncomment for GPU support (NVIDIA)
        # resources:
        #   limits:
        #     nvidia.com/gpu: 1
      volumes:
      - name: data-storage
        persistentVolumeClaim:
          claimName: immich-data-pvc
      - name: config-storage
        persistentVolumeClaim:
          claimName: immich-config-pvc

---
# Immich Server Service
apiVersion: v1
kind: Service
metadata:
  name: immich-server
  namespace: immich
  labels:
    app: immich-server
spec:
  selector:
    app: immich-server
  ports:
  - port: 3001
    targetPort: 2283
    protocol: TCP
    name: http
  type: ClusterIP

---
# Immich Machine Learning Service
apiVersion: v1
kind: Service
metadata:
  name: immich-machine-learning
  namespace: immich
  labels:
    app: immich-machine-learning
spec:
  selector:
    app: immich-machine-learning
  ports:
  - port: 3003
    targetPort: 3003
    protocol: TCP
    name: http
  type: ClusterIP

---
# Traefik IngressRoute (HTTP)
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: immich-http
  namespace: immich
spec:
  entryPoints:
    - web
  routes:
    - match: Host(`immich.servers.local`) || Host(`immich.techbysean.com`)  # CHANGE TO YOUR DOMAINS
      kind: Rule
      services:
        - name: immich-server
          port: 3001

---
# Traefik IngressRoute (HTTPS)
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: immich-https
  namespace: immich
spec:
  entryPoints:
    - websecure
  routes:
    - match: Host(`immich.servers.local`) || Host(`immich.techbysean.com`)  # CHANGE TO YOUR DOMAINS
      kind: Rule
      services:
        - name: immich-server
          port: 3001
  tls:
    certResolver: letsencrypt  # Change to match your Traefik cert resolver
```

### Configuration

**Before deploying, update these values:**

#### In `01-immich-storage.yaml`:
1. **TrueNAS IP** (lines 11 and 35):
   ```yaml
   server: 10.10.5.40  # Your actual TrueNAS IP
   ```

2. **Storage sizes** (optional, lines 8 and 31):
   ```yaml
   storage: 1000Gi  # Adjust based on your needs
   ```

#### In `02-immich-application.yaml`:
1. **Database password** (line 26):
   ```yaml
   DB_PASSWORD: "YourSecurePassword123!"  # Use a strong password!
   ```

2. **Domains** (lines 406 and 418):
   ```yaml
   - match: Host(`immich.yourlocal.domain`) || Host(`immich.yourdomain.com`)
   ```

3. **TLS Certificate Resolver** (line 430):
   ```yaml
   certResolver: letsencrypt  # Match your Traefik configuration
   ```

### Deploy

```bash
# Step 1: Deploy storage layer
kubectl apply -f 01-immich-storage.yaml

# Verify PVs are created
kubectl get pv
# Should show: immich-data-pv (1000Gi) and immich-config-pv (50Gi)

# Step 2: Deploy application
kubectl apply -f 02-immich-application.yaml

# Step 3: Watch pods starting (~60-90 seconds)
kubectl get pods -n immich -w

# Press Ctrl+C when all pods show 1/1 Ready
```

**Expected output:**
```
NAME                                      READY   STATUS    RESTARTS   AGE
immich-machine-learning-xxxxxxxxx-xxxxx   1/1     Running   0          90s
immich-postgresql-xxxxxxxxx-xxxxx         1/1     Running   0          90s
immich-redis-xxxxxxxxx-xxxxx              1/1     Running   0          90s
immich-server-xxxxxxxxx-xxxxx             1/1     Running   0          90s
```

### Verify Deployment

```bash
# Check all resources
kubectl get all,pv,pvc,ingressroute -n immich

# Test health endpoint
kubectl exec -n immich -l app=immich-server -- curl -s http://localhost:2283/api/server/ping
# Should return: {"res":"pong"}

# Check logs
kubectl logs -n immich -l app=immich-server --tail=20
```

### Access Immich

Open your browser:
- **HTTP**: `http://immich.servers.local`
- **HTTPS**: `https://immich.techbysean.com`

**First-time setup:**
1. Create admin account
2. Configure storage libraries  
3. Set up mobile apps

---

## Backup & Restore

### Database Backup

```bash
# Get PostgreSQL pod
PGPOD=$(kubectl get pod -n immich -l app=immich-postgresql -o jsonpath='{.items[0].metadata.name}')

# Create backup
kubectl exec -n immich $PGPOD -- pg_dumpall -U postgres > immich-backup-$(date +%Y%m%d).sql

# Verify
ls -lh immich-backup-*.sql

# Store safely off-cluster
```

### Database Restore

```bash
# Scale down Immich
kubectl scale deployment immich-server immich-machine-learning --replicas=0 -n immich

# Drop and recreate database
kubectl exec -it -n immich $PGPOD -- psql -U postgres -c "DROP DATABASE IF EXISTS immich;"
kubectl exec -it -n immich $PGPOD -- psql -U postgres -c "CREATE DATABASE immich;"
kubectl exec -it -n immich $PGPOD -- psql -U postgres -d immich -c "CREATE EXTENSION IF NOT EXISTS vectors;"

# Restore
kubectl cp immich-backup-20251230.sql immich/$PGPOD:/tmp/backup.sql
kubectl exec -it -n immich $PGPOD -- psql -U postgres -d immich -f /tmp/backup.sql

# Scale back up
kubectl scale deployment immich-server immich-machine-learning --replicas=1 -n immich
```

### TrueNAS Snapshots

**Recommended schedule:**

**Data (photos):**
- Frequency: Every 12 hours
- Retention: 7-14 days
- Replication: Daily to backup location

**Config (database):**
- Frequency: Every 4 hours
- Retention: 30 days
- SQL dumps: Daily exports

---

## Troubleshooting

### Pods Not Starting

```bash
# Check status
kubectl get pods -n immich
kubectl describe pod -n immich <pod-name>

# Check logs
kubectl logs -n immich <pod-name>
```

### NFS Mount Issues

```bash
# Verify from worker node
showmount -e 10.10.5.40

# Test mount
mount -t nfs 10.10.5.40:/mnt/master-storage/immich-photos/data /tmp/test
```

### Permission Issues

```bash
# On TrueNAS
chown -R 999:999 /mnt/master-storage/immich-photos/data
chown -R 999:999 /mnt/master-storage/immich-photos/config
```

---

## Maintenance

### Updating Immich

```bash
# Update to latest version
kubectl set image deployment/immich-server immich-server=ghcr.io/immich-app/immich-server:release -n immich
kubectl set image deployment/immich-machine-learning immich-machine-learning=ghcr.io/immich-app/immich-machine-learning:release -n immich

# Watch rollout
kubectl rollout status deployment/immich-server -n immich
```

### Restart Services

```bash
# Restart Immich server
kubectl rollout restart deployment immich-server -n immich

# Restart all
kubectl rollout restart deployment -n immich
```

### Quick Reference

```bash
# View all resources
kubectl get all,pv,pvc,ingressroute -n immich

# View logs (follow)
kubectl logs -n immich -l app=immich-server -f

# Access database
PGPOD=$(kubectl get pod -n immich -l app=immich-postgresql -o jsonpath='{.items[0].metadata.name}')
kubectl exec -it -n immich $PGPOD -- psql -U postgres -d immich

# Port forward for testing
kubectl port-forward -n immich svc/immich-server 3001:3001

# Check resource usage
kubectl top pods -n immich
```

---

## Support

- **Immich Docs**: https://immich.app/docs
- **Immich Discord**: https://discord.gg/immich
- **GitHub**: https://github.com/immich-app/immich

---

**Last Updated**: December 30, 2025  
**Immich Version**: v2.4.1  
**Status**: ✅ Production Ready
