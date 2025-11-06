#!/bin/bash
# Deploy OTTfilter backend to VPS

set -e

VPS_HOST="103.118.17.51"
VPS_USER="root"
BRANCH="claude/health-check-repo-011CUcrUBdWGKXuKfjcceTWQ"

echo "🚀 Deploying OTTfilter to VPS..."

# Create a deployment script to run on VPS
cat > /tmp/deploy_commands.sh << 'DEPLOY_EOF'
cd /root/OTTfilter
echo "📥 Pulling latest changes..."
git fetch origin
git checkout claude/health-check-repo-011CUcrUBdWGKXuKfjcceTWQ
git pull origin claude/health-check-repo-011CUcrUBdWGKXuKfjcceTWQ

echo "🔄 Restarting backend service..."
systemctl restart ottfilter-backend

echo "⏳ Waiting for service to start..."
sleep 3

echo "📊 Checking service status..."
systemctl status ottfilter-backend --no-pager | head -20

echo "📝 Recent logs:"
tail -30 /root/OTTfilter/backend/backend.log

echo "✅ Deployment complete!"
DEPLOY_EOF

# Transfer and execute
echo "Transferring deployment script..."
scp -o StrictHostKeyChecking=no /tmp/deploy_commands.sh ${VPS_USER}@${VPS_HOST}:/tmp/

echo "Executing deployment on VPS..."
ssh -o StrictHostKeyChecking=no ${VPS_USER}@${VPS_HOST} "bash /tmp/deploy_commands.sh"

echo "🎉 Deployment successful!"
