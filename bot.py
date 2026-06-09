from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import os

TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привіт! Я RedGear Assistant 🏍️\n\n"
        "Доступні команди:\n"
        "/finance\n"
        "/stock\n"
        "/scooters\n"
        "/clients"
    )

async def finance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Фінансовий модуль")

async def stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Склад запчастин")

async def scooters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Оренда скутерів")

async def clients(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("База клієнтів")

app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("finance", finance))
app.add_handler(CommandHandler("stock", stock))
app.add_handler(CommandHandler("scooters", scooters))
app.add_handler(CommandHandler("clients", clients))

app.run_polling()
