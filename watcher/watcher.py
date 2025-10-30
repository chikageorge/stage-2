import os, time, re, json, requests
from collections import deque
from datetime import datetime

LOG_FILE = "/var/log/nginx/access.log"
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
ERROR_THRESHOLD = float(os.getenv("ERROR_RATE_THRESHOLD", 2))
WINDOW_SIZE = int(os.getenv("WINDOW_SIZE", 200))
COOLDOWN = int(os.getenv("ALERT_COOLDOWN_SEC", 300))
MAINTENANCE = os.getenv("MAINTENANCE_MODE", "false").lower() == "true"

last_alert_time = 0
last_pool = None
window = deque(maxlen=WINDOW_SIZE)

pattern = re.compile(r'pool=(\w+).*upstream_status=(\d+)')

def post_slack(msg):
    global last_alert_time
    now = time.time()
    if now - last_alert_time < COOLDOWN:
        return
    payload = {"text": f"{msg}\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"}
    try:
        requests.post(SLACK_WEBHOOK_URL, json=payload)
    except Exception as e:
        print("Slack error:", e)
    last_alert_time = now

def watch_logs():
    global last_pool
    with open(LOG_FILE, "r") as f:
        f.seek(0, 2)
        print("Watching logs...")
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.5)
                continue
            m = pattern.search(line)
            if not m:
                continue
            pool, status = m.groups()
            status = int(status)
            window.append(status)

            # Detect pool switch
            if last_pool and pool != last_pool and not MAINTENANCE:
                post_slack(f":rotating_light: Failover detected! {last_pool} → {pool}")
            last_pool = pool

            # Error rate check
            errors = sum(1 for s in window if s >= 500)
            rate = errors / len(window) * 100 if window else 0
            if rate > ERROR_THRESHOLD and not MAINTENANCE:
                post_slack(f":fire: High error rate detected: {rate:.2f}% (> {ERROR_THRESHOLD}%)")

if __name__ == "__main__":
    watch_logs()