# OmniDownloader - Hostinger VPS Deployment Guide

This guide covers deploying the OmniDownloader platform (FastAPI Gateway + Microservices) on a Hostinger VPS running Ubuntu.

## 1. Initial VPS Setup

### SSH into your Hostinger VPS
```bash
ssh root@your_vps_ip
```

### Update System Packages
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv nginx ffmpeg git curl supervisor
```

> **Note on `ffmpeg`:** FFmpeg is required for the Instagram downloader microservice to properly merge high-quality video and audio streams.

## 2. Project Setup

### Clone or Upload Your Code
Upload your project files to `/var/www/omnidownloader`. 

```bash
mkdir -p /var/www/omnidownloader
# Upload your files here
cd /var/www/omnidownloader
```

### Setup Virtual Environments & Install Dependencies

You need to setup virtual environments for the gateway and each microservice.

**For the Gateway:**
```bash
cd /var/www/omnidownloader/main-platform
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install uvicorn
deactivate
```

**For the Instagram Microservice:**
```bash
cd /var/www/omnidownloader/instagrm
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install uvicorn yt-dlp ffmpeg-python
deactivate
```
*(Repeat for other microservices)*

## 3. Configure Supervisor (Process Management)

Supervisor will keep your FastAPI apps running in the background and restart them if they crash.

Create a new configuration file:
```bash
sudo nano /etc/supervisor/conf.d/omnidownloader.conf
```

Paste the following configuration (adjust paths if necessary):

```ini
[program:omni-gateway]
command=/var/www/omnidownloader/main-platform/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
directory=/var/www/omnidownloader/main-platform
autostart=true
autorestart=true
stderr_logfile=/var/log/omni-gateway.err.log
stdout_logfile=/var/log/omni-gateway.out.log
user=root

[program:omni-instagram]
command=/var/www/omnidownloader/instagrm/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8002
directory=/var/www/omnidownloader/instagrm
autostart=true
autorestart=true
stderr_logfile=/var/log/omni-instagram.err.log
stdout_logfile=/var/log/omni-instagram.out.log
user=root
```

Update Supervisor:
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl status
```
*Both services should now be listed as RUNNING.*

## 4. Configure Nginx (Reverse Proxy)

Nginx will serve your static files and route API traffic to the correct FastAPI backend.

Create a new Nginx configuration:
```bash
sudo nano /etc/nginx/sites-available/omnidownloader
```

Paste the following configuration (replace `yourdomain.com` with your actual domain or VPS IP):

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    # Serve Static Files
    location /static/ {
        alias /var/www/omnidownloader/main-platform/gateway/static/;
        expires 30d;
        add_header Cache-Control "public, max-age=2592000";
    }

    # Serve HTML Pages directly
    location / {
        root /var/www/omnidownloader/main-platform/gateway/static;
        index index.html;
        try_files $uri $uri/ $uri.html =404;
    }

    # Proxy /api/ requests to the API Gateway
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable the site and restart Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/omnidownloader /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## 5. SSL / HTTPS (Let's Encrypt)

To secure your site with HTTPS, use Certbot.

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

Follow the prompts to enable HTTPS and automatic redirects.

## 6. Maintenance & Troubleshooting

**View Gateway Logs:**
```bash
tail -f /var/log/omni-gateway.out.log
tail -f /var/log/omni-gateway.err.log
```

**View Instagram Service Logs:**
```bash
tail -f /var/log/omni-instagram.err.log
```

**Restart Services after Code Updates:**
```bash
sudo supervisorctl restart omni-gateway
sudo supervisorctl restart omni-instagram
```

## Summary of Fixes Implemented for Production:
1. **FFmpeg is installed** at the OS level to allow `yt-dlp` to merge DASH video and audio streams seamlessly.
2. **Local Temp Storage** is utilized in the microservice `/downloads/` folder, and FastAPIs `BackgroundTask` ensures files are cleaned up after they are served.
3. **Nginx** handles all the static file serving for maximum performance.
4. **Supervisor** manages the process lifecycle of both the gateway and the microservices.
