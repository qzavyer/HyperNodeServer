# 🚀 План миграции на Real-time обработку

## 📝 Обзор

Текущая проблема: **40-минутная задержка** обработки ордеров неприемлема для криптотрейдинга.

**Цель**: Сократить задержку с 40 минут до 1-5 секунд через итерационную миграцию на streaming архитектуру.

## 🎯 Стратегия миграции

### Принципы:
- ✅ **Итерационная миграция** (6 недель)
- ✅ **Параллельная работа** старого и нового подходов
- ✅ **Тестирование каждого этапа**
- ✅ **Возможность отката** на любой стадии
- ✅ **Zero downtime** deployment

---

## 📋 Итерационный план

### 🔥 Итерация 1: Real-time Tail Reader
**Срок:** Неделя 1  
**Цель:** Добавить streaming обработку без изменения существующей логики

#### Архитектура:
```
┌─────────────────┐    ┌──────────────────┐
│ Existing        │    │ New Realtime     │
│ FileWatcher     │    │ TailWatcher      │
│ (batch files)   │    │ (streaming)      │
└─────────────────┘    └──────────────────┘
         │                       │
         └───────┬───────────────┘
                 │
         ┌───────▼──────┐
         │ HybridManager │ 
         │ (dedup logic) │
         └───────┬──────┘
                 │
         ┌───────▼──────┐
         │ OrderManager │
         └──────────────┘
```

#### Новые файлы:
```
src/watcher/
├── file_watcher.py          # Существующий (без изменений)  
├── realtime_watcher.py      # НОВЫЙ - streaming tail reader
└── hybrid_manager.py        # НОВЫЙ - координатор двух подходов
```

#### Реализация RealtimeWatcher:
```python
class RealtimeWatcher:
    async def tail_file(self, file_path: str):
        """Streaming tail как 'tail -f'"""
        async with aiofiles.open(file_path, 'r') as f:
            # Переходим в конец файла
            await f.seek(0, 2)
            
            while self.running:
                line = await f.readline()
                if line:
                    yield line
                else:
                    await asyncio.sleep(0.1)  # 100ms polling
```

#### Тестирование:
- [ ] Сравнение времени обработки: legacy vs realtime
- [ ] Проверка дублирования ордеров
- [ ] Мониторинг производительности

**Ожидаемый результат:** Задержка ~5-10 секунд, +50% throughput

---

### ⚡ Итерация 2: Streaming JSON Parser
**Срок:** Неделя 2  
**Цель:** Оптимизировать парсинг больших JSON файлов

#### Новые файлы:
```
src/parser/
├── log_parser.py           # Существующий
├── streaming_parser.py     # НОВЫЙ - IJSONParser для больших файлов
└── parser_factory.py       # НОВЫЙ - выбор парсера по размеру файла
```

#### Логика выбора парсера:
```python
def get_parser(file_size_gb: float) -> LogParser:
    if file_size_gb > 1.0:  # Файлы >1GB
        return StreamingParser()  # Streaming подход
    else:
        return LogParser()        # Batch подход
```

#### Реализация StreamingParser:
```python
import ijson

class StreamingParser:
    async def parse_large_file(self, file_path: str):
        """Streaming JSON parser для больших файлов"""
        async with aiofiles.open(file_path, 'rb') as f:
            async for obj in ijson.parse(f, 'item'):
                yield self.extract_order(obj)
```

#### Тестирование:
- [ ] A/B тест парсеров на одних файлах
- [ ] Измерение memory usage
- [ ] Проверка корректности парсинга

**Ожидаемый результат:** Задержка ~3-5 секунд, +100% throughput, -30% memory

---

### 🎯 Итерация 3: Smart File Prioritization
**Срок:** Неделя 3  
**Цель:** Приоритетная обработка свежих данных

#### Новые файлы:
```
src/watcher/
├── file_watcher.py
├── realtime_watcher.py  
├── hybrid_manager.py
└── priority_scheduler.py    # НОВЫЙ - умная очередь файлов
```

#### Алгоритм приоритизации:
```python
class FilePriority:
    REALTIME = 1      # Текущий активный файл
    RECENT = 2        # Файлы <1 часа  
    HISTORICAL = 3    # Старые файлы
    
def schedule_files(files: List[File]) -> Queue[File]:
    # Сортировка: сначала свежие, потом исторические
    current_hour = get_current_hour_file()
    recent_files = get_files_last_hour()
    historical_files = get_older_files()
    
    return Queue([current_hour] + recent_files + historical_files)
```

#### Тестирование:
- [ ] Проверка порядка обработки файлов
- [ ] Измерение задержки для свежих данных
- [ ] Stress test с большим количеством файлов

**Ожидаемый результат:** Задержка ~1-3 секунды, +150% throughput

---

### 🔄 Итерация 4: Dual-Stream Architecture
**Срок:** Неделя 4  
**Цель:** Параллельные потоки обработки

#### Архитектура:
```
┌─────────────────┐    ┌─────────────────┐
│ Fast Stream     │    │ Batch Stream    │
│ (current file)  │    │ (historical)    │
│ Latency: ~1sec  │    │ Latency: ~mins  │
└─────────────────┘    └─────────────────┘
         │                       │
         └───────┬───────────────┘
                 │
         ┌───────▼──────┐
         │ OrderMerger  │ 
         │ (timestamp   │
         │  dedup)      │
         └───────┬──────┘
                 │
         ┌───────▼──────┐
         │ WebSocket    │
         │ Broadcaster  │
         └──────────────┘
```

