"""Order extractor for parsing order data from log entries."""

from datetime import datetime
from typing import Optional, Dict, Any
from src.storage.models import Order
from src.utils.logger import get_logger

logger = get_logger(__name__)

class OrderExtractor:
    """Извлекает Order объекты из логов нового формата."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    def extract_order(self, log_entry: dict) -> Optional['Order']:
        """Извлекает Order из нового формата лога."""
        try:
            order_data = log_entry.get("order", {})
            status = log_entry.get("status", "open")
            
            # Преобразование side: B->Bid, A->Ask
            raw_side = order_data.get("side", "")
            if raw_side == "B":
                side = "Bid"
            elif raw_side == "A":
                side = "Ask"
            else:
                self.logger.warning(f"Неизвестная сторона ордера: {raw_side}")
                return None
            
            # Нормализация статуса (обратная совместимость)
            if status == "cancelled":
                status = "canceled"  # Приводим к единому формату

            not_created_statuses = [
                "badAloPxRejected",
                "perpMarginRejected", 
                "iocCancelRejected",
                "insufficientSpotBalanceRejected",
                "reduceOnlyCanceled",
                "minTradeNtlRejected"
            ]

            if status in not_created_statuses:
                return None

            if status not in ["filled", "triggered", "open", "canceled"]:
                self.logger.warning(f"Неизвестный статус ордера: {status}")
                return None
            
            return Order(
                id=str(order_data.get("oid")),
                symbol=order_data.get("coin"),
                side=side,
                price=float(order_data.get("limitPx", 0)),
                size=float(order_data.get("sz", 0)),
                owner=log_entry.get("user"),
                timestamp=datetime.fromisoformat(log_entry.get("time")),
                status=status
            )
        except Exception as e:
            self.logger.warning(f"Ошибка извлечения ордера: {e}\n{log_entry}")
            return None