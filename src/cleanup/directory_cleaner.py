"""
Модуль для очистки директорий с логами.
Интегрирует функциональность из clean.py в архитектуру приложения.
"""

import os
import re
import shutil
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple
import logging

from config.settings import settings


class DirectoryCleaner:
    """Класс для очистки директорий с логами."""
    
    def __init__(self, base_dir: str = "/app/node_logs"):
        """Инициализация очистителя директорий.
        
        Args:
            base_dir: Базовая директория для очистки
        """
        self.base_dir = Path(base_dir).expanduser().resolve()
        self.logger = logging.getLogger(__name__)
        
        # Регулярка для поиска папок с форматом даты yyyyMMdd
        self.date_pattern = re.compile(r"^\d{8}$")
        
        # Настройки очистки
        self.cleanup_interval_hours = 1  # Очистка каждый час
        self.file_retention_hours = 1    # Файлы старше 1 часа удаляются
        
    async def cleanup_async(self) -> Tuple[int, int]:
        """Асинхронная очистка директорий.
        
        Returns:
            Tuple[int, int]: (количество удаленных директорий, количество удаленных файлов)
        """
        try:
            self.logger.info(f"🧹 Начинаем очистку директории: {self.base_dir}")
            
            if not self.base_dir.exists():
                self.logger.warning(f"Директория не существует: {self.base_dir}")
                return 0, 0
            
            now = datetime.now()
            today_str = now.strftime("%Y%m%d")
            one_hour_ago = now - timedelta(hours=self.file_retention_hours)
            
            removed_dirs = 0
            removed_files = 0
            
            # Рекурсивно ищем все директории с датами
            date_directories = await self._find_date_directories_async()
            
            for dir_path in date_directories:
                # Получаем имя директории (последний элемент пути)
                dir_name = dir_path.name
                
                try:
                    dir_date = datetime.strptime(dir_name, "%Y%m%d").date()
                except ValueError:
                    continue
                
                # Удаляем папки со старыми датами
                if dir_date < now.date():
                    self.logger.info(f"🗑️ Удаляем старую директорию: {dir_path}")
                    await self._remove_directory_async(dir_path)
                    removed_dirs += 1
                    continue
                
                # Работаем только с сегодняшней папкой
                # НЕ ТРОГАЕМ сегодняшние файлы - нода может упасть!
                # if dir_name == today_str:
                #     files_removed = await self._cleanup_today_directory_async(dir_path, one_hour_ago)
                #     removed_files += files_removed
            
            self.logger.info(f"✅ Очистка завершена: удалено {removed_dirs} директорий, {removed_files} файлов")
            return removed_dirs, removed_files
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка при очистке директорий: {e}")
            raise
    
    async def _list_directory_async(self) -> List[str]:
        """Асинхронно получает список директорий."""
        try:
            # Используем asyncio для неблокирующего чтения директории
            loop = asyncio.get_event_loop()
            entries = await loop.run_in_executor(None, os.listdir, str(self.base_dir))
            return entries
        except OSError as e:
            self.logger.error(f"Ошибка чтения директории {self.base_dir}: {e}")
            return []
    
    async def _find_date_directories_async(self) -> List[Path]:
        """Рекурсивно находит все директории с форматом даты yyyyMMdd."""
        date_directories = []
        
        try:
            # Используем asyncio для неблокирующего обхода директорий
            loop = asyncio.get_event_loop()
            
            def find_directories():
                directories = []
                for root, dirs, files in os.walk(self.base_dir):
                    for dir_name in dirs:
                        if self.date_pattern.match(dir_name):
                            dir_path = Path(root) / dir_name
                            directories.append(dir_path)
                return directories
            
            date_directories = await loop.run_in_executor(None, find_directories)
            self.logger.debug(f"Найдено {len(date_directories)} директорий с датами")
            
        except Exception as e:
            self.logger.error(f"Ошибка при поиске директорий с датами: {e}")
        
        return date_directories
    
    async def _remove_directory_async(self, dir_path: Path) -> None:
        """Асинхронно удаляет директорию."""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, shutil.rmtree, str(dir_path))
        except OSError as e:
            self.logger.error(f"Ошибка удаления директории {dir_path}: {e}")
    
    async def _cleanup_today_directory_async(self, dir_path: Path, cutoff_time: datetime) -> int:
        """Асинхронно очищает файлы в сегодняшней директории.
        
        Args:
            dir_path: Путь к директории
            cutoff_time: Время, после которого файлы считаются старыми
            
        Returns:
            int: Количество удаленных файлов
        """
        removed_files = 0
        
        try:
            # Рекурсивно обходим директорию
            for root, _, files in os.walk(dir_path):
                for file in files:
                    file_path = Path(root) / file
                    
                    try:
                        # Получаем время модификации файла
                        mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                        
                        if mtime < cutoff_time:
                            self.logger.debug(f"🗑️ Удаляем старый файл: {file_path}")
                            file_path.unlink()
                            removed_files += 1
                            
                    except OSError as e:
                        self.logger.warning(f"Не удалось удалить файл {file_path}: {e}")
                        
        except Exception as e:
            self.logger.error(f"Ошибка при очистке директории {dir_path}: {e}")
        
        return removed_files
    
    async def start_periodic_cleanup_async(self) -> None:
        """Запускает периодическую очистку каждые N часов."""
        self.logger.info(f"🔄 Запускаем периодическую очистку каждые {self.cleanup_interval_hours} часов")
        
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval_hours * 3600)  # Конвертируем часы в секунды
                await self.cleanup_async()
            except asyncio.CancelledError:
                self.logger.info("🛑 Периодическая очистка остановлена")
                break
            except Exception as e:
                self.logger.error(f"❌ Ошибка в периодической очистке: {e}")
                # Продолжаем работу даже при ошибке
                await asyncio.sleep(60)  # Ждем минуту перед следующей попыткой
    
    def get_cleanup_stats(self) -> dict:
        """Получает статистику очистки."""
        return {
            "base_directory": str(self.base_dir),
            "cleanup_interval_hours": self.cleanup_interval_hours,
            "file_retention_hours": self.file_retention_hours,
            "directory_exists": self.base_dir.exists(),
            "directory_size_mb": self._get_directory_size_mb() if self.base_dir.exists() else 0
        }
    
    def _get_directory_size_mb(self) -> float:
        """Получает размер директории в мегабайтах."""
        try:
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(self.base_dir):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.exists(filepath):
                        total_size += os.path.getsize(filepath)
            return total_size / (1024 * 1024)  # Конвертируем в MB
        except Exception:
            return 0.0
