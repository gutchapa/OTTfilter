#!/bin/bash

# OTT Filter - Deploy and Run Script (Linux/Mac)
# Run this script to pull latest code and start both backend and frontend

echo "🚀 OTT Filter Deployment Script"
echo "================================"
echo ""

# Step 1: Pull latest code
echo "📥 Step 1: Pulling latest code from branch..."
git fetch origin
git checkout claude/refactor-modular-011CUxA7enEtHUZHSL1WZbaa
git pull origin claude/refactor-modular-011CUxA7enEtHUZHSL1WZbaa

if [ $? -ne 0 ]; then
    echo "❌ Git pull failed!"
    exit 1
fi

echo "✅ Code updated successfully"
echo ""

# Step 2: Backend Setup
echo "🔧 Step 2: Setting up Backend..."
cd backend

# Check if venv exists, create if not
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate venv
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing/updating Python dependencies..."
pip install -r requirements.txt --quiet

if [ $? -ne 0 ]; then
    echo "❌ Backend dependencies installation failed!"
    exit 1
fi

echo "✅ Backend setup complete"
echo ""

# Step 3: Start Backend
echo "🚀 Step 3: Starting Backend Server..."
echo "Backend will run on http://localhost:8000"

# Start backend in background
nohup python server.py > backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

sleep 3
echo "✅ Backend started"
echo ""

# Step 4: Frontend Setup
echo "🔧 Step 4: Setting up Frontend..."
cd ../frontend

# Install dependencies
echo "Installing/updating npm dependencies..."
npm install --legacy-peer-deps --silent

if [ $? -ne 0 ]; then
    echo "❌ Frontend dependencies installation failed!"
    exit 1
fi

echo "✅ Frontend setup complete"
echo ""

# Step 5: Start Frontend
echo "🚀 Step 5: Starting Frontend..."
echo "Frontend will run on http://localhost:3000"

# Start frontend
npm start

echo ""
echo "================================"
echo "🎉 Deployment Complete!"
echo "================================"
echo ""
echo "📍 Backend:  http://localhost:8000"
echo "📍 Frontend: http://localhost:3000"
echo ""
echo "💡 Backend PID: $BACKEND_PID"
echo "   To stop backend: kill $BACKEND_PID"
