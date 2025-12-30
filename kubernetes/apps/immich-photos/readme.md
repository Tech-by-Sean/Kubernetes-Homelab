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
recordsize=128K      # Optimal for photos/videos (large sequential files)
compression=lz4      # Fast compression, good ratio for media
atime=off           # Don't track access times (performance boost)
```

**NFS Mount Options:**
```yaml
- nfsvers=4         # NFSv4 protocol
- hard              # Don't give up on mount failures
- intr              # Allow interruption of hung mounts
- noatime           # Performance: skip access time updates
- nodiratime        # Performance: skip dir access time updates
```

**Backup Strategy:**
- Snapshot frequency: Every 12 hours
- Retention: 7-14 days (user data is large, balance cost vs protection)
- Replication: Daily to backup location
- User data is **irreplaceable** - protect accordingly

#### 2. **Config PV/PVC** (`immich-config`)
**Purpose**: Store system configuration and metadata

**Characteristics:**
- **Smaller capacity**: 50Gi (typically uses <10GB)
- **Random I/O**: Database operations with small blocks
- **Frequent updates**: Metadata changes on every photo action
- **Important but recoverable**: Can be restored from SQL backup

**ZFS Optimizations:**
```bash
recordsize=16K       # Optimal for database small random I/O
compression=lz4      # Fast compression
```

**NFS Mount Options:**
```yaml
- nfsvers=4         # NFSv4 protocol
- hard              # Don't give up on mount failures
- intr              # Allow interruption of hung mounts
```

**What's Stored:**
- **PostgreSQL database**: User accounts, albums, sharing, metadata, EXIF data
- **Redis data**: Session cache, job queues
- **ML model cache**: Downloaded face recognition models (~2GB)

**Backup Strategy:**
- Snapshot frequency: Every 4-6 hours (small, cheap to snapshot frequently)
- Retention: 30+ days (easier to recover from config issues)
- Database dumps: Daily SQL exports for portability

### Benefits of This Separation

| Benefit | Explanation |
|---------|-------------|
| **Different backup schedules** | Photos backed up daily (large), config every 4 hours (small) |
| **Independent scaling** | Grow photo storage to 10TB without affecting config |
| **Performance tuning** | Different ZFS recordsize optimized for each workload |
| **Easier migrations** | Move photos to new storage without touching database |
| **Better organization** | Clear separation: user data vs system data |
| **Selective restore** | Restore corrupted database without touching photos |
| **Cost optimization** | Use different storage tiers (SSD for DB, HDD for photos) |
| **Snapshot efficiency** | Config snapshots are tiny, can snapshot very frequently |

### Storage Usage Examples

**Typical Usage After 1 Year:**
```
immich-data (photos):        150 GB  (grows continuously with uploads)
immich-config (database):    500 MB  (grows slowly with metadata)
immich-config (redis):         5 MB  (ephemeral, resets on restart)
immich-config (ml-cache):    2.5 GB  (one-time download, static)
```

**Why This Matters:**
- You can snapshot config 6x per day (96 snapshots = ~50GB total)
- Photo backups can be slower without affecting system responsiveness
- Database can be moved to faster storage (SSD) independent of photos
- Troubleshooting is easier when data/config are isolated
- Recovery is faster (restore 500MB DB vs 150GB photos)

### The Alternative (Single PVC) - Why Not?

A single combined storage volume would:
- ❌ Require same backup schedule for both (inefficient)
- ❌ Cannot tune ZFS recordsize for both workloads
- ❌ Makes migrations complex (can't move DB separately)
- ❌ Snapshots are huge (GB instead of MB)
- ❌ One I/O pattern affects the other
- ❌ Cannot scale independently

---

## Prerequisites

### TrueNAS Requirements
- **Version**: TrueNAS SCALE or CORE
- **IP Address**: `10.10.5.40` (update in manifests)
- **Pool**: `master-storage` (or your pool name)
- **NFS Service**: Enabled
- **Network**: Accessible from Kubernetes nodes (test with `ping`)

### Kubernetes Cluster
- **Version**: 1.24 or newer
- **Ingress**: Traefik controller installed
- **kubectl**: Configured with cluster admin access
- **NFS Client**: Installed on all worker nodes

**Install NFS client on all Kubernetes worker nodes:**
```bash
# Ubuntu/Debian
sudo apt-get install -y nfs-common

