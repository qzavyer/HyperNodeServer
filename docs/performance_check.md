# Performance Monitoring Guide

This guide explains how to monitor server performance after deploying the HyperLiquid Node Parser application in Docker.

## Prerequisites

- Docker container running the application
- Access to the host system where Docker is running
- Basic knowledge of Linux commands

## Container Information

### Finding the Container

```bash
# List all running containers
docker ps

# Find the HyperLiquid parser container
docker ps | grep hyperliquid

# Example output:
# CONTAINER ID   IMAGE                    COMMAND                  CREATED        STATUS        PORTS                    NAMES
# abc123def456   hyperliquid-parser:latest   "python -m uvicorn..."   2 hours ago   Up 2 hours    0.0.0.0:8000->8000/tcp   hyperliquid-parser
```

### Container Name/ID
- **Container Name**: `hyperliquid-parser`
- **Container ID**: `abc123def456` (example)

## Performance Monitoring Commands

### 1. CPU Usage Monitoring

```bash
# Monitor CPU usage in real-time
docker stats hyperliquid-parser

# Monitor CPU usage with custom format
docker stats --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}" hyperliquid-parser

# Get current CPU usage
docker exec hyperliquid-parser top -bn1 | grep "Cpu(s)"
```

**Expected CPU Usage:**
- **Normal mode**: 10-30%
- **Ultra-fast mode**: 30-60%
- **Emergency mode**: 50-80%

### 2. Memory Usage Monitoring

```bash
# Monitor memory usage
docker stats hyperliquid-parser --no-stream

# Get detailed memory info
docker exec hyperliquid-parser cat /proc/meminfo

# Monitor memory usage over time
watch -n 1 'docker stats hyperliquid-parser --no-stream --format "{{.MemUsage}}"'
```

**Expected Memory Usage:**
- **Base application**: 100-200MB
- **With large buffers**: 200-500MB
- **Peak usage**: 500MB-1GB

### 3. Disk I/O Monitoring

```bash
# Monitor disk I/O
docker exec hyperliquid-parser iostat -x 1

# Check disk usage
docker exec hyperliquid-parser df -h

# Monitor file system activity
docker exec hyperliquid-parser iotop -a
```

### 4. Network Monitoring

```bash
# Monitor network usage
docker exec hyperliquid-parser netstat -i

# Check WebSocket connections
docker exec hyperliquid-parser netstat -an | grep :8000

# Monitor network traffic
docker exec hyperliquid-parser iftop
```

### 5. Application-Specific Monitoring

#### Check Processing Performance

```bash
# View application logs for performance metrics
docker logs hyperliquid-parser --tail 100 | grep -E "(lines_processed|orders_processed|performance)"

# Monitor processing speed
docker logs hyperliquid-parser -f | grep "WS Order"

# Check for errors
docker logs hyperliquid-parser --tail 50 | grep -E "(ERROR|WARNING)"
```

#### Check WebSocket Performance

```bash
# Test WebSocket endpoint
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" -H "Sec-WebSocket-Key: test" -H "Sec-WebSocket-Version: 13" http://localhost:8000/ws

# Check WebSocket connections
docker exec hyperliquid-parser ss -tuln | grep :8000
```

## Performance Metrics Dashboard

### Create a Monitoring Script

Create `monitor_performance.sh`:

```bash
#!/bin/bash

CONTAINER_NAME="hyperliquid-parser"

echo "=== HyperLiquid Parser Performance Monitor ==="
echo "Container: $CONTAINER_NAME"
echo "Timestamp: $(date)"
echo

# CPU Usage
echo "CPU Usage:"
docker stats $CONTAINER_NAME --no-stream --format "{{.CPUPerc}}"
echo

# Memory Usage
echo "Memory Usage:"
docker stats $CONTAINER_NAME --no-stream --format "{{.MemUsage}}"
echo

# Network I/O
echo "Network I/O:"
docker stats $CONTAINER_NAME --no-stream --format "{{.NetIO}}"
echo

# Block I/O
echo "Block I/O:"
docker stats $CONTAINER_NAME --no-stream --format "{{.BlockIO}}"
echo

# Application Logs (last 10 lines)
echo "Recent Application Activity:"
docker logs $CONTAINER_NAME --tail 10
echo

# WebSocket Connections
echo "WebSocket Connections:"
docker exec $CONTAINER_NAME netstat -an | grep :8000 | wc -l
echo
```

Make it executable:
```bash
chmod +x monitor_performance.sh
```

### Continuous Monitoring

```bash
# Monitor every 5 seconds
watch -n 5 ./monitor_performance.sh

# Monitor with logging
while true; do
    echo "$(date): $(docker stats hyperliquid-parser --no-stream --format '{{.CPUPerc}} {{.MemUsage}}')" >> performance.log
    sleep 5
done
```

