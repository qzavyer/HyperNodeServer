# Исправление системы очистки дискового пространства

## Проблема

1. **replica_cmds**: Не очищалась папка `replica_cmds`, в которой накопилось 20 подпапок вместо максимум 5
2. **periodic_abci_states**: Отсутствовала очистка папки `periodic_abci_states`
3. **evm_block_and_receipts/hourly**: Отсутствовала очистка папки `evm_block_and_receipts/hourly`
4. **node_fast_block_times**: Отсутствовала очистка папки `node_fast_block_times`

## Причина

- Папки в `replica_cmds` имеют формат ISO 8601 с временем: `2025-10-10T23:11:09Z`
- Старый regex паттерн `^\d{8}$` искал только формат `yyyyMMdd`
- Отсутствовали методы для очистки `periodic_abci_states`, `evm_block_and_receipts/hourly`, `node_fast_block_times`

## Решение

### Изменения в `src/cleanup/directory_cleaner.py`

1. **Добавлен новый regex паттерн для ISO datetime формата:**
```python
# Поддерживает как Linux формат (с :), так и Windows формат (с -)
self.iso_datetime_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}[:\-]\d{2}[:\-]\d{2}Z$")
```

2. **Добавлены пути для новых директорий:**
```python
self.periodic_abci_path = self.base_dir / "periodic_abci_states"
self.evm_block_receipts_path = self.base_dir / "evm_block_and_receipts" / "hourly"
self.node_fast_block_times_path = self.base_dir / "node_fast_block_times"
```

3. **Обновлен метод `_cleanup_replica_cmds_async()`:**
- Теперь использует `iso_datetime_pattern` вместо `date_pattern`
- Корректно находит и удаляет директории в формате ISO datetime
- Сохраняет последние 5 директорий (настраивается через `max_replica_dirs`)

4. **Добавлен метод `_cleanup_periodic_abci_async()`:**
- Очищает папку `periodic_abci_states`
- Сохраняет только последнюю директорию (в формате `yyyyMMdd`)
- Удаляет все остальные старые директории

5. **Добавлен метод `_cleanup_evm_block_receipts_async()`:**
- Очищает папку `evm_block_and_receipts/hourly`
- Сохраняет только последнюю директорию (в формате `yyyyMMdd`)
- Удаляет все остальные старые директории

6. **Добавлен метод `_cleanup_node_fast_block_times_async()`:**
- Очищает папку `node_fast_block_times`
- Сохраняет только последнюю директорию (в формате `yyyyMMdd`)
- Удаляет все остальные старые директории

7. **Обновлен метод `cleanup_async()`:**
- Добавлены вызовы всех новых методов очистки
- Теперь очищает 6 типов директорий: `node_order_statuses`, `replica_cmds`, `periodic_abci_states`, `evm_block_and_receipts`, `node_fast_block_times`, `checkpoints`

### Тесты

Добавлены 17 новых тестов в `tests/test_directory_cleaner.py`:

**replica_cmds:**
1. `test_cleanup_replica_cmds_async` - проверка очистки с несколькими директориями
2. `test_cleanup_replica_cmds_async_no_directories` - нет директорий
3. `test_cleanup_replica_cmds_async_less_than_max` - меньше максимума
4. `test_cleanup_replica_cmds_async_nonexistent_path` - несуществующий путь

**periodic_abci_states:**
5. `test_cleanup_periodic_abci_async` - проверка очистки с несколькими директориями
6. `test_cleanup_periodic_abci_async_single_directory` - одна директория
7. `test_cleanup_periodic_abci_async_no_directories` - нет директорий
8. `test_cleanup_periodic_abci_async_nonexistent_path` - несуществующий путь

**evm_block_and_receipts:**
9. `test_cleanup_evm_block_receipts_async` - проверка очистки с несколькими директориями
10. `test_cleanup_evm_block_receipts_async_single_directory` - одна директория
11. `test_cleanup_evm_block_receipts_async_nonexistent_path` - несуществующий путь

**node_fast_block_times:**
12. `test_cleanup_node_fast_block_times_async` - проверка очистки с несколькими директориями
13. `test_cleanup_node_fast_block_times_async_single_directory` - одна директория
14. `test_cleanup_node_fast_block_times_async_nonexistent_path` - несуществующий путь

**Общие тесты:**
15. `test_cleanup_async_all_directories` - комплексный тест всех типов директорий
16. `test_iso_datetime_pattern_validation` - валидация regex паттерна
17. `test_init` - обновлен для проверки нового паттерна

**Все тесты пройдены успешно ✅**

## Результат

После применения изменений:

- ✅ **replica_cmds**: Будет автоматически очищаться каждый час, сохраняя последние 5 директорий
- ✅ **periodic_abci_states**: Будет автоматически очищаться каждый час, сохраняя последнюю директорию
- ✅ **evm_block_and_receipts/hourly**: Будет автоматически очищаться каждый час, сохраняя последнюю директорию
- ✅ **node_fast_block_times**: Будет автоматически очищаться каждый час, сохраняя последнюю директорию
- ✅ **Совместимость**: Поддержка как Linux (с `:` в именах), так и Windows (с `-` в именах)
- ✅ **Тестирование**: Полное покрытие тестами новой функциональности (17 новых тестов)

## Конфигурация

Настройки очистки в `DirectoryCleaner.__init__()`:

```python
self.max_replica_dirs = 5           # Максимум директорий в replica_cmds
self.max_checkpoints_dirs = 10      # Максимум директорий в checkpoints
self.cleanup_interval_hours = 1     # Интервал очистки (часы)
```

## Логирование

Система пишет подробные логи о процессе очистки:

```
🧹 Starting cleanup in: /app/node_logs/node_order_statuses/hourly
Found 2 directories in /app/node_logs/node_order_statuses/hourly
🗑️ Deleting old directory: 20251001

🧹 Starting cleanup in: /app/node_logs/replica_cmds
Found 20 directories in /app/node_logs/replica_cmds
🗑️ Deleting old directory: 2025-10-01T10:30:00Z
🗑️ Deleting old directory: 2025-10-02T11:45:00Z
...

🧹 Starting cleanup in: /app/node_logs/periodic_abci_states
Found 5 directories in /app/node_logs/periodic_abci_states
🗑️ Deleting old directory: 20251001
🗑️ Deleting old directory: 20251002
...

🧹 Starting cleanup in: /app/node_logs/evm_block_and_receipts/hourly
Found 3 directories in /app/node_logs/evm_block_and_receipts/hourly
🗑️ Deleting old directory: 20251001
...

🧹 Starting cleanup in: /app/node_logs/node_fast_block_times
Found 4 directories in /app/node_logs/node_fast_block_times
🗑️ Deleting old directory: 20251001
...

✅ Cleanup completed: removed 25 directories, 0 files
```

