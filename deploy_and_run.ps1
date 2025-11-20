# OTT Filter - Deploy and Run Script
# Run this script to pull latest code and start both backend and frontend

Write-Host "🚀 OTT Filter Deployment Script" -ForegroundColor Cyan
Write-Host "================================`n" -ForegroundColor Cyan

# Step 1: Pull latest code
Write-Host "📥 Step 1: Pulling latest code from branch..." -ForegroundColor Yellow
git fetch origin
git checkout claude/refactor-modular-011CUxA7enEtHUZHSL1WZbaa
git pull origin claude/refactor-modular-011CUxA7enEtHUZHSL1WZbaa

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Git pull failed!" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Code updated successfully`n" -ForegroundColor Green

# Step 2: Backend Setup
Write-Host "🔧 Step 2: Setting up Backend..." -ForegroundColor Yellow
cd backend

# Check if venv exists, create if not
if (-not (Test-Path "venv")) {
    Write-Host "Creating Python virtual environment..." -ForegroundColor Gray
    python -m venv venv
}

# Activate venv
Write-Host "Activating virtual environment..." -ForegroundColor Gray
.\venv\Scripts\Activate.ps1

# Install dependencies
Write-Host "Installing/updating Python dependencies..." -ForegroundColor Gray
pip install -r requirements.txt --quiet

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Backend dependencies installation failed!" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Backend setup complete`n" -ForegroundColor Green

# Step 3: Start Backend
Write-Host "🚀 Step 3: Starting Backend Server..." -ForegroundColor Yellow
Write-Host "Backend will run on http://localhost:8000" -ForegroundColor Gray

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD'; .\venv\Scripts\Activate.ps1; python server.py"

Start-Sleep -Seconds 3
Write-Host "✅ Backend started in new window`n" -ForegroundColor Green

# Step 4: Frontend Setup
Write-Host "🔧 Step 4: Setting up Frontend..." -ForegroundColor Yellow
cd ..\frontend

# Install dependencies
Write-Host "Installing/updating npm dependencies..." -ForegroundColor Gray
npm install --legacy-peer-deps --silent

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Frontend dependencies installation failed!" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Frontend setup complete`n" -ForegroundColor Green

# Step 5: Start Frontend
Write-Host "🚀 Step 5: Starting Frontend..." -ForegroundColor Yellow
Write-Host "Frontend will run on http://localhost:3000" -ForegroundColor Gray

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD'; npm start"

Start-Sleep -Seconds 3
Write-Host "✅ Frontend started in new window`n" -ForegroundColor Green

# Done
Write-Host "`n================================" -ForegroundColor Cyan
Write-Host "🎉 Deployment Complete!" -ForegroundColor Green
Write-Host "================================`n" -ForegroundColor Cyan

Write-Host "📍 Backend:  http://localhost:8000" -ForegroundColor White
Write-Host "📍 Frontend: http://localhost:3000`n" -ForegroundColor White

Write-Host "💡 The app should open automatically in your browser." -ForegroundColor Gray
Write-Host "   If not, visit http://localhost:3000 manually.`n" -ForegroundColor Gray

Write-Host "Press any key to exit this window..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