## Performance Thresholds

### Warning Levels

| Metric | Normal | Warning | Critical |
|--------|--------|---------|----------|
| CPU Usage | < 30% | 30-70% | > 70% |
| Memory Usage | < 200MB | 200-500MB | > 500MB |
| Processing Delay | < 1s | 1-3s | > 3s |
| WebSocket Connections | < 10 | 10-50 | > 50 |

### Alert Commands

```bash
# Check if CPU is too high
if [ $(docker stats hyperliquid-parser --no-stream --format "{{.CPUPerc}}" | sed 's/%//') -gt 70 ]; then
    echo "WARNING: High CPU usage detected!"
fi

# Check if memory is too high
MEMORY_MB=$(docker stats hyperliquid-parser --no-stream --format "{{.MemUsage}}" | sed 's/MiB.*//')
if [ $MEMORY_MB -gt 500 ]; then
    echo "WARNING: High memory usage detected!"
fi
```

## Troubleshooting

### High CPU Usage

```bash
# Check what's consuming CPU
docker exec hyperliquid-parser top -bn1

# Check for infinite loops in logs
docker logs hyperliquid-parser | grep -E "(loop|infinite|error)"

# Restart container if needed
docker restart hyperliquid-parser
```

### High Memory Usage

```bash
# Check memory breakdown
docker exec hyperliquid-parser cat /proc/meminfo

# Check for memory leaks
docker exec hyperliquid-parser ps aux --sort=-%mem

# Restart container if needed
docker restart hyperliquid-parser
```

### Slow Processing

```bash
# Check processing logs
docker logs hyperliquid-parser | grep -E "(processing|delay|slow)"

# Check file system performance
docker exec hyperliquid-parser iostat -x 1 5

# Check network latency
docker exec hyperliquid-parser ping -c 5 8.8.8.8
```

## Performance Optimization

### If Performance is Poor

1. **Reduce Aggressiveness**:
   ```bash
   # Edit settings in container
   docker exec -it hyperliquid-parser vi /app/config/settings.py
   
   # Or restart with different settings
   docker-compose down
   docker-compose up -d
   ```

2. **Monitor Resource Usage**:
   ```bash
   # Check system resources
   docker system df
   docker system prune  # Clean up if needed
   ```

3. **Adjust Docker Resources**:
   ```yaml
   # In docker-compose.yml
   deploy:
     resources:
       limits:
         cpus: '2.0'
         memory: 1G
       reservations:
         cpus: '0.5'
         memory: 512M
   ```

## Log Analysis

### Key Log Patterns

```bash
# Processing speed
docker logs hyperliquid-parser | grep "lines_processed"

# Order processing
docker logs hyperliquid-parser | grep "WS Order"

# Performance metrics
docker logs hyperliquid-parser | grep "performance"

# Errors and warnings
docker logs hyperliquid-parser | grep -E "(ERROR|WARNING|CRITICAL)"
```

### Performance Logs

```bash
# Save performance logs
docker logs hyperliquid-parser > performance_$(date +%Y%m%d_%H%M%S).log

# Analyze processing speed
docker logs hyperliquid-parser | grep "lines_processed" | tail -100
```

## Automated Monitoring

### Create a Health Check Script

```bash
#!/bin/bash
# health_check.sh

CONTAINER_NAME="hyperliquid-parser"
ALERT_EMAIL="admin@example.com"

# Check if container is running
if ! docker ps | grep -q $CONTAINER_NAME; then
    echo "CRITICAL: Container $CONTAINER_NAME is not running!"
    # Send alert
    exit 1
fi

# Check CPU usage
CPU_USAGE=$(docker stats $CONTAINER_NAME --no-stream --format "{{.CPUPerc}}" | sed 's/%//')
if [ $CPU_USAGE -gt 80 ]; then
    echo "WARNING: High CPU usage: ${CPU_USAGE}%"
fi

# Check memory usage
MEMORY_MB=$(docker stats $CONTAINER_NAME --no-stream --format "{{.MemUsage}}" | sed 's/MiB.*//')
if [ $MEMORY_MB -gt 1000 ]; then
    echo "WARNING: High memory usage: ${MEMORY_MB}MB"
fi

echo "Health check passed"
```

### Schedule Health Checks

```bash
# Add to crontab
crontab -e

# Check every 5 minutes
*/5 * * * * /path/to/health_check.sh
```

## Conclusion

Regular monitoring of the HyperLiquid Node Parser application is essential for maintaining optimal performance. Use the commands and scripts provided in this guide to:

1. Monitor system resources (CPU, memory, disk, network)
2. Track application performance metrics
3. Identify and resolve performance issues
4. Maintain optimal processing speed

Remember to adjust monitoring frequency based on your system's needs and always keep performance logs for analysis.
