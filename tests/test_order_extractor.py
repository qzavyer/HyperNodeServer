import pytest
from datetime import datetime
from src.parser.order_extractor import OrderExtractor
from src.storage.models import Order

class TestOrderExtractor:
    """Тесты для OrderExtractor."""
    
    def setup_method(self):
        """Настройка перед каждым тестом."""
        self.extractor = OrderExtractor()
    
    def test_extract_order_new_format(self):
        """Тест извлечения ордера из нового формата лога."""
        # Arrange
        log_entry = {
            "time": "2025-09-02T08:26:36.877863946",
            "user": "0x123",
            "status": "open",
            "order": {
                "coin": "BTC",
                "side": "B",
                "limitPx": "50000",
                "origSz": "1.0",
                "oid": 123
            }
        }
        
        # Act
        result = self.extractor.extract_order(log_entry)
        
        # Assert
        assert result is not None
        assert result.id == "123"
        assert result.symbol == "BTC"
        assert result.side == "Bid"
        assert result.price == 50000.0
        assert result.size == 1.0
        assert result.owner == "0x123"
        assert result.status == "open"
    
    def test_extract_order_ask_side(self):
        """Тест извлечения ордера со стороной Ask."""
        # Arrange
        log_entry = {
            "time": "2025-09-02T08:26:36.877863946",
            "user": "0x456",
            "status": "filled",
            "order": {
                "coin": "ETH",
                "side": "A",
                "limitPx": "3000",
                "origSz": "10.0",
                "oid": 456
            }
        }
        
        # Act
        result = self.extractor.extract_order(log_entry)
        
        # Assert
        assert result is not None
        assert result.side == "Ask"
        assert result.status == "filled"
    
    def test_extract_order_canceled_status(self):
        """Тест извлечения отмененного ордера."""
        # Arrange
        log_entry = {
            "time": "2025-09-02T08:26:36.877863946",
            "user": "0x789",
            "status": "canceled",
            "order": {
                "coin": "HYPE",
                "side": "B",
                "limitPx": "44.663",
                "origSz": "223.03",
                "oid": 789
            }
        }
        
        # Act
        result = self.extractor.extract_order(log_entry)
        
        # Assert
        assert result is not None
        assert result.status == "canceled"
        assert result.size == 223.03
    
    def test_extract_order_invalid_side(self):
        """Тест обработки неверной стороны ордера."""
        # Arrange
        log_entry = {
            "time": "2025-09-02T08:26:36.877863946",
            "user": "0x123",
            "status": "open",
            "order": {
                "coin": "BTC",
                "side": "X",  # Неверная сторона
                "limitPx": "50000",
                "origSz": "1.0",
                "oid": 123
            }
        }
        
        # Act
        result = self.extractor.extract_order(log_entry)
        
        # Assert
        assert result is None
    
    def test_extract_order_missing_required_fields(self):
        """Тест обработки отсутствующих обязательных полей."""
        # Arrange
        log_entry = {
            "time": "2025-09-02T08:26:36.877863946",
            "user": "0x123",
            "status": "open",
            "order": {
                "coin": "BTC",
                # Отсутствует side
                "limitPx": "50000",
                "origSz": "1.0",
                "oid": 123
            }
        }
        
        # Act
        result = self.extractor.extract_order(log_entry)
        
        # Assert
        assert result is None
    
    def test_extract_order_invalid_timestamp(self):
        """Тест обработки неверного формата времени."""
        # Arrange
        log_entry = {
            "time": "invalid-timestamp",
            "user": "0x123",
            "status": "open",
            "order": {
                "coin": "BTC",
                "side": "B",
                "limitPx": "50000",
                "origSz": "1.0",
                "oid": 123
            }
        }
        
        # Act
        result = self.extractor.extract_order(log_entry)
        
        # Assert
        assert result is None
    
    def test_extract_order_rejected_statuses_return_none(self):
        """Тест что отклоненные статусы возвращают None."""
        rejected_statuses = [
            "badAloPxRejected",
            "iocCancelRejected",
            "insufficientSpotBalanceRejected",
            "marginCanceled",
            "minTradeNtlRejected",
            "perpMarginRejected",
            "perpMaxPositionRejected",
            "reduceOnlyCanceled",
            "reduceOnlyRejected",
            "scheduledCancel",
            "selfTradeCanceled",
            "siblingFilledCanceled"
        ]
        
        for status in rejected_statuses:
            # Arrange
            log_entry = {
                "time": "2025-09-02T08:26:36.877863946",
                "user": "0x123",
                "status": status,
                "order": {
                    "coin": "BTC",
                    "side": "B",
                    "limitPx": "50000",
                    "origSz": "1.0",
                    "oid": 123
                }
            }
            
            # Act
            result = self.extractor.extract_order(log_entry)
            
            # Assert
            assert result is None, f"Статус {status} должен возвращать None"