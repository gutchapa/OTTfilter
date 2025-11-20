#!/bin/bash

# PM2 Setup Script for OTTfilter
# This script sets up PM2 to manage both frontend and backend processes

set -e

echo "======================================"
echo "OTTfilter PM2 Setup"
echo "======================================"
echo ""

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
    npm install
fi
echo "Running npm build..."
npm run build
cd ..

echo ""
echo "✅ Setup complete!"
echo ""
echo "======================================"
echo "PM2 Commands:"
echo "======================================"
echo ""
echo "Start all services:"
echo "  pm2 start ecosystem.config.js"
echo ""
echo "Stop all services:"
echo "  pm2 stop all"
echo ""
echo "Restart all services:"
echo "  pm2 restart all"
echo ""
echo "View logs:"
echo "  pm2 logs                    # All logs"
echo "  pm2 logs ottfilter-backend  # Backend only"
echo "  pm2 logs ottfilter-frontend # Frontend only"
echo ""
echo "View status:"
echo "  pm2 status"
echo "  pm2 monit"
echo ""
echo "Auto-start on server reboot:"
echo "  pm2 startup"
echo "  pm2 save"
echo ""
echo "Delete all processes:"
echo "  pm2 delete all"
echo ""
echo "======================================"
