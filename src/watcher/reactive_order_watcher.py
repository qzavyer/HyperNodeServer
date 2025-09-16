"""Реактивный наблюдатель за ордерами - читает файл только по запросу."""

import asyncio
import re
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, List, Any, TYPE_CHECKING
from watchdog.observers import Observer

from src.models.tracked_order import TrackedOrder, OrderSearchCriteria
from src.parser.log_parser import LogParser
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

if TYPE_CHECKING:
    from src.storage.order_manager import OrderManager
    from src.websocket.websocket_manager import WebSocketManager
    from src.storage.models import Order
    from src.storage.config_manager import ConfigManager


class ReactiveOrderWatcher:
    """Реактивный наблюдатель за ордерами - читает файл только по запросу."""
    
    def __init__(
        self, 
        logs_path: str, 
        order_manager: 'OrderManager', 
        websocket_manager: 'WebSocketManager',
        config_manager: Optional['ConfigManager'] = None
    ):
        """Инициализация ReactiveOrderWatcher.
        
        Args:
            logs_path: Путь к директории с логами
            order_manager: Менеджер ордеров для обработки найденных ордеров
            websocket_manager: Менеджер WebSocket для отправки данных подписчикам
        """
        self.logs_path = Path(logs_path)
        self.order_manager = order_manager
        self.websocket_manager = websocket_manager
        self.config_manager = config_manager
        
        # Текущий файл (как в SingleFileTailWatcher)
        self.current_file_path: Optional[Path] = None
        self.current_file_handle: Optional[object] = None
        self.file_position: int = 0
        
        # Флаг для управления жизненным циклом
        self.is_running: bool = False
        
        # Отслеживаемые ордера
        self.tracked_orders: Dict[str, TrackedOrder] = {}  # order_id -> TrackedOrder
        self.is_active: bool = False  # Активен ли мониторинг
        
        # Кэширование ордеров за последние 10 секунд
        self.cached_orders: Dict[str, List['Order']] = {}  # timestamp -> orders
        self.cache_duration_seconds: int = 10
        
        # Лимиты для чтения файла
        self.max_lines_to_read: int = 10000  # Максимальное количество строк для чтения
        
        # Watchdog для переключения файлов
        self.watchdog_observer: Optional[Observer] = None
        self.event_handler: Optional[object] = None
        
        # Парсер логов
        self.log_parser = LogParser()
        
        # Мониторинг отслеживаемых ордеров
        self.monitoring_task: Optional[asyncio.Task] = None
        self.monitoring_interval_ms: float = 10.0  # 10 мс интервал мониторинга

        # Система обработки запросов
        self.active_requests: List[Dict[str, Any]] = []  # Активные запросы на поиск
        self.orders_cache: Dict[str, List['Order']] = {}  # Кэш ордеров по тикерам
        self.processing_task: Optional[asyncio.Task] = None  # Задача обработки
        self.max_tracking_time_minutes: int = 60  # Максимальное время отслеживания
    
    def _find_current_file(self) -> Optional[Path]:
        """Найти текущий файл по алгоритму SingleFileTailWatcher.
        
        Returns:
            Path к текущему файлу или None если не найден
        """
        try:
            hourly_path = self.logs_path / "node_order_statuses" / "hourly"
            logger.debug(f"Looking for current file in: {hourly_path}")
            
            if not hourly_path.exists():
                logger.warning(f"Hourly directory not found: {hourly_path}")
                return None
            
            # Find all date directories (yyyyMMdd format)
            date_dirs = []
            for item in hourly_path.iterdir():
                if item.is_dir() and re.match(r'^\d{8}$', item.name):
                    try:
                        # Validate date format
                        datetime.strptime(item.name, '%Y%m%d')
                        date_dirs.append(item)
                    except ValueError:
                        logger.debug(f"Invalid date directory: {item.name}")
                        continue
            
            if not date_dirs:
                logger.warning(f"No valid date directories found in {hourly_path}")
                return None
            
            # Find directory with maximum date
            max_date_dir = max(date_dirs, key=lambda d: d.name)
            logger.info(f"Found max date directory: {max_date_dir}")
            
            # Find all numeric files in the max date directory
            numeric_files = []
            for item in max_date_dir.iterdir():
                if item.is_file() and item.name.isdigit():
                    try:
                        hour = int(item.name)
                        if 0 <= hour <= 23:  # Valid hour range
                            numeric_files.append(item)
                    except ValueError:
                        logger.debug(f"Invalid hour file: {item.name}")
                        continue
            
            if not numeric_files:
                logger.warning(f"No valid hour files found in {max_date_dir}")
                return None
            
            # Find file with maximum hour
            max_hour_file = max(numeric_files, key=lambda f: int(f.name))
            
            # Log detailed file info
            try:
                file_stat = max_hour_file.stat()
                logger.info(f"Found current file: {max_hour_file} (date: {max_date_dir.name}, hour: {max_hour_file.name})")
                logger.info(f"File size: {file_stat.st_size} bytes, modified: {file_stat.st_mtime}")
            except Exception as e:
                logger.warning(f"Could not get file stats for {max_hour_file}: {e}")
            
            return max_hour_file
            
        except Exception as e:
            logger.error(f"Error finding current file: {e}")
            return None
    
    async def _open_current_file(self) -> None:
        """Открыть текущий файл и установить позицию в конец.
        
        Raises:
            FileNotFoundError: Если файл не найден
            IOError: Если не удалось открыть файл
        """
        if not self.current_file_path:
            raise FileNotFoundError("No current file path set")
        
        if not self.current_file_path.exists():
            raise FileNotFoundError(f"File not found: {self.current_file_path}")
        
        try:
            # Открываем файл обычным способом (не aiofiles)
            self.current_file_handle = open(self.current_file_path, 'r', encoding='utf-8')
            
            # Устанавливаем позицию в конец файла
            self.current_file_handle.seek(0, 2)  # 2 = SEEK_END
            self.file_position = self.current_file_handle.tell()
            
            logger.info(f"Opened file: {self.current_file_path} (position: {self.file_position})")
            
        except Exception as e:
            logger.error(f"Error opening file {self.current_file_path}: {e}")
            raise IOError(f"Failed to open file: {e}")
    
    async def _close_current_file(self) -> None:
        """Закрыть текущий файл."""
        if self.current_file_handle:
            try:
                self.current_file_handle.close()
                logger.info(f"Closed file: {self.current_file_path}")
            except Exception as e:
                logger.warning(f"Error closing file: {e}")
            finally:
                self.current_file_handle = None
                self.file_position = 0
    
    def _cleanup_expired_cache(self) -> None:
        """Очистить устаревшие записи из кэша."""
        current_time = time.time()
        expired_keys = []
        
        for timestamp_str in self.cached_orders.keys():
            try:
                timestamp = float(timestamp_str)
                if current_time - timestamp > self.cache_duration_seconds:
                    expired_keys.append(timestamp_str)
            except ValueError:
                # Невалидный timestamp, удаляем
                expired_keys.append(timestamp_str)
        
        for key in expired_keys:
            del self.cached_orders[key]
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    async def _read_last_lines(self, count: int) -> List[str]:
        """Прочитать последние N строк из файла.
        
        Args:
            count: Количество строк для чтения
            
        Returns:
            Список строк (от старых к новым)
            
        Raises:
            IOError: Если не удалось прочитать файл
        """
        if not self.current_file_handle:
            raise IOError("File not opened")
        
        # Ограничиваем количество строк
        count = min(count, self.max_lines_to_read)
        
        try:
            # Получаем текущую позицию
            current_position = self.current_file_handle.tell()
            
            # Читаем с конца файла
            self.current_file_handle.seek(0, 2)  # Переходим в конец
            file_size = self.current_file_handle.tell()
            
            if file_size == 0:
                return []
            
            # Читаем блоки с конца файла
            lines = []
            buffer_size = 8192  # 8KB буфер
            position = file_size
            
            while len(lines) < count and position > 0:
                # Определяем размер блока для чтения
                read_size = min(buffer_size, position)
                position -= read_size
                
                # Читаем блок
                self.current_file_handle.seek(position)
                chunk = self.current_file_handle.read(read_size)
                
                # Разбиваем на строки
                chunk_lines = chunk.split('\n')
                
                # Добавляем строки в начало списка
                if lines:
                    # Объединяем первую строку с последней из предыдущего блока
                    lines[0] = chunk_lines[-1] + lines[0]
                    lines = chunk_lines[:-1] + lines
                else:
                    lines = chunk_lines
                
                # Удаляем пустую строку в конце если есть
                if lines and lines[-1] == '':
                    lines.pop()
            
            # Возвращаем последние count строк
            result = lines[-count:] if len(lines) > count else lines
            
            # Восстанавливаем позицию
            self.current_file_handle.seek(current_position)
            
            logger.debug(f"Read {len(result)} lines from file (requested: {count})")
            return result
            
        except Exception as e:
            logger.error(f"Error reading lines from file: {e}")
            raise IOError(f"Failed to read lines: {e}")
    
    async def _search_order_in_lines(self, lines: List[str], criteria: OrderSearchCriteria) -> List['Order']:
        """Найти ордера с заданными критериями в списке строк.
        
        Args:
            lines: Список строк для поиска
            criteria: Критерии поиска ордера
            
        Returns:
            Список найденных ордеров со статусом 'open'
        """
        found_orders = []
        
        for line in lines:
            try:
                # Парсим строку через LogParser
                order = self.log_parser.parse_line(line)
                
                if order and criteria.matches_order(order):
                    found_orders.append(order)
                    logger.info(f"Found matching order: {order.symbol} {order.side} @ {order.price} (ID: {order.id})")
                    
            except Exception as e:
                # Логируем ошибки парсинга, но продолжаем обработку
                logger.debug(f"Error parsing line: {e}, line: {line[:100]}...")
                continue
        
        if found_orders:
            logger.info(f"Found {len(found_orders)} matching orders for {criteria.symbol} {criteria.side} @ {criteria.price}")
        else:
            logger.info(f"No matching orders found for {criteria.symbol} {criteria.side} @ {criteria.price}")
        
        return found_orders
    
    async def add_search_request(self, ticker: str, side: str, price: float, timestamp: str, tolerance: float = 0.000001) -> None:
        """Добавить запрос на поиск ордера.
        
        Args:
            ticker: Символ торговой пары (например, "BTC")
            side: Сторона ордера ("Bid" или "Ask")
            price: Цена ордера
            timestamp: Время сигнала в UTC (ISO format)
            tolerance: Допустимое отклонение цены (по умолчанию 0.000001)
        """
        from datetime import datetime
        
        # Парсим время сигнала
        try:
            signal_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except ValueError:
            logger.error(f"Invalid timestamp format: {timestamp}")
            return
        
        # Создаем запрос
        request = {
            'ticker': ticker,
            'side': side,
            'price': price,
            'timestamp': signal_time,
            'tolerance': tolerance,
            'request_id': f"{ticker}_{side}_{price}_{int(signal_time.timestamp())}"
        }
        
        # Добавляем в активные запросы
        self.active_requests.append(request)
        logger.info(f"Added search request: {ticker} {side} @ {price} at {timestamp}")
        
        # Запускаем обработку если еще не запущена
        if not self.processing_task or self.processing_task.done():
            logger.info(f"Creating processing task for {len(self.active_requests)} active requests")
            self.processing_task = asyncio.create_task(self._process_active_requests())
            logger.info("Processing task created successfully")
        
        logger.info(f"Added search request to queue: {len(self.active_requests)} total requests")
    
    async def find_order(self, ticker: str, side: str, price: float, tolerance: float = 0.000001) -> List['Order']:
        """Найти ордер по критериям.
        
        Args:
            ticker: Символ торговой пары (например, "BTC")
            side: Сторона ордера ("Bid" или "Ask")
            price: Цена ордера
            tolerance: Допустимое отклонение цены (по умолчанию 0.000001)
            
        Returns:
            Список найденных ордеров со статусом 'open'
        """
        logger.info(f"Searching for order: {ticker} {side} @ {price} (tolerance: {tolerance})")
        
        # Создаем критерии поиска
        criteria = OrderSearchCriteria(
            symbol=ticker,
            side=side,
            price=price,
            tolerance=tolerance
        )
        
        # Сначала ищем в кэше ордеров за последние 10 секунд
        cached_orders = await self._search_in_cache(criteria)
        if cached_orders:
            logger.info(f"Found {len(cached_orders)} orders in cache for {ticker} {side} @ {price}")
            
            # Отправляем найденные ордера из кэша в WebSocket
            await self._send_orders_to_websocket(cached_orders)
            
            return cached_orders
        
        # Если не найдено в кэше, читаем последние 1000 строк из файла
        if not self.current_file_handle:
            logger.warning("No file handle available for search")
            return []
        
        try:
            lines = await self._read_last_lines(1000)
            if not lines:
                logger.info(f"No lines to search for {ticker} {side} @ {price}")
                return []
            
            # Ищем ордера в строках
            found_orders = await self._search_order_in_lines(lines, criteria)
            
            # Добавляем найденные ордера в кэш
            if found_orders:
                await self._add_to_cache(found_orders)
                
                # Отправляем все найденные ордера в WebSocket
                await self._send_orders_to_websocket(found_orders)
            
            return found_orders
            
        except Exception as e:
            logger.error(f"Error searching for order {ticker} {side} @ {price}: {e}")
            return []

    
    async def _search_in_cache(self, criteria: OrderSearchCriteria) -> List['Order']:
        """Поиск ордеров в кэше.
        
        Args:
            criteria: Критерии поиска
            
        Returns:
            Список найденных ордеров
        """
        found_orders = []
        current_time = time.time()
        
        for timestamp_str, orders in self.cached_orders.items():
            try:
                timestamp = float(timestamp_str)
                # Проверяем, что кэш не устарел
                if current_time - timestamp <= self.cache_duration_seconds:
                    for order in orders:
                        if criteria.matches_order(order):
                            found_orders.append(order)
            except ValueError:
                continue
        
        return found_orders
    
    async def _add_to_cache(self, orders: List['Order']) -> None:
        """Добавить ордера в кэш.
        
        Args:
            orders: Список ордеров для добавления в кэш
        """
        if not orders:
            return
        
        current_time = time.time()
        timestamp_str = str(current_time)
        
        # Добавляем ордера в кэш
        self.cached_orders[timestamp_str] = orders
        
        # Очищаем устаревшие записи
        self._cleanup_expired_cache()
        
        logger.debug(f"Added {len(orders)} orders to cache at {timestamp_str}")
    
    async def start_tracking_order(self, order_id: str) -> None:
        """Начать отслеживание ордера по ID.
        
        Args:
            order_id: ID ордера для отслеживания
        """
        if order_id not in self.tracked_orders:
            # Создаем TrackedOrder с базовыми данными
            tracked_order = TrackedOrder(
                order_id=order_id,
                symbol="",  # Будет заполнено при первом обнаружении
                side="",
                price=0.0,
                owner="",
                timestamp=datetime.now(),
                search_criteria=OrderSearchCriteria("", "", 0.0)
            )
            self.tracked_orders[order_id] = tracked_order
            logger.info(f"Started tracking order: {order_id}")
            
            # Запускаем мониторинг если еще не запущен
            if not self.monitoring_task or self.monitoring_task.done():
                self.monitoring_task = asyncio.create_task(self._monitor_tracked_orders())
                logger.info("Started order monitoring task")
        else:
            logger.debug(f"Order {order_id} is already being tracked")
    
    async def stop_tracking_order(self, order_id: str) -> None:
        """Остановить отслеживание ордера.
        
        Args:
            order_id: ID ордера для остановки отслеживания
        """
        if order_id in self.tracked_orders:
            del self.tracked_orders[order_id]
            logger.info(f"Stopped tracking order: {order_id}")
            
            # Останавливаем мониторинг если больше нет отслеживаемых ордеров
            if not self.tracked_orders and self.monitoring_task and not self.monitoring_task.done():
                self.monitoring_task.cancel()
                logger.info("Stopped order monitoring task - no orders to track")
        else:
            logger.debug(f"Order {order_id} is not being tracked")
    
    async def _monitor_tracked_orders(self) -> None:
        """Мониторинг изменений статуса отслеживаемых ордеров."""
        logger.info("Started monitoring tracked orders")
        
        try:
            while self.is_running:  # Работаем пока сервис запущен
                try:
                    # Читаем новые строки из файла только если есть отслеживаемые ордера
                    if self.tracked_orders and self.current_file_handle:
                        lines = await self._read_last_lines(100)  # Читаем последние 100 строк
                        
                        # Проверяем изменения статуса отслеживаемых ордеров
                        await self._check_order_status_changes(lines)
                    
                    # Ждем интервал мониторинга
                    await asyncio.sleep(self.monitoring_interval_ms / 1000.0)
                    
                except asyncio.CancelledError:
                    logger.info("Order monitoring task cancelled")
                    break
                except Exception as e:
                    logger.error(f"Error in order monitoring: {e}")
                    await asyncio.sleep(1.0)  # Ждем 1 секунду при ошибке
                    
        except Exception as e:
            logger.error(f"Fatal error in order monitoring: {e}")
        finally:
            logger.info("Order monitoring task finished")
    
    async def _check_order_status_changes(self, lines: List[str]) -> None:
        """Проверить изменения статуса отслеживаемых ордеров.
        
        Args:
            lines: Список строк для проверки
        """
        if not lines or not self.tracked_orders:
            return
        
        orders_to_remove = []
        
        for line in lines:
            try:
                # Парсим строку
                order = self.log_parser.parse_line(line)
                
                if order and order.id in self.tracked_orders:
                    tracked_order = self.tracked_orders[order.id]
                    
                    # Обновляем данные отслеживаемого ордера
                    tracked_order.symbol = order.symbol
                    tracked_order.side = order.side
                    tracked_order.price = order.price
                    tracked_order.owner = order.owner
                    tracked_order.timestamp = order.timestamp
                    
                    # Проверяем изменение статуса
                    if order.status in ['canceled', 'filled']:
                        logger.info(f"Order {order.id} status changed to {order.status}")
                        
                        # Отправляем в WebSocket
                        await self._send_order_to_websocket(order)
                        
                        # Добавляем в список для удаления
                        orders_to_remove.append(order.id)
                        
            except Exception as e:
                logger.debug(f"Error parsing line in status monitoring: {e}")
                continue
        
        # Удаляем ордера с измененным статусом
        for order_id in orders_to_remove:
            await self.stop_tracking_order(order_id)
    
    async def _send_order_to_websocket(self, order: 'Order') -> None:
        """Отправить ордер в WebSocket.
        
        Args:
            order: Ордер для отправки
        """
        try:
            if self.websocket_manager:
                # Отправляем ордер в WebSocket
                await self.websocket_manager.broadcast_order_update(order)
                logger.info(f"Sent order {order.id} to WebSocket subscribers")
            else:
                logger.warning("WebSocket manager not available")
        except Exception as e:
            logger.error(f"Error sending order to WebSocket: {e}")
    
    async def _send_orders_to_websocket(self, orders: List['Order']) -> None:
        """Отправить список ордеров в WebSocket.
        
        Args:
            orders: Список ордеров для отправки
        """
        if not orders:
            return
        
        try:
            if self.websocket_manager:
                # Отправляем каждый ордер в WebSocket через orderUpdate канал
                for order in orders:
                    await self.websocket_manager.broadcast_order_update(order)
                
                logger.info(f"Sent {len(orders)} orders to WebSocket subscribers")
            else:
                logger.warning("WebSocket manager not available for sending orders")
        except Exception as e:
            logger.error(f"Error sending orders to WebSocket: {e}")
    
    async def initialize(self) -> None:
        """Инициализация - найти текущий файл и открыть его.
        
        TODO: Реализовать полную инициализацию в следующих итерациях
        """
        current_file = self._find_current_file()
        if current_file:
            self.current_file_path = current_file
            try:
                await self._open_current_file()
                logger.info(f"✅ ReactiveOrderWatcher initialized with file: {current_file}")
            except Exception as e:
                logger.error(f"❌ Failed to open file during initialization: {e}")
                self.current_file_path = None
        else:
            logger.error("❌ Failed to find current file during initialization")

    async def _process_active_requests(self) -> None:
        """Обработка активных запросов на поиск ордеров."""
        logger.info("Started processing active requests")
        
        try:
            while self.is_running:  # Работаем пока сервис запущен
                if self.active_requests:
                    # Находим максимальное время среди активных запросов
                    max_time = max(req['timestamp'] for req in self.active_requests)
                    
                    # Читаем файл до максимального времени
                    await self._process_file_until_time(max_time)
                    
                    # Обрабатываем все активные запросы
                    await self._process_requests_batch()
                
                # Ждем интервал мониторинга
                await asyncio.sleep(self.monitoring_interval_ms / 1000.0)
                
        except asyncio.CancelledError:
            logger.info("Active requests processing cancelled")
        except Exception as e:
            logger.error(f"Error processing active requests: {e}")
        finally:
            logger.info("Active requests processing finished")

    async def _process_file_until_time(self, target_time: datetime) -> None:
        """Читать файл до указанного времени.
        
        Args:
            target_time: Время до которого читать файл
        """
        logger.info(f"Processing file until time: {target_time}")
        
        if not self.current_file_handle:
            logger.warning("No file handle available for processing")
            return
        
        if not self.current_file_path:
            logger.warning("No current file path available for processing")
            return
        
        try:
            # Читаем последние строки (можно оптимизировать)
            lines = await self._read_last_lines(10000)
            logger.info(f"Read {len(lines)} lines from file")
            
            processed_orders = 0
            parsed_orders = 0
            for line in lines:
                try:
                    # Парсим строку
                    order = self.log_parser.parse_line(line)
                    if not order:
                        continue
                    
                    parsed_orders += 1
                    
                    # Проверяем время ордера
                    if order.timestamp >= target_time:
                        logger.info(f"Reached target time: {order.timestamp} >= {target_time}")
                        break  # Дошли до целевого времени
                    
                    processed_orders += 1
                    
                    # Проверяем конфигурацию
                    if not await self._check_order_configuration(order):
                        continue
                    
                    # Проверяем соответствие активным запросам
                    matching_requests = await self._find_matching_requests(order)
                    if not matching_requests:
                        continue
                    
                    # Добавляем в кэш
                    await self._add_order_to_cache(order)
                    
                except Exception as e:
                    logger.debug(f"Error processing line: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error processing file until time {target_time}: {e}")
        finally:
            logger.info(f"Parsed {parsed_orders} orders, processed {processed_orders} orders from file")

    async def _check_order_configuration(self, order: 'Order') -> bool:
        """Проверить соответствие ордера конфигурации.
        
        Args:
            order: Ордер для проверки
            
        Returns:
            True если ордер соответствует конфигурации
        """
        if not self.config_manager:
            return True  # Если нет конфигурации, пропускаем проверку
        
        try:
            config = self.config_manager.get_config()
            
            # Ищем конфигурацию для символа
            symbol_config = None
            for symbol in config.symbols_config:
                if symbol.symbol == order.symbol:
                    symbol_config = symbol
                    break
            
            if not symbol_config:
                return False  # Символ не найден в конфигурации
            
            # Проверяем минимальную ликвидность
            order_liquidity = order.price * order.size
            if order_liquidity < symbol_config.min_liquidity:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking order configuration: {e}")
            return False

    async def _find_matching_requests(self, order: 'Order') -> List[Dict[str, Any]]:
        """Найти запросы, которым соответствует ордер.
        
        Args:
            order: Ордер для проверки
            
        Returns:
            Список соответствующих запросов
        """
        matching_requests = []
        
        for request in self.active_requests:
            # Проверяем тикер
            if order.symbol != request['ticker']:
                continue
            
            # Проверяем сторону
            if order.side != request['side']:
                continue
            
            # Проверяем цену
            if abs(order.price - request['price']) > request['tolerance']:
                continue
            
            # Проверяем время (ордер должен быть не раньше чем за 2 секунды от запроса)
            time_diff = (request['timestamp'] - order.timestamp).total_seconds()
            if time_diff > 2.0:
                continue
            
            matching_requests.append(request)
        
        return matching_requests

    async def _add_order_to_cache(self, order: 'Order') -> None:
        """Добавить ордер в кэш.
        
        Args:
            order: Ордер для добавления
        """
        if order.symbol not in self.orders_cache:
            self.orders_cache[order.symbol] = []
        
        self.orders_cache[order.symbol].append(order)
        logger.debug(f"Added order {order.id} to cache for {order.symbol}")

    async def _process_requests_batch(self) -> None:
        """Обработать батч активных запросов."""
        processed_requests = []
        
        for request in self.active_requests:
            ticker = request['ticker']
            
            # Получаем ордера для тикера из кэша
            if ticker in self.orders_cache:
                orders = self.orders_cache[ticker]
                
                # Выбираем лучший ордер
                best_order = await self._select_best_order(orders, request)
                
                if best_order:
                    # Отправляем в WebSocket
                    await self._send_order_to_websocket(best_order)
                    
                    # Начинаем отслеживание если ордер в статусе open
                    if best_order.status == 'open':
                        await self._start_tracking_order(best_order)
                    
                    logger.info(f"Processed request for {ticker}: found order {best_order.id}")
                else:
                    logger.info(f"Processed request for {ticker}: no matching orders found")
            else:
                logger.info(f"Processed request for {ticker}: no orders in cache")
            
            # Помечаем запрос как обработанный (всегда)
            processed_requests.append(request)
        
        # Удаляем обработанные запросы
        for request in processed_requests:
            self.active_requests.remove(request)
        
        # Очищаем кэш
        self.orders_cache.clear()

    async def _select_best_order(self, orders: List['Order'], request: Dict[str, Any]) -> Optional['Order']:
        """Выбрать лучший ордер из списка.
        
        Args:
            orders: Список ордеров
            request: Запрос на поиск
            
        Returns:
            Лучший ордер или None
        """
        if not orders:
            return None
        
        # Фильтруем ордера по критериям запроса
        matching_orders = []
        for order in orders:
            if (order.symbol == request['ticker'] and
                order.side == request['side'] and
                abs(order.price - request['price']) <= request['tolerance']):
                matching_orders.append(order)
        
        if not matching_orders:
            return None
        
        # Разделяем на open и закрытые ордера
        open_orders = [o for o in matching_orders if o.status == 'open']
        closed_orders = [o for o in matching_orders if o.status in ['canceled', 'filled']]
        
        if open_orders:
            # Выбираем open ордер с максимальной ликвидностью
            best_order = max(open_orders, key=lambda o: o.price * o.size)
            return best_order
        elif closed_orders:
            # Если все закрыты, выбираем максимальный open (если есть)
            # и отправляем его вместе с закрывающим
            open_orders_all = [o for o in orders if o.status == 'open']
            if open_orders_all:
                best_open = max(open_orders_all, key=lambda o: o.price * o.size)
                # Здесь нужно найти соответствующий закрывающий ордер
                # Пока возвращаем best_open
                return best_open
        
        return None

    async def _start_tracking_order(self, order: 'Order') -> None:
        """Начать отслеживание ордера.
        
        Args:
            order: Ордер для отслеживания
        """
        tracked_order = TrackedOrder(
            order_id=order.id,
            symbol=order.symbol,
            side=order.side,
            price=order.price,
            owner=order.owner,
            timestamp=order.timestamp,
            search_criteria=OrderSearchCriteria(order.symbol, order.side, order.price)
        )
        
        self.tracked_orders[order.id] = tracked_order
        logger.info(f"Started tracking order: {order.id}")
        
        # Запускаем мониторинг если еще не запущен
        if not self.monitoring_task or self.monitoring_task.done():
            self.monitoring_task = asyncio.create_task(self._monitor_tracked_orders())

    async def start_monitoring(self) -> None:
        """Запускает мониторинг отслеживаемых ордеров."""
        logger.info("Starting ReactiveOrderWatcher monitoring...")
        
        # Устанавливаем флаг запуска
        self.is_running = True
        
        if not self.monitoring_task or self.monitoring_task.done():
            logger.info("Creating monitoring task...")
            try:
                self.monitoring_task = asyncio.create_task(self._monitor_tracked_orders())
                logger.info("✅ Reactive order watcher monitoring started")
            except Exception as e:
                logger.error(f"Error creating monitoring task: {e}")
                raise
        else:
            logger.info("Monitoring task already running")
        
        # Также запускаем обработку активных запросов
        if not self.processing_task or self.processing_task.done():
            logger.info("Creating processing task...")
            try:
                self.processing_task = asyncio.create_task(self._process_active_requests())
                logger.info("✅ Reactive order watcher processing started")
            except Exception as e:
                logger.error(f"Error creating processing task: {e}")
                raise
        else:
            logger.info("Processing task already running")
        
        logger.info("ReactiveOrderWatcher startup completed")

    async def stop_monitoring(self) -> None:
        """Останавливает мониторинг отслеживаемых ордеров."""
        logger.info("Stopping ReactiveOrderWatcher monitoring...")
        
        # Устанавливаем флаг остановки
        self.is_running = False
        
        # Отменяем задачи
        if self.monitoring_task and not self.monitoring_task.done():
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        if self.processing_task and not self.processing_task.done():
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass
        
        logger.info("✅ ReactiveOrderWatcher monitoring stopped")

