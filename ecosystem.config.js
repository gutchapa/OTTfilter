module.exports = {
  apps: [
    {
      name: 'ottfilter-backend',
      script: 'venv/bin/python',
      args: '-m uvicorn app.main:app --host 0.0.0.0 --port 8081',
      cwd: '/var/www/OTTfilter/backend',
      interpreter: 'none',
      env: {
        PYTHONUNBUFFERED: '1',
        PATH: '/var/www/OTTfilter/backend/venv/bin:' + process.env.PATH,
      },
      error_file: '/var/www/OTTfilter/backend/logs/pm2-error.log',
      out_file: '/var/www/OTTfilter/backend/logs/pm2-out.log',
      log_file: '/var/www/OTTfilter/backend/logs/pm2-combined.log',
      time: true,
      autorestart: true,
      max_restarts: 10,
      min_uptime: '10s',
      restart_delay: 4000,
      watch: false
    },
    {
      name: 'ottfilter-frontend',
      script: 'npx',
      args: 'serve -s build -l 10000',
      cwd: '/var/www/OTTfilter/frontend',
      interpreter: 'none',
      env: {
        NODE_ENV: 'production',
      },
      error_file: '/var/www/OTTfilter/frontend/logs/pm2-error.log',
      out_file: '/var/www/OTTfilter/frontend/logs/pm2-out.log',
      log_file: '/var/www/OTTfilter/frontend/logs/pm2-combined.log',
      time: true,
      autorestart: true,
      max_restarts: 10,
      min_uptime: '10s',
      restart_delay: 4000,
      watch: false
    }
  ]
};
