# 🧭 Runbook: Nginx Failover and Error-Rate Alerts

## 1. Alerts Overview

### 🔴 Failover Detected
**Meaning:** Traffic switched from one pool to another (e.g., Blue → Green).  
**Action:**  
1. Run `docker compose ps` to check which container is unhealthy.  
2. View logs with `docker logs app_blue` or `docker logs app_green`.  
3. Confirm recovery before switching back.

---

### 🔥 High Error Rate
**Meaning:** More than 2% of the last 200 requests returned 5xx errors.  
**Action:**  
1. Check which pool is active (`ACTIVE_POOL` in `.env`).  
2. Inspect container logs of that pool.  
3. Switch pools if errors persist:
   ```bash
   ./switch_pool.sh green