# HyperLiquid Node Cleanup API Guide

## Обзор API

REST API для управления системой очистки файлов HyperLiquid Node. Поддерживает dry-run режим, конфигурируемые правила и детальную отчетность.

**Base URL:** `http://localhost:8000/api/v1/cleanup`

## Endpoints

### 1. Запуск очистки

**POST** `/run`

Запускает процесс очистки с возможностью dry-run режима.

#### Параметры запроса

```json
{
  "dry_run": boolean,    // true для симуляции, false для реальной очистки
  "force": boolean       // true для принудительной очистки
}
```

#### Примеры запросов

**Dry-run тестирование:**
```bash
curl -X POST "http://localhost:8000/api/v1/cleanup/run" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true, "force": false}'
```

**Реальная очистка:**
```bash
curl -X POST "http://localhost:8000/api/v1/cleanup/run" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": false, "force": true}'
```

#### Ответ

```json
{
  "success": true,
  "removed_directories": 5,
  "removed_files": 10,
  "dry_run": true,
  "execution_time_seconds": 1.23,
  "timestamp": "2025-01-01T12:00:00Z"
}
```

### 2. Получение отчета

**GET** `/report`

Генерирует детальный отчет о планируемых операциях очистки.

#### Параметры запроса

- `dry_run` (boolean, optional) - режим отчета (по умолчанию true)

#### Пример запроса

```bash
curl "http://localhost:8000/api/v1/cleanup/report?dry_run=true"
```

#### Ответ

```json
{
  "success": true,
  "dry_run": true,
  "report": {
    "timestamp": 1234567890,
    "dry_run": true,
    "summary": {
      "total_directories_to_remove": 5,
      "total_files_to_remove": 10,
      "estimated_space_to_free_mb": 100.5,
      "status": "report_generated",
      "message": "Cleanup report generated successfully"
    },
    "categories": {
      "temporary_files": {
        "directories_to_remove": 2,
        "files_to_remove": 5,
        "estimated_space_mb": 50.0
      }
    }
  }
}
```

### 3. Статистика очистки

**GET** `/stats`

Возвращает статистику выполненных операций очистки.

#### Пример запроса

```bash
curl "http://localhost:8000/api/v1/cleanup/stats"
```

#### Ответ

```json
{
  "success": true,
  "stats": {
    "total_cleanups": 10,
    "total_directories_removed": 50,
    "total_files_removed": 100,
    "total_space_freed_mb": 500.0,
    "last_cleanup": "2025-01-01T12:00:00Z",
    "average_execution_time_seconds": 2.5
  }
}
```

### 4. Управление конфигурацией

#### Получение сводки конфигурации

**GET** `/config/summary`

```bash
curl "http://localhost:8000/api/v1/cleanup/config/summary"
```

#### Загрузка конфигурации

**POST** `/config/load`

```bash
curl -X POST "http://localhost:8000/api/v1/cleanup/config/load?config_path=/path/to/cleanup_rules.json"
```

#### Применение конфигурации

**POST** `/config/apply`

```bash
# Dry-run применение
curl -X POST "http://localhost:8000/api/v1/cleanup/config/apply?dry_run=true"

# Реальное применение
curl -X POST "http://localhost:8000/api/v1/cleanup/config/apply?dry_run=false"
```

### 5. Состояние системы

**GET** `/health`

Проверяет состояние системы очистки.

#### Пример запроса

```bash
curl "http://localhost:8000/api/v1/cleanup/health"
```

#### Ответ

```json
{
  "success": true,
  "health": {
    "status": "healthy",
    "cleanup_path_exists": true,
    "config_loaded": true,
    "last_cleanup": "2025-01-01T12:00:00Z",
    "next_scheduled_cleanup": "2025-01-01T14:00:00Z",
    "disk_usage_percent": 75.5
  }
}
```

## Коды ответов

- **200 OK** - Успешное выполнение
- **400 Bad Request** - Неверные параметры запроса
- **404 Not Found** - Ресурс не найден
- **500 Internal Server Error** - Внутренняя ошибка сервера

