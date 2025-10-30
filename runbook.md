# Runbook — Blue/Green Observability & Alerts (Stage 3)

## Overview
This runbook explains alerts posted by the `alert_watcher` service and what operators should do when Slack alerts are received. It assumes the Stage-2 Blue/Green deployment is running and that the `alert_watcher` sidecar reads nginx access logs from `/var/log/nginx/access.log`.

---

## Alert types (what you'll see in Slack)
### 1) Failover detected
**Message sample:** "Failover detected: traffic moved to *green* (release: green-1)."
**Meaning:** Nginx started serving traffic from the other pool (primary failed or timed out).
**Immediate actions (operator):**
1. SSH to the host and check container statuses:
   ```bash
   docker ps --filter "name=app_blue" --filter "name=app_green" --format "table {{.Names}}	{{.Status}}	{{.Ports}}"
   docker logs app_blue --tail 200
   docker logs app_green --tail 200
   docker logs nginx --tail 200
   ```
2. If primary shows errors, inspect its logs and resource usage:
   ```bash
   docker inspect app_blue
   docker stats app_blue --no-stream
   ```
3. If the failure is due to an ongoing chaos test, stop chaos by running:
   ```bash
   curl -X POST "http://<HOST>:8081/chaos/stop"
   ```
4. If the primary does not recover, keep the backup (green) active and escalate the incident to the engineering team with relevant logs and timestamps.

---

### 2) High error rate detected
**Message sample:** "High error rate detected: 60/200 requests are 5xx (30.00% >= threshold 2.00%)."
**Meaning:** Elevated 5xx responses in the most recent sliding window (default window: 200 requests).
**Immediate actions (operator):**
1. Inspect Nginx structured logs to find which upstream produced 5xx responses:
   ```bash
   docker exec nginx tail -n 200 /var/log/nginx/access.log | grep 'upstream_status="5'
   ```
2. Tail the failing app logs (blue or green) to identify the cause:
   ```bash
   docker logs app_blue --tail 300
   docker logs app_green --tail 300
   ```
3. Consider switching pools manually while investigating:
   ```bash
   ./switch_pool.sh green
   ```
4. If under scheduled maintenance, enable maintenance mode to suppress alerts:
   ```bash
   # set MAINTENANCE_MODE=true in .env and restart watcher container
   ```

---

### 3) Recovery / Return to healthy
**Meaning:** The primary or backup has recovered and watcher observed traffic returning to it.
**Actions:**
1. Review logs to confirm stable responses.
2. Optionally toggle pool back to primary with `./switch_pool.sh blue` after confirming health.

---

## Maintenance Mode
Set `MAINTENANCE_MODE=true` in `.env` to suppress alerts during planned maintenance or chaos drills. **Remember to revert to false** afterwards.

```bash
# Example
nano .env
# change MAINTENANCE_MODE=false -> true
docker compose restart alert_watcher
```

---

## Troubleshooting & Diagnostics
- If `alert_watcher` is not posting to Slack:
  - Confirm `SLACK_WEBHOOK_URL` is set in the environment (not committed to repo).
  - Check watcher logs: `docker logs -f alert_watcher`
  - Test webhook from the host:
    ```bash
    curl -X POST -H 'Content-type: application/json' --data '{"text":"watcher test"}' "$SLACK_WEBHOOK_URL"
    ```
- If Nginx access log lines do not include expected fields:
  - Ensure `nginx/nginx.conf` has the `bg_access` log_format and access_log path `/var/log/nginx/access.log`.
  - Confirm volumes mount the nginx log directory into the watcher container.
- If alerts are duplicate or noisy:
  - Increase `ALERT_COOLDOWN_SEC` in `.env` (default 300s) to reduce frequency.

---

## Playbook summary (quick commands)
```bash
# Inspect containers
docker ps
docker logs nginx --tail 200
docker logs alert_watcher --tail 200

# Stop chaos (if testing)
curl -X POST "http://<HOST>:8081/chaos/stop"

# Toggle pools (manual intervention)
./switch_pool.sh green
./switch_pool.sh blue
```

---

## Escalation
If the issue persists beyond immediate remediation (primary app crashes, repeated failovers), escalate to engineering and include:
- Timestamps of the Slack alerts
- `docker ps` output
- `nginx` and app logs (relevant excerpts)
- Recent deploy or change notes (if any)