# RHEL/CentOS/Rocky
sudo yum install -y nfs-utils

# Verify installation
showmount -e 10.10.5.40
```

### DNS Configuration
Configure these DNS records (or use `/etc/hosts`):
- `immich.servers.local` → Traefik ingress IP (internal)
- `immich.techbysean.com` → Traefik ingress IP (external)

### Required Files
```
immich-k8s/
├── README.md                     (this file)
├── 01-immich-storage.yaml        (PV/PVC definitions)
└── 02-immich-application.yaml    (Application stack)
```

---

## TrueNAS Configuration

### 1. Create ZFS Datasets

SSH to TrueNAS and create optimized datasets for each workload:

```bash
ssh root@10.10.5.40

# Create parent dataset
zfs create master-storage/immich-photos

# Create DATA dataset - optimized for large media files
zfs create master-storage/immich-photos/data
zfs set recordsize=128K master-storage/immich-photos/data    # Large blocks for photos/videos
zfs set compression=lz4 master-storage/immich-photos/data    # Fast compression
zfs set atime=off master-storage/immich-photos/data          # Performance: no access time tracking

# Create CONFIG dataset - optimized for database
zfs create master-storage/immich-photos/config
zfs set recordsize=16K master-storage/immich-photos/config   # Small blocks for database
zfs set compression=lz4 master-storage/immich-photos/config  # Fast compression

# Create subdirectories
mkdir -p /mnt/master-storage/immich-photos/data/library
mkdir -p /mnt/master-storage/immich-photos/config/database
mkdir -p /mnt/master-storage/immich-photos/config/redis
mkdir -p /mnt/master-storage/immich-photos/config/model-cache

# Set ownership (Immich containers run as UID/GID 999)
chown -R 999:999 /mnt/master-storage/immich-photos/data
chown -R 999:999 /mnt/master-storage/immich-photos/config
chmod -R 755 /mnt/master-storage/immich-photos

# Verify ownership
ls -lan /mnt/master-storage/immich-photos/
```

### 2. Configure NFS Shares

**Via TrueNAS Web UI:**

#### Data Share (Photos/Videos)
1. Navigate to **Sharing → Unix Shares (NFS) → Add**
2. Configure:
   - **Path**: `/mnt/master-storage/immich-photos/data`
   - **Description**: `Immich Photo Data`
   - **Authorized Networks**: `10.10.5.0/24` (adjust to your Kubernetes subnet)
   - **Mapall User**: `root`
   - **Mapall Group**: `root`
   - **Enable NFSv4**: ✓
3. Click **Save**

#### Config Share (Database/Cache)
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

From any machine with NFS client tools:

```bash
# List available exports
showmount -e 10.10.5.40

# Expected output:
# Export list for 10.10.5.40:
# /mnt/master-storage/immich-photos/data   10.10.5.0/24
# /mnt/master-storage/immich-photos/config 10.10.5.0/24

# Test mount (run on a Kubernetes worker node)
mkdir -p /tmp/test-nfs-data
mkdir -p /tmp/test-nfs-config

mount -t nfs 10.10.5.40:/mnt/master-storage/immich-photos/data /tmp/test-nfs-data
mount -t nfs 10.10.5.40:/mnt/master-storage/immich-photos/config /tmp/test-nfs-config

# Verify
ls -la /tmp/test-nfs-data
ls -la /tmp/test-nfs-config

# Check write access
touch /tmp/test-nfs-data/test-file
touch /tmp/test-nfs-config/test-file

# Cleanup
rm /tmp/test-nfs-data/test-file
rm /tmp/test-nfs-config/test-file
umount /tmp/test-nfs-data
umount /tmp/test-nfs-config
```

---

## Kubernetes Deployment

### Step 1: Customize Manifests

Before deploying, update these values in your manifest files:

#### In `01-immich-storage.yaml`:
1. **TrueNAS IP** (appears twice, once per PV):
   ```yaml
   nfs:
     server: 10.10.5.40  # Change to your TrueNAS IP
   ```

2. **Storage sizes** (optional):
   ```yaml
   capacity:
     storage: 1000Gi  # Data PV - adjust based on photo library size
   
   capacity:
     storage: 50Gi    # Config PV - usually sufficient
   ```

#### In `02-immich-application.yaml`:
1. **Database password** (in Secret section):
   ```yaml
   stringData:
     DB_PASSWORD: "YourSecurePassword123!"  # Change this!
   ```

2. **Domain names** (in both IngressRoute sections):
   ```yaml
   - match: Host(`immich.yourlocal.domain`) || Host(`immich.yourdomain.com`)
   ```

3. **TLS Certificate Resolver** (in HTTPS IngressRoute):
   ```yaml
   tls:
     certResolver: letsencrypt  # Match your Traefik config
   ```

### Step 2: Deploy Storage Layer

Apply the **`01-immich-storage.yaml`** manifest to create PVs and PVCs:

```bash
# Apply storage manifest
kubectl apply -f 01-immich-storage.yaml

