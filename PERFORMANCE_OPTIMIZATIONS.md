# 🚀 Оптимизации производительности для больших файлов

## Проблема

Приложение подвисало при обработке файлов размером 30+ ГБ:
- HTTP-сервер долго не отвечал
- Telnet зависал при подключении
- Блокировка event loop при чтении файлов

## Решения

### 1. Асинхронное чтение файлов

**Было:** Синхронное чтение всего файла в память
```python
# Старый код - блокирует event loop
with open(path, 'r') as f:
    for line in f:  # Блокирующая операция
        process_line(line)
```

**Стало:** Асинхронное чтение по частям
```python
# Новый код - не блокирует
async with aiofiles.open(path, 'r') as f:
    while True:
        chunk = await f.read(chunk_size)  # Асинхронно
        if not chunk:
            break
        process_chunk(chunk)
```

### 2. Батчевая обработка ордеров

**Было:** Обработка по одному ордеру
```python
for order in orders:
    await order_manager.update_order(order)  # Много I/O операций
```

**Стало:** Батчевая обработка
```python
# Обработка группами по 1000 ордеров
for i in range(0, len(orders), batch_size):
    batch = orders[i:i + batch_size]
    await order_manager.update_orders_batch_async(batch)
    await asyncio.sleep(0.01)  # Небольшая пауза
```

### 3. Таймауты и ограничения

**Добавлены:**
- Таймаут на обработку файла: 5 секунд на ГБ
- Максимальный размер файла: 50 ГБ
- Максимум ордеров на файл: 1,000,000
- Размер чанка для чтения: 8KB

### 4. Оптимизация сохранения

**Было:** Сохранение при каждом обновлении
```python
await self.storage.save_orders_async(list(self.orders.values()))
```

**Стало:** Отложенное сохранение с батчингом
```python
async def _schedule_save_async(self):
    if self._save_pending:
        return
    self._save_pending = True
    await asyncio.sleep(0.1)  # Собираем обновления
    await self.storage.save_orders_async(list(self.orders.values()))
```

### 5. Middleware для мониторинга

**Добавлены:**
- `TimeoutMiddleware` - таймаут 60 секунд на запрос
- `PerformanceMiddleware` - мониторинг медленных запросов
- Endpoint `/performance` для диагностики

## Конфигурация

### Настройки производительности

```bash
# .env файл
MAX_FILE_SIZE_GB=50.0
MAX_ORDERS_PER_FILE=1000000
CHUNK_SIZE_BYTES=8192
BATCH_SIZE=1000
PROCESSING_TIMEOUT_PER_GB=5
```

### Для разных сценариев

**Большие файлы (50+ ГБ):**
```bash
MAX_FILE_SIZE_GB=100.0
CHUNK_SIZE_BYTES=16384
BATCH_SIZE=2000
PROCESSING_TIMEOUT_PER_GB=3
```

**Ограниченная память:**
```bash
MAX_FILE_SIZE_GB=20.0
MAX_ORDERS_PER_FILE=500000
BATCH_SIZE=500
PROCESSING_TIMEOUT_PER_GB=10
```

## Мониторинг

### Проверка состояния

```bash
# Общая информация о производительности
curl http://localhost:8000/performance

# Проверка здоровья системы
curl http://localhost:8000/health

# Тестирование производительности
python scripts/performance_test.py
```

### Логи производительности

Приложение автоматически логирует:
- Файлы размером > 1 ГБ
- Время обработки файлов
- Медленные запросы (> 1 секунды)
- Таймауты обработки

## Результаты

### До оптимизации
- ❌ Файлы 30 ГБ вызывали зависание
- ❌ HTTP-сервер не отвечал
- ❌ Блокировка event loop
- ❌ Высокое потребление памяти

### После оптимизации
- ✅ Поддержка файлов до 50 ГБ
- ✅ HTTP-сервер всегда отвечает
- ✅ Асинхронная обработка
- ✅ Контролируемое потребление памяти
- ✅ Автоматические таймауты
- ✅ Мониторинг производительности

## Рекомендации

### Для продакшена

1. **Мониторинг памяти** - следите за RAM
2. **Настройка таймаутов** - под ваши требования
3. **Размер батчей** - увеличьте для лучшей производительности
4. **Логирование** - используйте INFO уровень

### При проблемах

1. Уменьшите `BATCH_SIZE`
2. Увеличьте `PROCESSING_TIMEOUT_PER_GB`
3. Ограничьте `MAX_FILE_SIZE_GB`
4. Проверьте `/performance` endpoint

## Тестирование

Запустите тест производительности:
```bash
python scripts/performance_test.py
```

Это покажет:
- Время ответа endpoints
- Обработку concurrent запросов
- Рекомендации по настройке
