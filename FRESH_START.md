# Fresh Start Instructions

This guide provides step-by-step commands to completely reset and start fresh with the VIB application on both Windows and Unraid servers.

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

#### Step 5: Start Backend Services

```powershell
# Start all Docker services (backend)
docker-compose up -d

# Wait for services to be healthy (check logs)
docker-compose logs -f orchestrator

# Press Ctrl+C when you see "Application startup complete"
```

#### Step 6: Install and Start Frontend

```powershell
# Navigate to frontend directory
cd app\web

# Install dependencies
npm install

# Start development server
npm run dev

# Frontend will be available at http://localhost:3000 (or next available port)
```

### Option 2: Keep Git History (Soft Reset)

```powershell
# Navigate to project
cd C:\Users\Sultan\Documents\brainda

# Stop all processes
Get-Process node -ErrorAction SilentlyContinue | Stop-Process -Force
docker-compose down -v

# Reset all changes and clean untracked files
git reset --hard HEAD
git clean -fdx

# Pull latest changes
git pull

# Start services
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

#### Step 6: Start Backend Services

```bash
# Start all Docker services
docker-compose up -d

# Or newer syntax
docker compose up -d

# Check status
docker-compose ps

# View logs to ensure services are healthy
docker-compose logs -f orchestrator

# Press Ctrl+C to exit logs
```

#### Step 7: Install and Start Frontend

```bash
# Navigate to frontend directory
cd app/web

# Install dependencies
npm install

# Start development server in background
nohup npm run dev > /tmp/vite.log 2>&1 &

# View the log
tail -f /tmp/vite.log

# Frontend will be available at http://<unraid-ip>:3000
```

### Option 2: Soft Reset (Keep Git History)

```bash
# Navigate to project
cd /mnt/user/appdata/brainda

# Stop all services
docker-compose down -v

# Kill node processes
pkill -9 node

# Reset git and clean
git reset --hard HEAD
git clean -fdx

# Pull latest
git pull

# Restart services
docker-compose up -d

# Reinstall frontend dependencies
cd app/web
npm install
nohup npm run dev > /tmp/vite.log 2>&1 &
```

---

## Post-Installation Steps

### 1. Verify Backend Health

**Windows:**
```powershell
# Check API health
curl http://localhost:8000/api/v1/health

# Check all services are running
docker-compose ps

# All services should show "Up (healthy)" status
```

**Unraid:**
```bash
# Check API health
curl http://localhost:8000/api/v1/health

# Check all services
docker-compose ps
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
- **Windows**: http://localhost:3001 (or port shown in terminal)
- **Unraid**: http://<unraid-server-ip>:3001

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
- **Windows**: http://localhost:3001
- **Unraid**: http://<unraid-server-ip>:3001

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
# Force remove all containers
docker rm -f $(docker ps -aq)

# Remove all volumes
docker volume prune -f
```

#### Database Password Mismatch

**Problem**: `password authentication failed for user "vib"`

**Solution**:
```powershell
# Must remove volumes to reset database
docker-compose down -v
docker-compose up -d
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

**Solution**:
```bash
# Check if Vite is running
ps aux | grep vite

# Check the log
tail -f /tmp/vite.log

# Restart if needed
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

# Restart services
docker-compose down
docker-compose up -d
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

### Windows

```powershell
# Complete reset and restart
cd C:\Users\Sultan\Documents
docker-compose -f brainda/docker-compose.yml down -v
Remove-Item -Recurse -Force brainda
git clone <repo-url> brainda
cd brainda
docker-compose up -d
cd app\web
npm install
npm run dev
```

### Unraid

```bash
# Complete reset and restart
cd /mnt/user/appdata
docker-compose -f brainda/docker-compose.yml down -v
rm -rf brainda
git clone <repo-url> brainda
cd brainda
docker-compose up -d
cd app/web
npm install
nohup npm run dev > /tmp/vite.log 2>&1 &
```

---

## Additional Resources

- **Main Documentation**: See [CLAUDE.md](./CLAUDE.md) for detailed architecture
- **Environment Variables**: See `.env.example` for all available configuration options
- **Testing**: See [CLAUDE.md#Testing](./CLAUDE.md#testing) for integration test instructions
- **API Documentation**: Backend API runs on http://localhost:8000 with automatic OpenAPI docs at `/docs`

---

## Support

If you encounter issues not covered in this guide:

1. Check logs: `docker-compose logs -f orchestrator`
2. Check frontend logs: Look at the terminal running `npm run dev`
3. Verify all services are healthy: `docker-compose ps`
4. Review [CLAUDE.md](./CLAUDE.md) for architecture details
5. Check browser console (F12) for frontend errors
