import os
import asyncpg
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

MAIN_MENU = [
    ["💰 Фінанси", "🛵 Оренда"],
    ["🔧 Сервіс", "📦 Склад"],
    ["👤 Клієнти", "📊 Звіт"],
]

FINANCE_MENU = [
    ["➕ Дохід", "➖ Витрата"],
    ["💼 Баланс", "⬅️ Назад"],
]


def keyboard(menu):
    return ReplyKeyboardMarkup(menu, resize_keyboard=True)


async def init_db():
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS finance (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP NOT NULL,
            type TEXT NOT NULL,
            amount NUMERIC(10,2) NOT NULL,
            description TEXT
        );
    """)
    await conn.close()


async def add_finance_record(record_type, amount, description):
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("""
        INSERT INTO finance (created_at, type, amount, description)
        VALUES ($1, $2, $3, $4)
    """, datetime.now(), record_type, amount, description)
    await conn.close()


async def get_balance():
    conn = await asyncpg.connect(DATABASE_URL)
    income = await conn.fetchval("""
        SELECT COALESCE(SUM(amount), 0)
        FROM finance
        WHERE type = 'income'
    """)
    expense = await conn.fetchval("""
        SELECT COALESCE(SUM(amount), 0)
        FROM finance
        WHERE type = 'expense'
    """)
    await conn.close()
    return income, expense, income - expense


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "RedGear Assistant 🏍️\n\nОбери розділ:",
        reply_markup=keyboard(MAIN_MENU),
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if text == "💰 Фінанси":
        await update.message.reply_text("Фінанси:", reply_markup=keyboard(FINANCE_MENU))
        return

    if text == "➕ Дохід":
        context.user_data["mode"] = "income"
        await update.message.reply_text(
            "Введи дохід у форматі:\n\n1500 ремонт CRF1000"
        )
        return

    if text == "➖ Витрата":
        context.user_data["mode"] = "expense"
        await update.message.reply_text(
            "Введи витрату у форматі:\n\n250 масло Motul"
        )
        return

    if text == "💼 Баланс":
        income, expense, balance = await get_balance()
        await update.message.reply_text(
            f"💼 Баланс RedGear Moto\n\n"
            f"Доходи: {income} zł\n"
            f"Витрати: {expense} zł\n"
            f"Баланс: {balance} zł"
        )
        return

    if text == "⬅️ Назад":
        context.user_data.clear()
        await update.message.reply_text("Головне меню:", reply_markup=keyboard(MAIN_MENU))
        return

    mode = context.user_data.get("mode")

    if mode in ["income", "expense"]:
        parts = text.split(" ", 1)

        if len(parts) < 2:
            await update.message.reply_text("Помилка. Формат: 1500 опис")
            return

        try:
            amount = float(parts[0].replace(",", "."))
        except ValueError:
            await update.message.reply_text("Помилка. Перше значення має бути сумою.")
            return

        description = parts[1]
        await add_finance_record(mode, amount, description)

        if mode == "income":
            await update.message.reply_text(
                f"✅ Дохід додано\n\n{amount} zł\n{description}",
                reply_markup=keyboard(FINANCE_MENU),
            )
        else:
            await update.message.reply_text(
                f"✅ Витрату додано\n\n{amount} zł\n{description}",
                reply_markup=keyboard(FINANCE_MENU),
            )

        context.user_data.clear()
        return

    await update.message.reply_text(
        "Поки що цей розділ у розробці.",
        reply_markup=keyboard(MAIN_MENU),
            )
    async def post_init(app):
        await init_db()


app = Application.builder().token(TOKEN).post_init(post_init).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

app.run_polling()

