#!/usr/bin/env bash
# Установка и обновление бота на Ubuntu/Debian. Запускать от root:
#   bash setup.sh            — первая установка или обновление до свежего кода
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/artemsihov6-ux/barber-booking-bot.git}"
APP_DIR=/opt/barber-bot
APP_USER=barberbot
SERVICE=barber-bot

apt-get update -y
apt-get install -y python3 python3-venv git

id -u "$APP_USER" &>/dev/null || useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
git config --global --add safe.directory "$APP_DIR"

if [ -d "$APP_DIR/.git" ]; then
    git -C "$APP_DIR" pull --ff-only
else
    git clone "$REPO_URL" "$APP_DIR"
fi

python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -q --upgrade pip
"$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

FIRST_RUN=0
if [ ! -f "$APP_DIR/.env" ]; then
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    FIRST_RUN=1
fi

chown -R "$APP_USER:$APP_USER" "$APP_DIR"
chmod 600 "$APP_DIR/.env"

cp "$APP_DIR/deploy/$SERVICE.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable "$SERVICE" >/dev/null

if [ "$FIRST_RUN" = 1 ]; then
    echo
    echo "Готово. Заполни $APP_DIR/.env (токены и ID админов для Telegram и/или MAX) и запусти:"
    echo "  systemctl start $SERVICE"
else
    systemctl restart "$SERVICE"
    echo "Бот обновлён и перезапущен."
fi
echo "Логи: journalctl -u $SERVICE -f"
