# HyperLiquid Node Parser

Парсер логов HyperLiquid Node для извлечения данных об ордерах и предоставления их через API.

## Описание

Приложение парсит логи ноды HyperLiquid, извлекает данные об ордерах и предоставляет их через REST API с возможностью фильтрации.

## Установка

1. Клонируйте репозиторий
2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Скопируйте файл конфигурации:
```bash
cp env.example .env
```

4. Настройте переменные окружения в `.env`

## Запуск

### Локальный запуск
```bash
python run.py
```

### Через uvicorn
```bash
uvicorn src.main:app --reload
```

## API Endpoints

- `GET /` - Информация о приложении
- `GET /health` - Проверка состояния
- `GET /api/v1/orders` - Получение списка ордеров
- `GET /api/v1/config` - Получение конфигурации
- `PUT /api/v1/config` - Обновление конфигурации

## Тестирование

```bash
pytest
```

## Структура проекта

```
src/
├── main.py              # Точка входа FastAPI
├── parser/              # Парсер логов
├── api/                 # API endpoints
├── storage/             # Файловое хранение
└── watcher/             # Мониторинг файлов
```

## Конфигурация

Основные настройки в файле `.env`:

- `NODE_LOGS_PATH` - путь к логам ноды
- `API_HOST` - хост API сервера
- `API_PORT` - порт API сервера
- `LOG_LEVEL` - уровень логирования
