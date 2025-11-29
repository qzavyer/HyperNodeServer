"""Configuration manager for HyperLiquid Node Parser."""

import json
import aiofiles
from pathlib import Path
from typing import Dict, Any, Optional, List
from src.storage.models import Config, SymbolConfig, NodeHealthConfig
from src.utils.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)

class ConfigError(Exception):
    """Base exception for configuration errors."""
    pass

class ConfigManager:
    """Manages application configuration."""
    
    def __init__(self, config_file_path: str = "data/config.json"):
        """Initialize configuration manager.
        
        Args:
            config_file_path: Path to configuration file
        """
        self.config_file = Path(config_file_path)
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        self._config: Optional[Config] = None
        
    async def load_config_async(self) -> Config:
        """Load configuration from file asynchronously.
        
        Returns:
            Loaded configuration
            
        Raises:
            ConfigError: If configuration loading fails
        """
        try:
            if not self.config_file.exists():
                # Create default configuration
                default_config = self._create_default_config()
                await self.save_config_async(default_config)
                self._config = default_config
                logger.info("Created default configuration")
                return default_config
            
            async with aiofiles.open(self.config_file, 'r') as f:
                content = await f.read()
                config_data = json.loads(content)
                
            self._config = Config(**config_data)
            logger.info(f"Loaded configuration from {self.config_file}")
            return self._config
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise ConfigError(f"Configuration loading failed: {e}")
    
    async def save_config_async(self, config: Config) -> None:
        """Save configuration to file asynchronously.
        
        Args:
            config: Configuration to save
            
        Raises:
            ConfigError: If configuration saving fails
        """
        try:
            config_data = config.model_dump()
            async with aiofiles.open(self.config_file, 'w') as f:
                await f.write(json.dumps(config_data, indent=2, default=str))
            
            self._config = config
            logger.info(f"Saved configuration to {self.config_file}")
            
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            raise ConfigError(f"Configuration saving failed: {e}")
    
    def get_config(self) -> Config:
        """Get current configuration.
        
        Returns:
            Current configuration
            
        Raises:
            ConfigError: If configuration not loaded
        """
        if self._config is None:
            raise ConfigError("Configuration not loaded. Call load_config_async() first.")
        return self._config
    
    async def update_config_async(self, updates: Dict[str, Any]) -> Config:
        """Update configuration with new values.
        
        Args:
            updates: Configuration updates
            
        Returns:
            Updated configuration
            
        Raises:
            ConfigError: If update fails
        """
        try:
            current_config = self.get_config()
            current_data = current_config.model_dump()
            
            # Apply updates
            current_data.update(updates)
            
            # Validate updated configuration
            updated_config = Config(**current_data)
            
            # Save updated configuration
            await self.save_config_async(updated_config)
            
            logger.info("Configuration updated successfully")
            return updated_config
            
        except Exception as e:
            logger.error(f"Failed to update configuration: {e}")
            raise ConfigError(f"Configuration update failed: {e}")
    
    async def update_symbols_async(self, symbols: List[SymbolConfig]) -> Config:
        """Update symbols configuration only.
        
        Args:
            symbols: List of symbol configurations
            
        Returns:
            Updated configuration
            
        Raises:
            ConfigError: If update fails
        """
        try:
            current_config = self.get_config()
            
            # Create updated configuration with new symbols
            updated_config = current_config.model_copy(update={"symbols_config": symbols})
            
            # Save updated configuration
            await self.save_config_async(updated_config)
            
            # Log each symbol for debugging
            symbol_names = [s.symbol for s in symbols]
            logger.info(f"Updated symbols configuration with {len(symbols)} symbols: {symbol_names}")
            for symbol in symbols:
                logger.debug(f"Symbol config: {symbol.symbol} - min_liquidity={symbol.min_liquidity:.2f}, price_deviation={symbol.price_deviation}")
            
            return updated_config
            
        except Exception as e:
            logger.error(f"Failed to update symbols configuration: {e}")
            raise ConfigError(f"Symbols configuration update failed: {e}")
    
    def _create_default_config(self) -> Config:
        """Create default configuration from settings.
        
        Returns:
            Default configuration
        """
        return Config(
            node_logs_path=settings.NODE_DATA_PATH,
            cleanup_interval_hours=settings.CLEANUP_INTERVAL_HOURS,
            api_host=settings.API_HOST,
            api_port=settings.API_PORT,
            log_level=settings.LOG_LEVEL,
            log_file_path=settings.LOG_FILE_PATH,
            log_max_size_mb=settings.LOG_MAX_SIZE_MB,
            log_retention_days=settings.LOG_RETENTION_DAYS,
            config_file_path=settings.CONFIG_FILE_PATH,
            max_orders_per_request=settings.MAX_ORDERS_PER_REQUEST,
            file_read_retry_attempts=settings.FILE_READ_RETRY_ATTEMPTS,
            file_read_retry_delay=settings.FILE_READ_RETRY_DELAY,
            symbols_config=[],
            node_health=NodeHealthConfig()
        )
