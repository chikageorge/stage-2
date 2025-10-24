##  Blue/Green Deployment with Nginx (Auto-Failover + Manual Toggle)

###  Overview
This project demonstrates a **Blue/Green Deployment setup** using **Docker Compose** and **Nginx** with **automatic failover** and **manual toggle** capability.  
Both Blue and Green are identical Node.js apps served behind Nginx.

---

##  Features
✅ Blue/Green environment using Docker Compose  
✅ Health-based automatic failover (Blue → Green)  
✅ Manual pool switching (`./switch_pool.sh`)  
✅ Header forwarding (`X-App-Pool`, `X-Release-Id`)  
✅ Zero downtime during chaos testing  
✅ Environment-driven configuration via `.env`  

---

##  Project Structure
```
.
├── docker-compose.yml
├── nginx.conf
├── .env.example
├── switch_pool.sh
├── README.md
└── DECISION.md (optional)
```

---

##  Prerequisites
Make sure you have:
-  Docker & Docker Compose installed
-  Git Bash or any Linux shell (on Windows, use Git Bash)
-  Internet access to pull Docker images

---

##  Environment Variables

Copy `.env.example` → `.env`, then update values as needed:

```env
# .env.example
BLUE_IMAGE=yimikaade/wonderful:devops-stage-two
GREEN_IMAGE=yimikaade/wonderful:devops-stage-two
ACTIVE_POOL=blue
RELEASE_ID_BLUE=v1.0.0
RELEASE_ID_GREEN=v1.0.1
PORT=80
```

---

##  Docker Compose Setup

**docker-compose.yml**
```yaml
services:
  app_blue:
    image: ${BLUE_IMAGE}
    container_name: app_blue
    environment:
      - RELEASE_ID=${RELEASE_ID_BLUE}
    ports:
      - "8081:80"

  app_green:
    image: ${GREEN_IMAGE}
    container_name: app_green
    environment:
      - RELEASE_ID=${RELEASE_ID_GREEN}
    ports:
      - "8082:80"

  nginx:
    image: nginx:latest
    container_name: nginx
    depends_on:
      - app_blue
      - app_green
    ports:
      - "8080:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
```

---

##  Nginx Configuration

**nginx.conf**
```nginx
events {}

http {
    upstream backend {
        server app_blue:80 max_fails=2 fail_timeout=5s;
        server app_green:80 backup;
    }

    server {
        listen 80;

        location / {
            proxy_pass http://backend;
            proxy_connect_timeout 1s;
            proxy_read_timeout 2s;
            proxy_next_upstream error timeout http_500 http_502 http_503 http_504;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_pass_header X-App-Pool;
            proxy_pass_header X-Release-Id;
        }
    }
}
```

---

##  Manual Pool Switch Script

**switch_pool.sh**
```bash
#!/bin/bash
# Toggle between blue and green environments
POOL=$1

if [ -z "$POOL" ]; then
  echo "Usage: ./switch_pool.sh [blue|green]"
  exit 1
fi

sed -i "s/^ACTIVE_POOL=.*/ACTIVE_POOL=$POOL/" .env
echo "Switched active pool to: $POOL"

docker compose down
docker compose up -d
```

Make the script executable:
```bash
chmod +x switch_pool.sh
```

---

##  How to Run

### Step 1: Pull the required image
```bash
docker pull yimikaade/wonderful:devops-stage-two
```

### Step 2: Start all services
```bash
docker compose up -d
```

### Step 3: Verify everything
| Component | URL | Description |
|------------|-----|-------------|
| Blue | http://localhost:8081/version | Direct access to Blue |
| Green | http://localhost:8082/version | Direct access to Green |
| Nginx | http://localhost:8080/version | Routed via Nginx (active pool) |

You should see JSON output with:
```json
{
  "X-App-Pool": "blue",
  "X-Release-Id": "v1.0.0"
}
```

---

##  Test Failover

1. Trigger chaos on Blue:
   ```bash
   curl -X POST http://localhost:8081/chaos/start?mode=error
   ```

2. Check Nginx again:
   ```bash
   curl -i http://localhost:8080/version
   ```
   You should now see:
   ```
   X-App-Pool: green
   X-Release-Id: v1.0.1
   ```

3. Stop chaos:
   ```bash
   curl -X POST http://localhost:8081/chaos/stop
   ```

---

##  Manual Pool Switch
To manually switch traffic between environments:

```bash
./switch_pool.sh blue
# or
./switch_pool.sh green
```

---

##  Tear Down
To stop and remove containers:
```bash
docker compose down
```

---

##  Notes
- Blue = Primary  
- Green = Backup  
- All responses must include valid headers:
  - `X-App-Pool`
  - `X-Release-Id`
- No request should exceed 10 seconds during chaos mode.

---

##  Author
**Name:** _Your Full Name_  
**Slack Display Name:** _Your Slack Name_  
**Task:** DevOps Stage 2 — Blue/Green Deployment with Nginx