#### Конфигурация:
```python
class ProcessingConfig:
    fast_stream_enabled: bool = True
    batch_stream_enabled: bool = True
    dedup_window_seconds: int = 60
    fast_stream_file_pattern: str = "*/[0-9]"  # Текущий файл
    batch_stream_max_delay_hours: int = 6
```

#### Реализация OrderMerger:
```python
class OrderMerger:
    def __init__(self):
        self.seen_orders = {}  # order_id -> timestamp
        
    async def merge_order(self, order: Order, source: str):
        """Дедупликация ордеров из разных потоков"""
        if order.id in self.seen_orders:
            if source == "fast_stream":
                return  # Fast stream имеет приоритет
        
        self.seen_orders[order.id] = order.timestamp
        await self.broadcast_order(order)
```

#### Тестирование:
- [ ] End-to-end latency test
- [ ] Data consistency verification
- [ ] Failover scenarios

**Ожидаемый результат:** Задержка ~1 секунда, +200% throughput

---

### 📊 Итерация 5: Performance Monitoring
**Срок:** Неделя 5  
**Цель:** Мониторинг и алертинг производительности

#### Новые метрики:
```python
class StreamingMetrics:
    fast_stream_latency: float      # Задержка fast stream
    batch_stream_latency: float     # Задержка batch stream
    orders_per_second: float        # Throughput
    duplicate_orders_count: int     # Дублирование
    memory_usage_mb: float          # Потребление памяти
    file_processing_queue_size: int # Размер очереди
```

#### Dashboard endpoints:
```
GET /metrics/streaming          # Метрики производительности
GET /metrics/latency           # Задержки по потокам
GET /metrics/comparison        # Сравнение legacy vs new
```

#### Тестирование:
- [ ] Load testing (высокая нагрузка)
- [ ] Memory leak detection
- [ ] Alerting configuration

**Ожидаемый результат:** Полный мониторинг производительности

---

### 🎛️ Итерация 6: Feature Toggle & Migration
**Срок:** Неделя 6  
**Цель:** Плавный переход и откат при проблемах

#### Configuration-driven переключение:
```yaml
# config/processing.yaml
processing:
  mode: "hybrid"  # legacy | realtime | hybrid
  
  legacy:
    enabled: true
    batch_size: 1000
    
  realtime:
    enabled: true
    tail_interval_ms: 100
    
  hybrid:
    primary_stream: "realtime"     # realtime | legacy
    fallback_enabled: true
    consistency_check: true
```

#### Migration phases:
1. **Phase 1**: `hybrid` mode (оба потока, legacy primary)
2. **Phase 2**: `hybrid` mode (оба потока, realtime primary)  
3. **Phase 3**: `realtime` mode (только новый поток)

#### Testing & Rollback:
- [ ] Canary deployment (10% traffic)
- [ ] A/B testing (50/50 split)
- [ ] Full migration with rollback plan
- [ ] Performance benchmarks

**Ожидаемый результат:** Готовая production система с возможностью отката

---

## 📈 Ожидаемые результаты

| Итерация | Задержка | Throughput | Memory | Готовность |
|----------|----------|------------|---------|------------|
| 1        | ~5-10 сек | +50%      | +20%    | MVP        |
| 2        | ~3-5 сек  | +100%     | -30%    | Beta       |
| 3        | ~1-3 сек  | +150%     | -30%    | RC         |
| 4        | ~1 сек    | +200%     | -20%    | Production |
| 5        | ~1 сек    | +200%     | -20%    | Monitoring |
| 6        | ~1 сек    | +200%     | -20%    | Complete   |

## 🔧 Технические требования

### Зависимости:
```bash
# Для streaming JSON parsing
pip install ijson

# Для async file operations
pip install aiofiles

# Для monitoring
pip install prometheus-client
```

### Настройки системы:
```bash
# Увеличить лимиты file descriptors
ulimit -n 65536

# Настроить inotify для file watching
echo 8192 > /proc/sys/fs/inotify/max_user_watches
```

## 🚨 Риски и митигация

### Риски:
1. **Memory leaks** в streaming парсере
2. **Дублирование ордеров** между потоками
3. **Race conditions** при параллельной обработке
4. **Increased complexity** кодовой базы

### Митигация:
1. **Comprehensive testing** на каждой итерации
2. **Memory profiling** и мониторинг
3. **Feature toggles** для быстрого отката
4. **Detailed documentation** и code reviews

## 📚 Документация

### Обновления документации:
- [ ] API документация для новых endpoints
- [ ] Архитектурные диаграммы
- [ ] Troubleshooting guide
- [ ] Performance tuning guide
- [ ] Migration runbook

## ✅ Критерии успеха

### Обязательные:
- [ ] Задержка обработки < 5 секунд
- [ ] Zero data loss
- [ ] Backward compatibility
- [ ] Успешный rollback test

### Желательные:
- [ ] Задержка < 1 секунды
- [ ] 50% improvement в throughput
- [ ] Reduced memory usage
- [ ] Improved monitoring

---

**Статус**: 📝 Планирование  
**Следующий шаг**: Начать Итерацию 1 - Real-time Tail Reader  
**Ответственный**: Development Team  
**Обновлено**: 2025-09-09
