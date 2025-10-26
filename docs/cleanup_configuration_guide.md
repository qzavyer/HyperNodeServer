# HyperLiquid Node Cleanup Configuration Guide

## Обзор конфигурации

Система очистки использует JSON-конфигурацию для определения правил очистки файлов и директорий. Конфигурация поддерживает различные типы правил и гибкие настройки.

## Структура конфигурации

### Основная структура

```json
{
  "version": "1.0",
  "categories": {
    "category_name": {
      "paths": ["/path/to/clean"],
      "rules": [
        {
          "type": "rule_type",
          "parameters": {}
        }
      ]
    }
  }
}
```

### Поля конфигурации

- `version` - версия конфигурации (обязательно)
- `categories` - категории правил очистки (обязательно)
- `category_name` - имя категории (произвольное)
- `paths` - массив путей для очистки (обязательно)
- `rules` - массив правил для категории (обязательно)

## Типы правил

### 1. Удаление по дате в имени файла

Удаляет файлы старше указанного количества дней на основе даты в имени файла.

```json
{
  "type": "date_in_filename",
  "pattern": "\\d{4}-\\d{2}-\\d{2}_\\d{2}:\\d{2}:\\d{2}\\.",
  "days_old": 2
}
```

**Параметры:**
- `pattern` - регулярное выражение для извлечения даты из имени файла
- `days_old` - количество дней (файлы старше будут удалены)

**Примеры паттернов:**
- `\\d{4}-\\d{2}-\\d{2}_\\d{2}:\\d{2}:\\d{2}\\.` - ISO формат: `2025-01-01_12:30:45.`
- `\\d{8}_\\d{6}` - формат: `20250101_123045`
- `\\d{4}\\d{2}\\d{2}` - формат: `20250101`

### 2. Оставить последние N файлов

Сохраняет последние N файлов, соответствующих паттерну, остальные удаляет.

```json
{
  "type": "keep_last_n_files",
  "pattern": "\\d{8}",
  "keep_count": 30
}
```

**Параметры:**
- `pattern` - регулярное выражение для фильтрации файлов
- `keep_count` - количество файлов для сохранения

### 3. Оставить последние N директорий

Сохраняет последние N директорий, соответствующих паттерну, остальные удаляет.

```json
{
  "type": "keep_last_n_dirs",
  "pattern": "\\d{8}",
  "keep_count": 10
}
```

**Параметры:**
- `pattern` - регулярное выражение для фильтрации директорий
- `keep_count` - количество директорий для сохранения

### 4. Удаление по времени создания

Удаляет файлы и директории старше указанного количества дней на основе времени создания.

```json
{
  "type": "by_creation_time",
  "days_old": 7
}
```

**Параметры:**
- `days_old` - количество дней (файлы/директории старше будут удалены)

### 5. Удаление по шаблону имени

Удаляет файлы и директории, соответствующие указанному шаблону.

```json
{
  "type": "by_pattern",
  "pattern": "temp_.*\\.log",
  "days_old": 1
}
```

**Параметры:**
- `pattern` - регулярное выражение для сопоставления имен
- `days_old` - минимальный возраст для удаления (опционально)

## Примеры конфигураций

### Временные файлы

```json
{
  "version": "1.0",
  "categories": {
    "temporary_files": {
      "paths": [
        "/home/hl/hl/tmp/fu_write_string_to_file_tmp/",
        "/home/hl/hl/tmp/shell_rs_out/"
      ],
      "rules": [
        {
          "type": "date_in_filename",
          "pattern": "\\d{4}-\\d{2}-\\d{2}_\\d{2}:\\d{2}:\\d{2}\\.",
          "days_old": 2
        }
      ]
    }
  }
}
```

### Статистика сообщений

```json
{
  "version": "1.0",
  "categories": {
    "critical_message_stats": {
      "paths": [
        "/home/hl/hl/data/crit_msg_stats/hl-node/",
        "/home/hl/hl/data/crit_msg_stats/hl-visor/"
      ],
      "rules": [
        {
          "type": "keep_last_n_files",
          "pattern": "\\d{8}",
          "keep_count": 30
        }
      ]
    }
  }
}
```

### DHS данные

```json
{
  "version": "1.0",
  "categories": {
    "dhs_data": {
      "paths": [
        "/home/hl/hl/data/dhs/EvmBlockNumbers/hourly/",
        "/home/hl/hl/data/dhs/EvmBlocks/hourly/",
        "/home/hl/hl/data/dhs/EvmTxs/hourly/",
        "/home/hl/hl/data/evm_block_and_receipts/hourly/"
      ],
      "rules": [
        {
          "type": "keep_last_n_dirs",
          "pattern": "\\d{8}",
          "keep_count": 10
        }
      ]
    }
  }
}
```

### Логи узлов

