#!/usr/bin/env bash
set -euo pipefail
POOL="${1:-}"
if [ -z "$POOL" ]; then
  echo "Usage: $0 <blue|green>"
  exit 1
fi
if [ "$POOL" != "blue" ] && [ "$POOL" != "green" ]; then
  echo "Invalid pool: $POOL"
  exit 2
fi

OUT="nginx/nginx.conf"
if [ "$POOL" = "green" ]; then
  cat > "$OUT" <<'EOF'
upstream backend_pool {
    server app_green:8082 max_fails=1 fail_timeout=2s;
    server app_blue:8081 backup;
}

server {
    listen 80;
    server_name _;
    client_body_timeout 5s;
    client_header_timeout 5s;
    send_timeout 10s;
    location / {
        proxy_pass http://backend_pool;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 2s;
        proxy_send_timeout 5s;
        proxy_read_timeout 7s;
        proxy_next_upstream error timeout http_500 http_502 http_503 http_504;
        proxy_next_upstream_tries 2;
        proxy_next_upstream_timeout 10s;
        proxy_buffering off;
    }
}
EOF
else
  cat > "$OUT" <<'EOF'
upstream backend_pool {
    server app_blue:8081 max_fails=1 fail_timeout=2s;
    server app_green:8082 backup;
}

server {
    listen 80;
    server_name _;
    client_body_timeout 5s;
    client_header_timeout 5s;
    send_timeout 10s;
    location / {
        proxy_pass http://backend_pool;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 2s;
        proxy_send_timeout 5s;
        proxy_read_timeout 7s;
        proxy_next_upstream error timeout http_500 http_502 http_503 http_504;
        proxy_next_upstream_tries 2;
        proxy_next_upstream_timeout 10s;
        proxy_buffering off;
    }
}
EOF
fi

echo "Switched active pool to: $POOL"
docker compose up -d nginx >/dev/null 2>&1 || true
sleep 1
if docker ps --format '{{.Names}}' | grep -q '^nginx$'; then
  docker exec nginx nginx -t && docker exec nginx nginx -s reload
  echo "nginx reloaded successfully."
fi