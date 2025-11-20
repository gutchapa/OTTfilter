#!/bin/bash

# PM2 Setup Script for OTTfilter
# This script sets up PM2 to manage both frontend and backend processes

set -e

echo "======================================"
echo "OTTfilter PM2 Setup"
echo "======================================"
echo ""

# Change to app directory
cd /var/www/OTTfilter

# Check if PM2 is installed
if ! command -v pm2 &> /dev/null; then
    echo "📦 Installing PM2 globally..."
    npm install -g pm2
else
    echo "✅ PM2 already installed: $(pm2 --version)"
fi

# Check if serve is installed
if ! command -v serve &> /dev/null; then
    echo "📦 Installing serve globally..."
    npm install -g serve
else
    echo "✅ serve already installed"
fi

# Create log directories
echo ""
echo "📁 Creating log directories..."
mkdir -p backend/logs
mkdir -p frontend/logs

# Build frontend
echo ""
echo "🏗️  Building frontend..."
cd frontend
if [ ! -d "build" ]; then
    echo "Running npm install..."
    npm install --legacy-peer-deps
fi
echo "Running npm build..."
npm run build
cd ..

# Kill any processes on ports 8081 and 10000
echo ""
echo "🧹 Cleaning up old processes..."
lsof -ti:8081 | xargs kill -9 2>/dev/null || echo "  Port 8081 is free"
lsof -ti:10000 | xargs kill -9 2>/dev/null || echo "  Port 10000 is free"

echo ""
echo "✅ Setup complete!"
echo ""
echo "======================================"
echo "Next Steps:"
echo "======================================"
echo ""
echo "1. Start services (ports are now free):"
echo "   pm2 start ecosystem.config.js"
echo ""
echo "2. Enable auto-start on reboot:"
echo "   pm2 startup"
echo "   pm2 save"
echo ""
echo "======================================"
echo "PM2 Commands:"
echo "======================================"
echo ""
echo "View status:    pm2 status"
echo "View logs:      pm2 logs"
echo "Restart:        pm2 restart all"
echo "Stop:           pm2 stop all"
echo "Monitor:        pm2 monit"
echo ""
echo "Frontend: http://your-ip:10000"
echo "Backend:  http://your-ip:8081"
echo ""
echo "======================================"
