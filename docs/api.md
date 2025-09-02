# API Documentation

## Обзор

HyperLiquid Node Parser предоставляет REST API для работы с данными ордеров и конфигурацией системы.

**Base URL**: `http://localhost:8000`

**API Version**: `v1`

**Content-Type**: `application/json`

## Аутентификация

В текущей версии API не требует аутентификации.

## Endpoints

### Системные Endpoints

#### GET /

Информация о приложении.

**Response:**
```json
{
  "message": "HyperLiquid Node Parser API",
  "version": "1.0.0"
}
```

#### GET /health

Проверка состояния приложения.

**Response:**
```json
{
  "status": "healthy",
  "order_count": 150,
  "order_manager_stats": {
    "open": 100,
    "filled": 30,
    "cancelled": 15,
    "triggered": 5
  }
}
```

### Ордера

#### GET /api/v1/orders

Получить список ордеров с возможностью фильтрации.

**Query Parameters:**

| Параметр | Тип | Описание | Пример |
|----------|-----|----------|--------|
| `symbol` | string | Фильтр по символу | `BTC`, `ETH` |
| `side` | string | Фильтр по стороне | `Bid`, `Ask` |
| `min_liquidity` | float | Минимальная ликвидность | `1000.0` |
| `status` | string | Фильтр по статусу | `open`, `filled` |

**Пример запроса:**
```bash
curl "http://localhost:8000/api/v1/orders?symbol=BTC&side=Bid&min_liquidity=1000"
```

**Response:**
```json
[
  {
    "id": "0x1234567890abcdef_123",
    "symbol": "BTC",
    "side": "Bid",
    "price": 50000.0,
    "size": 1.0,
    "owner": "0x1234567890abcdef",
    "timestamp": "2024-01-01T12:00:00Z",
    "status": "open"
  }
]
```

#### GET /api/v1/orders/{order_id}

Получить ордер по ID.

**Path Parameters:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `order_id` | string | Уникальный ID ордера |

**Пример запроса:**
```bash
curl "http://localhost:8000/api/v1/orders/0x1234567890abcdef_123"
```

**Response:**
```json
{
  "id": "0x1234567890abcdef_123",
  "symbol": "BTC",
  "side": "Bid",
  "price": 50000.0,
  "size": 1.0,
  "owner": "0x1234567890abcdef",
  "timestamp": "2024-01-01T12:00:00Z",
  "status": "open"
}
```

**Ошибки:**
- `404 Not Found` - ордер не найден

#### GET /api/v1/orders/stats/summary

Получить статистику ордеров.

**Пример запроса:**
```bash
curl "http://localhost:8000/api/v1/orders/stats/summary"
```

**Response:**
```json
{
  "total_orders": 150,
  "status_counts": {
    "open": 100,
    "filled": 30,
    "cancelled": 15,
    "triggered": 5
  },
  "open_orders_count": 100
}
```

### Конфигурация

#### GET /api/v1/config

Получить текущую конфигурацию системы.

**Пример запроса:**
```bash
curl "http://localhost:8000/api/v1/config"
```

**Response:**
```json
{
  "node_logs_path": "/app/node_logs",
  "cleanup_interval_hours": 2,
  "api_host": "0.0.0.0",
  "api_port": 8000,
  "log_level": "DEBUG",
  "log_file_path": "logs/app.log",
  "log_max_size_mb": 100,
  "log_retention_days": 30,
  "data_dir": "data",
  "config_file_path": "config/config.json",
  "max_orders_per_request": 1000,
  "file_read_retry_attempts": 3,
  "file_read_retry_delay": 1.0,
  "symbols_config": [
    {
      "symbol": "BTC",
      "min_liquidity": 1000.0,
      "price_deviation": 0.03
    },
    {
      "symbol": "ETH", 
      "min_liquidity": 500.0,
      "price_deviation": 0.05
    },
    {
      "symbol": "SOL",
      "min_liquidity": 100.0,
      "price_deviation": 0.02
    }
  ]
}
```

