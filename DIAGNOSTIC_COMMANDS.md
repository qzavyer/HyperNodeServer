# Diagnostic Commands for HyperNodeServer (Ubuntu)

## 1. Проверить что работает

```bash
docker ps | grep hyperliquid-parser
docker logs hyperliquid-parser --tail=10
```

## 2. Найти логи о batch обработке

```bash
# Последние 1000 строк, показать только Processing batch
docker logs hyperliquid-parser --tail=1000 2>&1 | grep "Processing batch"

# Последние 5000 строк, показать количество
docker logs hyperliquid-parser --tail=5000 2>&1 | grep -c "Processing batch"
```

## 3. Найти логи о добавлении в buffer

```bash
# Последние добавления
docker logs hyperliquid-parser --tail=1000 2>&1 | grep "Added.*to buffer"

# Размеры buffer'а
docker logs hyperliquid-parser --tail=1000 2>&1 | grep "buffer size:" | tail -20
```

## 4. Проверить последовательность событий

```bash
# Показать что происходит после "Decoded X lines"
docker logs hyperliquid-parser --tail=500 2>&1 | grep -A 5 "Decoded.*lines"

# Показать что происходит с batch
docker logs hyperliquid-parser --tail=500 2>&1 | grep -B 2 -A 2 "Processing batch"
```

## 5. Полная картина batch обработки

```bash
docker logs hyperliquid-parser --tail=2000 2>&1 | grep -E "Decoded|Added.*buffer|Processing batch|Parallel|WebSocket|order_manager"
```

## 6. Проверить ошибки

```bash
# Все ошибки
docker logs hyperliquid-parser --tail=1000 2>&1 | grep ERROR

# Ошибки batch обработки
docker logs hyperliquid-parser --tail=1000 2>&1 | grep -E "ERROR.*batch|ERROR.*buffer"
```

## 7. Статистика обработки

```bash
# Сколько раз Processing batch за последние логи
docker logs hyperliquid-parser --tail=10000 2>&1 | grep -c "Processing batch"

# Сколько раз Decoded lines
docker logs hyperliquid-parser --tail=10000 2>&1 | grep -c "Decoded.*lines"

# Сколько раз Added to buffer
docker logs hyperliquid-parser --tail=10000 2>&1 | grep -c "Added.*to buffer"
```

## 8. Live monitoring (полезно!)

```bash
# Смотреть в реальном времени всё важное
docker logs hyperliquid-parser -f 2>&1 | grep --line-buffered -E "Decoded|Added.*buffer|Processing batch|Parallel batch|WebSocket|completed"
```

## 9. Сохранить логи для анализа

```bash
# Сохранить последние 5000 строк
docker logs hyperliquid-parser --tail=5000 2>&1 > /tmp/parser_logs.txt

# Потом можно анализировать локально
cat /tmp/parser_logs.txt | grep "Processing batch"
```

## 10. Проверить размер buffer в текущий момент

```bash
# Последнее значение buffer size
docker logs hyperliquid-parser --tail=100 2>&1 | grep "buffer size:" | tail -1
```

---

## Что нужно узнать:

1. **Вызывается ли `Processing batch`?**
   ```bash
   docker logs hyperliquid-parser --tail=5000 2>&1 | grep "Processing batch" | wc -l
   ```

2. **Какого размера batches?**
   ```bash
   docker logs hyperliquid-parser --tail=5000 2>&1 | grep "Processing batch of"
   ```

3. **Очищается ли buffer?**
   ```bash
   docker logs hyperliquid-parser --tail=1000 2>&1 | grep "buffer size:" | tail -20
   # Смотрим - уменьшается ли число после Processing batch?
   ```

4. **Как часто декодируются строки vs обрабатываются batches?**
   ```bash
   echo "Decoded lines:"
   docker logs hyperliquid-parser --tail=1000 2>&1 | grep -c "Decoded.*lines"
   echo "Processing batches:"
   docker logs hyperliquid-parser --tail=1000 2>&1 | grep -c "Processing batch"
   ```

