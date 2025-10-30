# Stage 3 — Observability & Alerts (Blue/Green)

This repository extends the Stage-2 Blue/Green deployment by adding operational visibility and Slack alerts. It uses structured Nginx access logs and a small Python sidecar (`alert_watcher`) that tails logs and posts alerts to Slack when failovers or high 5xx error rates are detected.

## What was added
- `nginx/nginx.conf.template` — structured access log format with pool & release fields.
- `watcher/` — Python watcher sidecar that tails logs and posts Slack alerts.
- `.env.example` — new observability variables (SLACK_WEBHOOK_URL, ERROR_RATE_THRESHOLD, WINDOW_SIZE, ALERT_COOLDOWN_SEC).
- `runbook.md` — operator runbook for alerts & remediation.

## Quick setup (local or EC2)
1. Copy `.env.example` to `.env` and set `SLACK_WEBHOOK_URL` (do **not** commit secrets):
   ```bash
   cp .env.example .env
   # edit .env and set SLACK_WEBHOOK_URL and other vars
   ```

2. Build and start services:
   ```bash
   docker compose pull
   docker compose up -d --build
   ```

3. Verify Nginx log formatting:
   ```bash
   docker exec nginx tail -n 5 /var/log/nginx/access.log
   ```

4. Watch the watcher logs:
   ```bash
   docker logs -f alert_watcher
   ```

## Testing alerts
- **Failover alert**: trigger chaos on the active app:
  ```bash
  curl -X POST "http://35.176.120.145:8081/chaos/start?mode=error"
  ```
  Watch Slack for a failover alert, then stop chaos:
  ```bash
  curl -X POST "http://35.176.120.145:8081/chaos/stop"
  ```

- **Error-rate alert**: run many requests to trigger 5xx and exceed threshold:
  ```bash
  for i in {1..250}; do curl -s -o /dev/null -w "%{http_code}
" "http://<HOST>:8080/version"; done
  ```

## Files to commit
- `nginx/nginx.conf.template` (structured log format)
- `watcher/Dockerfile`, `watcher/requirements.txt`, `watcher/watcher.py`
- `.env.example` (no secrets)
- `runbook.md`
- Updated `docker-compose.yml` with `alert_watcher` service

## Troubleshooting
See `runbook.md` for detailed operator steps and diagnostics commands.
