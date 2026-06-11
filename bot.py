import os
import json
import asyncpg
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    ContextTypes, 
    ConversationHandler, 
    filters
)

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


# --- КЛІЄНТ GOOGLE SHEETS ---
def get_google_sheet():
    try:
        # Беремо правильну назву змінної зі скриншоту!
        creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        if not creds_json:
            print("Помилка: Змінна GOOGLE_CREDENTIALS_JSON не знайдена в Railway")
            return None
            
        creds_data = json.loads(creds_json)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        creds = Credentials.from_service_account_info(creds_data, scopes=scope)
        client = gspread.authorize(creds)
        
        # Беремо правильну назву ID таблиці зі скриншоту!
        spreadsheet_id = os.environ.get("GOOGLE_SHEET_ID")
        return client.open_by_key(spreadsheet_id)
    except Exception as e:
        print(f"Помилка підключення до Google Sheets: {e}")
        return None


TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

COMPANY_NAME = os.getenv("COMPANY_NAME", "RedGear Moto")
COMPANY_NIP = os.getenv("COMPANY_NIP", "8961641170")
COMPANY_PHONE = os.getenv("COMPANY_PHONE", "881198440")
COMPANY_INSTAGRAM = os.getenv("COMPANY_INSTAGRAM", "@redgearmoto")
COMPANY_ADDRESS = os.getenv("COMPANY_ADDRESS", "Przyjaźni 4, Wrocław")
COMPANY_CITY = os.getenv("COMPANY_CITY", "Wrocław")

LOGO_PATH = "logo.png"

# --- КОНСТАНТИ СТАНІВ ---
S_KLIENT, S_TELEFON, S_POJAZD, S_REJ, S_USLUGA, S_CZESCI, S_ROBOCIZNA, S_FORMA = range(100, 108)
C_NAME, C_PHONE, C_MIASTO, C_POJAZD = range(200, 204)
F_KWOTA, F_KIERUNEK, F_KATEGORIA, F_FORMA, F_OPIS = range(300, 305)

# --- МЕНЮ ---
MAIN_MENU = [
    ["💰 Finanse", "🛵 Rental"],
    ["🔧 Serwis", "📦 Magazyn"],
    ["👤 Klienci", "🏍 Skutery"],
    ["🤖 AI Mechanik", "🤖 AI wpis"],
    ["📊 Raport"],
]

FINANCE_MENU = [
    ["➕ Dochód", "➖ Wydatek"],
    ["💼 Bilans", "📊 Raport finansowy"],
    ["⬅️ Powrót"],
]

CLIENTS_MENU = [
    ["➕ Nowy klient", "📋 Lista klientów"],
    ["🔍 Szukaj klienta", "⬅️ Powrót"],
]

SCOOTERS_MENU = [
    ["➕ Dodaj skuter", "📋 Lista skuterów"],
    ["📍 Aktualizuj przebieg", "🔁 Zmień status"],
    ["⬅️ Powrót"],
]

RENTAL_MENU = [
    ["➕ Opłata rental", "➖ Koszt skutera"],
    ["📍 Przebieg skutera", "📋 Płatności rental"],
    ["📊 Raport rental", "⬅️ Powrót"],
]

SERVICE_MENU = [
    ["➕ Nowe zlecenie", "📋 Aktywne zlecenia"],
    ["🔍 Historia pojazdu", "📄 PDF dla klienta"],
    ["✅ Zamknij zlecenie", "⬅️ Powrót"],
]

STOCK_MENU = [
    ["➕ Przyjęcie towaru", "➖ Wydanie towaru"],
    ["📦 Stan magazynu", "🔍 Szukaj części"],
    ["⬅️ Powrót"],
]

def keyboard(menu):
    return ReplyKeyboardMarkup(menu, resize_keyboard=True)

CANCEL_KEYBOARD = ReplyKeyboardMarkup([["❌ Anuluj"]], resize_keyboard=True)


# --- БД (asyncpg) ---
async def get_db():
    if not DATABASE_URL:
        raise RuntimeError("Brak DATABASE_URL w Railway.")
    return await asyncpg.connect(DATABASE_URL)

