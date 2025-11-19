#!/usr/bin/env bash

# build_on_vps.sh – Build the frontend on a low‑memory VPS
# ------------------------------------------------------
# This script installs a compatible Node LTS version (20) via nvm,
# installs npm dependencies (using --legacy-peer-deps to avoid peer conflicts),
# and runs the production build with an increased memory limit.
# It is safe to run multiple times – it will reuse existing installations.

set -e

# 1. Install nvm if not present
if [ -z "$(command -v nvm)" ]; then
  echo "Installing nvm..."
  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
  # Load nvm into the current shell
  export NVM_DIR="$HOME/.nvm"
  [ -s "$NVM_DIR/nvm.sh" ] && \ . "$NVM_DIR/nvm.sh"
fi

# 2. Use Node 20 (LTS) – install if missing
nvm install 20
nvm use 20

# Verify Node version
node -v
npm -v

# 3. Navigate to the frontend directory
cd "$(dirname "$0")/../frontend"

# 4. Install dependencies (skip peer‑dependency errors)
npm install --legacy-peer-deps

# 5. Build with increased memory (4 GB) – adjust if needed
export NODE_OPTIONS="--max-old-space-size=4096"
npm run build

echo "✅ Frontend build completed successfully."