#### PUT /api/v1/config

Обновить конфигурацию системы.

**Request Body:**
```json
{
  "api_port": 9000,
  "log_level": "INFO",
  "symbols_config": [
    {
      "symbol": "BTC",
      "min_liquidity": 2000.0,
      "price_deviation": 0.02
    }
  ]
}
```

**Пример запроса:**
```bash
curl -X PUT "http://localhost:8000/api/v1/config" \
  -H "Content-Type: application/json" \
  -d '{"api_port": 9000, "log_level": "INFO"}'
```

**Response:**
```json
{
  "node_logs_path": "/app/node_logs",
  "cleanup_interval_hours": 2,
  "api_host": "0.0.0.0",
  "api_port": 9000,
  "log_level": "INFO",
  "log_file_path": "logs/app.log",
  "log_max_size_mb": 100,
  "log_retention_days": 30,
  "data_dir": "data",
  "config_file_path": "config/config.json",
  "max_orders_per_request": 1000,
  "file_read_retry_attempts": 3,
  "file_read_retry_delay": 1.0,
  "symbols_config": [
    {
      "symbol": "BTC",
      "min_liquidity": 2000.0,
      "price_deviation": 0.02
    },
    {
      "symbol": "ETH",
      "min_liquidity": 1000.0,
      "price_deviation": 0.03
    }
  ]
}
```

**Ошибки:**
- `400 Bad Request` - неверные параметры конфигурации

## Модели данных

### Order

```json
{
  "id": "string",           // Уникальный ID ордера
  "symbol": "string",       // Символ (BTC, ETH, etc.)
  "side": "string",         // Сторона (Bid/Ask)
  "price": "float",         // Цена
  "size": "float",          // Размер
  "owner": "string",        // Адрес владельца
  "timestamp": "datetime",  // Временная метка
  "status": "string"        // Статус (open/filled/cancelled/triggered)
}
```

### Config

```json
{
  "node_logs_path": "string",           // Путь к логам node
  "cleanup_interval_hours": "integer",  // Интервал очистки в часах
  "api_host": "string",                 // API host
  "api_port": "integer",                // API port
  "log_level": "string",                // Уровень логирования
  "log_file_path": "string",            // Путь к файлу логов
  "log_max_size_mb": "integer",         // Максимальный размер лога в MB
  "log_retention_days": "integer",      // Дни хранения логов
  "data_dir": "string",                 // Директория данных
  "config_file_path": "string",         // Путь к файлу конфигурации
  "max_orders_per_request": "integer",  // Максимум ордеров в запросе
  "file_read_retry_attempts": "integer", // Попытки чтения файла
  "file_read_retry_delay": "float",     // Задержка между попытками
  "symbols_config": "array"             // Конфигурация символов
}
```

## Коды ошибок

| Код | Описание |
|-----|----------|
| `200` | Успешный запрос |
| `400` | Неверный запрос |
| `404` | Ресурс не найден |
| `500` | Внутренняя ошибка сервера |

## Примеры использования

### Получение всех открытых ордеров BTC

```bash
curl "http://localhost:8000/api/v1/orders?symbol=BTC&status=open"
```

### Получение ордеров с минимальной ликвидностью

```bash
curl "http://localhost:8000/api/v1/orders?min_liquidity=5000"
```

### Обновление уровня логирования

```bash
curl -X PUT "http://localhost:8000/api/v1/config" \
  -H "Content-Type: application/json" \
  -d '{"log_level": "WARNING"}'
```

### Получение статистики

```bash
curl "http://localhost:8000/api/v1/orders/stats/summary"
```

## Rate Limiting

В текущей версии API не имеет ограничений на количество запросов.

## Версионирование

API использует версионирование в URL: `/api/v1/`

При изменении API будет создана новая версия: `/api/v2/`

## Swagger Documentation

Интерактивная документация доступна по адресу: `http://localhost:8000/docs`
