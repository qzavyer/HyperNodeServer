"""Тесты для моделей данных ReactiveOrderWatcher."""

import pytest
from datetime import datetime
from unittest.mock import Mock

from src.models.tracked_order import TrackedOrder, OrderSearchCriteria
from src.storage.models import Order


class TestOrderSearchCriteria:
    """Тесты для OrderSearchCriteria."""
    
    def test_init(self):
        """Тест инициализации OrderSearchCriteria."""
        criteria = OrderSearchCriteria(
            symbol="BTC",
            side="Bid",
            price=50000.0,
            tolerance=0.001
        )
        
        assert criteria.symbol == "BTC"
        assert criteria.side == "Bid"
        assert criteria.price == 50000.0
        assert criteria.tolerance == 0.001
    
    def test_init_default_tolerance(self):
        """Тест инициализации с дефолтным tolerance."""
        criteria = OrderSearchCriteria(
            symbol="ETH",
            side="Ask",
            price=3000.0
        )
        
        assert criteria.tolerance == 0.000001
    
    def test_matches_order_exact_match(self):
        """Тест точного совпадения ордера."""
        criteria = OrderSearchCriteria(
            symbol="BTC",
            side="Bid",
            price=50000.0,
            tolerance=0.001
        )
        
        order = Order(
            id="123",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            size=1.0,
            owner="0x123",
            timestamp=datetime.now(),
            status="open"
        )
        
        assert criteria.matches_order(order) is True
    
    def test_matches_order_within_tolerance(self):
        """Тест совпадения ордера в пределах tolerance."""
        criteria = OrderSearchCriteria(
            symbol="BTC",
            side="Bid",
            price=50000.0,
            tolerance=0.001
        )
        
        order = Order(
            id="123",
            symbol="BTC",
            side="Bid",
            price=50000.001,  # В пределах tolerance
            size=1.0,
            owner="0x123",
            timestamp=datetime.now(),
            status="open"
        )
        
        assert criteria.matches_order(order) is True
    
    def test_matches_order_outside_tolerance(self):
        """Тест несовпадения ордера за пределами tolerance."""
        criteria = OrderSearchCriteria(
            symbol="BTC",
            side="Bid",
            price=50000.0,
            tolerance=0.001
        )
        
        order = Order(
            id="123",
            symbol="BTC",
            side="Bid",
            price=50000.01,  # За пределами tolerance
            size=1.0,
            owner="0x123",
            timestamp=datetime.now(),
            status="open"
        )
        
        assert criteria.matches_order(order) is False
    
    def test_matches_order_wrong_symbol(self):
        """Тест несовпадения по символу."""
        criteria = OrderSearchCriteria(
            symbol="BTC",
            side="Bid",
            price=50000.0
        )
        
        order = Order(
            id="123",
            symbol="ETH",  # Неправильный символ
            side="Bid",
            price=50000.0,
            size=1.0,
            owner="0x123",
            timestamp=datetime.now(),
            status="open"
        )
        
        assert criteria.matches_order(order) is False
    
    def test_matches_order_wrong_side(self):
        """Тест несовпадения по направлению."""
        criteria = OrderSearchCriteria(
            symbol="BTC",
            side="Bid",
            price=50000.0
        )
        
        order = Order(
            id="123",
            symbol="BTC",
            side="Ask",  # Неправильное направление
            price=50000.0,
            size=1.0,
            owner="0x123",
            timestamp=datetime.now(),
            status="open"
        )
        
        assert criteria.matches_order(order) is False
    
    def test_matches_order_wrong_status(self):
        """Тест несовпадения по статусу."""
        criteria = OrderSearchCriteria(
            symbol="BTC",
            side="Bid",
            price=50000.0
        )
        
        order = Order(
            id="123",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            size=1.0,
            owner="0x123",
            timestamp=datetime.now(),
            status="canceled"  # Неправильный статус
        )
        
        assert criteria.matches_order(order) is False


class TestTrackedOrder:
    """Тесты для TrackedOrder."""
    
    def test_init(self):
        """Тест инициализации TrackedOrder."""
        criteria = OrderSearchCriteria(
            symbol="BTC",
            side="Bid",
            price=50000.0
        )
        
        timestamp = datetime.now()
        tracked_order = TrackedOrder(
            order_id="123",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            owner="0x123",
            timestamp=timestamp,
            search_criteria=criteria
        )
        
        assert tracked_order.order_id == "123"
        assert tracked_order.symbol == "BTC"
        assert tracked_order.side == "Bid"
        assert tracked_order.price == 50000.0
        assert tracked_order.owner == "0x123"
        assert tracked_order.timestamp == timestamp
        assert tracked_order.search_criteria == criteria
