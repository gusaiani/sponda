#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 1: Install Nginx and certbot nginx plugin ==="
apt-get update
apt-get install -y nginx python3-certbot-nginx

echo "=== Step 2: Stop Nginx (it auto-starts after install) ==="
systemctl stop nginx

echo "=== Step 3: Generate SSL params for Nginx (if missing) ==="
if [ ! -f /etc/letsencrypt/options-ssl-nginx.conf ]; then
    certbot install --nginx --dry-run 2>/dev/null || true
    # Manual fallback: download the standard options file
    curl -sL https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf \
        -o /etc/letsencrypt/options-ssl-nginx.conf
fi
if [ ! -f /etc/letsencrypt/ssl-dhparams.pem ]; then
    curl -sL https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem \
        -o /etc/letsencrypt/ssl-dhparams.pem
fi

echo "=== Step 4: Copy Nginx site configs ==="
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
for conf in "$SCRIPT_DIR"/*.conf; do
    cp "$conf" /etc/nginx/sites-available/
    name="$(basename "$conf")"
    ln -sf "/etc/nginx/sites-available/$name" "/etc/nginx/sites-enabled/$name"
done

# Remove default Nginx site
rm -f /etc/nginx/sites-enabled/default

echo "=== Step 5: Test Nginx config ==="
nginx -t

echo "=== Step 6: Stop Apache, start Nginx ==="
systemctl stop apache2
systemctl disable apache2
systemctl start nginx
systemctl enable nginx

echo "=== Step 7: Update certbot renewal configs to use nginx ==="
for renewal in /etc/letsencrypt/renewal/*.conf; do
    sed -i 's/authenticator = apache/authenticator = nginx/' "$renewal"
    sed -i 's/installer = apache/installer = nginx/' "$renewal"
done

echo "=== Step 8: Bump Gunicorn workers to 3 ==="
sed -i 's/--workers 2/--workers 3/' /etc/systemd/system/sponda.service
systemctl daemon-reload
systemctl restart sponda

echo "=== Step 9: Verify ==="
systemctl status nginx --no-pager
systemctl status sponda --no-pager
echo ""
echo "All done. Test your sites!"