# Verify PersistentVolumes were created
kubectl get pv

# Expected output:
# NAME               CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS      STORAGECLASS
# immich-data-pv     1000Gi     RWX            Retain           Available   nfs-immich-data
# immich-config-pv   50Gi       RWX            Retain           Available   nfs-immich-config

# Verify PersistentVolumeClaims
kubectl get pvc -n immich

# Expected output:
# NAME                STATUS    VOLUME             CAPACITY   ACCESS MODES   STORAGECLASS
# immich-data-pvc     Bound     immich-data-pv     1000Gi     RWX            nfs-immich-data
# immich-config-pvc   Bound     immich-config-pv   50Gi       RWX            nfs-immich-config
```

**What This Did:**
- Created namespace `immich`
- Created two PersistentVolumes pointing to TrueNAS NFS exports
- Created two PersistentVolumeClaims that bind to those PVs
- PVCs are now ready for pods to mount

### Step 3: Deploy Application Stack

Apply the **`02-immich-application.yaml`** manifest to deploy all components:

```bash
# Apply application manifest
kubectl apply -f 02-immich-application.yaml

# Watch pods starting (takes ~60-90 seconds)
kubectl get pods -n immich -w

# Press Ctrl+C when all pods show 1/1 Ready
```

**What This Did:**
- Created ConfigMap with database connection settings
- Created Secret with database password
- Deployed PostgreSQL (with pgvecto-rs extension for vector search)
- Deployed Redis (for job queues and caching)
- Deployed Immich Server (main web application)
- Deployed Immich Machine Learning (face detection, object recognition)
- Created Services for inter-pod communication
- Created Traefik IngressRoutes for external access

**Expected Pod Status:**
```
NAME                                      READY   STATUS    RESTARTS   AGE
immich-machine-learning-xxxxxxxxx-xxxxx   1/1     Running   0          90s
immich-postgresql-xxxxxxxxx-xxxxx         1/1     Running   0          90s
immich-redis-xxxxxxxxx-xxxxx              1/1     Running   0          90s
immich-server-xxxxxxxxx-xxxxx             1/1     Running   0          90s
```

**Note**: Pods have a 60-second initial readiness probe delay, so they take ~60-90 seconds to show `1/1 Ready`.

### Step 4: Verify Deployment

```bash
# Check all resources
kubectl get all,pv,pvc,ingressroute -n immich

# Test health endpoint
kubectl exec -n immich -l app=immich-server -- curl -s http://localhost:2283/api/server/ping
# Should return: {"res":"pong"}

# Check Immich Server logs
kubectl logs -n immich -l app=immich-server --tail=20
# Should show: "Immich Server is listening on http://[::1]:2283"

# Verify NFS mounts inside pods
kubectl exec -n immich -l app=immich-server -- df -h | grep nfs
```

### Step 5: Access Immich

Open your browser and navigate to:
- **HTTP**: `http://immich.servers.local`
- **HTTPS**: `https://immich.techbysean.com`

**First-Time Setup:**
1. Create admin account (email and password)
2. Configure storage libraries (optional)
3. Install mobile apps and point them to your domain
4. Start uploading photos!

**Existing Installation (with restored database):**
1. Log in with existing credentials
2. Photos should appear automatically from NFS storage
3. Trigger library scan if needed: **Administration → Jobs → Library**

---

## Backup & Restore

### Database Backup

The PostgreSQL database contains all user accounts, albums, sharing settings, and photo metadata. Back it up regularly.

```bash
# Get PostgreSQL pod name
PGPOD=$(kubectl get pod -n immich -l app=immich-postgresql -o jsonpath='{.items[0].metadata.name}')

# Create database backup
kubectl exec -n immich $PGPOD -- pg_dumpall -U postgres > immich-backup-$(date +%Y%m%d).sql

# Verify backup file
ls -lh immich-backup-*.sql
# Should show ~100-500MB file depending on library size

# Store backup safely (off-cluster)
cp immich-backup-*.sql /backup/location/
# Or upload to S3, Backblaze, etc.
```

