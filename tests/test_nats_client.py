"""Тесты для NATS клиента."""

import pytest
import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

from src.nats.nats_client import NATSClient


class TestNATSClient:
    """Тесты для NATSClient."""
    
    def setup_method(self):
        """Настройка перед каждым тестом."""
        self.client = NATSClient()
    
    def test_init(self):
        """Тест инициализации клиента."""
        assert not self.client.is_connected()
        assert self.client._nc is None
    
    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Тест успешного подключения."""
        with patch('nats.connect', new_callable=AsyncMock) as mock_connect:
            mock_nc = AsyncMock()
            mock_connect.return_value = mock_nc
            
            await self.client.connect("nats://localhost:4222")
            
            assert self.client.is_connected()
            mock_connect.assert_called_once_with("nats://localhost:4222")
    
    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Тест ошибки подключения."""
        with patch('nats.connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.side_effect = Exception("Connection failed")
            
            with pytest.raises(ConnectionError, match="Не удалось подключиться к NATS"):
                await self.client.connect("nats://localhost:4222")
            
            assert not self.client.is_connected()
    
    @pytest.mark.asyncio
    async def test_disconnect_success(self):
        """Тест успешного отключения."""
        with patch('nats.connect', new_callable=AsyncMock) as mock_connect:
            mock_nc = AsyncMock()
            mock_connect.return_value = mock_nc
            
            await self.client.connect()
            await self.client.disconnect()
            
            assert not self.client.is_connected()
            mock_nc.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self):
        """Тест отключения когда не подключен."""
        await self.client.disconnect()  # Не должно вызывать ошибку
        assert not self.client.is_connected()
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Тест контекстного менеджера."""
        with patch('nats.connect', new_callable=AsyncMock) as mock_connect:
            mock_nc = AsyncMock()
            mock_connect.return_value = mock_nc
            
            async with self.client as client:
                assert client.is_connected()
            
            assert not self.client.is_connected()
            mock_nc.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_is_connected_after_connect(self):
        """Тест проверки подключения после подключения."""
        with patch('nats.connect', new_callable=AsyncMock) as mock_connect:
            mock_nc = AsyncMock()
            mock_connect.return_value = mock_nc
            
            assert not self.client.is_connected()
            await self.client.connect()
            assert self.client.is_connected()
            await self.client.disconnect()
            assert not self.client.is_connected()
    
    def test_load_credentials_success(self):
        """Тест успешной загрузки JWT учетных данных."""
        test_creds = {
            "jwt": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
            "seed": "SUA...",
            "user": "parser"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_creds, f)
            temp_file = f.name
        
        try:
            self.client.load_credentials(temp_file)
            
            assert self.client.is_authenticated()
        finally:
            Path(temp_file).unlink()
    
    def test_load_credentials_file_not_found(self):
        """Тест ошибки при отсутствии JWT файла."""
        with pytest.raises(FileNotFoundError):
            self.client.load_credentials("nonexistent.json")
    
    def test_is_authenticated_initial_state(self):
        """Тест начального состояния аутентификации."""
        assert not self.client.is_authenticated()
    
    @pytest.mark.asyncio
    async def test_connect_with_jwt_credentials(self):
        """Тест подключения с JWT учетными данными."""
        test_creds = {
            "jwt": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
            "seed": "SUA...",
            "user": "parser"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_creds, f)
            temp_file = f.name
        
        try:
            with patch('nats.connect', new_callable=AsyncMock) as mock_connect:
                mock_nc = AsyncMock()
                mock_connect.return_value = mock_nc
                
                await self.client.connect("nats://localhost:4222", temp_file)
                
                assert self.client.is_connected()
                assert self.client.is_authenticated()
                
                # Проверяем, что connect был вызван с правильными опциями
                mock_connect.assert_called_once()
                call_args = mock_connect.call_args
                assert call_args[0][0] == "nats://localhost:4222"
                assert "user_jwt" in call_args[1]
                assert "user_seed" in call_args[1]
        finally:
            Path(temp_file).unlink()
    
    @pytest.mark.asyncio
    async def test_connect_with_invalid_jwt_file(self):
        """Тест подключения с неверным JWT файлом."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json")
            temp_file = f.name
        
        try:
            with pytest.raises(ConnectionError, match="Не удалось подключиться к NATS"):
                await self.client.connect("nats://localhost:4222", temp_file)
        finally:
            Path(temp_file).unlink()
