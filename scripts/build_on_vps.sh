#!/bin/bash

# build_on_vps.sh – Safe build for low‑memory VPS
# -------------------------------------------------
# This script ensures we only install what is needed and avoids
# spawning duplicate processes. It:
#   1. Installs nvm (if missing) and uses Node 20 (LTS).
#   2. Skips Node installation if the correct version is already active.
#   3. Installs npm dependencies only when node_modules is absent.
#   4. Sets a memory limit for the build.
#   5. Cleans up any stray headless Chrome processes after the build.

set -e

# 1. Install nvm if not present
if ! command -v nvm >/dev/null 2>&1; then
  echo "Installing nvm..."
  curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
fi

# Load nvm (in case it was just installed)
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"
[ -s "$NVM_DIR/bash_completion" ] && source "$NVM_DIR/bash_completion"

# 2. Use Node 20 if not already active
CURRENT_NODE=$(node -v 2>/dev/null || echo "none")
if [[ "$CURRENT_NODE" != v20* ]]; then
  echo "Installing/using Node 20 (LTS)..."
  nvm install 20
  nvm use 20
else
  echo "Node $CURRENT_NODE already active."
fi

node -v
npm -v

# 3. Navigate to frontend directory
cd "$(dirname "$0")/../frontend"

# 4. Install npm dependencies only if needed
if [ ! -d "node_modules" ]; then
  echo "Installing npm dependencies..."
  npm install --legacy-peer-deps
else
  echo "node_modules already present – skipping npm install."
fi

# 5. Build with increased memory (4 GB) – adjust if needed
export NODE_OPTIONS="--max-old-space-size=4096"
echo "Running production build..."
npm run build

# 6. Clean up any stray headless Chrome processes (common source of OOM)
if pgrep -f "headless_shell" >/dev/null; then
  echo "Killing stray headless_shell processes..."
  pkill -f headless_shell || true
fi

echo "✅ Frontend build completed successfully."
