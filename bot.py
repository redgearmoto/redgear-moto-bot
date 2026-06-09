from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import os

TOKEN = os.getenv("BOT_TOKEN")

MAIN_MENU = [
    ["💰 Фінанси", "🛵 Оренда"],
    ["🔧 Сервіс", "📦 Склад"],
    ["👤 Клієнти", "📊 Звіт"],
]

FINANCE_MENU = [
    ["➕ Дохід", "➖ Витрата"],
    ["💼 Баланс", "⬅️ Назад"],
]

RENTAL_MENU = [
    ["➕ Оплата оренди", "➖ Витрата скутера"],
    ["📍 Пробіг", "🔁 Статус скутера"],
    ["⬅️ Назад"],
]

SERVICE_MENU = [
    ["➕ Новий ремонт", "✅ Закрити ремонт"],
    ["📋 Активні ремонти", "⬅️ Назад"],
]

STOCK_MENU = [
    ["➕ Прихід товару", "➖ Списання товару"],
    ["🔍 Залишки", "⬅️ Назад"],
]

CLIENTS_MENU = [
    ["➕ Додати клієнта", "📋 Список клієнтів"],
    ["⬅️ Назад"],
]


def keyboard(menu):
    return ReplyKeyboardMarkup(menu, resize_keyboard=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "RedGear Assistant 🏍️\n\nОбери розділ:",
        reply_markup=keyboard(MAIN_MENU),
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "💰 Фінанси":
        await update.message.reply_text("Фінанси:", reply_markup=keyboard(FINANCE_MENU))

    elif text == "🛵 Оренда":
        await update.message.reply_text("Оренда скутерів:", reply_markup=keyboard(RENTAL_MENU))

    elif text == "🔧 Сервіс":
        await update.message.reply_text("Сервіс:", reply_markup=keyboard(SERVICE_MENU))

    elif text == "📦 Склад":
        await update.message.reply_text("Склад:", reply_markup=keyboard(STOCK_MENU))

    elif text == "👤 Клієнти":
        await update.message.reply_text("Клієнти:", reply_markup=keyboard(CLIENTS_MENU))

    elif text == "📊 Звіт":
        await update.message.reply_text("📊 Звіт поки в розробці.")

    elif text == "⬅️ Назад":
        await update.message.reply_text("Головне меню:", reply_markup=keyboard(MAIN_MENU))

    else:
        await update.message.reply_text(
            f"Прийняв: {text}\n\nНаступним кроком підключимо AI, щоб я сам розбирав такі повідомлення.",
            reply_markup=keyboard(MAIN_MENU),
        )


app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

app.run_polling()

