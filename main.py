import os
import logging
import asyncio
import random
import time
from datetime import datetime
from typing import Dict

import pytz
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiohttp import web

# ====================== CONFIG ======================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID_STR = os.getenv("OWNER_ID")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 8443))

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден!")
if not WEBHOOK_URL:
    raise ValueError("❌ WEBHOOK_URL не задан в Environment Variables!")

# Безопасное преобразование OWNER_ID
OWNER_ID = int(OWNER_ID_STR) if OWNER_ID_STR and OWNER_ID_STR.isdigit() else None

kiev = pytz.timezone("Europe/Kiev")
START_DATE = datetime(2025, 1, 1).date()

# Состояния пользователей
user_guessing: Dict[int, bool] = {}
last_request: Dict[int, float] = {}

# ====================== LOGGING ======================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ====================== HELPERS ======================
def is_spam(user_id: int, cooldown: float = 2.0) -> bool:
    now = time.time()
    if user_id in last_request and now - last_request[user_id] < cooldown:
        return True
    last_request[user_id] = now
    return False


def get_custom_time() -> str:
    t = time.localtime()
    total_min = t.tm_hour * 60 + t.tm_min
    return f"{t.tm_sec:02d}:{total_min // 40:02d}:{total_min % 40:02d}"


# ====================== КАЛЕНДАРИ ======================
def get_10month_date():
    delta = (datetime.now().date() - START_DATE).days
    year = 25 + delta // 365
    day_of_year = delta % 365
    month_lengths = [37 if i % 2 == 0 else 36 for i in range(10)]
    month = 0
    while month < 10 and day_of_year >= month_lengths[month]:
        day_of_year -= month_lengths[month]
        month += 1
    return year, month + 1, day_of_year + 1


def build_10month_calendar() -> str:
    year, cur_month, cur_day = get_10month_date()
    month_lengths = [37 if i % 2 == 0 else 36 for i in range(10)]
    cal = f"📅 Персональный календарь (10 месяцев)\nГод: {year}\n\n"
    for i, days in enumerate(month_lengths):
        cal += f"Месяц {i+1:02d}:\n"
        for d in range(1, days + 1):
            cal += f"[{d:02d}] " if (d == cur_day and i + 1 == cur_month) else f" {d:02d} "
            if d % 10 == 0:
                cal += "\n"
        cal += "\n"
    return cal


def get_13month_date():
    delta = (datetime.now().date() - START_DATE).days
    year = 25 + delta // 365
    day_of_year = delta % 365
    is_leap = (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))
    months = [28] * 12 + [29 + int(is_leap)]
    month = 0
    while month < 13 and day_of_year >= months[month]:
        day_of_year -= months[month]
        month += 1
    return year, month + 1, day_of_year + 1


def build_13month_calendar() -> str:
    year, cur_month, cur_day = get_13month_date()
    is_leap = (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))
    months = [28] * 12 + [29 + int(is_leap)]
    cal = f"📅 Альтернативный календарь (13 месяцев)\nГод: {year}\n\n"
    for i, days in enumerate(months):
        cal += f"Месяц {i+1:02d}:\n"
        for d in range(1, days + 1):
            cal += f"[{d:02d}] " if (d == cur_day and i + 1 == cur_month) else f" {d:02d} "
            if d % 7 == 0:
                cal += "\n"
        cal += "\n"
    return cal


# ====================== NOTIFY ======================
async def notify_owner(bot, user, action: str):
    if OWNER_ID and user.id != OWNER_ID:   # Защита от самофлуда
        try:
            text = f"👤 @{user.username or user.first_name} (ID: {user.id})\n{action}"
            await bot.send_message(chat_id=OWNER_ID, text=text)
        except Exception as e:
            logger.error(f"Notify failed: {e}")


# ====================== HANDLERS ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_spam(update.effective_user.id):
        await update.message.reply_text("⏳ Подожди пару секунд...")
        return

    year, month, day = get_10month_date()
    text = f"{year:02d}:{day:02d}:{month:02d}\n{get_custom_time()}\n{datetime.now(kiev).strftime('%y:%d:%m   %H:%M:%S')}"
    await update.message.reply_text(text)
    await notify_owner(context.bot, update.effective_user, "Запустил бота (/start)")