### Database Restore

**⚠️ Warning**: This will overwrite the current database!

```bash
# Step 1: Scale down Immich to close database connections
kubectl scale deployment immich-server immich-machine-learning --replicas=0 -n immich

# Step 2: Wait for pods to terminate
kubectl get pods -n immich
# Should only show PostgreSQL and Redis

# Step 3: Get PostgreSQL pod name
PGPOD=$(kubectl get pod -n immich -l app=immich-postgresql -o jsonpath='{.items[0].metadata.name}')

# Step 4: Drop and recreate database
kubectl exec -it -n immich $PGPOD -- psql -U postgres -c "DROP DATABASE IF EXISTS immich;"
kubectl exec -it -n immich $PGPOD -- psql -U postgres -c "CREATE DATABASE immich;"
kubectl exec -it -n immich $PGPOD -- psql -U postgres -d immich -c "CREATE EXTENSION IF NOT EXISTS vectors;"

# Step 5: Copy backup to pod
kubectl cp immich-backup-20251230.sql immich/$PGPOD:/tmp/backup.sql

# Step 6: Restore backup
kubectl exec -it -n immich $PGPOD -- psql -U postgres -d immich -f /tmp/backup.sql

# Step 7: Verify users are restored
kubectl exec -it -n immich $PGPOD -- psql -U postgres -d immich -c "SELECT email, name FROM \"user\";"
# Should show your user accounts

# Step 8: Clean up backup file
kubectl exec -it -n immich $PGPOD -- rm /tmp/backup.sql

# Step 9: Scale deployments back up
kubectl scale deployment immich-server immich-machine-learning --replicas=1 -n immich

# Step 10: Watch pods start
kubectl get pods -n immich -w
# Wait for all pods to show 1/1 Ready
```

### TrueNAS Snapshot Configuration

Configure automatic ZFS snapshots for point-in-time recovery:

**Via TrueNAS Web UI: Storage → Snapshots → Add**

#### Data Dataset (Photos)
- **Dataset**: `master-storage/immich-photos/data`
- **Schedule**: Every 12 hours (midnight and noon)
- **Retention**: 14 snapshots (7 days)
- **Naming**: `auto-%Y%m%d-%H%M`

#### Config Dataset (Database)
- **Dataset**: `master-storage/immich-photos/config`
- **Schedule**: Every 4 hours
- **Retention**: 60 snapshots (10 days)
- **Naming**: `auto-%Y%m%d-%H%M`

### Backup Best Practices

**Daily:**
- [ ] Automated PostgreSQL dump via cron
- [ ] Verify backup file exists and has size > 0

**Weekly:**
- [ ] Test backup file integrity (try restoring to test environment)
- [ ] Verify TrueNAS snapshots are being created
- [ ] Check available storage space

**Monthly:**
- [ ] Full disaster recovery test (restore to clean cluster)
- [ ] Review and clean up old backup files
- [ ] Update documentation if procedures changed

---

## Troubleshooting

### Pods Not Starting

**Symptoms**: Pods stuck in `Pending`, `ContainerCreating`, or `CrashLoopBackOff`

```bash
# Check pod status
kubectl get pods -n immich

# Describe problem pod
kubectl describe pod -n immich <pod-name>

# Look for events
kubectl get events -n immich --sort-by='.lastTimestamp'

# Check logs
kubectl logs -n immich <pod-name>

# For crashed pods, check previous logs
kubectl logs -n immich <pod-name> --previous
```

**Common Causes:**
- **NFS mount failure**: Check TrueNAS exports and network connectivity
- **Image pull errors**: Check internet connectivity and registry access
- **Resource constraints**: Check if nodes have available CPU/memory
- **Permission issues**: Verify UID/GID 999 owns NFS directories

### NFS Mount Failures

**Symptoms**: PVCs stuck in `Pending`, pods show mount errors in events

```bash
# Check PVC status
kubectl get pvc -n immich
kubectl describe pvc -n immich immich-data-pvc

# Test NFS from a Kubernetes worker node
showmount -e 10.10.5.40
mount -t nfs 10.10.5.40:/mnt/master-storage/immich-photos/data /tmp/test

# Check TrueNAS NFS service
ssh root@10.10.5.40
systemctl status nfs-server
cat /etc/exports
```

