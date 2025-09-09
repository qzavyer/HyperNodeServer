# HyperNodeServer Makefile
# Упрощенный деплой с автоматической настройкой пользователя

.PHONY: setup deploy start stop clean logs test

# Подготовка пользователя и системы
setup:
	@echo "🔧 Настройка пользователя hl..."
	@chmod +x scripts/setup-user.sh
	@./scripts/setup-user.sh
	@echo "✅ Настройка завершена"

# Полный деплой (setup + build + start)
deploy: setup
	@echo "🚀 Разворачивание HyperNodeServer..."
	@docker-compose up --build -d
	@echo "✅ Развертывание завершено"
	@echo "📍 Приложение доступно по адресу: http://localhost:8000"

# Запуск контейнеров
start:
	@echo "▶️  Запуск контейнеров..."
	@docker-compose up -d

# Остановка контейнеров  
stop:
	@echo "⏹️  Остановка контейнеров..."
	@docker-compose down

# Просмотр логов
logs:
	@docker-compose logs -f

# Очистка
clean:
	@echo "🧹 Очистка..."
	@docker-compose down -v
	@docker system prune -f

# Запуск тестов
test:
	@echo "🧪 Запуск тестов..."
	@python -m pytest tests/ -v

# Проверка состояния
health:
	@echo "🏥 Проверка состояния..."
	@curl -f http://localhost:8000/health || echo "Сервис недоступен"

# Помощь
help:
	@echo "HyperNodeServer - Доступные команды:"
	@echo ""
	@echo "  setup    - Настройка пользователя hl"
	@echo "  deploy   - Полный деплой (setup + build + start)"
	@echo "  start    - Запуск контейнеров"
	@echo "  stop     - Остановка контейнеров"
	@echo "  logs     - Просмотр логов"
	@echo "  clean    - Очистка контейнеров и volumes"
	@echo "  test     - Запуск тестов"
	@echo "  health   - Проверка состояния сервиса"
	@echo "  help     - Показать это сообщение"
