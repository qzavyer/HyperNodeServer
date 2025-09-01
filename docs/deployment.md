# Руководство по развертыванию

## Обзор

Данное руководство описывает процесс развертывания HyperLiquid Node Parser на Ubuntu сервере с использованием Docker.

## Требования к системе

### Минимальные требования

- **OS**: Ubuntu 20.04 LTS или новее
- **RAM**: 2 GB
- **CPU**: 2 ядра
- **Disk**: 10 GB свободного места
- **Network**: стабильное интернет-соединение

### Рекомендуемые требования

- **OS**: Ubuntu 22.04 LTS
- **RAM**: 4 GB
- **CPU**: 4 ядра
- **Disk**: 50 GB SSD
- **Network**: 100 Mbps

## Подготовка сервера

### 1. Обновление системы

```bash
sudo apt update
sudo apt upgrade -y
```

### 2. Установка необходимых пакетов

```bash
sudo apt install -y \
    curl \
    wget \
    git \
    unzip \
    htop \
    nano \
    ufw
```

### 3. Настройка файрвола

```bash
# Включить UFW
sudo ufw enable

# Разрешить SSH
sudo ufw allow ssh

# Разрешить HTTP/HTTPS
sudo ufw allow 80
sudo ufw allow 443

# Разрешить порт приложения
sudo ufw allow 8000

# Проверить статус
sudo ufw status
```

## Установка Docker

### 1. Удаление старых версий

```bash
sudo apt remove -y docker docker-engine docker.io containerd runc
```

### 2. Установка зависимостей

```bash
sudo apt install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release
```

### 3. Добавление GPG ключа Docker

```bash
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
```

### 4. Добавление репозитория Docker

```bash
echo \
  "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
```

### 5. Установка Docker

```bash
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
```

### 6. Настройка Docker

```bash
# Добавить пользователя в группу docker
sudo usermod -aG docker $USER

# Включить автозапуск Docker
sudo systemctl enable docker
sudo systemctl start docker

# Проверить установку
docker --version
docker compose version
```

## Развертывание приложения

### 1. Клонирование репозитория

```bash
git clone <repository-url>
cd HyperNodeServer
```

### 2. Создание конфигурационных файлов

**Создать .env файл:**
```bash
cp .env.example .env
nano .env
```

**Содержимое .env:**
```env
# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Logging
LOG_LEVEL=INFO
LOG_FILE_PATH=logs/app.log
LOG_MAX_SIZE_MB=100
LOG_RETENTION_DAYS=30

# Node Logs Path
NODE_LOGS_PATH=/app/node_logs

# Data Directory
DATA_DIR=data

# Cleanup
CLEANUP_INTERVAL_HOURS=2

# File Reading
FILE_READ_RETRY_ATTEMPTS=3
FILE_READ_RETRY_DELAY=1.0

# Orders
MAX_ORDERS_PER_REQUEST=1000
```

### 3. Создание docker-compose.yml

```yaml
version: '3.8'

services:
  hyperliquid-parser:
    build: .
    container_name: hyperliquid-parser
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - ./logs:/app/logs
      - ./data:/app/data
      - /path/to/node/logs:/app/node_logs:ro
    environment:
      - NODE_LOGS_PATH=/app/node_logs
      - API_HOST=0.0.0.0
      - API_PORT=8000
      - LOG_LEVEL=INFO
    networks:
      - hyperliquid-network

  nginx:
    image: nginx:alpine
    container_name: hyperliquid-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/ssl:/etc/nginx/ssl
    depends_on:
      - hyperliquid-parser
    networks:
      - hyperliquid-network

networks:
  hyperliquid-network:
    driver: bridge
```

### 4. Создание Nginx конфигурации

**Создать директорию:**
```bash
mkdir -p nginx
```

**Создать nginx.conf:**
```nginx
events {
    worker_connections 1024;
}

http {
    upstream hyperliquid_backend {
        server hyperliquid-parser:8000;
    }

    server {
        listen 80;
        server_name your-domain.com;

        location / {
            proxy_pass http://hyperliquid_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        location /health {
            proxy_pass http://hyperliquid_backend/health;
            access_log off;
        }
    }
}
```

### 5. Создание директорий

```bash
mkdir -p logs data nginx/ssl
chmod 755 logs data
```

