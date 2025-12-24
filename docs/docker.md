# Docker Deployment

## Quick Start

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

---

## docker-compose.yml

```yaml
version: '3.8'

services:
  conductor:
    build: .
    container_name: trainforge-conductor
    ports:
      - "8000:8000"
    volumes:
      - ./config:/app/config:ro
    environment:
      - CONDUCTOR_LOG_LEVEL=INFO
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

---

## Manual Docker Build

```bash
# Build
docker build -t trainforge-conductor .

# Run
docker run -d \
  --name trainforge-conductor \
  -p 8000:8000 \
  -v $(pwd)/config:/app/config:ro \
  trainforge-conductor

# Check logs
docker logs -f trainforge-conductor

# Stop
docker stop trainforge-conductor
docker rm trainforge-conductor
```

---

## Environment Variables

Pass configuration via environment:

```bash
docker run -d \
  -p 8000:8000 \
  -e CONDUCTOR_PORT=8000 \
  -e CONDUCTOR_LOG_LEVEL=DEBUG \
  -v $(pwd)/config:/app/config:ro \
  trainforge-conductor
```

---

## Production Deployment

### With resource limits

```yaml
services:
  conductor:
    build: .
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 256M
```

### With multiple replicas (load balancer required)

```yaml
services:
  conductor:
    build: .
    deploy:
      replicas: 3
```

---

## Cloud Deployment

### Railway

1. Push to GitHub
2. Connect repo to Railway
3. Add config as volume or environment

### Fly.io

```bash
fly launch
fly secrets set CONDUCTOR_CONFIG_PATH=/app/config/config.yaml
fly deploy
```

### DigitalOcean App Platform

1. Connect GitHub repo
2. Set build command: `docker build -t app .`
3. Mount config volume

---

## Health Checks

The container includes a health check:

```bash
curl http://localhost:8000/health
# {"status": "healthy", "service": "trainforge-conductor"}
```

Docker will automatically restart unhealthy containers when using `restart: unless-stopped`.