**Solutions:**
1. Verify NFS service is running on TrueNAS
2. Check firewall rules allow NFS (ports 111, 2049)
3. Verify authorized networks in NFS share config match Kubernetes subnet
4. Ensure `nfs-common` package is installed on all Kubernetes nodes

### Permission Denied Errors

**Symptoms**: Pods start but show permission errors in logs

```bash
# Check file ownership on TrueNAS
ssh root@10.10.5.40
ls -lan /mnt/master-storage/immich-photos/data
ls -lan /mnt/master-storage/immich-photos/config

# Should show: drwxr-xr-x 999 999
# If not, fix ownership:
chown -R 999:999 /mnt/master-storage/immich-photos/data
chown -R 999:999 /mnt/master-storage/immich-photos/config
chmod -R 755 /mnt/master-storage/immich-photos

# Verify pod security context
kubectl get pod -n immich -l app=immich-server -o yaml | grep -A 10 securityContext
```

### Database Connection Issues

**Symptoms**: Immich server logs show database connection or authentication errors

```bash
# Check database password in secret
kubectl get secret immich-secrets -n immich -o jsonpath='{.data.DB_PASSWORD}' | base64 -d
echo

# Check PostgreSQL logs
kubectl logs -n immich -l app=immich-postgresql --tail=50

# Test database connection from PostgreSQL pod
PGPOD=$(kubectl get pod -n immich -l app=immich-postgresql -o jsonpath='{.items[0].metadata.name}')
kubectl exec -it -n immich $PGPOD -- psql -U postgres -d immich -c "SELECT version();"

# If password is wrong, update it:
# 1. In PostgreSQL
kubectl exec -it -n immich $PGPOD -- psql -U postgres -c "ALTER USER postgres PASSWORD 'NewPassword';"

# 2. Update the secret
kubectl delete secret immich-secrets -n immich
kubectl create secret generic immich-secrets -n immich --from-literal=DB_PASSWORD='NewPassword'

# 3. Restart immich-server
kubectl rollout restart deployment immich-server -n immich
```

### Health Check Failures

**Symptoms**: Pods show `0/1 Ready`, readiness probe failures in describe output

```bash
# Test health endpoint manually from inside pod
kubectl exec -n immich -l app=immich-server -- curl -s http://localhost:2283/api/server/ping
# Should return: {"res":"pong"}

# Check if server is actually running
kubectl logs -n immich -l app=immich-server --tail=20
# Should show: "Immich Server is listening on http://[::1]:2283"

# Check probe configuration
kubectl describe pod -n immich -l app=immich-server | grep -A 10 "Readiness:"
```

**Note**: Readiness probe has 60-second initial delay. New pods take 60-90 seconds to show `1/1 Ready`.

### Slow Performance

**Symptoms**: Slow photo loading, timeouts, UI lag

```bash
# Check pod resource usage
kubectl top pods -n immich

# Check node resources
kubectl top nodes

# Check NFS performance from worker node
time dd if=/dev/zero of=/mnt/test-nfs/testfile bs=1M count=1000
# Should complete in <30 seconds for good performance

# Check database performance
PGPOD=$(kubectl get pod -n immich -l app=immich-postgresql -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n immich $PGPOD -- psql -U postgres -d immich -c "
  SELECT COUNT(*) as photo_count FROM asset;
  SELECT pg_size_pretty(pg_database_size('immich')) as db_size;
"

# If resource constrained, increase limits in 02-immich-application.yaml
```

---

## Maintenance

### Updating Immich

Always create a database backup before updating!

```bash
# Create backup first
PGPOD=$(kubectl get pod -n immich -l app=immich-postgresql -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n immich $PGPOD -- pg_dumpall -U postgres > immich-backup-pre-update-$(date +%Y%m%d).sql

# Check current version
kubectl get deployment -n immich immich-server -o jsonpath='{.spec.template.spec.containers[0].image}'

# Update to latest release
kubectl set image deployment/immich-server \
  immich-server=ghcr.io/immich-app/immich-server:release -n immich

kubectl set image deployment/immich-machine-learning \
  immich-machine-learning=ghcr.io/immich-app/immich-machine-learning:release -n immich

# Watch rollout progress
kubectl rollout status deployment/immich-server -n immich
kubectl rollout status deployment/immich-machine-learning -n immich

# Verify new version is running
kubectl get pods -n immich
kubectl logs -n immich -l app=immich-server | grep "Immich Server is listening"

# Test in browser
# Open https://immich.techbysean.com and verify everything works
```

