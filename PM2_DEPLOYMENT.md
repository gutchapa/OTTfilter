# OTTfilter PM2 Deployment Guide

This guide explains how to deploy and manage OTTfilter using PM2 process manager on your VPS.

## Why PM2?

- **Auto-restart**: Automatically restarts if app crashes
- **Process monitoring**: View CPU, memory usage in real-time
- **Log management**: Centralized logs with timestamps
- **Startup script**: Auto-start on server reboot
- **Zero-downtime reload**: Update without downtime

## Initial Setup (First Time Only)

### 1. Install Node.js (if not already installed)

```bash
# Install Node.js 18.x on CentOS
curl -fsSL https://rpm.nodesource.com/setup_18.x | sudo bash -
sudo yum install -y nodejs
```

### 2. Run Setup Script

```bash
cd /root/OTTfilter
./setup_pm2.sh
```

This will:
- Install PM2 globally
- Install `serve` (static file server for frontend)
- Create log directories
- Build the frontend

### 3. Configure PM2 Paths

Edit `ecosystem.config.js` and update the `cwd` paths if your app is not in `/root/OTTfilter`:

```javascript
cwd: '/your/actual/path/OTTfilter/backend',
cwd: '/your/actual/path/OTTfilter/frontend',
```

### 4. Start Services

```bash
pm2 start ecosystem.config.js
```

### 5. Enable Auto-Start on Reboot

```bash
pm2 startup
# Copy and run the command it outputs
pm2 save
```

## Daily Usage

### Deploy New Changes

```bash
cd /root/OTTfilter
./deploy_pm2.sh
```

This automatically:
1. Pulls latest code
2. Installs dependencies
3. Rebuilds frontend
4. Restarts services

### Common PM2 Commands

```bash
# View all processes
pm2 status

# View real-time logs
pm2 logs

# View backend logs only
pm2 logs ottfilter-backend

# View frontend logs only
pm2 logs ottfilter-frontend

# Monitor CPU/Memory
pm2 monit

# Restart all services
pm2 restart all

# Restart specific service
pm2 restart ottfilter-backend

# Stop all services
pm2 stop all

# Delete all processes (stops and removes)
pm2 delete all

# View detailed info
pm2 show ottfilter-backend
```

## Accessing the App

- **Frontend**: http://your-vps-ip:3000
- **Backend API**: http://your-vps-ip:8081

If using Apache as reverse proxy, configure it to proxy:
- Port 80/443 → Port 3000 (frontend)
- Port 80/443/api → Port 8081 (backend)

## Troubleshooting

### Services not starting?

```bash
# Check PM2 logs
pm2 logs --lines 100

# Check if ports are in use
lsof -i :8081  # Backend
lsof -i :3000  # Frontend
```

### Backend crashes?

```bash
# View backend logs
pm2 logs ottfilter-backend --lines 50

# Check Python virtual environment
cd backend
source venv/bin/activate
python -c "import fastapi"  # Should not error
```

### Frontend not building?

```bash
cd frontend
npm install
npm run build

# Check build output
ls -la build/
```

### Clear MongoDB cache after changes

```bash
cd /root/OTTfilter/backend
source venv/bin/activate
python clear_cache.py

# Restart backend to fetch fresh data
pm2 restart ottfilter-backend
```

## Production Checklist

- [ ] PM2 installed and services running
- [ ] Auto-startup enabled (`pm2 startup` + `pm2 save`)
- [ ] Apache/Nginx reverse proxy configured
- [ ] Firewall allows ports 3000, 8081 (or proxy ports)
- [ ] Environment variables in `/root/OTTfilter/backend/.env`
- [ ] MongoDB running and accessible
- [ ] SSL certificate configured (optional)

## File Structure

```
/root/OTTfilter/
├── ecosystem.config.js      # PM2 configuration
├── setup_pm2.sh            # Initial setup script
├── deploy_pm2.sh           # Quick deploy script
├── backend/
│   ├── app/
│   ├── venv/
│   ├── requirements.txt
│   ├── logs/               # PM2 logs
│   └── .env                # API keys
└── frontend/
    ├── build/              # Production build
    ├── src/
    ├── package.json
    └── logs/               # PM2 logs
```

## Advanced Configuration

### Change Ports

Edit `ecosystem.config.js`:

```javascript
// Backend port
args: '-m uvicorn app.main:app --host 0.0.0.0 --port 8082',

// Frontend port
args: '-s build -l 3001',
```

Then restart: `pm2 restart all`

### Watch for File Changes (Development)

Add to ecosystem.config.js:

```javascript
watch: true,
ignore_watch: ['node_modules', 'logs', '.git'],
```

### Cluster Mode (Multiple Instances)

For better performance, run multiple backend instances:

```javascript
instances: 2,  // Or 'max' for all CPU cores
exec_mode: 'cluster'
```

## Updating to Latest Code

```bash
cd /root/OTTfilter
git pull origin claude/refactor-modular-011CUxA7enEtHUZHSL1WZbaa
./deploy_pm2.sh
```

That's it! PM2 handles the rest.
