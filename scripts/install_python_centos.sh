#!/bin/bash

# Exit on error
set -e

echo "🚀 Starting Python 3.10 Installation for CentOS..."

# 1. Install Build Dependencies
echo "📦 Installing build dependencies..."
sudo yum groupinstall -y "Development Tools"
sudo yum install -y openssl-devel bzip2-devel libffi-devel zlib-devel wget make

# 2. Download Python 3.10 Source
echo "⬇️ Downloading Python 3.10.13..."
cd /usr/src
sudo wget https://www.python.org/ftp/python/3.10.13/Python-3.10.13.tgz

# 3. Extract and Compile
echo "🔨 Compiling Python (this may take a few minutes)..."
sudo tar xzf Python-3.10.13.tgz
cd Python-3.10.13
sudo ./configure --enable-optimizations
sudo make altinstall

# 4. Cleanup
echo "🧹 Cleaning up..."
sudo rm /usr/src/Python-3.10.13.tgz

# 5. Verify Installation
echo "✅ Verifying installation..."
if command -v python3.10 &> /dev/null; then
    echo "🎉 Python 3.10 installed successfully!"
    python3.10 --version
else
    echo "❌ Python 3.10 installation failed."
    exit 1
fi

echo "--------------------------------------------------"
echo "👉 Now run the following commands to setup your project:"
echo ""
echo "cd /path/to/your/project/backend"
echo "rm -rf venv"
echo "/usr/local/bin/python3.10 -m venv venv"
echo "source venv/bin/activate"
echo "pip install -r requirements.txt"
echo "--------------------------------------------------"
