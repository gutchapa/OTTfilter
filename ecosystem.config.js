module.exports = {
  apps: [
    {
      name: 'ottfilter-backend',
      script: 'python',
      args: '-m uvicorn app.main:app --host 0.0.0.0 --port 8081',
      cwd: '/root/OTTfilter/backend',
      interpreter: 'none',
      env: {
        PYTHONUNBUFFERED: '1',
      },
      error_file: '/root/OTTfilter/backend/logs/pm2-error.log',
      out_file: '/root/OTTfilter/backend/logs/pm2-out.log',
      log_file: '/root/OTTfilter/backend/logs/pm2-combined.log',
      time: true,
      autorestart: true,
      max_restarts: 10,
      min_uptime: '10s',
      restart_delay: 4000,
      watch: false
    },
    {
      name: 'ottfilter-frontend',
      script: 'serve',
      args: '-s build -l 3000',
      cwd: '/root/OTTfilter/frontend',
      interpreter: 'none',
      env: {
        NODE_ENV: 'production',
      },
      error_file: '/root/OTTfilter/frontend/logs/pm2-error.log',
      out_file: '/root/OTTfilter/frontend/logs/pm2-out.log',
      log_file: '/root/OTTfilter/frontend/logs/pm2-combined.log',
      time: true,
      autorestart: true,
      max_restarts: 10,
      min_uptime: '10s',
      restart_delay: 4000,
      watch: false
    }
  ]
};
