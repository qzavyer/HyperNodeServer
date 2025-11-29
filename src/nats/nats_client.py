"""Базовый NATS клиент для подключения к серверу."""

import asyncio
import json
import logging
from typing import Optional, Dict, Any, Callable
from datetime import datetime

import nats

from .auth import JWTAuth
from .monitoring import NATSMonitoring

logger = logging.getLogger(__name__)


class NATSClient:
    """Базовый клиент для работы с NATS сервером."""
    
    def __init__(self, max_retry_attempts: int = 5, retry_delay: float = 1.0):
        """Инициализация NATS клиента.
        
        Args:
            max_retry_attempts: Максимальное количество попыток переподключения
            retry_delay: Базовая задержка между попытками (секунды)
        """
        self._nc: Optional[nats.NATS] = None
        self._is_connected = False
        self._auth = JWTAuth()
        self._config_callback: Optional[Callable] = None
        self._config_subscription: Optional[Any] = None
        
        # Параметры retry
        self._max_retry_attempts = max_retry_attempts
        self._retry_delay = retry_delay
        self._retry_count = 0
        self._reconnect_task: Optional[asyncio.Task] = None
        
        # Мониторинг
        self._monitoring = NATSMonitoring()
    
    async def connect(self, url: str = "nats://localhost:4222", creds_file: Optional[str] = None) -> None:
        """Подключается к NATS серверу.
        
        Args:
            url: URL NATS сервера
            creds_file: Путь к JWT файлу с учетными данными
            
        Raises:
            ConnectionError: Если не удалось подключиться
            ValueError: Если неверные учетные данные
        """
        try:
            logger.info(f"Подключение к NATS серверу: {url}")
            
            # Загружаем учетные данные если указан файл
            connection_options = {}
            if creds_file:
                logger.info(f"Загрузка JWT файла: {creds_file}")
                self._auth.load_credentials(creds_file)
                connection_options = self._auth.get_connection_options()
                logger.info("JWT аутентификация настроена")
            
            # Подключаемся с опциями
            if connection_options:
                self._nc = await nats.connect(url, **connection_options)
            else:
                self._nc = await nats.connect(url)
            
            self._is_connected = True
            self._monitoring.on_connection_established()
            logger.info("Успешно подключен к NATS серверу")
            
        except Exception as e:
            logger.error(f"Ошибка подключения к NATS: {e}")
            self._is_connected = False
            raise ConnectionError(f"Не удалось подключиться к NATS: {e}")
    
    async def disconnect(self) -> None:
        """Отключается от NATS сервера."""
        if self._nc and self._is_connected:
            try:
                # Отписываемся от конфигураций
                if self._config_subscription:
                    await self._config_subscription.unsubscribe()
                    self._config_subscription = None
                    logger.info("Отписались от конфигурационных сообщений")
                
                await self._nc.close()
                self._is_connected = False
                self._monitoring.on_connection_lost()
                logger.info("Отключен от NATS сервера")
            except Exception as e:
                logger.error(f"Ошибка при отключении от NATS: {e}")
    
    def is_connected(self) -> bool:
        """Проверяет состояние подключения.
        
        Returns:
            True если подключен, False иначе
        """
        return self._is_connected and self._nc is not None
    
    def load_credentials(self, creds_file: str) -> None:
        """Загружает JWT файл с учетными данными.
        
        Args:
            creds_file: Путь к JWT файлу
            
        Raises:
            FileNotFoundError: Если файл не найден
            ValueError: Если файл содержит неверные данные
        """
        self._auth.load_credentials(creds_file)
        logger.info(f"JWT учетные данные загружены из: {creds_file}")
    
    def is_authenticated(self) -> bool:
        """Проверяет, загружены ли учетные данные.
        
        Returns:
            True если данные загружены, False иначе
        """
        return self._auth.is_loaded()
    
    async def publish_order_data(self, order_data: Dict[str, Any], topic: str = "parser_data.orders") -> None:
        """Публикует данные ордера в NATS топик с retry механизмом.
        
        Args:
            order_data: Данные ордера для публикации
            topic: NATS топик для публикации
            
        Raises:
            ConnectionError: Если не удалось подключиться после всех попыток
            ValueError: Если данные невалидны
        """
        await self._publish_with_retry(order_data, topic)
    
    async def _publish_with_retry(self, order_data: Dict[str, Any], topic: str) -> None:
        """Публикует данные с повторными попытками при ошибках.
        
        Args:
            order_data: Данные ордера для публикации
            topic: NATS топик для публикации
        """
        last_error = None
        
        for attempt in range(self._max_retry_attempts):
            try:
                # Проверяем подключение
                if not self.is_connected():
                    logger.warning(f"Попытка {attempt + 1}: Не подключен к NATS, пытаемся переподключиться")
                    await self._reconnect_with_retry()
                
                # Валидация данных
                self._validate_order_data(order_data)
                
                # Форматирование данных
                formatted_data = self._format_order_data(order_data)
                
                # Публикация в NATS
                message = json.dumps(formatted_data, ensure_ascii=False, default=str)
                await self._nc.publish(topic, message.encode('utf-8'))
                
                # Обновляем метрики
                self._monitoring.on_message_sent()
                
                logger.debug(f"Опубликованы данные ордера {order_data.get('id', 'unknown')} в топик {topic}")
                self._retry_count = 0  # Сбрасываем счетчик при успехе
                return
                
            except Exception as e:
                last_error = e
                self._monitoring.on_error(str(e))
                logger.warning(f"Попытка {attempt + 1} публикации не удалась: {e}")
                
                if attempt < self._max_retry_attempts - 1:
                    # Экспоненциальная задержка
                    delay = self._retry_delay * (2 ** attempt)
                    logger.info(f"Повторная попытка через {delay} секунд")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Все {self._max_retry_attempts} попыток публикации исчерпаны")
        
        # Если все попытки исчерпаны
        raise ConnectionError(f"Не удалось опубликовать данные после {self._max_retry_attempts} попыток: {last_error}")
    
    async def _reconnect_with_retry(self) -> None:
        """Переподключается к NATS серверу с повторными попытками.
        
        Raises:
            ConnectionError: Если не удалось переподключиться
        """
        last_error = None
        
        for attempt in range(self._max_retry_attempts):
            try:
                logger.info(f"Попытка переподключения {attempt + 1}/{self._max_retry_attempts}")
                
                # Закрываем существующее соединение
                if self._nc:
                    try:
                        await self._nc.close()
                    except:
                        pass
                
                # Подключаемся заново
                await self.connect()
                
                # Восстанавливаем подписку на конфигурации
                if self._config_callback:
                    await self.subscribe_to_config(self._config_callback)
                
                logger.info("Переподключение успешно")
                self._monitoring.on_reconnect()
                self._retry_count = 0
                return
                
            except Exception as e:
                last_error = e
                self._monitoring.on_error(str(e))
                logger.warning(f"Попытка переподключения {attempt + 1} не удалась: {e}")
                
                if attempt < self._max_retry_attempts - 1:
                    # Экспоненциальная задержка
                    delay = self._retry_delay * (2 ** attempt)
                    logger.info(f"Повторная попытка переподключения через {delay} секунд")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Все {self._max_retry_attempts} попыток переподключения исчерпаны")
        
        # Если все попытки исчерпаны
        raise ConnectionError(f"Не удалось переподключиться после {self._max_retry_attempts} попыток: {last_error}")
    
    def get_retry_stats(self) -> Dict[str, Any]:
        """Получает статистику retry операций.
        
        Returns:
            Словарь со статистикой
        """
        return {
            "retry_count": self._retry_count,
            "max_retry_attempts": self._max_retry_attempts,
            "retry_delay": self._retry_delay,
            "is_connected": self.is_connected(),
            "is_authenticated": self.is_authenticated()
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Получает статус здоровья NATS соединения.
        
        Returns:
            Словарь со статусом здоровья
        """
        return self._monitoring.get_health_status()
    
    def get_metrics(self) -> Dict[str, Any]:
        """Получает метрики NATS клиента.
        
        Returns:
            Словарь с метриками
        """
        return self._monitoring.get_metrics()
    
    def reset_metrics(self) -> None:
        """Сбрасывает все метрики мониторинга."""
        self._monitoring.reset_metrics()
    
    def _validate_order_data(self, order_data: Dict[str, Any]) -> None:
        """Валидирует данные ордера перед публикацией.
        
        Args:
            order_data: Данные ордера для валидации
            
        Raises:
            ValueError: Если данные невалидны
        """
        required_fields = ['id', 'symbol', 'side', 'price', 'size', 'owner', 'timestamp', 'status']
        
        for field in required_fields:
            if field not in order_data:
                raise ValueError(f"Отсутствует обязательное поле: {field}")
        
        # Валидация типов и значений
        if not isinstance(order_data['id'], str) or not order_data['id']:
            raise ValueError("Поле 'id' должно быть непустой строкой")
        
        if not isinstance(order_data['symbol'], str) or not order_data['symbol']:
            raise ValueError("Поле 'symbol' должно быть непустой строкой")
        
        if order_data['side'] not in ['Bid', 'Ask', 'bid', 'ask']:
            raise ValueError("Поле 'side' должно быть 'Bid' или 'Ask'")
        
        if not isinstance(order_data['price'], (int, float)) or order_data['price'] <= 0:
            raise ValueError("Поле 'price' должно быть положительным числом")
        
        if not isinstance(order_data['size'], (int, float)) or order_data['size'] < 0:
            raise ValueError("Поле 'size' должно быть неотрицательным числом")
        
        if not isinstance(order_data['owner'], str) or not order_data['owner']:
            raise ValueError("Поле 'owner' должно быть непустой строкой")
        
        if not isinstance(order_data['status'], str) or order_data['status'] not in ['open', 'filled', 'canceled', 'triggered']:
            raise ValueError("Поле 'status' должно быть одним из: open, filled, canceled, triggered")
    
    def _format_order_data(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Форматирует данные ордера согласно спецификации.
        
        Args:
            order_data: Исходные данные ордера
            
        Returns:
            Отформатированные данные для публикации
        """
        # Нормализация side
        side = order_data['side'].lower()
        if side == 'bid':
            side = 'bid'
        elif side == 'ask':
            side = 'ask'
        else:
            side = order_data['side']
        
        # Форматирование timestamp
        timestamp = order_data['timestamp']
        if isinstance(timestamp, datetime):
            timestamp = timestamp.isoformat() + 'Z'
        elif isinstance(timestamp, str):
            # Если уже строка, оставляем как есть
            pass
        else:
            timestamp = str(timestamp)
        
        return {
            "id": str(order_data['id']),
            "symbol": str(order_data['symbol']),
            "side": side,
            "price": float(order_data['price']),
            "size": float(order_data['size']),
            "owner": str(order_data['owner']),
            "timestamp": timestamp,
            "status": str(order_data['status']),
            "source": "parser"
        }
    
    async def subscribe_to_config(self, callback: Callable[[Dict[str, Any]], None], topic: str = "parser_config.>") -> None:
        """Подписывается на конфигурационные сообщения.
        
        Args:
            callback: Функция обратного вызова для обработки конфигураций
            topic: NATS топик для подписки
            
        Raises:
            ConnectionError: Если не подключен к NATS
            ValueError: Если callback не предоставлен
        """
        if not self.is_connected():
            raise ConnectionError("Не подключен к NATS серверу")
        
        if not callback:
            raise ValueError("Callback функция обязательна")
        
        try:
            logger.info(f"Подписка на конфигурационные сообщения: {topic}")
            
            # Сохраняем callback
            self._config_callback = callback
            
            # Создаем подписку
            self._config_subscription = await self._nc.subscribe(
                topic,
                cb=self._handle_config_message
            )
            
            logger.info("Успешно подписались на конфигурационные сообщения")
            
        except Exception as e:
            logger.error(f"Ошибка подписки на конфигурации: {e}")
            raise
    
    async def _handle_config_message(self, msg) -> None:
        """Обрабатывает входящие конфигурационные сообщения.
        
        Args:
            msg: NATS сообщение
        """
        try:
            # Декодируем сообщение
            message_data = msg.data.decode('utf-8')
            logger.debug(f"Получено конфигурационное сообщение: {msg.subject}")
            
            # Парсим JSON
            try:
                config_data = json.loads(message_data)
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка парсинга JSON конфигурации: {e}")
                return
            
            # Валидируем конфигурацию
            self._validate_config_data(config_data)
            
            # Вызываем callback
            if self._config_callback:
                self._config_callback(config_data)
                self._monitoring.on_message_received()
                logger.debug(f"Конфигурация обработана: {msg.subject}")
            
        except Exception as e:
            self._monitoring.on_error(str(e))
            logger.error(f"Ошибка обработки конфигурационного сообщения: {e}")
    
    def _validate_config_data(self, config_data: Dict[str, Any]) -> None:
        """Валидирует конфигурационные данные.
        
        Args:
            config_data: Данные конфигурации для валидации
            
        Raises:
            ValueError: Если данные невалидны
        """
        if not isinstance(config_data, dict):
            raise ValueError("Конфигурация должна быть объектом")
        
        # Минимальная валидация - конфигурация не должна быть пустой
        if not config_data:
            raise ValueError("Конфигурация не может быть пустой")
        
        logger.debug("Конфигурационные данные валидны")
    
    def is_subscribed_to_config(self) -> bool:
        """Проверяет, подписан ли на конфигурационные сообщения.
        
        Returns:
            True если подписан, False иначе
        """
        return self._config_subscription is not None
    
    async def __aenter__(self):
        """Асинхронный контекстный менеджер для подключения."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Асинхронный контекстный менеджер для отключения."""
        await self.disconnect()