async def full(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(build_10month_calendar())
    await notify_owner(context.bot, update.effective_user, "Открыл календарь 10 месяцев (/full)")


async def open_alt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    year, month, day = get_13month_date()
    text = f"{year:02d}:{day:02d}:{month:02d}\n{get_custom_time()}\n{datetime.now(kiev).strftime('%y:%d:%m   %H:%M:%S')}"
    await update.message.reply_text(text)
    await notify_owner(context.bot, update.effective_user, "Открыл дату 13 месяцев (/open)")


async def all_alt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(build_13month_calendar())
    await notify_owner(context.bot, update.effective_user, "Открыл календарь 13 месяцев (/all)")


async def me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start — текущая дата\n"
        "/full — календарь 10 месяцев\n"
        "/open — дата 13 месяцев\n"
        "/all — календарь 13 месяцев\n"
        "/joking — игра с кубиками\n"
        "/me — это меню"
    )


async def joking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_guessing.get(user_id):
        await update.message.reply_text("🎲 Вы уже в игре!")
        return
    user_guessing[user_id] = True
    await update.message.reply_text("🎲 Введите два числа от 1 до 6 через пробел:")


async def handle_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_guessing.get(user_id):
        return

    try:
        g1, g2 = map(int, update.message.text.strip().split())
        if not (1 <= g1 <= 6 and 1 <= g2 <= 6):
            raise ValueError
    except:
        await update.message.reply_text("⚠️ Введите два числа от 1 до 6 через пробел.")
        return

    d1 = random.randint(1, 6)
    d2 = random.randint(1, 6)

    if (g1, g2) == (d1, d2) or (g1, g2) == (d2, g1):
        await update.message.reply_text(f"🎉 Угадали! Выпало: {d1} и {d2}")
        user_guessing[user_id] = False
    else:
        await update.message.reply_text(f"❌ Не угадали. Выпало: {d1} и {d2}")


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❓ Неизвестная команда.\nНапиши /me — чтобы увидеть список команд.")


# ====================== AUTO SEND ======================
async def periodic_send(application: Application):
    if not OWNER_ID:
        return
    try:
        year, month, day = get_10month_date()
        text = f"{year:02d}:{day:02d}:{month:02d}\n{get_custom_time()}\n{datetime.now(kiev).strftime('%y.%d.%m   %H:%M:%S')}"
        await application.bot.send_message(chat_id=OWNER_ID, text=text)
    except Exception as e:
        logger.error(f"Auto send error: {e}")


# ====================== MAIN ======================
async def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("full", full))
    application.add_handler(CommandHandler("open", open_alt))
    application.add_handler(CommandHandler("all", all_alt))
    application.add_handler(CommandHandler("me", me))
    application.add_handler(CommandHandler("joking", joking))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_guess))
    application.add_handler(MessageHandler(filters.COMMAND, unknown))

    # Scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(periodic_send, 'interval', minutes=1, args=[application])
    scheduler.start()

    await application.initialize()
    await application.start()

    # Установка webhook
    await application.bot.set_webhook(WEBHOOK_URL)
    logger.info(f"✅ Webhook успешно установлен → {WEBHOOK_URL}")

    # aiohttp server
    app = web.Application()
    app["application"] = application

    async def webhook_handler(request):
        try:
            data = await request.json()
            update = Update.de_json(data, application.bot)
            await application.process_update(update)
            return web.Response(text="ok")
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return web.Response(status=500)

    app.router.add_post("/webhook", webhook_handler)        # ← Более безопасный путь
    app.router.add_get("/", lambda r: web.Response(text="Bot is running"))
    app.router.add_get("/health", lambda r: web.Response(text="OK"))

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()

    logger.info(f"🚀 Бот успешно запущен на порту {PORT}")

    try:
        await asyncio.Event().wait()
    finally:
        logger.info("🛑 Graceful shutdown...")
        scheduler.shutdown()
        await application.stop()
        await application.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
