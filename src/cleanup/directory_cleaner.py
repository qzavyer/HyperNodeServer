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
from src.utils.logger import setup_logger


class DirectoryCleaner:
    """Класс для очистки директорий с логами."""
    
    def __init__(self, base_dir: str = "/app/node_logs", single_file_watcher=None):
        """Инициализация очистителя директорий.
        
        Args:
            base_dir: Базовая директория для очистки
            single_file_watcher: Ссылка на SingleFileTailWatcher для защиты текущего файла
        """
        self.base_dir = Path(base_dir).expanduser().resolve()
        # Директория с числовыми файлами для очистки
        self.target_cleanup_path = self.base_dir / "node_order_statuses" / "hourly"
        self.logger = setup_logger(__name__)
        self.single_file_watcher = single_file_watcher
        
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
            self.logger.info(f"🧹 Starting cleanup in: {self.target_cleanup_path}")
            
            if not self.target_cleanup_path.exists():
                self.logger.warning(f"Target cleanup path does not exist: {self.target_cleanup_path}")
                return 0, 0
            
            removed_dirs = 0
            removed_files = 0
            
            # Находим все директории с датами в target_cleanup_path
            date_directories = []
            for item in self.target_cleanup_path.iterdir():
                if item.is_dir() and self.date_pattern.match(item.name):
                    date_directories.append(item)
            
            if not date_directories:
                self.logger.info("No date directories found")
                return 0, 0
            
            # Сортируем по имени (формат yyyyMMdd)
            date_directories.sort(key=lambda p: p.name, reverse=True)
            
            self.logger.info(f"Found {len(date_directories)} date directories in {self.target_cleanup_path}")
            
            # Оставляем последнюю директорию
            latest_directory = date_directories[0]
            directories_to_remove = date_directories[1:]
            
            self.logger.info(f"Keeping latest directory: {latest_directory.name}")
            
            # Удаляем старые директории
            for dir_path in directories_to_remove:
                self.logger.info(f"🗑️ Deleting old directory: {dir_path.name}")
                await self._remove_directory_async(dir_path)
                removed_dirs += 1
            
            # Очищаем старые числовые файлы в последней директории
            files_removed = await self._cleanup_numeric_files_async(latest_directory)
            removed_files += files_removed
            
            self.logger.info(f"✅ Очистка завершена: удалено {removed_dirs} директорий, {removed_files} файлов")
            return removed_dirs, removed_files
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка при очистке директорий: {e}")
            raise
    
    async def _remove_directory_async(self, dir_path: Path) -> None:
        """Асинхронно удаляет директорию."""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, shutil.rmtree, str(dir_path))
        except OSError as e:
            self.logger.error(f"Ошибка удаления директории {dir_path}: {e}")
    
    async def _cleanup_numeric_files_async(self, dir_path: Path) -> int:
        """Cleanup numeric files in directory, keeping only the last 3 files.
        
        Args:
            dir_path: Path to date directory (e.g., /app/node_logs/node_order_statuses/hourly/20251009)
            
        Returns:
            Number of files removed
        """
        removed_files = 0
        
        try:
            # Find all numeric files in directory
            numeric_files = []
            for file_path in dir_path.iterdir():
                if file_path.is_file() and file_path.name.isdigit():
                    numeric_files.append(file_path)
            
            if not numeric_files:
                self.logger.debug(f"No numeric files found in {dir_path}")
                return 0
            
            # Sort by numeric name (descending = newest first)
            numeric_files.sort(key=lambda f: int(f.name), reverse=True)
            
            self.logger.info(f"Found {len(numeric_files)} numeric files in {dir_path.name}, keeping last 3")
            
            # Keep last 3, delete the rest
            files_to_delete = numeric_files[3:]
            
            for file_path in files_to_delete:
                try:
                    self.logger.info(f"🗑️ Deleting old file: {file_path.name}")
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, file_path.unlink)
                    removed_files += 1
                except OSError as e:
                    self.logger.warning(f"Failed to delete file {file_path}: {e}")
            
            if removed_files > 0:
                self.logger.info(f"✅ Deleted {removed_files} old files from {dir_path.name}")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up numeric files in {dir_path}: {e}")
        
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
