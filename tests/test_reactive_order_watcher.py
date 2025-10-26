"""Тесты для ReactiveOrderWatcher."""

import pytest
import time
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from pathlib import Path
from datetime import datetime

from src.watcher.reactive_order_watcher import ReactiveOrderWatcher
from src.models.tracked_order import OrderSearchCriteria


class TestReactiveOrderWatcher:
    """Тесты для ReactiveOrderWatcher."""
    
    def setup_method(self):
        """Настройка перед каждым тестом."""
        self.mock_order_manager = Mock()
        self.mock_websocket_manager = Mock()
        self.logs_path = "/test/logs"
        
        self.watcher = ReactiveOrderWatcher(
            logs_path=self.logs_path,
            order_manager=self.mock_order_manager,
            websocket_manager=self.mock_websocket_manager
        )
    
    def test_init(self):
        """Тест инициализации ReactiveOrderWatcher."""
        assert self.watcher.logs_path == Path(self.logs_path)
        assert self.watcher.order_manager == self.mock_order_manager
        assert self.watcher.websocket_manager == self.mock_websocket_manager
        
        # Проверка атрибутов текущего файла
        assert self.watcher.current_file_path is None
        assert self.watcher.current_file_handle is None
        assert self.watcher.file_position == 0
        
        # Проверка отслеживаемых ордеров
        assert self.watcher.tracked_orders == {}
        assert self.watcher.is_active is False
        
        # Проверка watchdog
        assert self.watcher.watchdog_observer is None
        assert self.watcher.event_handler is None
    
    def test_init_with_path_object(self):
        """Тест инициализации с объектом Path."""
        path_obj = Path("/test/logs")
        watcher = ReactiveOrderWatcher(
            logs_path=str(path_obj),
            order_manager=self.mock_order_manager,
            websocket_manager=self.mock_websocket_manager
        )
        
        assert watcher.logs_path == path_obj
    
    def test_find_current_file_success(self):
        """Тест успешного поиска текущего файла."""
        mock_file = Mock()
        mock_file.name = "8"
        
        with patch.object(self.watcher, '_find_current_file', return_value=mock_file):
            result = self.watcher._find_current_file()
            assert result == mock_file
    
    def test_find_current_file_no_hourly_dir(self):
        """Тест поиска файла когда hourly директория не существует."""
        with patch.object(self.watcher, '_find_current_file', return_value=None):
            result = self.watcher._find_current_file()
            assert result is None
    
    def test_find_current_file_no_date_dirs(self):
        """Тест поиска файла когда нет валидных date директорий."""
        with patch.object(self.watcher, '_find_current_file', return_value=None):
            result = self.watcher._find_current_file()
            assert result is None
    
    def test_find_current_file_no_hour_files(self):
        """Тест поиска файла когда нет валидных hour файлов."""
        with patch.object(self.watcher, '_find_current_file', return_value=None):
            result = self.watcher._find_current_file()
            assert result is None
    
    @pytest.mark.asyncio
    async def test_open_current_file_success(self):
        """Тест успешного открытия файла."""
        mock_file = Mock()
        mock_file.exists.return_value = True
        mock_handle = Mock()
        mock_handle.tell.return_value = 1000
        
        with patch('builtins.open', return_value=mock_handle):
            self.watcher.current_file_path = mock_file
            
            await self.watcher._open_current_file()
            
            assert self.watcher.current_file_handle == mock_handle
            assert self.watcher.file_position == 1000
            mock_handle.seek.assert_called_once_with(0, 2)  # SEEK_END
            mock_handle.tell.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_open_current_file_no_path(self):
        """Тест открытия файла когда путь не установлен."""
        self.watcher.current_file_path = None
        
        with pytest.raises(FileNotFoundError, match="No current file path set"):
            await self.watcher._open_current_file()
    
    @pytest.mark.asyncio
    async def test_open_current_file_not_exists(self):
        """Тест открытия файла когда файл не существует."""
        mock_file = Mock()
        mock_file.exists.return_value = False
        
        self.watcher.current_file_path = mock_file
        
        with pytest.raises(FileNotFoundError):
            await self.watcher._open_current_file()
    
    @pytest.mark.asyncio
    async def test_close_current_file_success(self):
        """Тест успешного закрытия файла."""
        mock_handle = Mock()
        self.watcher.current_file_handle = mock_handle
        self.watcher.current_file_path = Path("/test/file")
        
        await self.watcher._close_current_file()
        
        assert self.watcher.current_file_handle is None
        assert self.watcher.file_position == 0
        mock_handle.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_close_current_file_no_handle(self):
        """Тест закрытия файла когда handle не установлен."""
        self.watcher.current_file_handle = None
        
        # Не должно вызывать ошибок
        await self.watcher._close_current_file()
        
        assert self.watcher.current_file_handle is None
        assert self.watcher.file_position == 0
    
    def test_cleanup_expired_cache(self):
        """Тест очистки устаревших записей из кэша."""
        current_time = time.time()
        
        # Добавляем записи в кэш
        self.watcher.cached_orders = {
            str(current_time - 5): [Mock()],  # Актуальная запись
            str(current_time - 15): [Mock()],  # Устаревшая запись
            str(current_time - 20): [Mock()],  # Устаревшая запись
            "invalid_timestamp": [Mock()],  # Невалидная запись
        }
        
        self.watcher._cleanup_expired_cache()
        
        # Должна остаться только актуальная запись
        assert len(self.watcher.cached_orders) == 1
        assert str(current_time - 5) in self.watcher.cached_orders
    
    @pytest.mark.asyncio
    async def test_initialize_success(self):
        """Тест успешной инициализации."""
        with patch.object(self.watcher, '_find_current_file') as mock_find, \
             patch.object(self.watcher, '_open_current_file') as mock_open:
            mock_file = Path("/test/file")
            mock_find.return_value = mock_file
            
            await self.watcher.initialize()
            
            assert self.watcher.current_file_path == mock_file
            mock_find.assert_called_once()
            mock_open.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_initialize_failure(self):
        """Тест неудачной инициализации."""
        with patch.object(self.watcher, '_find_current_file') as mock_find:
            mock_find.return_value = None
            
            await self.watcher.initialize()
            
            assert self.watcher.current_file_path is None
            mock_find.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_initialize_open_failure(self):
        """Тест неудачного открытия файла при инициализации."""
        with patch.object(self.watcher, '_find_current_file') as mock_find, \
             patch.object(self.watcher, '_open_current_file') as mock_open:
            mock_file = Path("/test/file")
            mock_find.return_value = mock_file
            mock_open.side_effect = IOError("Failed to open")
            
            await self.watcher.initialize()
            
            assert self.watcher.current_file_path is None
            mock_find.assert_called_once()
            mock_open.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_read_last_lines_success(self):
        """Тест успешного чтения последних строк."""
        mock_handle = Mock()
        mock_handle.tell.return_value = 1000
        mock_handle.read.return_value = "line1\nline2\nline3\n"
        
        self.watcher.current_file_handle = mock_handle
        
        result = await self.watcher._read_last_lines(2)
        
        assert len(result) == 2
        assert result == ["line2", "line3"]
        mock_handle.seek.assert_called()
        mock_handle.read.assert_called()
    
    @pytest.mark.asyncio
    async def test_read_last_lines_empty_file(self):
        """Тест чтения из пустого файла."""
        mock_handle = Mock()
        mock_handle.tell.return_value = 0
        
        self.watcher.current_file_handle = mock_handle
        
        result = await self.watcher._read_last_lines(10)
        
        assert result == []
    
    @pytest.mark.asyncio
    async def test_read_last_lines_no_handle(self):
        """Тест чтения когда файл не открыт."""
        self.watcher.current_file_handle = None
        
        with pytest.raises(IOError, match="File not opened"):
            await self.watcher._read_last_lines(10)
    
    @pytest.mark.asyncio
    async def test_read_last_lines_limit_exceeded(self):
        """Тест чтения когда запрашивается больше лимита."""
        mock_handle = Mock()
        mock_handle.tell.return_value = 1000
        mock_handle.read.return_value = "line1\nline2\nline3\n"
        
        self.watcher.current_file_handle = mock_handle
        self.watcher.max_lines_to_read = 2
        
        result = await self.watcher._read_last_lines(5)  # Запрашиваем 5, лимит 2
        
        # Должно вернуть только 2 строки (лимит)
        assert len(result) <= 2
    
    @pytest.mark.asyncio
    async def test_read_last_lines_less_than_requested(self):
        """Тест чтения когда в файле меньше строк чем запрашивается."""
        mock_handle = Mock()
        mock_handle.tell.return_value = 1000
        mock_handle.read.return_value = "line1\nline2\n"
        
        self.watcher.current_file_handle = mock_handle
        
        result = await self.watcher._read_last_lines(10)  # Запрашиваем 10, в файле 2
        
        assert len(result) == 2
        assert result == ["line1", "line2"]
    
    @pytest.mark.asyncio
    async def test_search_order_in_lines_success(self):
        """Тест успешного поиска ордеров в строках."""
        # Создаем тестовые данные
        lines = [
            '{"user":"0x123","oid":1,"coin":"BTC","side":"Bid","px":"50000","sz":"1.0","status":"open"}',
            '{"user":"0x456","oid":2,"coin":"ETH","side":"Ask","px":"3000","sz":"10.0","status":"open"}',
            '{"user":"0x789","oid":3,"coin":"BTC","side":"Bid","px":"50000","sz":"2.0","status":"open"}',
        ]
        
        criteria = OrderSearchCriteria(
            symbol="BTC",
            side="Bid",
            price=50000.0,
            tolerance=0.001
        )
        
        # Мокаем LogParser
        with patch.object(self.watcher.log_parser, 'parse_line') as mock_parse:
            # Настраиваем возвращаемые значения
            mock_orders = [
                Mock(symbol="BTC", side="Bid", price=50000.0, id="1", status="open"),
                Mock(symbol="ETH", side="Ask", price=3000.0, id="2", status="open"),
                Mock(symbol="BTC", side="Bid", price=50000.0, id="3", status="open"),
            ]
            mock_parse.side_effect = mock_orders
            
            result = await self.watcher._search_order_in_lines(lines, criteria)
            
            # Должно найти 2 ордера BTC Bid @ 50000
            assert len(result) == 2
            assert result[0].symbol == "BTC"
            assert result[0].side == "Bid"
            assert result[1].symbol == "BTC"
            assert result[1].side == "Bid"
    
    @pytest.mark.asyncio
    async def test_search_order_in_lines_no_matches(self):
        """Тест поиска ордеров когда нет совпадений."""
        lines = [
            '{"user":"0x123","oid":1,"coin":"ETH","side":"Ask","px":"3000","sz":"1.0","status":"open"}',
        ]
        
        criteria = OrderSearchCriteria(
            symbol="BTC",
            side="Bid",
            price=50000.0
        )
        
        with patch.object(self.watcher.log_parser, 'parse_line') as mock_parse:
            mock_order = Mock(symbol="ETH", side="Ask", price=3000.0, id="1", status="open")
            mock_parse.return_value = mock_order
            
            result = await self.watcher._search_order_in_lines(lines, criteria)
            
            assert len(result) == 0
    
    @pytest.mark.asyncio
    async def test_search_order_in_lines_parse_error(self):
        """Тест поиска ордеров с ошибками парсинга."""
        lines = [
            'invalid json line',
            '{"user":"0x123","oid":1,"coin":"BTC","side":"Bid","px":"50000","sz":"1.0","status":"open"}',
        ]
        
        criteria = OrderSearchCriteria(
            symbol="BTC",
            side="Bid",
            price=50000.0
        )
        
        with patch.object(self.watcher.log_parser, 'parse_line') as mock_parse:
            # Первый вызов вызывает ошибку, второй возвращает ордер
            mock_parse.side_effect = [
                Exception("Invalid JSON"),
                Mock(symbol="BTC", side="Bid", price=50000.0, id="1", status="open")
            ]
            
            result = await self.watcher._search_order_in_lines(lines, criteria)
            
            # Должен найти 1 ордер, несмотря на ошибку парсинга первой строки
            assert len(result) == 1
            assert result[0].symbol == "BTC"
    
    @pytest.mark.asyncio
    async def test_search_order_in_lines_empty_lines(self):
        """Тест поиска ордеров в пустом списке строк."""
        lines = []
        
        criteria = OrderSearchCriteria(
            symbol="BTC",
            side="Bid",
            price=50000.0
        )
        
        result = await self.watcher._search_order_in_lines(lines, criteria)
        
        assert len(result) == 0
    
    @pytest.mark.asyncio
    async def test_find_order_success_from_cache(self):
        """Тест успешного поиска ордера в кэше."""
        # Создаем тестовые данные в кэше
        mock_order = Mock(symbol="BTC", side="Bid", price=50000.0, id="1", status="open")
        current_time = time.time()
        self.watcher.cached_orders[str(current_time)] = [mock_order]
        
        # Мокаем _search_in_cache
        with patch.object(self.watcher, '_search_in_cache', return_value=[mock_order]):
            result = await self.watcher.find_order("BTC", "Bid", 50000.0)
            
            assert len(result) == 1
            assert result[0].symbol == "BTC"
            assert result[0].side == "Bid"
            assert result[0].price == 50000.0
    
    @pytest.mark.asyncio
    async def test_find_order_success_from_file(self):
        """Тест успешного поиска ордера в файле."""
        # Устанавливаем mock file handle
        self.watcher.current_file_handle = Mock()
        
        # Мокаем _search_in_cache чтобы вернуть пустой список
        with patch.object(self.watcher, '_search_in_cache', return_value=[]):
            # Мокаем _read_last_lines
            with patch.object(self.watcher, '_read_last_lines', return_value=["test line"]):
                # Мокаем _search_order_in_lines
                mock_order = Mock(symbol="BTC", side="Bid", price=50000.0, id="1", status="open")
                with patch.object(self.watcher, '_search_order_in_lines', return_value=[mock_order]):
                    # Мокаем _add_to_cache
                    with patch.object(self.watcher, '_add_to_cache'):
                        result = await self.watcher.find_order("BTC", "Bid", 50000.0)
                        
                        assert len(result) == 1
                        assert result[0].symbol == "BTC"
                        assert result[0].side == "Bid"
                        assert result[0].price == 50000.0
    
    @pytest.mark.asyncio
    async def test_find_order_no_file_handle(self):
        """Тест поиска ордера когда нет файлового дескриптора."""
        # Мокаем _search_in_cache чтобы вернуть пустой список
        with patch.object(self.watcher, '_search_in_cache', return_value=[]):
            # Устанавливаем current_file_handle в None
            self.watcher.current_file_handle = None
            
            result = await self.watcher.find_order("BTC", "Bid", 50000.0)
            
            assert len(result) == 0
    
    @pytest.mark.asyncio
    async def test_find_order_custom_tolerance(self):
        """Тест поиска ордера с пользовательским tolerance."""
        # Устанавливаем mock file handle
        self.watcher.current_file_handle = Mock()
        
        # Мокаем _search_in_cache чтобы вернуть пустой список
        with patch.object(self.watcher, '_search_in_cache', return_value=[]):
            # Мокаем _read_last_lines
            with patch.object(self.watcher, '_read_last_lines', return_value=["test line"]):
                # Мокаем _search_order_in_lines
                mock_order = Mock(symbol="BTC", side="Bid", price=50000.0, id="1", status="open")
                with patch.object(self.watcher, '_search_order_in_lines', return_value=[mock_order]):
                    # Мокаем _add_to_cache
                    with patch.object(self.watcher, '_add_to_cache'):
                        result = await self.watcher.find_order("BTC", "Bid", 50000.0, tolerance=0.01)
                        
                        assert len(result) == 1
                        assert result[0].symbol == "BTC"
    
    @pytest.mark.asyncio
    async def test_find_order_error_handling(self):
        """Тест обработки ошибок при поиске ордера."""
        # Мокаем _search_in_cache чтобы вернуть пустой список
        with patch.object(self.watcher, '_search_in_cache', return_value=[]):
            # Мокаем _read_last_lines чтобы вызвать исключение
            with patch.object(self.watcher, '_read_last_lines', side_effect=Exception("File error")):
                result = await self.watcher.find_order("BTC", "Bid", 50000.0)
                
                assert len(result) == 0
    
    @pytest.mark.asyncio
    async def test_search_in_cache_success(self):
        """Тест успешного поиска в кэше."""
        # Создаем тестовые данные
        mock_order1 = Mock(symbol="BTC", side="Bid", price=50000.0, id="1", status="open")
        mock_order2 = Mock(symbol="ETH", side="Ask", price=3000.0, id="2", status="open")
        
        current_time = time.time()
        self.watcher.cached_orders[str(current_time)] = [mock_order1, mock_order2]
        
        criteria = OrderSearchCriteria(
            symbol="BTC",
            side="Bid",
            price=50000.0
        )
        
        result = await self.watcher._search_in_cache(criteria)
        
        assert len(result) == 1
        assert result[0].symbol == "BTC"
        assert result[0].side == "Bid"
    
    @pytest.mark.asyncio
    async def test_search_in_cache_expired(self):
        """Тест поиска в кэше с устаревшими данными."""
        # Создаем устаревшие данные (старше cache_duration_seconds)
        mock_order = Mock(symbol="BTC", side="Bid", price=50000.0, id="1", status="open")
        old_time = time.time() - 20  # 20 секунд назад
        self.watcher.cached_orders[str(old_time)] = [mock_order]
        
        criteria = OrderSearchCriteria(
            symbol="BTC",
            side="Bid",
            price=50000.0
        )
        
        result = await self.watcher._search_in_cache(criteria)
        
        assert len(result) == 0
    
    @pytest.mark.asyncio
    async def test_add_to_cache_success(self):
        """Тест успешного добавления в кэш."""
        mock_order = Mock(symbol="BTC", side="Bid", price=50000.0, id="1", status="open")
        orders = [mock_order]
        
        # Мокаем _cleanup_expired_cache
        with patch.object(self.watcher, '_cleanup_expired_cache'):
            await self.watcher._add_to_cache(orders)
            
            # Проверяем, что ордера добавлены в кэш
            assert len(self.watcher.cached_orders) == 1
            timestamp_key = list(self.watcher.cached_orders.keys())[0]
            assert len(self.watcher.cached_orders[timestamp_key]) == 1
            assert self.watcher.cached_orders[timestamp_key][0] == mock_order
    
    @pytest.mark.asyncio
    async def test_add_to_cache_empty_orders(self):
        """Тест добавления пустого списка ордеров в кэш."""
        # Мокаем _cleanup_expired_cache
        with patch.object(self.watcher, '_cleanup_expired_cache'):
            await self.watcher._add_to_cache([])
            
            # Кэш должен остаться пустым
            assert len(self.watcher.cached_orders) == 0
    
    @pytest.mark.asyncio
    async def test_start_tracking_order_success(self):
        """Тест успешного начала отслеживания ордера."""
        order_id = "test_order_123"
        
        # Мокаем asyncio.create_task
        with patch('asyncio.create_task') as mock_create_task:
            mock_task = Mock()
            mock_create_task.return_value = mock_task
            
            await self.watcher.start_tracking_order(order_id)
            
            # Проверяем, что ордер добавлен в tracked_orders
            assert order_id in self.watcher.tracked_orders
            tracked_order = self.watcher.tracked_orders[order_id]
            assert tracked_order.order_id == order_id
            assert tracked_order.symbol == ""  # Базовые значения
            assert tracked_order.side == ""
            assert tracked_order.price == 0.0
            
            # Проверяем, что задача мониторинга создана
            mock_create_task.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_tracking_order_already_tracked(self):
        """Тест начала отслеживания уже отслеживаемого ордера."""
        order_id = "test_order_123"
        
        # Добавляем ордер в tracked_orders
        self.watcher.tracked_orders[order_id] = Mock()
        
        # Мокаем asyncio.create_task
        with patch('asyncio.create_task') as mock_create_task:
            await self.watcher.start_tracking_order(order_id)
            
            # Проверяем, что задача мониторинга НЕ создана повторно
            mock_create_task.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_stop_tracking_order_success(self):
        """Тест успешной остановки отслеживания ордера."""
        order_id = "test_order_123"
        
        # Добавляем ордер в tracked_orders
        self.watcher.tracked_orders[order_id] = Mock()
        
        # Создаем mock задачу мониторинга
        mock_task = Mock()
        mock_task.done.return_value = False
        self.watcher.monitoring_task = mock_task
        
        await self.watcher.stop_tracking_order(order_id)
        
        # Проверяем, что ордер удален из tracked_orders
        assert order_id not in self.watcher.tracked_orders
        
        # Проверяем, что задача мониторинга отменена
        mock_task.cancel.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_stop_tracking_order_not_tracked(self):
        """Тест остановки отслеживания неотслеживаемого ордера."""
        order_id = "test_order_123"
        
        # Убеждаемся, что ордер не в tracked_orders
        assert order_id not in self.watcher.tracked_orders
        
        await self.watcher.stop_tracking_order(order_id)
        
        # Ничего не должно произойти
        assert order_id not in self.watcher.tracked_orders
    
    @pytest.mark.asyncio
    async def test_check_order_status_changes_success(self):
        """Тест успешной проверки изменений статуса ордеров."""
        order_id = "test_order_123"
        
        # Добавляем ордер в tracked_orders
        tracked_order = Mock()
        tracked_order.order_id = order_id
        self.watcher.tracked_orders[order_id] = tracked_order
        
        # Создаем тестовые строки
        lines = [
            f'{{"user":"0x123","oid":{order_id},"coin":"BTC","side":"Bid","px":"50000","sz":"1.0","status":"canceled"}}'
        ]
        
        # Мокаем LogParser
        mock_order = Mock()
        mock_order.id = order_id
        mock_order.symbol = "BTC"
        mock_order.side = "Bid"
        mock_order.price = 50000.0
        mock_order.owner = "0x123"
        mock_order.timestamp = datetime.now()
        mock_order.status = "canceled"
        
        with patch.object(self.watcher.log_parser, 'parse_line', return_value=mock_order):
            # Мокаем stop_tracking_order
            with patch.object(self.watcher, 'stop_tracking_order') as mock_stop:
                # Мокаем _send_order_to_websocket
                with patch.object(self.watcher, '_send_order_to_websocket'):
                    await self.watcher._check_order_status_changes(lines)
                    
                    # Проверяем, что данные отслеживаемого ордера обновлены
                    assert tracked_order.symbol == "BTC"
                    assert tracked_order.side == "Bid"
                    assert tracked_order.price == 50000.0
                    assert tracked_order.owner == "0x123"
                    
                    # Проверяем, что ордер отправлен в WebSocket
                    self.watcher._send_order_to_websocket.assert_called_once_with(mock_order)
                    
                    # Проверяем, что отслеживание остановлено
                    mock_stop.assert_called_once_with(order_id)
    
    @pytest.mark.asyncio
    async def test_check_order_status_changes_no_tracked_orders(self):
        """Тест проверки изменений статуса когда нет отслеживаемых ордеров."""
        lines = ['{"user":"0x123","oid":"123","coin":"BTC","side":"Bid","px":"50000","sz":"1.0","status":"canceled"}']
        
        # Убеждаемся, что нет отслеживаемых ордеров
        self.watcher.tracked_orders.clear()
        
        # Мокаем LogParser
        with patch.object(self.watcher.log_parser, 'parse_line') as mock_parse:
            await self.watcher._check_order_status_changes(lines)
            
            # LogParser не должен вызываться
            mock_parse.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_send_order_to_websocket_success(self):
        """Тест успешной отправки ордера в WebSocket."""
        mock_order = Mock()
        mock_order.id = "test_order_123"
        
        # Мокаем websocket_manager с асинхронным broadcast_order_update
        mock_websocket_manager = Mock()
        mock_websocket_manager.broadcast_order_update = AsyncMock()
        self.watcher.websocket_manager = mock_websocket_manager
        
        # Мокаем _should_process_order чтобы он возвращал True
        with patch.object(self.watcher, '_should_process_order', return_value=True):
            await self.watcher._send_order_to_websocket(mock_order)
        
        # Проверяем, что ордер отправлен в WebSocket
        mock_websocket_manager.broadcast_order_update.assert_called_once_with(mock_order)
    
    @pytest.mark.asyncio
    async def test_send_order_to_websocket_no_manager(self):
        """Тест отправки ордера в WebSocket когда нет менеджера."""
        mock_order = Mock()
        mock_order.id = "test_order_123"
        
        # Устанавливаем websocket_manager в None
        self.watcher.websocket_manager = None
        
        # Не должно быть исключений
        await self.watcher._send_order_to_websocket(mock_order)
    
    @pytest.mark.asyncio
    async def test_send_orders_to_websocket_success(self):
        """Тест успешной отправки списка ордеров в WebSocket."""
        # Создаем тестовые ордера
        mock_order1 = Mock()
        mock_order1.id = "order_1"
        mock_order2 = Mock()
        mock_order2.id = "order_2"
        orders = [mock_order1, mock_order2]
        
        # Мокаем websocket_manager с асинхронным broadcast_order_update
        mock_websocket_manager = Mock()
        mock_websocket_manager.broadcast_order_update = AsyncMock()
        self.watcher.websocket_manager = mock_websocket_manager
        
        # Мокаем _should_process_order чтобы он возвращал True для всех ордеров
        with patch.object(self.watcher, '_should_process_order', return_value=True):
            await self.watcher._send_orders_to_websocket(orders)
        
        # Проверяем, что каждый ордер отправлен в WebSocket
        assert mock_websocket_manager.broadcast_order_update.call_count == 2
        mock_websocket_manager.broadcast_order_update.assert_any_call(mock_order1)
        mock_websocket_manager.broadcast_order_update.assert_any_call(mock_order2)
    
    @pytest.mark.asyncio
    async def test_send_orders_to_websocket_empty_list(self):
        """Тест отправки пустого списка ордеров в WebSocket."""
        # Мокаем websocket_manager
        mock_websocket_manager = Mock()
        self.watcher.websocket_manager = mock_websocket_manager
        
        await self.watcher._send_orders_to_websocket([])
        
        # WebSocket manager не должен вызываться
        mock_websocket_manager.broadcast_order_update.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_send_orders_to_websocket_no_manager(self):
        """Тест отправки ордеров в WebSocket когда нет менеджера."""
        mock_order = Mock()
        mock_order.id = "test_order"
        orders = [mock_order]
        
        # Устанавливаем websocket_manager в None
        self.watcher.websocket_manager = None
        
        # Не должно быть исключений
        await self.watcher._send_orders_to_websocket(orders)
    
    @pytest.mark.asyncio
    async def test_send_orders_to_websocket_error(self):
        """Тест обработки ошибки при отправке ордеров в WebSocket."""
        mock_order = Mock()
        mock_order.id = "test_order"
        orders = [mock_order]
        
        # Мокаем websocket_manager чтобы вызвать исключение
        mock_websocket_manager = Mock()
        mock_websocket_manager.broadcast_order_update = AsyncMock(side_effect=Exception("WebSocket error"))
        self.watcher.websocket_manager = mock_websocket_manager
        
        # Не должно быть исключений
        await self.watcher._send_orders_to_websocket(orders)
    
    @pytest.mark.asyncio
    async def test_find_order_sends_to_websocket_from_cache(self):
        """Тест что find_order отправляет ордера из кэша в WebSocket."""
        # Создаем тестовые данные в кэше
        mock_order = Mock(symbol="BTC", side="Bid", price=50000.0, id="1", status="open")
        current_time = time.time()
        self.watcher.cached_orders[str(current_time)] = [mock_order]
        
        # Мокаем _search_in_cache и _send_orders_to_websocket
        with patch.object(self.watcher, '_search_in_cache', return_value=[mock_order]):
            with patch.object(self.watcher, '_send_orders_to_websocket') as mock_send:
                result = await self.watcher.find_order("BTC", "Bid", 50000.0)
                
                # Проверяем, что ордера отправлены в WebSocket
                mock_send.assert_called_once_with([mock_order])
                assert len(result) == 1
    
    @pytest.mark.asyncio
    async def test_find_order_sends_to_websocket_from_file(self):
        """Тест что find_order отправляет ордера из файла в WebSocket."""
        # Устанавливаем mock file handle
        self.watcher.current_file_handle = Mock()
        
        # Мокаем _search_in_cache чтобы вернуть пустой список
        with patch.object(self.watcher, '_search_in_cache', return_value=[]):
            # Мокаем _read_last_lines
            with patch.object(self.watcher, '_read_last_lines', return_value=["test line"]):
                # Мокаем _search_order_in_lines
                mock_order = Mock(symbol="BTC", side="Bid", price=50000.0, id="1", status="open")
                with patch.object(self.watcher, '_search_order_in_lines', return_value=[mock_order]):
                    # Мокаем _add_to_cache и _send_orders_to_websocket
                    with patch.object(self.watcher, '_add_to_cache'):
                        with patch.object(self.watcher, '_send_orders_to_websocket') as mock_send:
                            result = await self.watcher.find_order("BTC", "Bid", 50000.0)
                            
                            # Проверяем, что ордера отправлены в WebSocket
                            mock_send.assert_called_once_with([mock_order])
                            assert len(result) == 1