### 6. Запуск приложения

```bash
# Сборка и запуск
docker compose up -d

# Проверка статуса
docker compose ps

# Просмотр логов
docker compose logs -f hyperliquid-parser
```

## Настройка SSL (опционально)

### 1. Установка Certbot

```bash
sudo apt install -y certbot python3-certbot-nginx
```

### 2. Получение SSL сертификата

```bash
sudo certbot --nginx -d your-domain.com
```

### 3. Обновление Nginx конфигурации

```nginx
events {
    worker_connections 1024;
}

http {
    upstream hyperliquid_backend {
        server hyperliquid-parser:8000;
    }

    server {
        listen 80;
        server_name your-domain.com;
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl;
        server_name your-domain.com;

        ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

        location / {
            proxy_pass http://hyperliquid_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        location /health {
            proxy_pass http://hyperliquid_backend/health;
            access_log off;
        }
    }
}
```

## Настройка мониторинга

### 1. Установка Prometheus

```yaml
# Добавить в docker-compose.yml
  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    restart: unless-stopped
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
    networks:
      - hyperliquid-network
```

### 2. Создание prometheus.yml

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'hyperliquid-parser'
    static_configs:
      - targets: ['hyperliquid-parser:8000']
```

### 3. Установка Grafana

```yaml
# Добавить в docker-compose.yml
  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana-storage:/var/lib/grafana
    networks:
      - hyperliquid-network

volumes:
  grafana-storage:
```

## Настройка бэкапов

### 1. Создание скрипта бэкапа

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Создать бэкап данных
docker compose exec -T hyperliquid-parser tar czf - /app/data > $BACKUP_DIR/data_$DATE.tar.gz

# Создать бэкап логов
docker compose exec -T hyperliquid-parser tar czf - /app/logs > $BACKUP_DIR/logs_$DATE.tar.gz

# Удалить старые бэкапы (старше 7 дней)
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete

echo "Backup completed: $DATE"
```

### 2. Настройка cron

```bash
# Добавить в crontab
0 2 * * * /path/to/backup.sh
```

## Обновление приложения

### 1. Остановка приложения

```bash
docker compose down
```

### 2. Обновление кода

```bash
git pull origin main
```

### 3. Пересборка и запуск

```bash
docker compose build --no-cache
docker compose up -d
```

### 4. Проверка обновления

```bash
# Проверить статус
docker compose ps

# Проверить логи
docker compose logs -f hyperliquid-parser

# Проверить API
curl http://localhost:8000/health
```

## Устранение неполадок

### Проблемы с Docker

```bash
# Проверить статус Docker
sudo systemctl status docker

# Перезапустить Docker
sudo systemctl restart docker

# Очистить неиспользуемые ресурсы
docker system prune -a
```

### Проблемы с приложением

```bash
# Просмотр логов
docker compose logs hyperliquid-parser

# Проверка конфигурации
docker compose config

# Перезапуск сервиса
docker compose restart hyperliquid-parser
```

### Проблемы с сетью

```bash
# Проверить порты
sudo netstat -tulpn | grep :8000

# Проверить файрвол
sudo ufw status

# Проверить DNS
nslookup your-domain.com
```

## Мониторинг производительности

### Команды для мониторинга

```bash
# Использование CPU и RAM
htop

# Использование диска
df -h

# Использование сети
iftop

# Логи приложения
tail -f logs/app_*.log
```

### Метрики для отслеживания

- **CPU Usage**: < 80%
- **Memory Usage**: < 85%
- **Disk Usage**: < 90%
- **Response Time**: < 500ms
- **Error Rate**: < 1%

## Безопасность

### Рекомендации

1. **Регулярные обновления**
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

2. **Мониторинг логов**
   ```bash
   tail -f /var/log/auth.log
   ```

3. **Резервное копирование**
   ```bash
   # Автоматические бэкапы
   crontab -e
   ```

4. **SSL сертификаты**
   ```bash
   # Автообновление Let's Encrypt
   sudo crontab -e
   0 12 * * * /usr/bin/certbot renew --quiet
   ```

## Контакты

При возникновении проблем:

1. Проверьте логи приложения
2. Проверьте документацию
3. Создайте issue в GitHub
4. Обратитесь к команде поддержки
