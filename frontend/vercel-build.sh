#!/bin/bash

# Vercel Build Script - bypasses CRACO issues

echo "📦 Installing dependencies..."
npm install --legacy-peer-deps --production=false

echo "🔧 Building with standard react-scripts (bypassing CRACO)..."
# Temporarily use react-scripts directly instead of craco
npx react-scripts build

echo "✅ Build complete!"
