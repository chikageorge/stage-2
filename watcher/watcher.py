#!/usr/bin/env python3
"""
watcher.py - tails nginx access log, detects failovers & elevated 5xx rate, posts to Slack
"""

import os
import time
import re
import json
import threading
from collections import deque, defaultdict
from datetime import datetime, timedelta
import requests

# Config from environment
LOG_PATH = os.environ.get("LOG_PATH", "/var/log/nginx/access.log")
SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
ERROR_RATE_THRESHOLD = float(os.environ.get("ERROR_RATE_THRESHOLD", "2.0"))  # percent
WINDOW_SIZE = int(os.environ.get("WINDOW_SIZE", "200"))
ALERT_COOLDOWN_SEC = int(os.environ.get("ALERT_COOLDOWN_SEC", "300"))
MAINTENANCE_MODE = os.environ.get("MAINTENANCE_MODE", "false").lower() in ("1","true","yes")
ACTIVE_POOL = os.environ.get("ACTIVE_POOL", "blue")

if not SLACK_WEBHOOK:
    print("WARNING: SLACK_WEBHOOK_URL not set. Alerts will be printed not posted.")

# regex to parse our structured log fields: pool="..." release="..." upstream_status="..." upstream_addr="..." request_time="..." upstream_response_time="..."
LOG_RE = re.compile(r'pool="(?P<pool>[^"]*)"|release="(?P<release>[^"]*)"|upstream_status="(?P<up_status>[^"]*)"|upstream_addr="(?P<up_addr>[^"]*)"|request_time="(?P<req_time>[^"]*)"|upstream_response_time="(?P<up_resp>[^"]*)"')
# We'll parse the full line by extracting the key fields; easier: match key="value"

# state
last_seen_pool = None
last_pool_change_ts = None
last_alert_ts = defaultdict(lambda: datetime.fromtimestamp(0))  # keyed by alert type
window = deque(maxlen=WINDOW_SIZE)  # store tuples (status_code, pool)
lock = threading.Lock()

def post_slack(msg, attachment=None):
    text = f"*Alert:* {msg}\n_Time: {datetime.utcnow().isoformat()}Z_"
    payload = {"text": text}
    if attachment:
        payload["attachments"] = [attachment]
    if SLACK_WEBHOOK:
        try:
            r = requests.post(SLACK_WEBHOOK, json=payload, timeout=5)
            if r.status_code >= 400:
                print(f"Failed to post Slack: {r.status_code} {r.text}")
        except Exception as e:
            print("Slack post exception:", e)
    else:
        print("SLACK (simulated):", text)

def should_rate_limit(alert_key):
    now = datetime.utcnow()
    if (now - last_alert_ts[alert_key]).total_seconds() < ALERT_COOLDOWN_SEC:
        return True
    last_alert_ts[alert_key] = now
    return False

def parse_line(line):
    # Quick parse: find pool, release, upstream_status, upstream_addr, request_time
    fields = {}
    # generic find: key="value"
    for m in re.finditer(r'(\w+)="([^"]*)"', line):
        k, v = m.group(1), m.group(2)
        # map keys to our expected names
        if k in ("pool","release","upstream_status","upstream_addr","request_time","upstream_response_time"):
            fields[k] = v
    # fallback: status code might be just after request; grab first 3-digit status
    status_match = re.search(r'"\s(?P<status>\d{3})\s', line)
    if status_match:
        fields["status"] = int(status_match.group("status"))
    else:
        # try separate
        sm = re.search(r'\s(?P<status>\d{3})\s', line)
        if sm:
            fields["status"] = int(sm.group("status"))
    return fields

def handle_event(fields):
    global last_seen_pool, last_pool_change_ts
    status = int(fields.get("status", 0))
    pool = fields.get("pool", "unknown")
    release = fields.get("release", "")
    upstream_status = fields.get("upstream_status", "")
    # push to window
    with lock:
        window.append((status, pool, release, upstream_status))
        # detect pool flips:
        if last_seen_pool is None:
            last_seen_pool = pool
        elif pool != last_seen_pool:
            # failover detected
            now = datetime.utcnow()
            last_seen_pool = pool
            last_pool_change_ts = now
            if MAINTENANCE_MODE:
                print("Maintenance mode active - suppressing failover alert")
            else:
                if not should_rate_limit("failover"):
                    msg = f"Failover detected: traffic moved to *{pool}* (release: {release}). Upstream status: {upstream_status}"
                    post_slack(msg)
                else:
                    print("Failover detected but rate-limited.")
        # check error rate only every few requests or when window full
        if len(window) >= WINDOW_SIZE:
            compute_error_rate()

def compute_error_rate():
    # compute percentage of 5xx in last WINDOW_SIZE entries
    with lock:
        total = len(window)
        if total == 0:
            return
        errors = sum(1 for (status, *_ ) in window if 500 <= status <= 599)
        pct = (errors/total)*100.0
    if pct >= ERROR_RATE_THRESHOLD:
        if MAINTENANCE_MODE:
            print("Maintenance mode active - suppressing error-rate alert")
            return
        if not should_rate_limit("error_rate"):
            post_slack(f"High error rate detected: {errors}/{total} requests are 5xx ({pct:.2f}% >= threshold {ERROR_RATE_THRESHOLD}%)")
        else:
            print("Error-rate alert suppressed due to cooldown")

def tail_f(file_path):
    # tail -F like behavior
    try:
        f = open(file_path, "r")
    except FileNotFoundError:
        print(f"{file_path} not found; waiting...")
        return None
    # seek to end
    f.seek(0, 2)
    return f

def main_loop():
    print("Starting watcher. Logging from:", LOG_PATH)
    f = None
    while True:
        if f is None:
            f = tail_f(LOG_PATH)
            if f is None:
                time.sleep(2)
                continue
        line = f.readline()
        if not line:
            # handle rotation: re-open
            if hasattr(f, "fileno"):
                try:
                    if os.stat(LOG_PATH).st_ino != os.fstat(f.fileno()).st_ino:
                        # rotated
                        f.close()
                        f = tail_f(LOG_PATH)
                        continue
                except Exception:
                    pass
            time.sleep(0.1)
            continue
        fields = parse_line(line)
        handle_event(fields)

if __name__ == "__main__":
    # warm-up: ensure SLACK_WEBHOOK available printed
    print("CONFIG:", {
        "LOG_PATH": LOG_PATH,
        "ERROR_RATE_THRESHOLD": ERROR_RATE_THRESHOLD,
        "WINDOW_SIZE": WINDOW_SIZE,
        "ALERT_COOLDOWN_SEC": ALERT_COOLDOWN_SEC,
        "MAINTENANCE_MODE": MAINTENANCE_MODE,
        "ACTIVE_POOL": ACTIVE_POOL
    })
    try:
        main_loop()
    except KeyboardInterrupt:
        print("Watcher stopped.")