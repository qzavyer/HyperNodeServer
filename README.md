# HyperLiquid Node Parser

FastAPI приложение для парсинга логов HyperLiquid node и предоставления данных order book через REST API.

## 🚀 Возможности

- **Парсинг логов** - автоматическое извлечение ордеров из JSON логов
- **Real-time мониторинг** - отслеживание изменений файлов в реальном времени
- **REST API** - полный набор endpoints для работы с ордерами
- **Конфигурация** - гибкая настройка через API и файлы
- **Логирование** - централизованное логирование с ротацией
- **Тестирование** - полное покрытие тестами (TDD подход)

## 🏗️ Архитектура

```
src/
├── main.py              # FastAPI приложение
├── api/
│   └── routes.py        # API endpoints
├── parser/
│   ├── log_parser.py    # Парсер логов
│   └── order_extractor.py # Извлечение ордеров
├── storage/
│   ├── models.py        # Pydantic модели
│   ├── file_storage.py  # Файловое хранение
│   ├── order_manager.py # Управление ордерами
│   └── config_manager.py # Управление конфигурацией
├── watcher/
│   └── file_watcher.py  # Мониторинг файлов
└── utils/
    └── logger.py        # Логирование
```

## 📋 Требования

- Python 3.11+
- FastAPI
- Uvicorn
- Pydantic
- Watchdog
- aiofiles

## 🛠️ Установка

1. **Клонировать репозиторий:**
```bash
git clone <repository-url>
cd HyperNodeServer
```

2. **Установить зависимости:**
```bash
pip install -r requirements.txt
```

3. **Настроить конфигурацию:**
```bash
# Создать .env файл
cp .env.example .env
# Отредактировать настройки
```

4. **Запустить приложение:**
```bash
python run.py
```

## 🐳 Docker

**Сборка образа:**
```bash
docker build -t hyperliquid-parser .
```

**Запуск контейнера:**
```bash
docker run -p 8000:8000 -v /path/to/logs:/app/logs hyperliquid-parser
```

## 📖 API Документация

### Основные Endpoints

#### Ордера

- `GET /api/v1/orders` - получить список ордеров с фильтрацией
- `GET /api/v1/orders/{order_id}` - получить ордер по ID
- `GET /api/v1/orders/stats/summary` - статистика ордеров

#### Конфигурация

- `GET /api/v1/config` - получить текущую конфигурацию
- `PUT /api/v1/config` - обновить конфигурацию

#### Система

- `GET /` - информация о приложении
- `GET /health` - проверка состояния
- `GET /docs` - Swagger документация

### Примеры запросов

**Получить все ордера:**
```bash
curl http://localhost:8000/api/v1/orders
```

**Фильтрация по символу:**
```bash
curl "http://localhost:8000/api/v1/orders?symbol=BTC&side=Bid"
```

**Получить конфигурацию:**
```bash
curl http://localhost:8000/api/v1/config
```

**Обновить конфигурацию:**
```bash
curl -X PUT http://localhost:8000/api/v1/config \
  -H "Content-Type: application/json" \
  -d '{"api_port": 9000, "log_level": "INFO"}'
```

## ⚙️ Конфигурация

### Основные настройки

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `NODE_LOGS_PATH` | Путь к логам node | `/app/node_logs` |
| `API_HOST` | Host для API | `0.0.0.0` |
| `API_PORT` | Порт для API | `8000` |
| `LOG_LEVEL` | Уровень логирования | `DEBUG` |
| `CLEANUP_INTERVAL_HOURS` | Интервал очистки | `2` |

### Логирование

- **Файл**: `logs/app_YYYYMMDD_HHMMSS.log`
- **Максимальный размер**: 100 MB
- **Ротация**: автоматическая
- **Удержание**: 30 дней

## 🧪 Тестирование

**Запуск всех тестов:**
```bash
python -m pytest
```

**Запуск конкретных тестов:**
```bash
python -m pytest tests/test_config_manager.py -v
python -m pytest tests/test_api_routes.py -v
python -m pytest tests/test_integration.py -v
```

**Покрытие кода:**
```bash
python -m pytest --cov=src --cov-report=html
```

## 📊 Модели данных

### Order

```python
class Order(BaseModel):
    id: str                    # Уникальный ID ордера
    symbol: str                # Символ (BTC, ETH, etc.)
    side: str                  # Сторона (Bid/Ask)
    price: float               # Цена
    size: float                # Размер
    owner: str                 # Адрес владельца
    timestamp: datetime        # Временная метка
    status: str                # Статус (open/filled/cancelled/triggered)
```

### Config

```python
class Config(BaseModel):
    node_logs_path: str        # Путь к логам
    api_host: str              # API host
    api_port: int              # API port
    log_level: str             # Уровень логирования
    cleanup_interval_hours: int # Интервал очистки
    # ... другие настройки
```

## 🔄 Жизненный цикл ордера

1. **open** - ордер создан
2. **filled** - ордер исполнен
3. **cancelled** - ордер отменен
4. **triggered** - ордер активирован

**Правила переходов:**
- `open` → `filled` ✅
- `open` → `cancelled` ✅
- `open` → `triggered` ✅
- `filled` → `cancelled` ❌ (невозможно)
- `cancelled` → `filled` ❌ (невозможно)

## 🚀 Развертывание

### Ubuntu + Docker

1. **Установить Docker:**
```bash
sudo apt update
sudo apt install docker.io docker-compose
```

2. **Создать docker-compose.yml:**
```yaml
version: '3.8'
services:
  hyperliquid-parser:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./logs:/app/logs
      - ./data:/app/data
      - /path/to/node/logs:/app/node_logs:ro
    environment:
      - NODE_LOGS_PATH=/app/node_logs
```

3. **Запустить:**
```bash
docker-compose up -d
```

### GitHub Actions

Автоматическое развертывание при push в main ветку.

## 📝 Логирование

### Уровни логирования

- **DEBUG** - детальная отладочная информация
- **INFO** - общая информация о работе
- **WARNING** - предупреждения
- **ERROR** - ошибки

### Формат логов

```
2024-01-01T12:00:00 [INFO] [src.main] ✅ Application started successfully
2024-01-01T12:00:01 [DEBUG] [src.parser.log_parser] Parsing file: /path/to/log.json
2024-01-01T12:00:02 [INFO] [src.storage.order_manager] Loaded 150 orders
```

## 🔧 Устранение неполадок

### Частые проблемы

1. **Ошибка доступа к файлам:**
   - Проверить права доступа к директории логов
   - Убедиться что путь в конфигурации корректный

2. **Проблемы с логгированием:**
   - Проверить права на запись в директорию logs
   - Убедиться что достаточно места на диске

3. **API не отвечает:**
   - Проверить что порт 8000 свободен
   - Проверить логи приложения

### Команды диагностики

```bash
# Проверить статус приложения
curl http://localhost:8000/health

# Посмотреть логи
tail -f logs/app_*.log

# Проверить конфигурацию
curl http://localhost:8000/api/v1/config
```

## 🤝 Вклад в проект

1. Fork репозитория
2. Создать feature branch
3. Внести изменения
4. Добавить тесты
5. Создать Pull Request

## 📄 Лицензия

MIT License

## 📞 Поддержка

- **Issues**: GitHub Issues
- **Документация**: `/docs` endpoint
- **Email**: support@example.com