```json
{
  "version": "1.0",
  "categories": {
    "node_logs": {
      "paths": [
        "/home/hl/hl/data/log/*/*/",
        "/home/hl/hl/data/node_logs/*/hourly"
      ],
      "rules": [
        {
          "type": "by_creation_time",
          "days_old": 7
        }
      ]
    }
  }
}
```

### Периодические данные

```json
{
  "version": "1.0",
  "categories": {
    "periodic_data": {
      "paths": [
        "/home/hl/hl/data/node_fast_block_times/",
        "/home/hl/hl/data/node_slow_block_times/",
        "/home/hl/hl/data/periodic_abci_state_statuses/20251014",
        "/home/hl/hl/data/rate_limited_ips/*/hourly",
        "/home/hl/hl/data/tcp_lz4_stats/20250914",
        "/home/hl/hl/data/tcp_traffic/hourly",
        "/home/hl/hl/data/tokio_spawn_forever_metrics/hourly",
        "/home/hl/hl/data/visor_abci_states/hourly",
        "/home/hl/hl/data/visor_child_stderr/"
      ],
      "rules": [
        {
          "type": "keep_last_n_dirs",
          "pattern": "\\d{8}",
          "keep_count": 5
        },
        {
          "type": "by_creation_time",
          "days_old": 14
        }
      ]
    }
  }
}
```

## Поддержка wildcard путей

Система поддерживает wildcard символы в путях:

- `*` - любое количество символов (кроме `/`)
- `**` - любое количество символов (включая `/`)

### Примеры wildcard путей

```json
{
  "paths": [
    "/home/hl/hl/data/log/*/*/",           // Все поддиректории в log/*
    "/home/hl/hl/data/node_logs/*/hourly", // hourly в каждой поддиректории node_logs
    "/home/hl/hl/data/rate_limited_ips/*/hourly" // hourly в каждой поддиректории rate_limited_ips
  ]
}
```

## Валидация конфигурации

### Обязательные поля

- `version` - должна быть строка
- `categories` - должен быть объект
- Каждая категория должна содержать:
  - `paths` - массив строк
  - `rules` - массив объектов

### Валидация правил

- `type` - должен быть одним из поддерживаемых типов
- Параметры зависят от типа правила
- `pattern` - должен быть валидным регулярным выражением
- `days_old` - должен быть положительным числом
- `keep_count` - должен быть положительным числом

### Проверка конфигурации

```bash
# Загрузка и валидация конфигурации
curl -X POST "http://localhost:8000/api/v1/cleanup/config/load?config_path=/path/to/config.json"

# Проверка сводки
curl "http://localhost:8000/api/v1/cleanup/config/summary"
```

## Лучшие практики

### 1. Организация конфигурации

- **Группируйте по типам данных** - временные файлы, логи, статистика
- **Используйте описательные имена категорий**
- **Комментируйте сложные правила**

### 2. Безопасность

- **Всегда тестируйте в dry-run режиме**
- **Начинайте с консервативных правил**
- **Проверяйте пути перед применением**

### 3. Производительность

- **Используйте специфичные паттерны** вместо широких
- **Ограничивайте количество файлов** в одной операции
- **Разделяйте большие операции** на несколько категорий

### 4. Мониторинг

- **Логируйте все операции**
- **Отслеживайте статистику очистки**
- **Настройте алерты на ошибки**

## Примеры сложных конфигураций

### Многоуровневая очистка

```json
{
  "version": "1.0",
  "categories": {
    "log_rotation": {
      "paths": ["/var/log/hyperliquid/"],
      "rules": [
        {
          "type": "keep_last_n_files",
          "pattern": "app\\.log\\.\\d+",
          "keep_count": 10
        },
        {
          "type": "by_creation_time",
          "days_old": 30
        }
      ]
    }
  }
}
```

### Условная очистка

```json
{
  "version": "1.0",
  "categories": {
    "conditional_cleanup": {
      "paths": ["/data/temp/"],
      "rules": [
        {
          "type": "by_pattern",
          "pattern": "temp_.*\\.tmp",
          "days_old": 1
        },
        {
          "type": "by_pattern",
          "pattern": "backup_.*\\.bak",
          "days_old": 7
        }
      ]
    }
  }
}
```

## Отладка конфигурации

### Проверка синтаксиса

```bash
# Валидация JSON
python -m json.tool config/cleanup_rules.json

# Проверка через API
curl "http://localhost:8000/api/v1/cleanup/config/summary"
```

### Тестирование правил

```bash
# Dry-run тест
curl -X POST "http://localhost:8000/api/v1/cleanup/run" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true, "force": false}'

# Получение отчета
curl "http://localhost:8000/api/v1/cleanup/report?dry_run=true"
```

### Логирование

```bash
# Просмотр логов очистки
tail -f logs/app.log | grep cleanup

# Фильтрация по категориям
tail -f logs/app.log | grep "temporary_files"
```
