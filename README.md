# 💈 Barber Booking Bot

Telegram-бот онлайн-записи для барбершопа, салона или любого мастера.
Python 3.11+, aiogram 3, SQLite.

## Возможности

**Для клиента**
- Запись в пару нажатий: услуга → день → время → имя → телефон → подтверждение
- Показывает только реально свободные окна с учётом длительности услуг
- Номер телефона одной кнопкой («Отправить мой номер»)
- Автонапоминание за 2 часа до визита
- «Мои записи» с отменой
- Прайс и контакты

**Для мастера (админа)**
- Мгновенные уведомления о новых записях и отменах
- `/admin`: список предстоящих записей с именами и телефонами, отмена в один клик (клиент получает уведомление)

**Под капотом**
- Защита от двойного бронирования одного слота
- Все настройки бизнеса (услуги, цены, график) в одном файле `config.py`
- Часовой пояс задаётся в `.env`

## Запуск (Windows)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

1. В Telegram открой [@BotFather](https://t.me/BotFather), отправь `/newbot` и скопируй токен в `.env` → `BOT_TOKEN`.
2. Запусти бота: `python bot.py`.
3. Напиши своему боту `/id`, скопируй число в `.env` → `ADMIN_IDS` и перезапусти бота.

## Деплой на VPS (Ubuntu 22.04/24.04)

Бот работает как systemd-сервис: стартует вместе с сервером и перезапускается при сбое.

```bash
curl -fsSL https://raw.githubusercontent.com/artemsihov6-ux/barber-booking-bot/main/deploy/setup.sh -o setup.sh
sudo bash setup.sh
sudo nano /opt/barber-bot/.env        # BOT_TOKEN и ADMIN_IDS
sudo systemctl start barber-bot
```

- Логи: `journalctl -u barber-bot -f`
- Обновление до свежего кода: снова `sudo bash setup.sh`

## Настройка под клиента

Открой `config.py`:
- `BUSINESS_NAME`, `ADDRESS`, `PHONE`: данные заведения
- `SERVICES`: услуги, цены и длительность в минутах
- `WORK_DAYS`, `WORK_START_HOUR`, `WORK_END_HOUR`: график работы
- `REMIND_BEFORE_MIN`: за сколько минут напоминать

## Структура

```
bot.py          точка входа
config.py       все настройки
db.py           SQLite-запросы
slots.py        расчёт свободных окон
keyboards.py    кнопки и callback-данные
views.py        тексты списков записей
reminders.py    фоновые напоминания
handlers/
  client.py     сценарий записи для клиента
  admin.py      команды мастера
deploy/
  setup.sh            установка/обновление на сервере
  barber-bot.service  systemd-юнит
```
