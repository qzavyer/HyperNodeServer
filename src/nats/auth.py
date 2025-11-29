"""Модуль для работы с JWT аутентификацией NATS."""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class JWTAuth:
    """Класс для работы с JWT аутентификацией NATS."""
    
    def __init__(self):
        """Инициализация JWT аутентификации."""
        self._credentials: Optional[Dict[str, Any]] = None
    
    def load_credentials(self, creds_file: str) -> Dict[str, Any]:
        """Загружает JWT файл с учетными данными.
        
        Args:
            creds_file: Путь к файлу с учетными данными
            
        Returns:
            Словарь с учетными данными
            
        Raises:
            FileNotFoundError: Если файл не найден
            ValueError: Если файл содержит неверные данные
        """
        try:
            creds_path = Path(creds_file)
            if not creds_path.exists():
                raise FileNotFoundError(f"JWT файл не найден: {creds_file}")
            
            logger.info(f"Загрузка JWT файла: {creds_file}")
            
            with open(creds_path, 'r', encoding='utf-8') as f:
                self._credentials = json.load(f)
            
            # Валидация обязательных полей
            required_fields = ['jwt', 'seed']
            for field in required_fields:
                if field not in self._credentials:
                    raise ValueError(f"Отсутствует обязательное поле: {field}")
            
            logger.info("JWT файл успешно загружен")
            return self._credentials
            
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JWT файла: {e}")
            raise ValueError(f"Неверный формат JWT файла: {e}")
        except Exception as e:
            logger.error(f"Ошибка загрузки JWT файла: {e}")
            raise
    
    def get_connection_options(self, creds: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Формирует опции подключения с JWT аутентификацией.
        
        Args:
            creds: Учетные данные (если None, используются загруженные)
            
        Returns:
            Словарь с опциями подключения
            
        Raises:
            ValueError: Если учетные данные не загружены
        """
        if creds is None:
            creds = self._credentials
        
        if not creds:
            raise ValueError("Учетные данные не загружены")
        
        logger.debug("Формирование опций подключения с JWT")
        
        return {
            'user_jwt': creds['jwt'],
            'user_seed': creds['seed']
        }
    
    def is_loaded(self) -> bool:
        """Проверяет, загружены ли учетные данные.
        
        Returns:
            True если данные загружены, False иначе
        """
        return self._credentials is not None
    
    def get_credentials(self) -> Optional[Dict[str, Any]]:
        """Возвращает загруженные учетные данные.
        
        Returns:
            Словарь с учетными данными или None
        """
        return self._credentials
