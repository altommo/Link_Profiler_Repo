# This file is for demonstration and needs to be adapted to your Nginx setup.
# It should be placed in /etc/nginx/sites-available/your_domain.conf
# and symlinked to /etc/nginx/sites-enabled/

server {
    listen 80;
    server_name www.yspanel.com api.yspanel.com linkprofiler.yspanel.com monitor.yspanel.com; # Add all your domains here
    return 301 https://$host$request_uri; # Redirect HTTP to HTTPS
}

server {
    listen 443 ssl http2; # Listen for HTTPS traffic
    server_name www.yspanel.com api.yspanel.com linkprofiler.yspanel.com monitor.yspanel.com; # Add all your domains here

    # SSL certificate paths (replace with your actual paths, e.g., from Certbot)
    ssl_certificate /etc/letsencrypt/live/www.yspanel.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/www.yspanel.com/privkey.pem;
    ssl_trusted_certificate /etc/letsencrypt/live/www.yspanel.com/chain.pem;

    # Basic SSL configuration (consider using a stronger one based on security best practices)
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers EECDH+AESGCM:EDH+AESGCM:AES256+EECDH:AES256+EDH;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Remove any 'add_header Access-Control-Allow-Origin ...;' directives from here.
    # FastAPI's CORSMiddleware will handle the Access-Control-Allow-Origin header.

    location / {
        proxy_pass http://127.0.0.1:8000; # Forward requests to your FastAPI app (main API)
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off; # Important for correct URL rewriting
    }

    # If you have a separate monitoring dashboard service on port 8001,
    # you might need a separate location block for it, or a separate server block
    # if it's on a different subdomain. Example for monitor.yspanel.com:
    # This assumes monitor.yspanel.com is served by the Python monitoring dashboard app on port 8001
    location /monitor/ { # Or just / if monitor.yspanel.com is dedicated to the dashboard
        proxy_pass http://127.0.0.1:8001/; # Forward requests to your Monitoring Dashboard app
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }

    # If you want to serve static files directly from Nginx
    # location /static/ {
    #     alias /opt/Link_Profiler_Repo/Link_Profiler/static/;
    # }
}
