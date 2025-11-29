"""Тесты для JWT аутентификации NATS."""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open

from src.nats.auth import JWTAuth


class TestJWTAuth:
    """Тесты для JWTAuth."""
    
    def setup_method(self):
        """Настройка перед каждым тестом."""
        self.auth = JWTAuth()
    
    def test_init(self):
        """Тест инициализации."""
        assert not self.auth.is_loaded()
        assert self.auth.get_credentials() is None
    
    def test_load_credentials_success(self):
        """Тест успешной загрузки JWT файла."""
        test_creds = {
            "jwt": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
            "seed": "SUA...",
            "user": "parser"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_creds, f)
            temp_file = f.name
        
        try:
            result = self.auth.load_credentials(temp_file)
            
            assert result == test_creds
            assert self.auth.is_loaded()
            assert self.auth.get_credentials() == test_creds
        finally:
            Path(temp_file).unlink()
    
    def test_load_credentials_file_not_found(self):
        """Тест ошибки при отсутствии файла."""
        with pytest.raises(FileNotFoundError, match="JWT файл не найден"):
            self.auth.load_credentials("nonexistent.json")
    
    def test_load_credentials_invalid_json(self):
        """Тест ошибки при неверном JSON."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content")
            temp_file = f.name
        
        try:
            with pytest.raises(ValueError, match="Неверный формат JWT файла"):
                self.auth.load_credentials(temp_file)
        finally:
            Path(temp_file).unlink()
    
    def test_load_credentials_missing_jwt_field(self):
        """Тест ошибки при отсутствии поля jwt."""
        test_creds = {
            "seed": "SUA...",
            "user": "parser"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_creds, f)
            temp_file = f.name
        
        try:
            with pytest.raises(ValueError, match="Отсутствует обязательное поле: jwt"):
                self.auth.load_credentials(temp_file)
        finally:
            Path(temp_file).unlink()
    
    def test_load_credentials_missing_seed_field(self):
        """Тест ошибки при отсутствии поля seed."""
        test_creds = {
            "jwt": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
            "user": "parser"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_creds, f)
            temp_file = f.name
        
        try:
            with pytest.raises(ValueError, match="Отсутствует обязательное поле: seed"):
                self.auth.load_credentials(temp_file)
        finally:
            Path(temp_file).unlink()
    
    def test_get_connection_options_success(self):
        """Тест успешного получения опций подключения."""
        test_creds = {
            "jwt": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
            "seed": "SUA...",
            "user": "parser"
        }
        
        self.auth._credentials = test_creds
        
        options = self.auth.get_connection_options()
        
        expected = {
            "user_jwt": test_creds["jwt"],
            "user_seed": test_creds["seed"]
        }
        assert options == expected
    
    def test_get_connection_options_with_creds_param(self):
        """Тест получения опций с переданными учетными данными."""
        test_creds = {
            "jwt": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
            "seed": "SUA...",
            "user": "parser"
        }
        
        options = self.auth.get_connection_options(test_creds)
        
        expected = {
            "user_jwt": test_creds["jwt"],
            "user_seed": test_creds["seed"]
        }
        assert options == expected
    
    def test_get_connection_options_no_credentials(self):
        """Тест ошибки при отсутствии учетных данных."""
        with pytest.raises(ValueError, match="Учетные данные не загружены"):
            self.auth.get_connection_options()
    
    def test_is_loaded_after_load(self):
        """Тест проверки загрузки после загрузки."""
        test_creds = {
            "jwt": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
            "seed": "SUA...",
            "user": "parser"
        }
        
        assert not self.auth.is_loaded()
        
        self.auth._credentials = test_creds
        
        assert self.auth.is_loaded()
