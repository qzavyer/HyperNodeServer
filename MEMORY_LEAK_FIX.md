# 🐛 Memory Leak Fix - Buffer Race Condition

## Проблема

### Симптомы
- Buffer (`line_buffer`) растет бесконтрольно: от 41M до 44M+ строк за короткое время
- Память сервера расходуется экспоненциально
- Логи показывают: `Processing batch of 43,878,206 lines` → `Processing batch of 44,095,415 lines` (рост!)

### Причина: Race Condition

**Архитектура проблемы:**

```python
# ❌ СТАРЫЙ КОД (с проблемой)

async def _process_batch(self):
    # 1. Начинаем обработку buffer (ДОЛГО!)
    if len(self.line_buffer) >= 1000:
        orders = await self._process_batch_parallel(self.line_buffer)  # 5+ секунд
        
    # 2. ТОЛЬКО ПОТОМ очищаем
    self.line_buffer.clear()  # <-- СЛИШКОМ ПОЗДНО!

# Параллельно в другой корутине:
async def _read_new_lines(self):
    # Продолжает добавлять в line_buffer
    for line in new_lines:
        self.line_buffer.append(line)  # <-- Добавляется пока идёт обработка!
```

**Что происходит:**
1. Итерация 1: `_process_batch()` начинает обработку 43M строк
2. **Пока обрабатывается** (5+ секунд):
   - `_read_new_lines()` продолжает добавлять строки
   - Buffer растет: 43M → 43.2M → 43.5M → 44M
3. Итерация 2: `_process_batch()` обрабатывает уже 44M строк!
4. Результат: **Buffer никогда не очищается полностью, только растет!**

### Доказательство из логов

```
# Логи показывают проблему:
2025-10-07T14:37:21 [INFO] Processing batch of 43,878,206 lines
2025-10-07T14:37:21 [INFO] Added 1000 lines to buffer, buffer size: 43,879,206  ← Растёт!
2025-10-07T14:37:22 [INFO] Added 2000 lines to buffer, buffer size: 43,880,206  ← Растёт!
...
2025-10-07T14:37:35 [INFO] Processing batch of 44,095,415 lines  ← Ещё больше!
```

## Решение

### Критическое изменение: Immediate Buffer Clearing

```python
# ✅ НОВЫЙ КОД (исправлен)

async def _process_batch(self):
    if not self.line_buffer:
        return
    
    # 🔑 КРИТИЧНО: Создаём snapshot и СРАЗУ очищаем!
    lines_to_process = list(self.line_buffer)  # Копия
    buffer_size = len(lines_to_process)
    self.line_buffer.clear()  # ← Очищаем НЕМЕДЛЕННО!
    
    logger.info(f"📦 Processing batch snapshot: {buffer_size} lines (buffer cleared)")
    
    # Теперь обрабатываем КОПИЮ, не оригинал
    if buffer_size >= self.parallel_batch_size:
        orders = await self._process_batch_parallel(lines_to_process)
    else:
        orders = await self._process_batch_sequential(lines_to_process)
    
    # Buffer уже очищен, новые _read_new_lines() пишут в чистый buffer
```

### Почему это работает

1. **Snapshot:** Создаём копию текущего buffer
2. **Immediate Clear:** Очищаем buffer **до** начала обработки
3. **Independent Processing:** Обрабатываем snapshot, не трогая buffer
4. **Concurrent Safety:** Новые `_read_new_lines()` пишут в **очищенный** buffer

**Результат:**
- Batch 1: snapshot 43M строк → buffer очищен → обработка идёт
- Пока обрабатывается Batch 1: новые строки идут в **новый** buffer (0 → 217K)
- Batch 2: snapshot 217K строк → buffer очищен → обработка идёт
- **Рост предотвращён!** ✅

## Тестирование

### Запуск тестов

```bash
# Все тесты race condition
pytest tests/test_buffer_race_condition.py -v

# Конкретный тест memory leak
pytest tests/test_buffer_race_condition.py::TestBufferMemoryLeak::test_buffer_does_not_grow_indefinitely -v
```

### Ключевые тесты

1. **`test_buffer_cleared_immediately_after_snapshot`**
   - Проверяет что buffer = 0 **во время** обработки
   - Гарантирует immediate clearing

2. **`test_concurrent_read_and_process_no_data_loss`**
   - Симулирует параллельные `_read_new_lines()` и `_process_batch()`
   - Проверяет что данные не теряются

3. **`test_buffer_snapshot_independence`**
   - Проверяет что snapshot независим от buffer
   - Изменения buffer не влияют на обработку

4. **`test_buffer_does_not_grow_indefinitely`**
   - **Главный тест!** Проверяет защиту от memory leak
   - Симулирует 10 циклов read/process
   - Проверяет что buffer не превышает разумный размер

## Мониторинг после деплоя

### Логи для проверки

```bash
# Смотрим размеры batch
docker logs hyperliquid-parser -f 2>&1 | grep "Processing batch snapshot"

# Должны видеть:
# 📦 Processing batch snapshot: 1174 lines (buffer cleared)
# 📦 Processing batch snapshot: 1175 lines (buffer cleared)
# 📦 Processing batch snapshot: 1176 lines (buffer cleared)
# ✅ Размеры стабильные, не растут!
```

### Метрики для отслеживания

1. **Размер batch:** Должен быть стабильным (~1000-2000 строк)
2. **Память процесса:** Не должна расти линейно
3. **Лог "buffer cleared":** Должен появляться в каждом batch

### Признаки что исправление работает

✅ **Хорошо:**
- Batch sizes: `1174 → 1175 → 1176 → 1177` (малый рост)
- Память стабильна
- Нет логов типа "Added 1000 lines to buffer, buffer size: 43M+"

❌ **Плохо (проблема вернулась):**
- Batch sizes: `1000 → 10000 → 100000 → 1M` (экспоненциальный рост)
- Память растёт
- Логи показывают огромные buffer sizes

## Технические детали

### Performance Impact

- **Копирование buffer:** `O(n)` где n = размер buffer (~1000-2000 строк)
- **Overhead:** ~1-2ms для копирования 1000 строк
- **Benefit:** Предотвращение memory leak и OOM (Out of Memory)

**Вывод:** Незначительный overhead полностью оправдан защитой от критической проблемы.

### Альтернативные решения (не выбраны)

1. **Lock/Mutex:** Блокировали бы buffer → потеря concurrency
2. **Queue вместо list:** Сложнее, не решает корневую проблему
3. **Один поток:** Теряем parallel processing

**Выбранное решение** (snapshot + immediate clear) - оптимально по простоте и эффективности.

## Checklist для деплоя

- [x] Исправление применено в `single_file_tail_watcher.py`
- [x] Тесты написаны и проходят
- [x] Документация создана
- [ ] Code review пройден
- [ ] Деплой на staging
- [ ] Мониторинг логов 1 час
- [ ] Проверка метрик памяти
- [ ] Деплой на production

## История изменений

**2025-10-07:** Обнаружена и исправлена race condition в `_process_batch()`
- Проблема: Buffer рос от 41M до 44M+ строк
- Решение: Immediate buffer clearing после snapshot
- Тесты: 7 unit tests покрывают все сценарии
- Status: ✅ Готово к деплою

