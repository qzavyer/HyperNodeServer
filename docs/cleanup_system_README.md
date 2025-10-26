# HyperLiquid Node Cleanup System

## Обзор

Система автоматической очистки файлов для HyperLiquid Node, основанная на конфигурируемых правилах. Поддерживает dry-run режим для безопасного тестирования операций очистки.

## Основные возможности

- **Конфигурируемые правила очистки** - JSON-конфигурация с поддержкой различных типов правил
- **Dry-run режим** - симуляция операций без фактического удаления
- **API endpoints** - REST API для управления очисткой
- **Отчеты и статистика** - детальная информация о планируемых операциях
- **Поддержка wildcard путей** - гибкие правила для сложных структур каталогов

## Архитектура

### Компоненты системы

1. **DirectoryCleaner** (`src/cleanup/directory_cleaner.py`)
   - Основной класс для выполнения операций очистки
   - Поддержка конфигурируемых правил
   - Dry-run режим
   - Генерация отчетов

2. **API Routes** (`src/api/cleanup_routes.py`)
   - REST API endpoints
   - Интеграция с DirectoryCleaner
   - Обработка ошибок и валидация

3. **Configuration** (`config/cleanup_rules.json`)
   - JSON-конфигурация правил очистки
   - Поддержка различных типов правил
   - Валидация конфигурации

## Типы правил очистки

### 1. По дате в имени файла
```json
{
  "type": "date_in_filename",
  "pattern": "\\d{4}-\\d{2}-\\d{2}_\\d{2}:\\d{2}:\\d{2}\\.",
  "days_old": 2
}
```

### 2. Оставить последние N файлов
```json
{
  "type": "keep_last_n_files",
  "pattern": "\\d{8}",
  "keep_count": 30
}
```

### 3. Оставить последние N директорий
```json
{
  "type": "keep_last_n_dirs",
  "pattern": "\\d{8}",
  "keep_count": 10
}
```

### 4. По времени создания
```json
{
  "type": "by_creation_time",
  "days_old": 7
}
```

## API Endpoints

### Запуск очистки
```http
POST /api/v1/cleanup/run
Content-Type: application/json

{
  "dry_run": true,
  "force": false
}
```

### Получение отчета
```http
GET /api/v1/cleanup/report?dry_run=true
```

### Статистика
```http
GET /api/v1/cleanup/stats
```

### Конфигурация
```http
GET /api/v1/cleanup/config/summary
POST /api/v1/cleanup/config/load?config_path=/path/to/config.json
POST /api/v1/cleanup/config/apply?dry_run=true
```

### Состояние системы
```http
GET /api/v1/cleanup/health
```

## Использование

### 1. Загрузка конфигурации
```bash
curl -X POST "http://localhost:8000/api/v1/cleanup/config/load?config_path=/path/to/cleanup_rules.json"
```

### 2. Dry-run тестирование
```bash
curl -X POST "http://localhost:8000/api/v1/cleanup/run" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true, "force": false}'
```

### 3. Получение отчета
```bash
curl "http://localhost:8000/api/v1/cleanup/report?dry_run=true"
```

### 4. Выполнение очистки
```bash
curl -X POST "http://localhost:8000/api/v1/cleanup/run" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": false, "force": true}'
```

## Конфигурация

### Структура файла конфигурации

```json
{
  "version": "1.0",
  "categories": {
    "temporary_files": {
      "paths": ["/home/hl/hl/tmp/fu_write_string_to_file_tmp/"],
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

### Поддерживаемые типы правил

- `date_in_filename` - удаление по дате в имени файла
- `keep_last_n_files` - оставить последние N файлов
- `keep_last_n_dirs` - оставить последние N директорий
- `by_creation_time` - удаление по времени создания
- `by_pattern` - удаление по шаблону имени

## Безопасность

- **Dry-run режим** - всегда тестируйте операции в dry-run режиме
- **Валидация путей** - проверка существования путей перед операциями
- **Логирование** - детальное логирование всех операций
- **Обработка ошибок** - graceful handling ошибок

## Мониторинг

### Логи
```bash
tail -f logs/app.log | grep cleanup
```

### Health check
```bash
curl "http://localhost:8000/api/v1/cleanup/health"
```

### Статистика
```bash
curl "http://localhost:8000/api/v1/cleanup/stats"
```

## Тестирование

### Запуск тестов
```bash
# Все тесты
python -m pytest tests/ -v

# Тесты конфигурации
python -m pytest tests/test_cleanup_config.py -v

# Тесты dry-run
python -m pytest tests/test_dry_run.py -v

# Тесты API
python -m pytest tests/test_cleanup_api.py -v
```

### Покрытие тестами
```bash
python -m pytest tests/ --cov=src/cleanup --cov-report=html
```

## Troubleshooting

### Частые проблемы

1. **Пути не найдены**
   - Проверьте существование директорий
   - Убедитесь в правильности путей в конфигурации

2. **Ошибки конфигурации**
   - Проверьте JSON синтаксис
   - Валидируйте структуру правил

3. **Проблемы с правами доступа**
   - Убедитесь в правах на запись в целевые директории
   - Проверьте права пользователя приложения

### Отладка

```bash
# Включить debug логирование
export LOG_LEVEL=DEBUG

# Проверить конфигурацию
curl "http://localhost:8000/api/v1/cleanup/config/summary"

# Тестовый dry-run
curl -X POST "http://localhost:8000/api/v1/cleanup/run" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true}'
```

## Разработка

### Структура проекта
```
src/
├── cleanup/
│   └── directory_cleaner.py    # Основной класс очистки
├── api/
│   └── cleanup_routes.py       # API endpoints
config/
└── cleanup_rules.json         # Конфигурация правил
tests/
├── test_cleanup_config.py      # Тесты конфигурации
├── test_dry_run.py            # Тесты dry-run
└── test_cleanup_api.py        # Тесты API
```

### Добавление новых правил

1. Определите тип правила в `cleanup_rules.json`
2. Реализуйте логику в `DirectoryCleaner`
3. Добавьте тесты
4. Обновите документацию

## Лицензия

Проект HyperLiquid Node Cleanup System
