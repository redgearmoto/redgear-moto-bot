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

CLIENTS_MENU = [
    ["➕ Новий клієнт", "📋 Список клієнтів"],
    ["⬅️ Назад"],
]


def keyboard(menu):
    return ReplyKeyboardMarkup(menu, resize_keyboard=True)


async def get_db():
    return await asyncpg.connect(DATABASE_URL)


async def init_db():
    conn = await get_db()

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS finance (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP NOT NULL,
            type TEXT NOT NULL,
            amount NUMERIC(10,2) NOT NULL,
            description TEXT
        );
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            name TEXT NOT NULL,
            phone TEXT,
            city TEXT,
            vehicle TEXT,
            plate TEXT,
            vin TEXT,
            mileage INTEGER DEFAULT 0,
            notes TEXT
        );
    """)

    await conn.close()


async def add_finance_record(record_type, amount, description):
    conn = await get_db()

    await conn.execute("""
        INSERT INTO finance (created_at, type, amount, description)
        VALUES ($1, $2, $3, $4)
    """, datetime.now(), record_type, amount, description)

    await conn.close()


async def get_balance():
    conn = await get_db()

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


async def add_client(text):
    parts = [x.strip() for x in text.split(";")]

    if len(parts) != 8:
        raise ValueError(
            "Потрібно 8 полів:\n"
            "Ім'я; Телефон; Місто; Мотоцикл; Номер; VIN; Пробіг; Примітка"
        )

    name, phone, city, vehicle, plate, vin, mileage, notes = parts

    conn = await get_db()

    await conn.execute("""
        INSERT INTO clients
        (name, phone, city, vehicle, plate, vin, mileage, notes)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
    """, name, phone, city, vehicle, plate, vin, int(mileage), notes)

    await conn.close()

    return name, vehicle, plate


async def get_clients():
    conn = await get_db()

    rows = await conn.fetch("""
        SELECT name, phone, city, vehicle, plate, mileage
        FROM clients
        ORDER BY id DESC
        LIMIT 20
    """)

    await conn.close()
    return rows


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.message.reply_text(
        "RedGear Assistant 🏍️\n\nОбери розділ:",
        reply_markup=keyboard(MAIN_MENU),
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if text == "💰 Фінанси":
        context.user_data.clear()
        await update.message.reply_text("Фінанси:", reply_markup=keyboard(FINANCE_MENU))
        return

    if text == "👤 Клієнти":
        context.user_data.clear()
        await update.message.reply_text("Клієнти:", reply_markup=keyboard(CLIENTS_MENU))
        return

    if text == "➕ Дохід":
        context.user_data["mode"] = "income"
        await update.message.reply_text("Введи дохід:\n\n1500 ремонт CRF1000")
        return

    if text == "➖ Витрата":
        context.user_data["mode"] = "expense"
        await update.message.reply_text("Введи витрату:\n\n250 масло Motul")
        return

    if text == "💼 Баланс":

    income, expense, balance = await get_balance()

    await update.message.reply_text(
        f"💼 Баланс RedGear Moto\n\n"
        f"Доходи: {income:.2f} zł\n"
        f"Витрати: {expense:.2f} zł\n"
        f"Баланс: {balance:.2f} zł"
    )

    return

    if text == "➕ Новий клієнт":
        context.user_data["mode"] = "new_client"
        await update.message.reply_text(
            "Введи клієнта у форматі:\n\n"
            "Ім'я; Телефон; Місто; Мотоцикл; Номер; VIN; Пробіг; Примітка\n\n"
            "Приклад:\n"
            "Іван;735066501;Wrocław;Yamaha TDM900;DW12345;JYARN181000123456;72000;Заміна мастила"
        )
        return

    if text == "📋 Список клієнтів":
        rows = await get_clients()

        if not rows:
            await update.message.reply_text("Клієнтів поки немає.")
            return

        result = "📋 Клієнти\n\n"

        for row in rows:
            result += (
                f"👤 {row['name']}\n"
                f"📞 {row['phone']}\n"
                f"🏙 {row['city']}\n"
                f"🏍 {row['vehicle']}\n"
                f"🔢 {row['plate']}\n"
                f"📍 Пробіг: {row['mileage']} км\n\n"
            )

        await update.message.reply_text(result)
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

        label = "Дохід" if mode == "income" else "Витрату"

        await update.message.reply_text(
            f"✅ {label} додано\n\n{amount:.2f} zł\n{description}",
            reply_markup=keyboard(FINANCE_MENU),
        )

        context.user_data.clear()
        return

    if mode == "new_client":
        try:
            name, vehicle, plate = await add_client(text)

            await update.message.reply_text(
                f"✅ Клієнта додано\n\n"
                f"👤 {name}\n"
                f"🏍 {vehicle}\n"
                f"🔢 {plate}",
                reply_markup=keyboard(CLIENTS_MENU),
            )

            context.user_data.clear()

        except Exception as e:
            await update.message.reply_text(f"❌ Помилка:\n{e}")

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
