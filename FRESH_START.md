# Fresh Start Instructions

This guide provides step-by-step commands to completely reset and start fresh with the Brainda application on both Windows and Unraid servers.

---

## Table of Contents

- [Windows Instructions](#windows-instructions)
- [Unraid Server Instructions](#unraid-server-instructions)
- [Post-Installation Steps](#post-installation-steps)
- [Troubleshooting](#troubleshooting)

---

## Windows Instructions

### Prerequisites

- Git installed
- Docker Desktop installed and running
- Node.js 20.19+ or 22.12+ installed
- PowerShell or Command Prompt with admin privileges (for some operations)

### Option 1: Complete Fresh Start (Delete Everything)

#### Step 1: Stop All Running Services

```powershell
# Navigate to project directory
cd C:\Users\Sultan\Documents\brainda

# Stop all Docker containers and remove volumes
docker-compose down -v
```

#### Step 2: Kill Any Node Processes

```powershell
# PowerShell
Get-Process node -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process npm -ErrorAction SilentlyContinue | Stop-Process -Force

# Or Command Prompt
taskkill /F /IM node.exe /T 2>nul
taskkill /F /IM npm.exe /T 2>nul
```

#### Step 3: Delete Project Directory

```powershell
# PowerShell - Navigate to parent directory
cd C:\Users\Sultan\Documents

# Remove the entire project (if permission denied, see workaround below)
Remove-Item -Recurse -Force brainda

# If permission denied, use robocopy workaround:
mkdir empty
robocopy empty brainda /MIR /R:0 /W:0
Remove-Item -Recurse -Force brainda
Remove-Item -Recurse -Force empty
```

#### Step 4: Clone Fresh Repository

```powershell
# Clone the repository
git clone <your-repository-url> brainda

# Navigate into the project
cd brainda
```

#### Step 5: Start All Services (Development Mode with Hot Reload)

```powershell
# Start all services including frontend with hot reload
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Wait for services to be healthy (check logs)
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f orchestrator frontend

# Press Ctrl+C when you see "Application startup complete" and Vite dev server ready

# Access the application:
# - Frontend: http://localhost:3000 (with hot reload)
# - Backend API: http://localhost:8000
```

**Alternative - Production Mode (Single Endpoint):**

```powershell
# For production builds (frontend served from backend)
docker compose -f docker-compose.prod.yml up -d --build

# Access everything at http://localhost:8000
```

### Option 2: Keep Git History (Soft Reset)

```powershell
# Navigate to project
cd C:\Users\Sultan\Documents\brainda

# Stop all services
docker compose -f docker-compose.yml -f docker-compose.dev.yml down -v

# Reset all changes and clean untracked files
git reset --hard HEAD
git clean -fdx

# Pull latest changes
git pull

# Start services with hot reload
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

### Option 3: Legacy Mode (Manual Frontend - Not Recommended)

```powershell
# Only use this if you need to run frontend outside Docker
docker-compose up -d
cd app\web
npm install
npm run dev
```

---

## Unraid Server Instructions

### Prerequisites

- SSH access to Unraid server
- Docker installed (comes with Unraid)
- Git installed
- Node.js 20.19+ or 22.12+ installed

### Connect to Unraid via SSH

```bash
# From your local machine
ssh root@<unraid-server-ip>

# Enter password when prompted
```

### Option 1: Complete Fresh Start

#### Step 1: Stop All Services

```bash
# Navigate to project directory (adjust path as needed)
cd /mnt/user/appdata/brainda

# Stop and remove all containers, networks, and volumes
docker-compose down -v

# Or if using docker compose (newer syntax)
docker compose down -v
```

#### Step 2: Kill Any Running Processes

```bash
# Kill node processes
pkill -9 node
pkill -9 npm

# Verify they're stopped
ps aux | grep node
```

#### Step 3: Delete Project Directory

```bash
# Navigate to parent directory
cd /mnt/user/appdata

# Remove entire project
rm -rf brainda

# Verify deletion
ls -la | grep brainda
```

#### Step 4: Clone Fresh Repository

```bash
# Clone the repository
git clone <your-repository-url> brainda

# Navigate into project
cd brainda

# Set proper permissions (important on Unraid)
chmod -R 755 .
```

#### Step 5: Configure Environment

```bash
# Copy and edit environment file if needed
cp .env.example .env
nano .env  # or vi .env

# Press Ctrl+X, then Y, then Enter to save in nano
```

#### Step 6: Start All Services (Development Mode)

```bash
# Start all services including frontend with hot reload
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Check status
docker compose -f docker-compose.yml -f docker-compose.dev.yml ps

# View logs to ensure services are healthy
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f orchestrator frontend

# Press Ctrl+C to exit logs

# Access the application:
# - Frontend: http://<unraid-ip>:3000 (with hot reload)
# - Backend API: http://<unraid-ip>:8000
```

**Alternative - Production Mode:**

```bash
# For production builds (single endpoint)
docker compose -f docker-compose.prod.yml up -d --build

# Access everything at http://<unraid-ip>:8000
```

### Option 2: Soft Reset (Keep Git History)

```bash
# Navigate to project
cd /mnt/user/appdata/brainda

# Stop all services
docker compose -f docker-compose.yml -f docker-compose.dev.yml down -v

# Reset git and clean
git reset --hard HEAD
git clean -fdx

# Pull latest
git pull

# Restart services with hot reload
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

### Option 3: Legacy Mode (Manual Frontend - Not Recommended)

```bash
# Only use this if you need to run frontend outside Docker
docker-compose up -d
cd app/web
npm install
nohup npm run dev > /tmp/vite.log 2>&1 &
tail -f /tmp/vite.log
```

---

## Post-Installation Steps

### 1. Verify Backend Health

**Windows (Development Mode):**
```powershell
# Check API health
curl http://localhost:8000/api/v1/health

# Check all services are running
docker compose -f docker-compose.yml -f docker-compose.dev.yml ps

# All services should show "Up (healthy)" status
```

**Unraid (Development Mode):**
```bash
# Check API health
curl http://localhost:8000/api/v1/health

# Check all services
docker compose -f docker-compose.yml -f docker-compose.dev.yml ps
```

**Production Mode:**
```bash
# Check API health
curl http://localhost:8000/api/v1/health

# Check all services
docker compose -f docker-compose.prod.yml ps
```

Expected healthy response:
```json
{
  "status": "healthy",
  "timestamp": "...",
  "services": {
    "redis": "ok",
    "qdrant": "ok",
    "postgres": "ok",
    "celery_worker": "ok"
  }
}
```

### 2. Verify Frontend

Navigate to the frontend URL:

**Development Mode:**
- **Windows**: http://localhost:3000
- **Unraid**: http://<unraid-server-ip>:3000

**Production Mode:**
- **Windows**: http://localhost:8000
- **Unraid**: http://<unraid-server-ip>:8000

You should see the login page.

### 3. Create First User (Backend Only - No Frontend)

If you need to test the backend API directly:

```bash
# Register a new user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "your-secure-password"
  }'

# Login to get session token
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "your-secure-password"
  }'
```

### 4. Access the Application

Open your browser and navigate to:

**Development Mode:**
- **Windows**: http://localhost:3000
- **Unraid**: http://<unraid-server-ip>:3000

**Production Mode:**
- **Windows**: http://localhost:8000
- **Unraid**: http://<unraid-server-ip>:8000

Use the registration page to create your first account.

---

## Troubleshooting

### Windows

#### Permission Denied Deleting Files

**Problem**: Cannot delete `node_modules` or build files

**Solution**:
```powershell
# Use robocopy trick
mkdir empty
robocopy empty brainda /MIR /R:0 /W:0
Remove-Item -Recurse -Force brainda
Remove-Item -Recurse -Force empty
```

#### Port Already in Use

**Problem**: Port 3000, 3001, or 8000 already in use

**Solution**:
```powershell
# Find what's using the port (replace 3000 with your port)
netstat -ano | findstr :3000

# Kill the process (replace PID with the number from above)
taskkill /PID <PID> /F
```

#### Docker Containers Won't Stop

**Problem**: Containers are stuck or won't stop

**Solution**:
```powershell
# Stop development mode services
docker compose -f docker-compose.yml -f docker-compose.dev.yml down -f

# Or stop production mode services
docker compose -f docker-compose.prod.yml down -f

# Force remove all containers if needed
docker rm -f $(docker ps -aq)

# Remove all volumes
docker volume prune -f
```

#### Database Password Mismatch

**Problem**: `password authentication failed for user "vib"`

**Solution**:
```powershell
# Must remove volumes to reset database (development mode)
docker compose -f docker-compose.yml -f docker-compose.dev.yml down -v
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Or production mode
docker compose -f docker-compose.prod.yml down -v
docker compose -f docker-compose.prod.yml up -d --build
```

### Unraid

#### Permission Issues

**Problem**: Cannot write files or permission denied

**Solution**:
```bash
# Fix permissions on entire project
cd /mnt/user/appdata/brainda
chmod -R 755 .
chown -R nobody:users .  # Typical Unraid user
```

#### Frontend Not Accessible

**Problem**: Cannot access frontend from browser

**Solution (Development Mode)**:
```bash
# Check frontend container status
docker compose -f docker-compose.yml -f docker-compose.dev.yml ps frontend

# Check frontend logs
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs frontend

# Restart frontend service
docker compose -f docker-compose.yml -f docker-compose.dev.yml restart frontend
```

**Solution (Legacy Manual Mode)**:
```bash
# Only if running frontend manually
ps aux | grep vite
tail -f /tmp/vite.log
pkill -9 node
cd /mnt/user/appdata/brainda/app/web
nohup npm run dev > /tmp/vite.log 2>&1 &
```

#### Docker Compose Command Not Found

**Problem**: `docker-compose: command not found`

**Solution**:
```bash
# Try newer syntax
docker compose up -d

# Or install docker-compose
curl -L "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
```

#### Out of Memory

**Problem**: Services crash or become unresponsive

**Solution**:
```bash
# Check memory usage
free -h

# Reduce worker concurrency in .env
echo "CELERY_WORKER_CONCURRENCY=1" >> .env

# Restart services (development mode)
docker compose -f docker-compose.yml -f docker-compose.dev.yml down
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Or production mode
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d --build
```

#### Node.js Version Issues

**Problem**: Vite requires Node.js 20.19+ or 22.12+

**Solution**:
```bash
# Update Node.js using nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
source ~/.bashrc
nvm install 22
nvm use 22
node --version
```

---

## Quick Reference Commands

### Windows (Development Mode - Recommended)

```powershell
# Complete reset and restart with hot reload
cd C:\Users\Sultan\Documents
docker compose -f brainda/docker-compose.yml -f brainda/docker-compose.dev.yml down -v
Remove-Item -Recurse -Force brainda
git clone <repo-url> brainda
cd brainda
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

### Windows (Production Mode)

```powershell
# Complete reset and restart with production build
cd C:\Users\Sultan\Documents
docker compose -f brainda/docker-compose.prod.yml down -v
Remove-Item -Recurse -Force brainda
git clone <repo-url> brainda
cd brainda
docker compose -f docker-compose.prod.yml up -d --build
```

### Unraid (Development Mode - Recommended)

```bash
# Complete reset and restart with hot reload
cd /mnt/user/appdata
docker compose -f brainda/docker-compose.yml -f brainda/docker-compose.dev.yml down -v
rm -rf brainda
git clone <repo-url> brainda
cd brainda
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

### Unraid (Production Mode)

```bash
# Complete reset and restart with production build
cd /mnt/user/appdata
docker compose -f brainda/docker-compose.prod.yml down -v
rm -rf brainda
git clone <repo-url> brainda
cd brainda
docker compose -f docker-compose.prod.yml up -d --build
```

---

## Additional Resources

- **Docker Setup Guide**: See [DOCKER_SETUP.md](./DOCKER_SETUP.md) for comprehensive Docker configuration documentation
- **Docker Quick Start**: See [DOCKER_QUICKSTART.md](./DOCKER_QUICKSTART.md) for quick reference commands
- **Main Documentation**: See [CLAUDE.md](./CLAUDE.md) for detailed architecture
- **Environment Variables**: See `.env.example` for all available configuration options
- **Testing**: See [CLAUDE.md#Testing](./CLAUDE.md#testing) for integration test instructions
- **API Documentation**: Backend API runs on http://localhost:8000 with automatic OpenAPI docs at `/docs`

## Docker Configuration Modes

Brainda now supports three Docker configurations:

1. **Development Mode** (Recommended for development)
   - Command: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d`
   - Features: Hot reload for frontend + backend, no rebuilds needed
   - Frontend: http://localhost:3000
   - Backend: http://localhost:8000

2. **Production Mode** (Recommended for deployment)
   - Command: `docker compose -f docker-compose.prod.yml up -d --build`
   - Features: Optimized build, single endpoint, smaller images
   - Everything: http://localhost:8000

3. **Legacy Mode** (Not recommended)
   - Command: `docker-compose up -d` + manual `npm run dev`
   - Only use if you need to run frontend outside Docker

See [DOCKER_SETUP.md](./DOCKER_SETUP.md) for detailed documentation.

---

## Support

If you encounter issues not covered in this guide:

1. Check logs:
   - Development: `docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f orchestrator frontend`
   - Production: `docker compose -f docker-compose.prod.yml logs -f orchestrator`
2. Verify all services are healthy:
   - Development: `docker compose -f docker-compose.yml -f docker-compose.dev.yml ps`
   - Production: `docker compose -f docker-compose.prod.yml ps`
3. Review [DOCKER_SETUP.md](./DOCKER_SETUP.md) for troubleshooting
4. Review [CLAUDE.md](./CLAUDE.md) for architecture details
5. Check browser console (F12) for frontend errors