async def init_db():
    conn = await get_db()
    await conn.execute("""
    CREATE TABLE IF NOT EXISTS finance (
        id SERIAL PRIMARY KEY,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        kierunek TEXT,
        typ TEXT NOT NULL,
        kategoria TEXT,
        kwota NUMERIC(10,2) NOT NULL,
        opis TEXT,
        forma_platnosci TEXT,
        source TEXT DEFAULT 'BOT'
    );
    """)
    await conn.execute("""
    CREATE TABLE IF NOT EXISTS clients (
        id SERIAL PRIMARY KEY,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        imie_nazwisko TEXT NOT NULL,
        telefon TEXT,
        typ TEXT,
        status TEXT,
        miasto TEXT,
        pojazd TEXT,
        rejestracja TEXT,
        vin TEXT,
        przebieg INTEGER DEFAULT 0,
        uwagi TEXT
    );
    """)
    await conn.execute("""
    CREATE TABLE IF NOT EXISTS scooters (
        id SERIAL PRIMARY KEY,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        nazwa TEXT NOT NULL,
        rejestracja TEXT,
        vin TEXT,
        status TEXT DEFAULT 'WOLNY',
        najemca TEXT,
        przebieg INTEGER DEFAULT 0,
        ostatni_serwis INTEGER DEFAULT 0,
        nastepny_serwis INTEGER DEFAULT 0,
        gps TEXT,
        uwagi TEXT
    );
    """)
    await conn.execute("""
    CREATE TABLE IF NOT EXISTS rental (
        id SERIAL PRIMARY KEY,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        skuter TEXT,
        klient TEXT,
        typ TEXT NOT NULL,
        kwota NUMERIC(10,2) NOT NULL,
        forma_platnosci TEXT,
        uwagi TEXT
    );
    """)
    await conn.execute("""
    CREATE TABLE IF NOT EXISTS service_orders (
        id SERIAL PRIMARY KEY,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        klient TEXT,
        telefon TEXT,
        pojazd TEXT,
        rejestracja TEXT,
        vin TEXT,
        przebieg INTEGER DEFAULT 0,
        usluga TEXT,
        czesci NUMERIC(10,2) DEFAULT 0,
        robocizna NUMERIC(10,2) DEFAULT 0,
        razem NUMERIC(10,2) DEFAULT 0,
        status TEXT DEFAULT 'OTWARTE',
        forma_platnosci TEXT,
        rekomendacje TEXT,
        uwagi TEXT
    );
    """)
    await conn.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        id SERIAL PRIMARY KEY,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        nazwa TEXT NOT NULL,
        ilosc INTEGER NOT NULL,
        cena NUMERIC(10,2) DEFAULT 0,
        typ_operacji TEXT NOT NULL,
        uwagi TEXT
    );
    """)
    await conn.execute("""
    CREATE TABLE IF NOT EXISTS ai_logs (
        id SERIAL PRIMARY KEY,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        raw_text TEXT,
        parsed_json TEXT,
        status TEXT
    );
    """)
    await conn.close()

async def add_finance(kierunek, typ, kategoria, kwota, opis, forma, source="BOT"):
    conn = await get_db()
    # Повертаємо згенерований ID для синхронізації з Excel
    new_id = await conn.fetchval("""
        INSERT INTO finance (created_at, kierunek, typ, kategoria, kwota, opis, forma_platnosci, source)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING id
    """, datetime.now(), kierunek, typ, kategoria, kwota, opis, forma, source)
    await conn.close()
    return new_id

async def get_balance():
    conn = await get_db()
    income = await conn.fetchval("SELECT COALESCE(SUM(kwota),0) FROM finance WHERE typ IN ('DOCHOD', 'income')")
    expense = await conn.fetchval("SELECT COALESCE(SUM(kwota),0) FROM finance WHERE typ IN ('WYDATEK', 'expense')")
    await conn.close()
    return income, expense, income - expense


# --- AI ШТУКИ ---
async def ask_ai_mechanic(text: str) -> str:
    if not OPENAI_API_KEY or not OpenAI:
        return "⚠️ Moduł AI nie skonfigurowany."
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Jesteś mechanikiem. Odpowiadaj krótko po polsku."},
                {"role": "user", "content": text}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"❌ Błąd AI: {e}"

async def process_ai_entry(text: str) -> str:
    return f"🤖 AI zapisało tekst: \"{text}\". Logika automatyczna w budowie."


# --- КРОКИ: СЕРВІС ---
async def s_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔧 Nowe zlecenie.\nKrok 1: Podaj imię i nazwisko klienta:", reply_markup=CANCEL_KEYBOARD)
    return S_KLIENT

async def s_klient(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['s_klient'] = update.message.text.strip()
    await update.message.reply_text("Krok 2: Podaj telefon:", reply_markup=CANCEL_KEYBOARD)
    return S_TELEFON

async def s_telefon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['s_telefon'] = update.message.text.strip()
    await update.message.reply_text("Krok 3: Podaj model pojazdu:", reply_markup=CANCEL_KEYBOARD)
    return S_POJAZD

async def s_pojazd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['s_pojazd'] = update.message.text.strip()
    await update.message.reply_text("Krok 4: Podaj nr rejestracyjny:", reply_markup=CANCEL_KEYBOARD)
    return S_REJ

async def s_rej(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['s_rej'] = update.message.text.strip()
    await update.message.reply_text("Krok 5: Opisz usługę:", reply_markup=CANCEL_KEYBOARD)
    return S_USLUGA

async def s_usluga(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['s_usluga'] = update.message.text.strip()
    await update.message.reply_text("Krok 6: Koszt części (0 lub kwota):", reply_markup=CANCEL_KEYBOARD)
    return S_CZESCI

async def s_czesci(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['s_czesci'] = float(update.message.text.strip().replace(",", "."))
    except ValueError:
        context.user_data['s_czesci'] = 0.0
    await update.message.reply_text("Krok 7: Koszt robocizny (0 lub kwota):", reply_markup=CANCEL_KEYBOARD)
    return S_ROBOCIZNA

async def s_robocizna(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['s_robocizna'] = float(update.message.text.strip().replace(",", "."))
    except ValueError:
        context.user_data['s_robocizna'] = 0.0
        
    km = ReplyKeyboardMarkup([["GOTÓWKA", "KARTA", "PRZELEW"]], resize_keyboard=True)
    await update.message.reply_text("Krok 8: Wybierz płatność:", reply_markup=km)
    return S_FORMA

async def s_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    forma = update.message.text.strip().upper()
    klient = context.user_data['s_klient']
    telefon = context.user_data['s_telefon']
    pojazd = context.user_data['s_pojazd']
    rej = context.user_data['s_rej']
    usluga = context.user_data['s_usluga']
    czesci = context.user_data['s_czesci']
    robocizna = context.user_data['s_robocizna']
    razem = czesci + robocizna

    try:
        conn = await get_db()
        order_id = await conn.fetchval("""
            INSERT INTO service_orders (klient, telefon, pojazd, rejestracja, usluga, czesci, robocizna, razem, forma_platnosci, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'OTWARTE') RETURNING id
        """, klient, telefon, pojazd, rej, usluga, czesci, robocizna, razem, forma)
        await conn.close()
        
        # Запис у Google Sheets (Вкладка має називатися точно 'SERWIS' як на скриншоті)
        try:
            sheet = get_google_sheet()
            if sheet:
                worksheet = sheet.worksheet("SERWIS")
                current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Точна структура твоєї таблиці:
                # ID_ZLECENIA | DATA | KLIENT | POJAZD | REJESTRACJA | PRZEBIEG | USLUGA | CZESCI | ROBOCIZNA | RAZEM | STATUS | FORMA PLATNOSCI | UWAGI
                row = [
                    f"S-{order_id:04d}", # Робимо гарний формат типу S-0012, як у тебе в таблиці
                    current_date,       # DATA
                    klient,             # KLIENT
                    pojazd,             # POJAZD
                    rej,                # REJESTRACJA
                    0,                  # PRZEBIEG (ставимо 0, бо в кроках його немає)
                    usluga,             # USLUGA
                    czesci,             # CZESCI
                    robocizna,          # ROBOCIZNA
                    razem,              # RAZEM
                    "W TOKU",           # STATUS
                    forma,              # FORMA PŁATNOŚCI
                    f"Tel: {telefon}"   # UWAGI (запишемо сюди телефон клієнта)
                ]
                worksheet.append_row(row)
        except Exception as sheet_err:
            print(f"Помилка запису SERWIS в Google Sheets: {sheet_err}")

        await update.message.reply_text(f"✅ Dodano zlecenie do bazy i Excel!\n👤 {klient} | 💰 {razem:.2f} zł", reply_markup=keyboard(SERVICE_MENU))
    except Exception as e:
        await update.message.reply_text(f"❌ Błąd DB: {e}", reply_markup=keyboard(SERVICE_MENU))
        
    context.user_data.clear()
    return ConversationHandler.END


# --- КРОКИ: КЛІЄНТ ---
async def c_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👤 Nowy klient.\nKrok 1: Podaj imię i nazwisko:", reply_markup=CANCEL_KEYBOARD)
    return C_NAME

async def c_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['c_name'] = update.message.text.strip()
    await update.message.reply_text("Krok 2: Podaj telefon:", reply_markup=CANCEL_KEYBOARD)
    return C_PHONE

async def c_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['c_phone'] = update.message.text.strip()
    await update.message.reply_text("Krok 3: Podaj miasto:", reply_markup=CANCEL_KEYBOARD)
    return C_MIASTO

async def c_miasto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['c_miasto'] = update.message.text.strip()
    await update.message.reply_text("Krok 4: Podaj markę/model pojazdu:", reply_markup=CANCEL_KEYBOARD)
    return C_POJAZD

async def c_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pojazd = update.message.text.strip()
    name = context.user_data['c_name']
    phone = context.user_data['c_phone']
    miasto = context.user_data['c_miasto']

    try:
        # 1. Записуємо в базу PostgreSQL
        conn = await get_db()
        client_id = await conn.fetchval("""
            INSERT INTO clients (imie_nazwisko, telefon, miasto, pojazd, typ, status)
            VALUES ($1, $2, $3, $4, 'SERWIS', 'AKTYWNY') RETURNING id
        """, name, phone, miasto, pojazd)
        await conn.close()
        
        # 2. Дублюємо в Google Sheets (Вкладка 'KLIENCI')
        try:
            sheet = get_google_sheet()
            if sheet:
                # Зверни увагу: назва вкладки має бути точно як в Excel — KLIENCI
                worksheet = sheet.worksheet("KLIENCI")
                current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Формуємо рядок під стовпчики твоєї таблиці:
                # ID_KLIENTA | DATA | IMIE_NAZWISKO | TELEFON | MIASTO | POJAZD | TYP | STATUS
                row = [
                    f"K-{client_id:04d}", # Формат клієнта: K-0001, K-0002 і т.д.
                    current_date,         # DATA
                    name,                 # IMIE_NAZWISKO
                    phone,                # TELEFON
                    miasto,               # MIASTO
                    pojazd,               # POJAZD
                    "SERWIS",             # TYP
                    "AKTYWNY"             # STATUS
                ]
                worksheet.append_row(row)
                print("Клієнта успішно додано в Google Sheets!")
        except Exception as sheet_err:
            print(f"Помилка запису Klienci в Google Sheets: {sheet_err}")

        await update.message.reply_text(f"✅ Klient {name} dodany do bazy i Excel!", reply_markup=keyboard(CLIENTS_MENU))
    except Exception as e:
        await update.message.reply_text(f"❌ Błąd: {e}", reply_markup=keyboard(CLIENTS_MENU))
        
    context.user_data.clear()
    return ConversationHandler.END


# --- КРОКИ: ФІНАНСИ ---
async def f_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data['f_typ'] = "DOCHOD" if "Dochód" in text else "WYDATEK"
    await update.message.reply_text("💰 Krok 1: Wpisz kwotę:", reply_markup=CANCEL_KEYBOARD)
    return F_KWOTA

async def f_kwota(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['f_kwota'] = float(update.message.text.strip().replace(",", "."))
    except ValueError:
        await update.message.reply_text("❌ Podaj liczbę!")
        return F_KWOTA
    
    km = ReplyKeyboardMarkup([["SERWIS", "RENTAL", "SKLEP", "INNE"]], resize_keyboard=True)
    await update.message.reply_text("Krok 2: Wybierz kierunek:", reply_markup=km)
    return F_KIERUNEK

async def f_kierunek(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['f_kierunek'] = update.message.text.strip().upper()
    km = ReplyKeyboardMarkup([["NAPRAWA", "CZESCI", "OPLATA", "PALIWO", "INNE"]], resize_keyboard=True)
    await update.message.reply_text("Krok 3: Wybierz kategorię:", reply_markup=km)
    return F_KATEGORIA

async def f_kategoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['f_kategoria'] = update.message.text.strip().upper()
    km = ReplyKeyboardMarkup([["GOTÓWKA", "KARTA", "PRZELEW", "BLIK"]], resize_keyboard=True)
    await update.message.reply_text("Krok 4: Wybierz formę płatności:", reply_markup=km)
    return F_FORMA

async def f_forma(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['f_forma'] = update.message.text.strip().upper()
    await update.message.reply_text("Krok 5: Wpisz krótki opis:", reply_markup=CANCEL_KEYBOARD)
    return F_OPIS

async def f_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    opis = update.message.text.strip()
    typ = context.user_data['f_typ']
    kwota = context.user_data['f_kwota']
    kierunek = context.user_data['f_kierunek']
    kategoria = context.user_data['f_kategoria']
    forma = context.user_data['f_forma']

    try:
        finance_id = await add_finance(kierunek, typ, kategoria, kwota, opis, forma)
        
        # --- СИНХРОНІЗАЦІЯ З EXCEL (Sheet: Finanse) ---
        try:
            sheet = get_google_sheet()
            if sheet:
                worksheet = sheet.worksheet("Finanse")
                current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                row = [
                    finance_id,   # ID
                    current_date, # Data
                    kierunek,     # Kierunek
                    typ,          # Typ
                    kategoria,    # Kategoria
                    kwota,        # Kwota
                    forma,        # Forma płatności
                    opis          # Opis
                ]
                worksheet.append_row(row)
        except Exception as sheet_err:
            print(f"Помилка запису Finanse в Google Sheets: {sheet_err}")

        await update.message.reply_text(f"✅ Zapisano w bazie i Excel! {typ}: {kwota:.2f} zł", reply_markup=keyboard(FINANCE_MENU))
    except Exception as e:
        await update.message.reply_text(f"❌ Błąd: {e}", reply_markup=keyboard(FINANCE_MENU))
        
    context.user_data.clear()
    return ConversationHandler.END


async def global_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Anulowano.", reply_markup=keyboard(MAIN_MENU))
    context.user_data.clear()
    return ConversationHandler.END


# --- ОБРОБКА ПОВІДОМЛЕНЬ ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if text == "💰 Finanse":
        await update.message.reply_text("Finanse:", reply_markup=keyboard(FINANCE_MENU))
        return
    if text == "👤 Klienci":
        await update.message.reply_text("Klienci:", reply_markup=keyboard(CLIENTS_MENU))
        return
    if text == "🏍 Skutery":
        await update.message.reply_text("Skutery:", reply_markup=keyboard(SCOOTERS_MENU))
        return
    if text == "🛵 Rental":
        await update.message.reply_text("Rental:", reply_markup=keyboard(RENTAL_MENU))
        return
    if text == "🔧 Serwis":
        await update.message.reply_text("Serwis:", reply_markup=keyboard(SERVICE_MENU))
        return
    if text == "📦 Magazyn":
        await update.message.reply_text("Magazyn:", reply_markup=keyboard(STOCK_MENU))
        return
    if text == "⬅️ Powrót":
        await update.message.reply_text("Menu główne:", reply_markup=keyboard(MAIN_MENU))
        return

    if text == "💼 Bilans":
        income, expense, balance = await get_balance()
        await update.message.reply_text(f"💼 Bilans {COMPANY_NAME}\n\nDochody: {income:.2f} zł\nWydatki: {expense:.2f} zł\nBilans: {balance:.2f} zł")
        return

    if text == "📋 Lista klientów":
        conn = await get_db()
        rows = await conn.fetch("SELECT imie_nazwisko, telefon, miasto, pojazd FROM clients ORDER BY id DESC LIMIT 20")
        await conn.close()
        if not rows:
            await update.message.reply_text("Baza klientów jest pusta.")
            return
        msg = "📋 Lista klientów:\n\n"
        for r in rows:
            msg += f"👤 {r['imie_nazwisko']} | 📞 {r['telefon']}\n🏙 {r['miasto']} | 🏍 {r['pojazd']}\n\n"
        await update.message.reply_text(msg)
        return

    if text == "📋 Aktywne zlecenia":
        conn = await get_db()
        rows = await conn.fetch("SELECT id, klient, pojazd, usluga, razem FROM service_orders WHERE status='OTWARTE' ORDER BY id DESC")
        await conn.close()
        if not rows:
            await update.message.reply_text("Brak aktywnych zleceń.")
            return
        msg = "🔧 Aktywne zlecenia:\n\n"
        for r in rows:
            msg += f"#{r['id']} | {r['klient']} - 🏍 {r['pojazd']}\n⚙️ {r['usluga']}\n💰 Razem: {r['razem']:.2f} zł\n\n"
        await update.message.reply_text(msg)
        return

    if text == "🤖 AI Mechanik":
        context.user_data["mode"] = "ai_mechanic"
        await update.message.reply_text("Opisz problem motocykla (AI Mechanik):")
        return

    if text == "🤖 AI wpis":
        context.user_data["mode"] = "ai_entry"
        await update.message.reply_text("Wpisz naturalnie co się stało:")
        return

    mode = context.user_data.get("mode")
    if mode == "ai_mechanic":
        answer = await ask_ai_mechanic(text)
        await update.message.reply_text(answer, reply_markup=keyboard(MAIN_MENU))
        context.user_data.clear()
        return

    if mode == "ai_entry":
        result = await process_ai_entry(text)
        await update.message.reply_text(result, reply_markup=keyboard(MAIN_MENU))
        context.user_data.clear()
        return

    await update.message.reply_text("Wybierz opcję z menu.", reply_markup=keyboard(MAIN_MENU))


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"{COMPANY_NAME} Assistant 🏍️", reply_markup=keyboard(MAIN_MENU))

async def post_init(app):
    await init_db()

if __name__ == "__main__":
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    
    serwis_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Text("➕ Nowe zlecenie"), s_start)],
        states={
            S_KLIENT: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), s_klient)],
            S_TELEFON: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), s_telefon)],
            S_POJAZD: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), s_pojazd)],
            S_REJ: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), s_rej)],
            S_USLUGA: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), s_usluga)],
            S_CZESCI: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), s_czesci)],
            S_ROBOCIZNA: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), s_robocizna)],
            S_FORMA: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), s_final)],
        },
        fallbacks=[MessageHandler(filters.Text("❌ Anuluj"), global_cancel)]
    )
    
    klient_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Text("➕ Nowy klient"), c_start)],
        states={
            C_NAME: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), c_name)],
            C_PHONE: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), c_phone)],
            C_MIASTO: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), c_miasto)],
            C_POJAZD: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), c_final)],
        },
        fallbacks=[MessageHandler(filters.Text("❌ Anuluj"), global_cancel)]
    )

    finance_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Text(["➕ Dochód", "➖ Wydatek"]), f_start)],
        states={
            F_KWOTA: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), f_kwota)],
            F_KIERUNEK: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), f_kierunek)],
            F_KATEGORIA: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), f_kategoria)],
            F_FORMA: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), f_forma)],
            F_OPIS: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), f_final)],
        },
        fallbacks=[MessageHandler(filters.Text("❌ Anuluj"), global_cancel)]
    )

    app.add_handler(serwis_conv)
    app.add_handler(klient_conv)
    app.add_handler(finance_conv)
    
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, callback=handle_message))
    
    app.run_polling()
