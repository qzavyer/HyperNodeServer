# 🔍 Diagnostic Logging Added

## Что добавлено

Добавлено **INFO level** логирование для отслеживания потока выполнения batch processing.

## Новые логи

### 1. Sequential Processing
```
🔄 Sequential processing: X lines
✅ Sequential completed: X lines → Y orders
```

### 2. Parallel Processing - Full Flow

**Начало:**
```
🔄 Parallel processing START: X lines, N workers
```

**Создание chunks:**
```
📊 Chunks created: N chunks, X lines per chunk
```

**Запуск задач:**
```
🚀 Starting parallel execution: N tasks
```

**Ожидание каждой задачи:**
```
⏳ Waiting for task 1/5...
✅ Task 1/5 completed successfully
⏳ Waiting for task 2/5...
✅ Task 2/5 completed successfully
...
```

**Завершение всех задач:**
```
✅ All parallel tasks completed: N results received
```

**Комбинирование результатов:**
```
📦 Combining results from N chunks...
✅ Parallel COMPLETED: X lines → Y orders (N workers)
```

### 3. Worker Execution (в thread pool)

**Начало:**
```
🔧 Worker START: processing X lines in thread pool
```

**Завершение:**
```
✅ Worker COMPLETED: X lines → Y orders (failed: Z)
```

### 4. Ошибки

**Timeout задачи:**
```
⏰ Task N/M timed out after 5 seconds, cancelling
```

**Ошибка задачи:**
```
❌ Task N/M failed: <error>
```

**Ошибка parallel processing:**
```
❌ Parallel batch processing FAILED: <error>
Traceback: <traceback>
```

## Как использовать

### Полный поток для успешной обработки:

```
📦 Processing batch snapshot: 16656 lines (buffer cleared)
🔄 Parallel processing START: 16656 lines, 16 workers
📊 Chunks created: 16 chunks, 1041 lines per chunk
🚀 Starting parallel execution: 16 tasks
⏳ Waiting for task 1/16...
🔧 Worker START: processing 1041 lines in thread pool
✅ Worker COMPLETED: 1041 lines → 812 orders (failed: 0)
✅ Task 1/16 completed successfully
⏳ Waiting for task 2/16...
🔧 Worker START: processing 1041 lines in thread pool
✅ Worker COMPLETED: 1041 lines → 798 orders (failed: 0)
✅ Task 2/16 completed successfully
...
✅ All parallel tasks completed: 16 results received
📦 Combining results from 16 chunks...
✅ Parallel COMPLETED: 16656 lines → 12945 orders (16 workers)
📡 WebSocket: 12945/12945 orders → 2 clients
Calling order_manager.update_orders_batch_async with 12945 orders
order_manager.update_orders_batch_async completed for 12945 orders
```

### Диагностика проблем

**Если НЕТ "Parallel processing START":**
- Проблема в условии `if buffer_size >= self.parallel_batch_size`
- Или код падает ДО входа в метод

**Если НЕТ "Chunks created":**
- Проблема в создании chunks (строка 764)
- Возможно memory allocation issue

**Если НЕТ "Starting parallel execution":**
- Проблема в создании tasks (строки 769-773)
- Возможно executor не работает

**Если НЕТ "Worker START":**
- Tasks не запускаются в thread pool
- Проблема с executor

**Если НЕТ "Worker COMPLETED":**
- Worker зависает в parsing
- Timeout срабатывает (видим `⏰ Task N/M timed out`)

**Если НЕТ "All parallel tasks completed":**
- Проблема в цикле ожидания tasks
- Exception в asyncio.wait_for

**Если НЕТ "Parallel COMPLETED":**
- Проблема в комбинировании results
- Exception после tasks

## Мониторинг команды

```bash
# Смотреть весь поток в реальном времени
docker logs hyperliquid-parser -f 2>&1 | grep -E "Processing batch snapshot|Sequential|Parallel|Worker|Waiting for task|All parallel tasks|WebSocket"

# Только критичные этапы
docker logs hyperliquid-parser -f 2>&1 | grep -E "📦|🔄|🚀|✅|❌|⏰|📡"

# Проверить последние батчи
docker logs hyperliquid-parser --tail=500 2>&1 | grep -E "Processing batch snapshot|Parallel|Sequential"
```

## Что покажут логи

После деплоя вы сразу увидите **где именно** застревает код:

1. Batch создаётся? → `📦 Processing batch snapshot`
2. Parallel processing начинается? → `🔄 Parallel processing START`
3. Chunks создаются? → `📊 Chunks created`
4. Tasks запускаются? → `🚀 Starting parallel execution`
5. Workers стартуют? → `🔧 Worker START`
6. Workers завершаются? → `✅ Worker COMPLETED`
7. Tasks завершаются? → `✅ Task N/M completed`
8. Все tasks завершены? → `✅ All parallel tasks completed`
9. Results комбинируются? → `📦 Combining results`
10. Parallel завершён? → `✅ Parallel COMPLETED`
11. WebSocket отправлен? → `📡 WebSocket`

**Где прервётся последовательность** - там и проблема!

## Пример проблемы

Если видим:
```
📦 Processing batch snapshot: 16656 lines (buffer cleared)
🔄 Parallel processing START: 16656 lines, 16 workers
📊 Chunks created: 16 chunks, 1041 lines per chunk
🚀 Starting parallel execution: 16 tasks
⏳ Waiting for task 1/16...
(ничего больше)
```

Значит проблема: **первый task не запускается или зависает в thread pool**.

