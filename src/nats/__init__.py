"""NATS модуль для работы с NATS сервером."""

from .nats_client import NATSClient
from .auth import JWTAuth

__all__ = ["NATSClient", "JWTAuth"]
