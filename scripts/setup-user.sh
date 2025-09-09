#!/bin/bash

# Скрипт для создания пользователя hl перед развертыванием
# Минимальные изменения для консистентности Docker

USER_NAME="hl"
USER_UID=1000
USER_GID=1000

echo "Checking if user $USER_NAME exists..."

# Проверяем существует ли пользователь
if id "$USER_NAME" &>/dev/null; then
    echo "✅ User $USER_NAME already exists"
    EXISTING_UID=$(id -u "$USER_NAME")
    EXISTING_GID=$(id -g "$USER_NAME")
    
    if [ "$EXISTING_UID" = "$USER_UID" ] && [ "$EXISTING_GID" = "$USER_GID" ]; then
        echo "✅ User $USER_NAME has correct UID/GID ($USER_UID:$USER_GID)"
    else
        echo "⚠️  User $USER_NAME exists but has different UID/GID ($EXISTING_UID:$EXISTING_GID)"
        echo "   Expected: $USER_UID:$USER_GID"
        echo "   This may cause permission issues with Docker volumes"
    fi
else
    echo "Creating user $USER_NAME with UID:GID $USER_UID:$USER_GID..."
    
    # Создаем группу если её нет
    if ! getent group "$USER_NAME" &>/dev/null; then
        sudo groupadd -g "$USER_GID" "$USER_NAME"
        echo "✅ Created group $USER_NAME"
    fi
    
    # Создаем пользователя
    sudo useradd -u "$USER_UID" -g "$USER_NAME" -m -d "/home/$USER_NAME" -s /bin/bash "$USER_NAME"
    echo "✅ Created user $USER_NAME"
    
    # Создаем директорию для данных Hyperliquid если её нет
    if [ ! -d "/home/$USER_NAME/hl" ]; then
        sudo mkdir -p "/home/$USER_NAME/hl/data"
        sudo chown -R "$USER_NAME:$USER_NAME" "/home/$USER_NAME/hl"
        echo "✅ Created data directory /home/$USER_NAME/hl/data"
    fi
fi

echo ""
echo "User setup complete. You can now run:"
echo "  docker-compose up -d"
