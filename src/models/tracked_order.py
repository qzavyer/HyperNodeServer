"""Модели данных для ReactiveOrderWatcher."""

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.storage.models import Order


@dataclass
class OrderSearchCriteria:
    """Критерии поиска ордера."""
    
    symbol: str
    side: str  # Bid/Ask
    price: float
    tolerance: float = 0.000001
    
    def matches_order(self, order: 'Order') -> bool:
        """Проверяет, соответствует ли ордер критериям поиска.
        
        Args:
            order: Объект Order для проверки
            
        Returns:
            True если ордер соответствует критериям, False иначе
        """
        return (self.symbol == order.symbol and 
                self.side == order.side and 
                abs(self.price - order.price) <= self.tolerance and
                order.status == 'open')


@dataclass
class TrackedOrder:
    """Отслеживаемый ордер."""
    
    order_id: str
    symbol: str
    side: str
    price: float
    owner: str
    timestamp: datetime
    search_criteria: OrderSearchCriteria
