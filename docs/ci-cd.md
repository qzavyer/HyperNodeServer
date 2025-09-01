# CI/CD Pipeline Documentation

## Обзор

GitHub Actions CI/CD pipeline для автоматического тестирования, сборки и развертывания HyperLiquid Node Parser.

## Workflows

### 1. CI - Tests (`ci.yml`)

**Триггеры:**
- Push в `main` или `develop` ветки
- Pull Request в `main` ветку

**Задачи:**
- **test**: Запуск тестов на Python 3.11
- **security**: Сканирование безопасности с Snyk
- **docker-build**: Сборка и тестирование Docker образа

**Этапы:**
1. Checkout кода
2. Установка Python 3.11
3. Кэширование зависимостей
4. Установка зависимостей
5. Создание директорий
6. Линтинг кода (flake8)
7. Запуск unit тестов
8. Запуск integration тестов
9. Загрузка результатов тестов
10. Сканирование безопасности
11. Сборка Docker образа
12. Тестирование Docker образа

### 2. CD - Deploy (`cd.yml`)

**Триггеры:**
- Push в `main` ветку
- Успешное завершение CI workflow

**Задачи:**
- **deploy**: Развертывание на серверы
- **docker-publish**: Публикация Docker образа

**Этапы:**
1. Checkout кода
2. Установка зависимостей
3. Создание пакета развертывания
4. Развертывание на staging (если настроено)
5. Развертывание на production (если настроено)
6. Уведомление о развертывании
7. Публикация Docker образа в Docker Hub

### 3. Локальное развертывание

**Процесс развертывания:**
1. CI тесты проходят успешно
2. Код мержится в `main` ветку
3. На сервере выполняется:
   ```bash
   git pull origin main
   docker compose up -d
   ```

**Преимущества:**
- Простота развертывания
- Нет зависимости от внешних сервисов
- Полный контроль над процессом
- Бесплатность

## Настройка секретов

### Обязательные секреты

```bash
# Security scanning (опционально)
SNYK_TOKEN=your-snyk-token
```

### Опциональные секреты

```bash
# Deployment servers
STAGING_HOST=staging.example.com
PRODUCTION_HOST=production.example.com
STAGING_SSH_KEY=your-staging-ssh-key
PRODUCTION_SSH_KEY=your-production-ssh-key

# Notifications
SLACK_WEBHOOK_URL=your-slack-webhook
DISCORD_WEBHOOK_URL=your-discord-webhook
```

## Настройка секретов в GitHub

1. Перейдите в Settings → Secrets and variables → Actions
2. Нажмите "New repository secret"
3. Добавьте необходимые секреты

## Локальное тестирование

### Запуск линтинга

```bash
pip install flake8
flake8 src/ --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 src/ --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
```

### Запуск тестов

```bash
# Unit tests
python -m pytest tests/test_config_manager.py -v --tb=short
python -m pytest tests/test_api_routes.py -v --tb=short

# Integration tests
python -m pytest tests/test_integration.py -v --tb=short --timeout=300
```

### Сборка Docker образа

```bash
docker build -t hyperliquid-parser:test .
docker run --rm -d --name test-container -p 8000:8000 hyperliquid-parser:test
sleep 10
curl -f http://localhost:8000/health
docker stop test-container
```

## Мониторинг

### GitHub Actions

- **Actions tab**: Просмотр всех workflow runs
- **Security tab**: Результаты сканирования безопасности
- **Artifacts**: Скачивание результатов тестов

### Уведомления

- **Email**: Автоматические уведомления о статусе
- **Slack/Discord**: Настраиваемые webhook уведомления
- **GitHub**: Комментарии в PR с результатами

## Troubleshooting

### Частые проблемы

1. **Тесты падают**
   - Проверьте логи в Actions tab
   - Запустите тесты локально
   - Проверьте зависимости

2. **Docker сборка падает**
   - Проверьте Dockerfile
   - Проверьте .dockerignore
   - Проверьте requirements.txt

3. **Deployment падает**
   - Проверьте секреты
   - Проверьте SSH ключи
   - Проверьте доступ к серверам

### Отладка

```bash
# Локальная отладка workflow
act -j test

# Просмотр логов
docker logs container-name

# Проверка статуса
docker ps
docker compose ps
```

## Best Practices

1. **Кэширование**: Используйте кэш для зависимостей
2. **Параллелизация**: Запускайте независимые задачи параллельно
3. **Безопасность**: Сканируйте код и образы на уязвимости
4. **Уведомления**: Настройте уведомления о статусе
5. **Артефакты**: Сохраняйте результаты тестов
6. **Версионирование**: Используйте семантическое версионирование

## Автоматизация

### Pre-commit hooks

```bash
# Установка pre-commit
pip install pre-commit
pre-commit install

# Запуск на всех файлах
pre-commit run --all-files
```

### Git hooks

```bash
# .git/hooks/pre-push
#!/bin/bash
python -m pytest tests/ -v
```

## Контакты

При проблемах с CI/CD:
1. Проверьте логи в GitHub Actions
2. Создайте issue с описанием проблемы
3. Обратитесь к команде DevOps