### Restarting Services

```bash
# Restart specific deployment
kubectl rollout restart deployment immich-server -n immich

# Restart all Immich deployments
kubectl rollout restart deployment -n immich

# Watch pods restart
kubectl get pods -n immich -w
```

### Scaling (Limited)

```bash
# Scale machine learning for faster processing
kubectl scale deployment immich-machine-learning --replicas=2 -n immich

# Scale down for maintenance
kubectl scale deployment immich-server --replicas=0 -n immich
```

**Important**: `immich-server` should stay at 1 replica due to session management. Multiple replicas can cause login issues.

### Resource Monitoring

```bash
# Pod resource usage
kubectl top pods -n immich

# Check storage usage on TrueNAS
ssh root@10.10.5.40
zfs list | grep immich-photos

# Check database size
PGPOD=$(kubectl get pod -n immich -l app=immich-postgresql -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n immich $PGPOD -- psql -U postgres -d immich -c "
  SELECT 
    pg_size_pretty(pg_database_size('immich')) as database_size,
    (SELECT COUNT(*) FROM asset) as photo_count,
    (SELECT COUNT(*) FROM \"user\") as user_count;
"
```

### Log Management

```bash
# View logs (follow mode)
kubectl logs -n immich -l app=immich-server -f

# Export logs for troubleshooting
kubectl logs -n immich -l app=immich-server --since=24h > immich-server-logs.txt

# Check logs from previous container (after crash)
kubectl logs -n immich <pod-name> --previous

# View PostgreSQL logs
kubectl logs -n immich -l app=immich-postgresql --tail=100
```

### Quick Reference Commands

```bash
# View all Immich resources
kubectl get all,pv,pvc,ingressroute -n immich

# Access PostgreSQL database
PGPOD=$(kubectl get pod -n immich -l app=immich-postgresql -o jsonpath='{.items[0].metadata.name}')
kubectl exec -it -n immich $PGPOD -- psql -U postgres -d immich

# Port forward for local testing
kubectl port-forward -n immich svc/immich-server 3001:3001
# Then open: http://localhost:3001

# Check resource usage
kubectl top pods -n immich
kubectl top nodes

# Restart everything
kubectl rollout restart deployment -n immich

# Delete and redeploy (nuclear option)
kubectl delete -f 02-immich-application.yaml
kubectl apply -f 02-immich-application.yaml
```

---

## Support & Resources

- **Immich Documentation**: https://immich.app/docs
- **Immich Discord**: https://discord.gg/immich
- **Immich GitHub**: https://github.com/immich-app/immich
- **Kubernetes Documentation**: https://kubernetes.io/docs
- **TrueNAS Documentation**: https://www.truenas.com/docs

---

## Configuration Reference

| Component | Value | Location |
|-----------|-------|----------|
| **Storage** | | |
| TrueNAS IP | `10.10.5.40` | `01-immich-storage.yaml` |
| Data PV Size | `1000Gi` | `01-immich-storage.yaml` |
| Config PV Size | `50Gi` | `01-immich-storage.yaml` |
| Data Path | `/mnt/master-storage/immich-photos/data` | TrueNAS |
| Config Path | `/mnt/master-storage/immich-photos/config` | TrueNAS |
| **Application** | | |
| Database User | `postgres` | `02-immich-application.yaml` ConfigMap |
| Database Name | `immich` | `02-immich-application.yaml` ConfigMap |
| Database Password | `ChangeThisPassword123!` | `02-immich-application.yaml` Secret |
| Server Port (internal) | `2283` | Container |
| Server Port (service) | `3001` | Service |
| **Security** | | |
| Pod UID/GID | `999` | SecurityContext |
| Run as non-root | `true` | SecurityContext |
| Capabilities | All dropped | SecurityContext |
| **URLs** | | |
| Internal | `http://immich.servers.local` | IngressRoute |
| External | `https://immich.techbysean.com` | IngressRoute |
| Health Check | `/api/server/ping` | Probes |

---

**Last Updated**: December 30, 2025  
**Immich Version**: v2.4.1  
**Kubernetes Version**: 1.24+  
**Status**: ✅ Production Ready
