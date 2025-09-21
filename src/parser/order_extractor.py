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
        self.filtered_orders_count = 0
        self.unknown_status_count = 0
        self.parsing_errors_count = 0
        self.unknown_side_count = 0
        self.rejected_status_counts = {}
        self.total_processed_count = 0
    
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
                self.unknown_side_count += 1
                self.logger.warning(f"Неизвестная сторона ордера: {raw_side}")
                return None
            
            # Нормализация статуса (обратная совместимость)
            if status == "cancelled":
                status = "canceled"  # Приводим к единому формату
            elif status == "vaultWithdrawalCanceled":
                status = "canceled"  # Обрабатываем как обычный canceled

            not_created_statuses =  [
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
                "siblingFilledCanceled",
                "positionIncreaseAtOpenInterestCapRejected",
                "positionFlipAtOpenInterestCapRejected"
            ]

            if status in not_created_statuses:
                self.filtered_orders_count += 1
                # Увеличиваем счетчик для конкретного статуса
                self.rejected_status_counts[status] = self.rejected_status_counts.get(status, 0) + 1
                return None

            if status not in ["filled", "triggered", "open", "canceled"]:
                self.unknown_status_count += 1
                self.logger.warning(f"Неизвестный статус ордера: {status}")
                # Не возвращаем None, а создаем ордер с неизвестным статусом
                # чтобы он попал в батч и был обработан
                pass  # Продолжаем создание ордера
            
            order = Order(
                id=str(order_data.get("oid")),
                symbol=order_data.get("coin"),
                side=side,
                price=float(order_data.get("limitPx", 0)),
                size=float(order_data.get("origSz", 0)),
                owner=log_entry.get("user"),
                timestamp=datetime.fromisoformat(log_entry.get("time")),
                status=status
            )
            
            return order
        except Exception as e:
            self.parsing_errors_count += 1
            self.logger.warning(f"Ошибка извлечения ордера: {e}\n{log_entry}")
            return None
        finally:
            # Увеличиваем общий счетчик обработанных записей
            self.total_processed_count += 1
            
            # Логируем детальную статистику каждые 1000 записей
            if self.total_processed_count % 1000 == 0:
                self._log_detailed_stats()
    
    def _log_detailed_stats(self):
        """Логирует детальную статистику обработки ордеров."""
        total_rejected = self.filtered_orders_count + self.unknown_status_count + self.parsing_errors_count + self.unknown_side_count
        success_rate = ((self.total_processed_count - total_rejected) / self.total_processed_count * 100) if self.total_processed_count > 0 else 0
        
        # Основная статистика
        stats_msg = (
            f"OrderExtractor stats: total={self.total_processed_count}, "
            f"success={self.total_processed_count - total_rejected} ({success_rate:.1f}%), "
            f"rejected={total_rejected}"
        )
        
        # Детальная статистика отклонений
        if self.rejected_status_counts:
            rejected_details = ", ".join([f"{status}={count}" for status, count in sorted(self.rejected_status_counts.items())])
            stats_msg += f", rejected_statuses=[{rejected_details}]"
        
        if self.parsing_errors_count > 0:
            stats_msg += f", parsing_errors={self.parsing_errors_count}"
        
        if self.unknown_side_count > 0:
            stats_msg += f", unknown_sides={self.unknown_side_count}"
        
        if self.unknown_status_count > 0:
            stats_msg += f", unknown_statuses={self.unknown_status_count}"
        
        self.logger.info(stats_msg)
        print(stats_msg)