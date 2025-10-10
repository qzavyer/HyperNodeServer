# 🚀 Deployment Instructions - Memory Leak + Deadlock Fix

## Что исправлено

### 1. Memory Leak (Race Condition) ✅
- Buffer больше не растёт бесконтрольно
- Immediate buffer clearing после snapshot

### 2. Deadlock в Parallel Processing ✅
- asyncio.gather() вместо wait_for()
- Chunks ограничены количеством workers

### 3. Diagnostic Logging ✅
- Полная видимость потока обработки
- Emoji маркеры для лёгкого отслеживания

---

## Деплой на staging

### 1. Build и deploy
```bash
cd ~/apps/HyperNodeServer

# Rebuild контейнер
docker-compose build hyperliquid-parser

# Перезапуск
docker-compose down hyperliquid-parser
docker-compose up -d hyperliquid-parser

# Проверка что запустился
docker ps | grep hyperliquid-parser
```

### 2. Мониторинг (первые 5 минут - критично!)

**Терминал 1 - Полный поток:**
```bash
docker logs hyperliquid-parser -f 2>&1 | grep -E "📦|🔄|📊|🚀|⏳|✅ All|✅ Parallel|📡"
```

**Ожидаем видеть:**
```
📦 Processing batch snapshot: ~1000-30000 lines (buffer cleared)
🔄 Parallel processing START: X lines, 4 workers
📊 Chunks created: 4 chunks, ~X lines per chunk (workers: 4)  ← Ровно 4!
🚀 Starting parallel execution: 4 tasks (executor: 4 max workers)
⏳ Waiting for all 4 tasks to complete...
✅ All parallel tasks completed: 4 results received  ← КРИТИЧНО!
📦 Combining results from 4 chunks...
✅ Parallel COMPLETED: X lines → Y orders (4 chunks, 0 failed)
📡 WebSocket: Y/Y orders → Z clients  ← WebSocket работает!
```

**Терминал 2 - Проверка batch sizes:**
```bash
docker logs hyperliquid-parser -f 2>&1 | grep "📦 Processing batch snapshot"
```

**Должны видеть:**
- Стабильные размеры: 1000-30000 lines
- НЕ растущие: НЕ 100K → 200K → 500K → 1M

**Терминал 3 - Ошибки:**
```bash
docker logs hyperliquid-parser -f 2>&1 | grep -E "ERROR|⏰|❌"
```

**Не должно быть:**
- `⏰ Parallel batch timed out` - означает deadlock
- `❌ Parallel batch processing FAILED` - означает exception
- `ERROR` - любые ошибки

### 3. Проверка памяти

```bash
# Память контейнера
docker stats hyperliquid-parser --no-stream

# Должна быть стабильной, НЕ расти линейно
```

### 4. Проверка WebSocket

```bash
# WebSocket логи
docker logs hyperliquid-parser -f 2>&1 | grep "📡 WebSocket"
```

**Если видим:**
```
📡 WebSocket: 0/0 orders → 0 clients
```
Это нормально - просто нет подходящих ордеров или нет клиентов.

**Если НЕ видим совсем:**
- Либо orders = [] (все отфильтрованы)
- Либо deadlock (см. ошибки выше)

---

## Критерии успеха (5 минут мониторинга)

### ✅ Успех:
1. Видим полный поток от `📦` до `✅ Parallel COMPLETED`
2. Каждый batch завершается (`✅ All parallel tasks completed`)
3. Batch sizes стабильные (~1000-30000)
4. Память не растёт
5. Нет timeout ошибок
6. WebSocket логи появляются (если есть ордера)

### ❌ Проблема:
1. Batch sizes растут экспоненциально (memory leak)
2. Зависает на `⏳ Waiting...` без `✅ All parallel` (deadlock)
3. Видим `⏰ timed out` (deadlock)
4. Память растёт линейно (memory leak)
5. Много `❌` ошибок

---

## Rollback (если что-то пошло не так)

```bash
cd ~/apps/HyperNodeServer

# Откатываем код
git checkout HEAD~1 src/watcher/single_file_tail_watcher.py

# Rebuild и restart
docker-compose build hyperliquid-parser
docker-compose down hyperliquid-parser
docker-compose up -d hyperliquid-parser
```

---

## После успешного staging (через 1 час)

### Проверить метрики:

```bash
# Batch sizes за последний час
docker logs hyperliquid-parser --since 1h 2>&1 | grep "📦 Processing batch snapshot" | tail -20

# Все batch завершились?
docker logs hyperliquid-parser --since 1h 2>&1 | grep -c "✅ All parallel tasks completed"
docker logs hyperliquid-parser --since 1h 2>&1 | grep -c "📦 Processing batch snapshot"
# Должны быть примерно равны!

# Были timeout?
docker logs hyperliquid-parser --since 1h 2>&1 | grep -c "⏰"
# Должно быть 0!

# WebSocket работает?
docker logs hyperliquid-parser --since 1h 2>&1 | grep "📡 WebSocket" | tail -10
```

### Если всё ОК:
✅ Деплой на production!

---

## Production Deploy

После успешного staging (1+ час без проблем):

```bash
# На production сервере
cd ~/apps/HyperNodeServer
git pull
docker-compose build hyperliquid-parser
docker-compose down hyperliquid-parser
docker-compose up -d hyperliquid-parser

# Мониторинг (те же команды что на staging)
docker logs hyperliquid-parser -f 2>&1 | grep -E "📦|✅ All|📡|⏰|❌"
```

---

## Troubleshooting

### Проблема: "⏰ Parallel batch timed out after 30 seconds"

**Причина:** Workers зависают в парсинге

**Решение:**
1. Проверить что в workers: `docker logs hyperliquid-parser | grep "Worker START"`
2. Если видим START но не COMPLETED - worker завис
3. Увеличить timeout до 60 секунд (в коде)

### Проблема: Batch sizes растут

**Причина:** Race condition не исправлен

**Решение:**
1. Проверить что buffer очищается: смотреть "(buffer cleared)" в логах
2. Проверить версию кода: `git log --oneline -1`
3. Возможно нужен force rebuild: `docker-compose build --no-cache`

### Проблема: WebSocket не работает

**Причина:** orders = [] (все отфильтрованы)

**Решение:**
1. Проверить логи: `docker logs hyperliquid-parser | grep "✅ Parallel COMPLETED"`
2. Если видим "0 orders" - проблема в парсинге/фильтрации
3. Проверить settings для фильтров

---

## Контакты для помощи

При проблемах с деплоем:
1. Сохранить логи: `docker logs hyperliquid-parser > /tmp/parser_error.log`
2. Проверить метрики: `docker stats hyperliquid-parser`
3. Проверить код: `git diff HEAD~1 src/watcher/single_file_tail_watcher.py`

---

**Prepared by:** AI Assistant  
**Date:** 2025-10-07  
**Priority:** 🔴 CRITICAL  
**Impact:** High - Prevents memory exhaustion and processing failures

