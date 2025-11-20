#!/bin/bash

# Cleanup script to kill processes on ports 8081 and 10000
# Run this if you get "port already in use" errors

echo "======================================"
echo "OTTfilter - Port Cleanup"
echo "======================================"
echo ""

# Check what's using port 8081
echo "Checking port 8081 (Backend)..."
if lsof -ti:8081 > /dev/null 2>&1; then
    echo "  Found process on port 8081:"
    lsof -i:8081
    echo "  Killing process..."
    lsof -ti:8081 | xargs kill -9 2>/dev/null
    echo "  ✅ Port 8081 freed"
else
    echo "  ✅ Port 8081 is already free"
fi

echo ""

# Check what's using port 10000
echo "Checking port 10000 (Frontend)..."
if lsof -ti:10000 > /dev/null 2>&1; then
    echo "  Found process on port 10000:"
    lsof -i:10000
    echo "  Killing process..."
    lsof -ti:10000 | xargs kill -9 2>/dev/null
    echo "  ✅ Port 10000 freed"
else
    echo "  ✅ Port 10000 is already free"
fi

echo ""
echo "======================================"
echo "Ports are now free! You can start PM2:"
echo "  pm2 start ecosystem.config.js"
echo "======================================"