## Обработка ошибок

### Структура ошибки

```json
{
  "success": false,
  "error": {
    "code": "CONFIG_NOT_FOUND",
    "message": "Configuration file not found",
    "details": "File /path/to/config.json does not exist"
  }
}
```

### Типы ошибок

- `CONFIG_NOT_FOUND` - Файл конфигурации не найден
- `INVALID_CONFIG` - Неверная конфигурация
- `PATH_NOT_FOUND` - Путь не существует
- `PERMISSION_DENIED` - Недостаточно прав доступа
- `CLEANUP_FAILED` - Ошибка выполнения очистки

## Примеры использования

### Полный цикл работы

1. **Проверка состояния системы:**
```bash
curl "http://localhost:8000/api/v1/cleanup/health"
```

2. **Загрузка конфигурации:**
```bash
curl -X POST "http://localhost:8000/api/v1/cleanup/config/load?config_path=/app/config/cleanup_rules.json"
```

3. **Получение отчета (dry-run):**
```bash
curl "http://localhost:8000/api/v1/cleanup/report?dry_run=true"
```

4. **Тестовый запуск (dry-run):**
```bash
curl -X POST "http://localhost:8000/api/v1/cleanup/run" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true, "force": false}'
```

5. **Реальная очистка:**
```bash
curl -X POST "http://localhost:8000/api/v1/cleanup/run" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": false, "force": true}'
```

6. **Проверка статистики:**
```bash
curl "http://localhost:8000/api/v1/cleanup/stats"
```

### Автоматизация

#### Скрипт для ежедневной очистки

```bash
#!/bin/bash

# Проверка состояния
HEALTH=$(curl -s "http://localhost:8000/api/v1/cleanup/health" | jq -r '.health.status')

if [ "$HEALTH" != "healthy" ]; then
    echo "System is not healthy, skipping cleanup"
    exit 1
fi

# Dry-run тест
DRY_RUN_RESULT=$(curl -s -X POST "http://localhost:8000/api/v1/cleanup/run" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true, "force": false}')

if [ $(echo $DRY_RUN_RESULT | jq -r '.success') = "true" ]; then
    # Выполнение реальной очистки
    curl -X POST "http://localhost:8000/api/v1/cleanup/run" \
      -H "Content-Type: application/json" \
      -d '{"dry_run": false, "force": true}'
    
    echo "Cleanup completed successfully"
else
    echo "Dry-run failed, skipping cleanup"
    exit 1
fi
```

#### Мониторинг

```bash
# Проверка последней очистки
LAST_CLEANUP=$(curl -s "http://localhost:8000/api/v1/cleanup/stats" | jq -r '.stats.last_cleanup')
echo "Last cleanup: $LAST_CLEANUP"

# Проверка использования диска
DISK_USAGE=$(curl -s "http://localhost:8000/api/v1/cleanup/health" | jq -r '.health.disk_usage_percent')
echo "Disk usage: $DISK_USAGE%"
```

## Безопасность

### Рекомендации

1. **Всегда используйте dry-run режим** для тестирования
2. **Проверяйте отчеты** перед реальной очисткой
3. **Мониторьте логи** для отслеживания операций
4. **Используйте HTTPS** в продакшене
5. **Ограничьте доступ** к API endpoints

### Аутентификация

В продакшене рекомендуется добавить аутентификацию:

```bash
# Пример с токеном
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "http://localhost:8000/api/v1/cleanup/health"
```

## Производительность

### Оптимизация

- Используйте **dry-run режим** для планирования
- **Батчинг операций** для больших объемов
- **Мониторинг производительности** через статистику
- **Кэширование конфигурации** для быстрого доступа

### Мониторинг

```bash
# Время выполнения
curl -s "http://localhost:8000/api/v1/cleanup/stats" | jq '.stats.average_execution_time_seconds'

# Количество операций
curl -s "http://localhost:8000/api/v1/cleanup/stats" | jq '.stats.total_cleanups'
```
