#!/bin/bash

# Quick Deploy Script using PM2
# Pulls latest code, rebuilds, and restarts services

set -e

echo "======================================"
echo "OTTfilter - Quick Deploy with PM2"
echo "======================================"
echo ""

# Change to app directory
cd /var/www/OTTfilter

# Git pull
echo "📥 Pulling latest code..."
git pull origin claude/refactor-modular-011CUxA7enEtHUZHSL1WZbaa

# Backend: Install dependencies if requirements.txt changed
echo ""
echo "🐍 Checking backend dependencies..."
cd backend
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    pip install -r requirements.txt --quiet
else
    echo "⚠️  Virtual environment not found. Please create one:"
    echo "   cd /var/www/OTTfilter/backend"
    echo "   python3 -m venv venv"
    echo "   source venv/bin/activate"
    echo "   pip install -r requirements.txt"
    exit 1
fi
cd ..

# Frontend: Rebuild
echo ""
echo "🏗️  Rebuilding frontend..."
cd frontend
npm install --quiet
npm run build
cd ..

# Restart PM2 services
echo ""
echo "🔄 Restarting PM2 services..."

if pm2 list | grep -q "ottfilter"; then
    echo "Restarting existing services..."
    pm2 restart ecosystem.config.js
else
    echo "Starting services for the first time..."
    pm2 start ecosystem.config.js
fi

echo ""
echo "✅ Deploy complete!"
echo ""
echo "Frontend: http://your-ip:10000"
echo "Backend:  http://your-ip:8081"
echo ""
echo "View status: pm2 status"
echo "View logs:   pm2 logs"
echo ""
