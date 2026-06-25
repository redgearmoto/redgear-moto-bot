import os
import json
import asyncpg
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters
)

TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

S_KLIENT, S_WYBOR, S_POJAZD, S_REJ, S_PRZEBIEG, S_USLUGA, S_CZESCI, S_ROBOCIZNA, S_FORMA, S_UWAGI = range(100, 110)
C_NAME, C_PHONE, C_TYP, C_STATUS, C_MIASTO, C_UWAGI, C_WIZYTA, C_ZAROBIONO, C_POJAZD = range(200, 209)
F_KIERUNEK, F_TYP, F_KATEGORIA, F_INWESTYCJA, F_OPIS, F_KWOTA, F_FORMA, F_KLIENT, F_WYBOR, F_DOKUMENT, F_NOTATKA = range(300, 311)
R_SKUTER, R_KLIENT, R_WYBOR, R_TYP, R_OPERACJA, R_KWOTA, R_FORMA, R_UWAGI = range(400, 408)
SK_ID, SK_MARKA, SK_MODEL, SK_ROK, SK_REJ, SK_VIN, SK_STATUS, SK_NAJEMCA, SK_WYBOR, SK_TYP, SK_KAUCJA, SK_START, SK_STOP, SK_TERMIN, SK_PLATNOSC, SK_ZALEGLOSC, SK_UWAGI, SK_GPS, SK_GPS_ID, SK_CENA, SK_PRZEBIEG, SK_SERWIS_OST, SK_SERWIS_NAST, SK_RAPORT, SK_UBEZP, SK_PRZEGLAD = range(500, 526)

MAIN_MENU = [
    ["💰 Finanse", "🛵 Rental"],
    ["🔧 Serwis", "👤 Klienci"],
    ["🏍 Skutery", "📊 Raport"]
]

FINANCE_MENU = [
    ["➕ Dodaj operację", "💼 Bilans"],
    ["⬅️ Powrót"]
]

CLIENTS_MENU = [
    ["➕ Nowy klient", "📋 Lista klientów"],
    ["⬅️ Powrót"]
]

SCOOTERS_MENU = [
    ["➕ Dodaj skuter", "📋 Lista skuterów"],
    ["⬅️ Powrót"]
]

RENTAL_MENU = [
    ["➕ Nowa operacja", "📋 Lista operacji"],
    ["⬅️ Powrót"]
]

SERVICE_MENU = [
    ["➕ Nowe zlecenie", "📋 Aktywne zlecenia"],
    ["⬅️ Powrót"]
]

def keyboard(menu):
    return ReplyKeyboardMarkup(menu, resize_keyboard=True)

def get_google_sheet():
    try:
        creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        if not creds_json:
            return None
        creds_data = json.loads(creds_json)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_data, scopes=scope)
        client = gspread.authorize(creds)
        spreadsheet_id = os.environ.get("GOOGLE_SHEET_ID")
        return client.open_by_key(spreadsheet_id)
    except Exception:
        return None

async def get_db():
    return await asyncpg.connect(DATABASE_URL)

async def init_db():
    conn = await get_db()
    await conn.execute("""
    CREATE TABLE IF NOT EXISTS clients (
        id SERIAL PRIMARY KEY,
        imie_nazwisko TEXT,
        telefon TEXT,
        typ TEXT,
        status TEXT,
        miasto TEXT,
        data_dodania TEXT,
        uwagi TEXT,
        ostatnia_wizyta TEXT,
        ile_zarobiono TEXT,
        pojazd TEXT
    );
    """)
    await conn.execute("""
    CREATE TABLE IF NOT EXISTS service_orders (
        id SERIAL PRIMARY KEY,
        data TEXT,
        klient_id INTEGER,
        klient_name TEXT,
        pojazd TEXT,
        rejestracja TEXT,
        przebieg TEXT,
        usluga TEXT,
        czesci TEXT,
        robocizna TEXT,
        razem TEXT,
        status TEXT,
        forma_platnosci TEXT,
        uwagi TEXT
    );
    """)
    await conn.execute("""
    CREATE TABLE IF NOT EXISTS finance (
        id SERIAL PRIMARY KEY,
        data TEXT,
        kierunek TEXT,
        typ TEXT,
        kategoria TEXT,
        czy_inwestycja TEXT,
        opis TEXT,
        kwota TEXT,
        forma_platnosci TEXT,
        klient TEXT,
        nr_dokumentu TEXT,
        notatka TEXT
    );
    """)
    await conn.execute("""
    CREATE TABLE IF NOT EXISTS rental (
        id SERIAL PRIMARY KEY,
        data TEXT,
        skuter TEXT,
        klient TEXT,
        typ TEXT,
        operacja TEXT,
        kwota TEXT,
        forma_platnosci TEXT,
        uwagi TEXT
    );
    """)
    await conn.execute("""
    CREATE TABLE IF NOT EXISTS scooters (
        id TEXT PRIMARY KEY,
        marka TEXT,
        model TEXT,
        rok TEXT,
        rejestracja TEXT,
        vin TEXT,
        status TEXT,
        najemca TEXT,
        typ_platnosci TEXT,
        kaucja TEXT,
        data_start TEXT,
        data_stop TEXT,
        termin_platnosci TEXT,
        ostatnia_platnosc TEXT,
        kwota_zaleglosci TEXT,
        uwagi TEXT,
        gps TEXT,
        gps_id TEXT,
        cena_tydz TEXT,
        aktualny_przebieg TEXT,
        ostatni_serwis TEXT,
        nastepny_serwis TEXT,
        pozostalo_km TEXT,
        data_raportu_km TEXT,
        ubezpieczenie_do TEXT,
        przeglad_do TEXT
    );
    """)
    await conn.close()

async def global_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Anulowano.", reply_markup=keyboard(MAIN_MENU))
    context.user_data.clear()
    return ConversationHandler.END

async def s_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Wpisz imię i nazwisko klienta (Wymagane):", reply_markup=keyboard([["❌ Anuluj"]]))
    return S_KLIENT

async def s_klient(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    context.user_data['s_klient_name'] = name
    conn = await get_db()
    rows = await conn.fetch("SELECT id, imie_nazwisko, telefon, pojazd FROM clients WHERE LOWER(imie_nazwisko) = LOWER($1)", name)
    await conn.close()
    if not rows:
        context.user_data['s_klient_id'] = None
        await update.message.reply_text("Klienta nie ma w bazie. Wpisz model pojazdu (Wymagane):", reply_markup=keyboard([["❌ Anuluj"]]))
        return S_POJAZD
    elif len(rows) == 1:
        context.user_data['s_klient_id'] = rows[0]['id']
        context.user_data['s_pojazd'] = rows[0]['pojazd'] if rows[0]['pojazd'] else "BRAK"
        await update.message.reply_text(f"Znaleziono klienta: {rows[0]['imie_nazwisko']} ({rows[0]['telefon']}). Pojazd: {context.user_data['s_pojazd']}\nWpisz nr rejestracyjny:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
        return S_REJ
    else:
        buttons = []
        for r in rows:
            buttons.append([f"ID: {r['id']} | {r['imie_nazwisko']} | {r['telefon']}"])
        buttons.append([f"Stwórz nowego: {name}"])
        buttons.append(["❌ Anuluj"])
        await update.message.reply_text("Znaleziono kilku klientów o tym imieniu. Wybierz właściwego:", reply_markup=keyboard(buttons))
        return S_WYBOR

async def s_wybor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if txt.startswith("ID: "):
        cid = int(txt.split("|")[0].replace("ID: ", "").strip())
        context.user_data['s_klient_id'] = cid
        conn = await get_db()
        row = await conn.fetchrow("SELECT pojazd FROM clients WHERE id = $1", cid)
        await conn.close()
        context.user_data['s_pojazd'] = row['pojazd'] if row['pojazd'] else "BRAK"
        await update.message.reply_text(f"Wybrano klienta ID {cid}. Pojazd: {context.user_data['s_pojazd']}\nWpisz nr rejestracyjny:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
        return S_REJ
    else:
        context.user_data['s_klient_id'] = None
        await update.message.reply_text("Wpisz model pojazdu (Wymagane):", reply_markup=keyboard([["❌ Anuluj"]]))
        return S_POJAZD

async def s_pojazd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['s_pojazd'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wpisz nr rejestracyjny:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
    return S_REJ

async def s_rej(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['s_rej'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wpisz przebieg:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
    return S_PRZEBIEG

async def s_przebieg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['s_przebieg'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Opisz usługę:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
    return S_USLUGA

async def s_usluga(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['s_usluga'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wpisz koszt części:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
    return S_CZESCI

async def s_czesci(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['s_czesci'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wpisz koszt robocizny:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
    return S_ROBOCIZNA

async def s_robocizna(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['s_robocizna'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wybierz formę płatności:", reply_markup=keyboard([["GOTÓWKA"], ["KARTA"], ["PRZELEW"], ["BRAK"], ["❌ Anuluj"]]))
    return S_FORMA

async def s_forma(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['s_forma'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wpisz uwagi:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
    return S_UWAGI

async def s_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    uwagi = "BRAK" if txt.upper() == "BRAK" else txt
    dt = datetime.now().strftime("%d.%m.%Y")
    klient_name = context.user_data['s_klient_name']
    klient_id = context.user_data['s_klient_id']
    pojazd = context.user_data['s_pojazd']
    rej = context.user_data['s_rej']
    przebieg = context.user_data['s_przebieg']
    usluga = context.user_data['s_usluga']
    czesci = context.user_data['s_czesci']
    robocizna = context.user_data['s_robocizna']
    forma = context.user_data['s_forma']
    try:
        c_val = float(czesci) if czesci != "BRAK" else 0.0
        r_val = float(robocizna) if robocizna != "BRAK" else 0.0
        razem = str(c_val + r_val)
    except Exception:
        razem = "BRAK"
    conn = await get_db()
    nid = await conn.fetchval("""
        INSERT INTO service_orders (data, klient_id, klient_name, pojazd, rejestracja, przebieg, usluga, czesci, robocizna, razem, status, forma_platnosci, uwagi)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13) RETURNING id
    """, dt, klient_id, klient_name, pojazd, rej, przebieg, usluga, czesci, robocizna, razem, "W TOKU", forma, uwagi)
    await conn.close()
    try:
        sheet = get_google_sheet()
        if sheet:
            worksheet = sheet.worksheet("SERWIS")
            row = [f"S-{nid:04d}", dt, klient_name, pojazd, rej, "" if Przebieg=="BRAK" else Przebieg, usluga, czesci, robocizna, razem, "W TOKU", forma, uwagi]
            worksheet.append_row(row)
    except Exception:
        pass
    await update.message.reply_text("Zlecenie dodane pomyślnie!", reply_markup=keyboard(MAIN_MENU))
    context.user_data.clear()
    return ConversationHandler.END

async def c_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Wpisz imię i nazwisko klienta (Wymagane):", reply_markup=keyboard([["❌ Anuluj"]]))
    return C_NAME

async def c_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['c_name'] = update.message.text.strip()
    await update.message.reply_text("Wpisz telefon (Wymagane):", reply_markup=keyboard([["❌ Anuluj"]]))
    return C_PHONE

async def c_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['c_phone'] = update.message.text.strip()
    await update.message.reply_text("Wybierz typ:", reply_markup=keyboard([["RENTAL"], ["SERWIS"], ["BRAK"], ["❌ Anuluj"]]))
    return C_TYP

async def c_typ(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['c_typ'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wybierz status:", reply_markup=keyboard([["AKTYWNY"], ["POTENCJALNY"], ["CZARNA LISTA"], ["BRAK"], ["❌ Anuluj"]]))
    return C_STATUS

async def c_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['c_status'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wpisz miasto:", reply_markup=keyboard([["WROCŁAW"], ["OLEŚNICA"], ["TRZEBNICA"], ["BRAK"], ["❌ Anuluj"]]))
    return C_MIASTO

async def c_miasto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['c_miasto'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wpisz uwagi:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
    return C_UWAGI

async def c_uwagi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['c_uwagi'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wpisz ostatnią wizytę:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
    return C_WIZYTA

async def c_wizyta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['c_wizyta'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wpisz ile zarobiono:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
    return C_ZAROBIONO

async def c_zarobiono(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['c_zarobiono'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wpisz model pojazdu:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
    return C_POJAZD

async def c_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    pojazd = "BRAK" if txt.upper() == "BRAK" else txt
    dt = datetime.now().strftime("%d.%m.%Y")
    name = context.user_data['c_name']
    phone = context.user_data['c_phone']
    typ = context.user_data['c_typ']
    status = context.user_data['c_status']
    miasto = context.user_data['c_miasto']
    uwagi = context.user_data['c_uwagi']
    wizyta = context.user_data['c_wizyta']
    zarobiono = context.user_data['c_zarobiono']
    conn = await get_db()
    nid = await conn.fetchval("""
        INSERT INTO clients (imie_nazwisko, telefon, typ, status, miasto, data_dodania, uwagi, ostatnia_wizyta, ile_zarobiono, pojazd)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) RETURNING id
    """, name, phone, typ, status, miasto, dt, uwagi, wizyta, zarobiono, pojazd)
    await conn.close()
    try:
        sheet = get_google_sheet()
        if sheet:
            worksheet = sheet.worksheet("KLIENCI")
            row = [f"K-{nid:03d}", name, phone, typ, status, miasto, dt, uwagi, wizyta, zarobiono, pojazd]
            worksheet.append_row(row)
    except Exception:
        pass
    await update.message.reply_text("Klient dodany pomyślnie!", reply_markup=keyboard(MAIN_MENU))
    context.user_data.clear()
    return ConversationHandler.END

async def f_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Wybierz kierunek (Wymagane):", reply_markup=keyboard([["RENTAL"], ["SERWIS"], ["SKLEP"], ["INNE"], ["❌ Anuluj"]]))
    return F_KIERUNEK

async def f_kierunek(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['f_kierunek'] = update.message.text.strip()
    await update.message.reply_text("Wybierz typ (Wymagane):", reply_markup=keyboard([["DOCHÓD"], ["WYDATEK"], ["❌ Anuluj"]]))
    return F_TYP

async def f_typ(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['f_typ'] = update.message.text.strip()
    await update.message.reply_text("Wpisz kategorię:", reply_markup=keyboard([["WYNAJEM TYGODNIOWY"], ["ELEKTRYKA"], ["BRAK"], ["❌ Anuluj"]]))
    return F_KATEGORIA

async def f_kategoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['f_kategoria'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Czy inwestycja?", reply_markup=keyboard([["NIE"], ["TAK"], ["❌ Anuluj"]]))
    return F_INWESTYCJA

async def f_inwestycja(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['f_inwestycja'] = update.message.text.strip()
    await update.message.reply_text("Wpisz opis:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
    return F_OPIS

async def f_opis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['f_opis'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wpisz kwotę (Wymagane):", reply_markup=keyboard([["❌ Anuluj"]]))
    return F_KWOTA

async def f_kwota(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['f_kwota'] = update.message.text.strip()
    await update.message.reply_text("Wybierz formę płatności:", reply_markup=keyboard([["GOTÓWKA"], ["KARTA"], ["PRZELEW"], ["BRAK"], ["❌ Anuluj"]]))
    return F_FORMA

async def f_forma(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['f_forma'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wpisz klienta:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
    return F_KLIENT

async def f_klient(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if name.upper() == "BRAK":
        context.user_data['f_klient'] = "BRAK"
        await update.message.reply_text("Wpisz nr dokumentu:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
        return F_DOKUMENT
    context.user_data['f_klient_name'] = name
    conn = await get_db()
    rows = await conn.fetch("SELECT id, imie_nazwisko, telefon FROM clients WHERE LOWER(imie_nazwisko) = LOWER($1)", name)
    await conn.close()
    if not rows:
        context.user_data['f_klient'] = name
        await update.message.reply_text("Wpisz nr dokumentu:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
        return F_DOKUMENT
    elif len(rows) == 1:
        context.user_data['f_klient'] = rows[0]['imie_nazwisko']
        await update.message.reply_text("Wpisz nr dokumentu:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
        return F_DOKUMENT
    else:
        buttons = []
        for r in rows:
            buttons.append([f"ID: {r['id']} | {r['imie_nazwisko']} | {r['telefon']}"])
        buttons.append([f"Zostaw tekst: {name}"])
        buttons.append(["❌ Anuluj"])
        await update.message.reply_text("Znaleziono kilku klientów, wybierz właściwego:", reply_markup=keyboard(buttons))
        return F_WYBOR

async def f_wybor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if txt.startswith("ID: "):
        context.user_data['f_klient'] = txt.split("|")[1].strip()
    else:
        context.user_data['f_klient'] = context.user_data['f_klient_name']
    await update.message.reply_text("Wpisz nr dokumentu:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
    return F_DOKUMENT

async def f_dokument(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['f_dokument'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wpisz notatkę:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
    return F_NOTATKA

async def f_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    notatka = "BRAK" if txt.upper() == "BRAK" else txt
    dt = datetime.now().strftime("%d.%m.%Y")
    kierunek = context.user_data['f_kierunek']
    typ = context.user_data['f_typ']
    kategoria = context.user_data['f_kategoria']
    inwestycja = context.user_data['f_inwestycja']
    opis = context.user_data['f_opis']
    kwota = context.user_data['f_kwota']
    forma = context.user_data['f_forma']
    klient = context.user_data['f_klient']
    dokument = context.user_data['f_dokument']
    conn = await get_db()
    nid = await conn.fetchval("""
        INSERT INTO finance (data, kierunek, typ, kategoria, czy_inwestycja, opis, kwota, forma_platnosci, klient, nr_dokumentu, notatka)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11) RETURNING id
    """, dt, kierunek, typ, kategoria, inwestycja, opis, kwota, forma, klient, dokument, notatka)
    await conn.close()
    try:
        sheet = get_google_sheet()
        if sheet:
            worksheet = sheet.worksheet("FINANSE")
            row = [f"F-{nid:04d}", dt, kierunek, typ, kategoria, inwestycja, opis, kwota, forma, klient, dokument, notatka]
            worksheet.append_row(row)
    except Exception:
        pass
    await update.message.reply_text("Operacja finansowa dodana!", reply_markup=keyboard(MAIN_MENU))
    context.user_data.clear()
    return ConversationHandler.END

async def r_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Wpisz ID skutera (Wymagane):", reply_markup=keyboard([["❌ Anuluj"]]))
    return R_SKUTER

async def r_skuter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['r_skuter'] = update.message.text.strip().upper()
    await update.message.reply_text("Wpisz imię i nazwisko klienta (Wymagane):", reply_markup=keyboard([["❌ Anuluj"]]))
    return R_KLIENT

async def r_klient(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    context.user_data['r_klient_name'] = name
    conn = await get_db()
    rows = await conn.fetch("SELECT id, imie_nazwisko, telefon FROM clients WHERE LOWER(imie_nazwisko) = LOWER($1)", name)
    await conn.close()
    if not rows:
        context.user_data['r_klient'] = name
        await update.message.reply_text("Wybierz typ operacji:", reply_markup=keyboard([["DOCHÓD"], ["KAUCJA"], ["WYDATEK"], ["❌ Anuluj"]]))
        return R_TYP
    elif len(rows) == 1:
        context.user_data['r_klient'] = rows[0]['imie_nazwisko']
        await update.message.reply_text("Wybierz typ operacji:", reply_markup=keyboard([["DOCHÓD"], ["KAUCJA"], ["WYDATEK"], ["❌ Anuluj"]]))
        return R_TYP
    else:
        buttons = []
        for r in rows:
            buttons.append([f"ID: {r['id']} | {r['imie_nazwisko']} | {r['telefon']}"])
        buttons.append([f"Zostaw tekst: {name}"])
        buttons.append(["❌ Anuluj"])
        await update.message.reply_text("Znaleziono kilku klientów, wybierz właściwego:", reply_markup=keyboard(buttons))
        return R_WYBOR

async def r_wybor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if txt.startswith("ID: "):
        context.user_data['r_klient'] = txt.split("|")[1].strip()
    else:
        context.user_data['r_klient'] = context.user_data['r_klient_name']
    await update.message.reply_text("Wybierz typ operacji:", reply_markup=keyboard([["DOCHÓD"], ["KAUCJA"], ["WYDATEK"], ["❌ Anuluj"]]))
    return R_TYP

async def r_typ(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['r_typ'] = update.message.text.strip()
    await update.message.reply_text("Wpisz nazwę operacji:", reply_markup=keyboard([["OPLATA TYGODNIOWA"], ["OPLATA MIESIECZNA"], ["KAUCJA"], ["NAPRAWA"], ["BRAK"], ["❌ Anuluj"]]))
    return R_OPERACJA

async def r_operacja(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['r_operacja'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wpisz kwotę (Wymagane):", reply_markup=keyboard([["❌ Anuluj"]]))
    return R_KWOTA

async def r_kwota(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['r_kwota'] = update.message.text.strip()
    await update.message.reply_text("Wybierz formę płatności:", reply_markup=keyboard([["GOTÓWKA"], ["KARTA"], ["PRZELEW"], ["PRZELEW NA TELEFON"], ["BRAK"], ["❌ Anuluj"]]))
    return R_FORMA

async def r_forma(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['r_forma'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wpisz uwagi:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
    return R_UWAGI

async def r_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    uwagi = "BRAK" if txt.upper() == "BRAK" else txt
    dt = datetime.now().strftime("%d.%m.%Y")
    skuter = context.user_data['r_skuter']
    klient = context.user_data['r_klient']
    typ = context.user_data['r_typ']
    operacja = context.user_data['r_operacja']
    kwota = context.user_data['r_kwota']
    forma = context.user_data['r_forma']
    conn = await get_db()
    nid = await conn.fetchval("""
        INSERT INTO rental (data, skuter, klient, typ, operacja, kwota, forma_platnosci, uwagi)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING id
    """, dt, skuter, klient, typ, operacja, kwota, forma, uwagi)
    await conn.close()
    try:
        sheet = get_google_sheet()
        if sheet:
            worksheet = sheet.worksheet("RENTAL")
            row = [f"R-{nid:03d}", dt, skuter, klient, typ, operacja, kwota, forma, uwagi]
            worksheet.append_row(row)
    except Exception:
        pass
    await update.message.reply_text("Operacja rental dodana!", reply_markup=keyboard(MAIN_MENU))
    context.user_data.clear()
    return ConversationHandler.END

async def sk_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Wpisz ID skutera (Wymagane):", reply_markup=keyboard([["❌ Anuluj"]]))
    return SK_ID

async def sk_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['sk_id'] = update.message.text.strip().upper()
    await update.message.reply_text("Wpisz markę:", reply_markup=keyboard([["HONDA"], ["TGB"], ["BRAK"], ["❌ Anuluj"]]))
    return SK_MARKA

async def sk_marka(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['sk_marka'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wpisz model:", reply_markup=keyboard([["WW125A"], ["101S ORION"], ["BRAK"], ["❌ Anuluj"]]))
    return SK_MODEL

async def sk_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['sk_model'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wpisz rok produkcji:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
    return SK_ROK

async def sk_rok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['sk_rok'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wpisz nr rejestracyjny:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
    return SK_REJ

async def sk_rej(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['sk_rej'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wpisz VIN:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
    return SK_VIN

async def sk_vin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['sk_vin'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wybierz status:", reply_markup=keyboard([["W NAJMIE"], ["WOLNY"], ["USZKODZONY"], ["BRAK"], ["❌ Anuluj"]]))
    return SK_STATUS

async def sk_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['sk_status'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wpisz najemcę:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
    return SK_NAJEMCA

async def sk_najemca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if name.upper() == "BRAK":
        context.user_data['sk_najemca'] = "BRAK"
        await update.message.reply_text("Wybierz typ płatności:", reply_markup=keyboard([["TYGODNIOWO"], ["MIESIĘCZNIE"], ["BRAK"], ["❌ Anuluj"]]))
        return SK_TYP
    context.user_data['sk_najemca_name'] = name
    conn = await get_db()
    rows = await conn.fetch("SELECT id, imie_nazwisko, telefon FROM clients WHERE LOWER(imie_nazwisko) = LOWER($1)", name)
    await conn.close()
    if not rows:
        context.user_data['sk_najemca'] = name
        await update.message.reply_text("Wybierz typ płatności:", reply_markup=keyboard([["TYGODNIOWO"], ["MIESIĘCZNIE"], ["BRAK"], ["❌ Anuluj"]]))
        return SK_TYP
    elif len(rows) == 1:
        context.user_data['sk_najemca'] = rows[0]['imie_nazwisko']
        await update.message.reply_text("Wybierz typ płatności:", reply_markup=keyboard([["TYGODNIOWO"], ["MIESIĘCZNIE"], ["BRAK"], ["❌ Anuluj"]]))
        return SK_TYP
    else:
        buttons = []
        for r in rows:
            buttons.append([f"ID: {r['id']} | {r['imie_nazwisko']} | {r['telefon']}"])
        buttons.append([f"Zostaw tekst: {name}"])
        buttons.append(["❌ Anuluj"])
        await update.message.reply_text("Znaleziono kilku klientów, wybierz właściwego najemcę:", reply_markup=keyboard(buttons))
        return SK_WYBOR

async def sk_wybor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if txt.startswith("ID: "):
        context.user_data['sk_najemca'] = txt.split("|")[1].strip()
    else:
        context.user_data['sk_najemca'] = context.user_data['sk_najemca_name']
    await update.message.reply_text("Wybierz typ płatności:", reply_markup=keyboard([["TYGODNIOWO"], ["MIESIĘCZNIE"], ["BRAK"], ["❌ Anuluj"]]))
    return SK_TYP

async def sk_typ(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['sk_typ'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wpisz kaucję:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
    return SK_KAUCJA

async def sk_kaucja(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['sk_kaucja'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wpisz datę startu najmu:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
    return SK_START

async def sk_start_dt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['sk_start'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wpisz datę stopu najmu:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
    return SK_STOP

async def sk_stop_dt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['sk_stop'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wpisz termin płatności:", reply_markup=keyboard([["WTOREK"], ["MIESIAC"], ["BRAK"], ["❌ Anuluj"]]))
    return SK_TERMIN

async def sk_termin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['sk_termin'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wpisz ostatnią płatność:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
    return SK_PLATNOSC

async def sk_platnosc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['sk_platnosc'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wpisz kwotę zaległości:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
    return SK_ZALEGLOSC

async def sk_zaleglosc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['sk_zaleglosc'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wpisz uwagi:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
    return SK_UWAGI

async def sk_uwagi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['sk_uwagi'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Czy posiada GPS?", reply_markup=keyboard([["BRAK GPS"], ["TAK"], ["BRAK"], ["❌ Anuluj"]]))
    return SK_GPS

async def sk_gps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['sk_gps'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wpisz GPS ID:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
    return SK_GPS_ID

async def sk_gps_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['sk_gps_id'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wpisz cenę za tydzień:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
    return SK_CENA

async def sk_cena(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['sk_cena'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wpisz aktualny przebieg:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
    return SK_PRZEBIEG

async def sk_przebieg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['sk_przebieg'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wpisz ostatni serwis:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
    return SK_SERWIS_OST

async def sk_serwis_ost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['sk_serwis_ost'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wpisz następny serwis при:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
    return SK_SERWIS_NAST

async def sk_serwis_nast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['sk_serwis_nast'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wpisz data raportu KM:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
    return SK_RAPORT

async def sk_raport(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['sk_raport'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wpisz ubezpieczenie do:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
    return SK_UBEZP

async def sk_ubezp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data['sk_ubezp'] = "BRAK" if txt.upper() == "BRAK" else txt
    await update.message.reply_text("Wpisz przegląd do:", reply_markup=keyboard([["BRAK"], ["❌ Anuluj"]]))
    return SK_PRZEGLAD

async def sk_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    przeglad_do = "BRAK" if txt.upper() == "BRAK" else txt
    sid = context.user_data['sk_id']
    marka = context.user_data['sk_marka']
    model = context.user_data['sk_model']
    rok = context.user_data['sk_rok']
    rej = context.user_data['sk_rej']
    vin = context.user_data['sk_vin']
    status = context.user_data['sk_status']
    najemca = context.user_data['sk_najemca']
    typ_platnosci = context.user_data['sk_typ']
    kaucja = context.user_data['sk_kaucja']
    data_start = context.user_data['sk_start']
    data_stop = context.user_data['sk_stop']
    termin_platnosci = context.user_data['sk_termin']
    ostatnia_platnosc = context.user_data['sk_platnosc']
    kwota_zaleglosci = context.user_data['sk_zaleglosc']
    uwagi = context.user_data['sk_uwagi']
    gps = context.user_data['sk_gps']
    gps_id = context.user_data['sk_gps_id']
    cena_tydz = context.user_data['sk_cena']
    aktualny_przebieg = context.user_data['sk_przebieg']
    ostatni_serwis = context.user_data['sk_serwis_ost']
    nastepny_serwis = context.user_data['sk_serwis_nast']
    data_raportu_km = context.user_data['sk_raport']
    ubezpieczenie_do = context.user_data['sk_ubezp']
    try:
        km_nast = float(nastepny_serwis)
        km_akt = float(aktualny_przebieg)
        pozostalo_km = str(km_nast - km_akt)
    except Exception:
        pozostalo_km = "BRAK"
    conn = await get_db()
    await conn.execute("""
        INSERT INTO scooters (id, marka, model, rok, rejestracja, vin, status, najemca, typ_platnosci, kaucja, data_start, data_stop, termin_platnosci, ostatnia_platnosc, kwota_zaleglosci, uwagi, gps, gps_id, cena_tydz, aktualny_przebieg, ostatni_serwis, nastepny_serwis, pozostalo_km, data_raportu_km, ubezpieczenie_do, przeglad_do)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26)
        ON CONFLICT (id) DO UPDATE SET marka=$2, model=$3, rok=$4, rejestracja=$5, vin=$6, status=$7, najemca=$8, typ_platnosci=$9, kaucja=$10, data_start=$11, data_stop=$12, termin_platnosci=$13, ostatnia_platnosc=$14, kwota_zaleglosci=$15, uwagi=$16, gps=$17, gps_id=$18, cena_tydz=$19, aktualny_przebieg=$20, ostatni_serwis=$21, nastepny_serwis=$22, pozostalo_km=$23, data_raportu_km=$24, ubezpieczenie_do=$25, przeglad_do=$26
    """, sid, marka, model, rok, rejestracja, vin, status, najemca, typ_platnosci, kaucja, data_start, data_stop, termin_platnosci, ostatnia_platnosc, kwota_zaleglosci, uwagi, gps, gps_id, cena_tydz, aktualny_przebieg, ostatni_serwis, nastepny_serwis, pozostalo_km, data_raportu_km, ubezpieczenie_do, przeglad_do)
    await conn.close()
    try:
        sheet = get_google_sheet()
        if sheet:
            worksheet = sheet.worksheet("SKUTERY")
            row = [sid, marka, model, rok, rejestracja, vin, status, najemca, typ_platnosci, kaucja, data_start, data_stop, termin_platnosci, ostatnia_platnosc, kwota_zaleglosci, uwagi, gps, gps_id, cena_tydz, aktualny_przebieg, ostatni_serwis, nastepny_serwis, pozostalo_km, data_raportu_km, ubezpieczenie_do, przeglad_do]
            worksheet.append_row(row)
    except Exception:
        pass
    await update.message.reply_text("Skuter zapisany pomyślnie!", reply_markup=keyboard(MAIN_MENU))
    context.user_data.clear()
    return ConversationHandler.END

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "💰 Finanse":
        await update.message.reply_text("Menu Finanse:", reply_markup=keyboard(FINANCE_MENU))
        return
    if text == "👤 Klienci":
        await update.message.reply_text("Menu Klienci:", reply_markup=keyboard(CLIENTS_MENU))
        return
    if text == "🏍 Skutery":
        await update.message.reply_text("Menu Skutery:", reply_markup=keyboard(SCOOTERS_MENU))
        return
    if text == "🛵 Rental":
        await update.message.reply_text("Menu Rental:", reply_markup=keyboard(RENTAL_MENU))
        return
    if text == "🔧 Serwis":
        await update.message.reply_text("Menu Serwis:", reply_markup=keyboard(SERVICE_MENU))
        return
    if text == "⬅️ Powrót":
        await update.message.reply_text("Menu główne:", reply_markup=keyboard(MAIN_MENU))
        return
    if text == "💼 Bilans":
        conn = await get_db()
        rows = await conn.fetch("SELECT typ, kwota FROM finance")
        await conn.close()
        inc, exp = 0.0, 0.0
        for r in rows:
            try:
                v = float(r['kwota'].replace("zł", "").strip())
                if "DOCH" in r['typ'].upper():
                    inc += v
                else:
                    exp += v
            except Exception:
                pass
        await update.message.reply_text(f"💼 Bilans:\nDochody: {inc:.2f}\nWydatki: {exp:.2f}\nRazem: {(inc-exp):.2f}")
        return
    if text == "📋 Lista klientów":
        conn = await get_db()
        rows = await conn.fetch("SELECT imie_nazwisko, telefon, pojazd FROM clients ORDER BY id DESC LIMIT 15")
        await conn.close()
        if not rows:
            await update.message.reply_text("Brak klientów w bazie.")
            return
        res = "📋 Ostatni klienci:\n"
        for r in rows:
            res += f"👤 {r['imie_nazwisko']} | 📞 {r['telefon']} | 🏍 {r['pojazd']}\n"
        await update.message.reply_text(res)
        return
    if text == "📋 Aktywne zlecenia":
        conn = await get_db()
        rows = await conn.fetch("SELECT id, klient_name, pojazd, razem, status FROM service_orders WHERE status='W TOKU' ORDER BY id DESC")
        await conn.close()
        if not rows:
            await update.message.reply_text("Brak aktywnych zleceń.")
            return
        res = "🔧 Aktywne zlecenia:\n"
        for r in rows:
            res += f"S-{r['id']:04d} | {r['klient_name']} | {r['pojazd']} | {r['razem']} zł | {r['status']}\n"
        await update.message.reply_text(res)
        return
    if text == "📋 Lista operacji":
        conn = await get_db()
        rows = await conn.fetch("SELECT id, skuter, klient, kwota, typ FROM rental ORDER BY id DESC LIMIT 15")
        await conn.close()
        if not rows:
            await update.message.reply_text("Brak operacji rental.")
            return
        res = "🛵 Ostatnie operacje Rental:\n"
        for r in rows:
            res += f"R-{r['id']:03d} | {r['skuter']} | {r['klient']} | {r['kwota']} zł | {r['typ']}\n"
        await update.message.reply_text(res)
        return
    if text == "📋 Lista skuterów":
        conn = await get_db()
        rows = await conn.fetch("SELECT id, marka, model, status, najemca FROM scooters")
        await conn.close()
        if not rows:
            await update.message.reply_text("Brak skuterów w bazie.")
            return
        res = "🏍 Lista skuterów:\n"
        for r in rows:
            res += f"#{r['id']} | {r['marka']} {r['model']} | {r['status']} | Najemca: {r['najemca']}\n"
        await update.message.reply_text(res)
        return
    await update.message.reply_text("Wybierz opcję z menu.", reply_markup=keyboard(MAIN_MENU))

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Witaj w systemie RedGear Moto!", reply_markup=keyboard(MAIN_MENU))

async def post_init(app):
    await init_db()

if __name__ == "__main__":
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    
    serwis_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Text("➕ Nowe zlecenie"), s_start)],
        states={
            S_KLIENT: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), s_klient)],
            S_WYBOR: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), s_wybor)],
            S_POJAZD: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), s_pojazd)],
            S_REJ: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), s_rej)],
            S_PRZEBIEG: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), s_przebieg)],
            S_USLUGA: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), s_usluga)],
            S_CZESCI: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), s_czesci)],
            S_ROBOCIZNA: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), s_robocizna)],
            S_FORMA: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), s_forma)],
            S_UWAGI: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), s_final)]
        },
        fallbacks=[MessageHandler(filters.Text("❌ Anuluj"), global_cancel)]
    )
    
    klient_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Text("➕ Nowy klient"), c_start)],
        states={
            C_NAME: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), c_name)],
            C_PHONE: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), c_phone)],
            C_TYP: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), c_typ)],
            C_STATUS: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), c_status)],
            C_MIASTO: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), c_miasto)],
            C_UWAGI: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), c_uwagi)],
            C_WIZYTA: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), c_wizyta)],
            C_ZAROBIONO: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), c_zarobiono)],
            C_POJAZD: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), c_final)]
        },
        fallbacks=[MessageHandler(filters.Text("❌ Anuluj"), global_cancel)]
    )
    
    finance_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Text("➕ Dodaj operację"), f_start)],
        states={
            F_KIERUNEK: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), f_kierunek)],
            F_TYP: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), f_typ)],
            F_KATEGORIA: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), f_kategoria)],
            F_INWESTYCJA: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), f_inwestycja)],
            F_OPIS: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), f_opis)],
            F_KWOTA: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), f_kwota)],
            F_FORMA: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), f_forma)],
            F_KLIENT: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), f_klient)],
            F_WYBOR: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), f_wybor)],
            F_DOKUMENT: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), f_dokument)],
            F_NOTATKA: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), f_final)]
        },
        fallbacks=[MessageHandler(filters.Text("❌ Anuluj"), global_cancel)]
    )
    
    rental_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Text("➕ Nowa operacja"), r_start)],
        states={
            R_SKUTER: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), r_skuter)],
            R_KLIENT: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), r_klient)],
            R_WYBOR: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), r_wybor)],
            R_TYP: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), r_typ)],
            R_OPERACJA: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), r_operacja)],
            R_KWOTA: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), r_kwota)],
            R_FORMA: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), r_forma)],
            R_UWAGI: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), r_final)]
        },
        fallbacks=[MessageHandler(filters.Text("❌ Anuluj"), global_cancel)]
    )
    
    scooters_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Text("➕ Dodaj skuter"), sk_start)],
        states={
            SK_ID: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), sk_id)],
            SK_MARKA: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), sk_marka)],
            SK_MODEL: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), sk_model)],
            SK_ROK: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), sk_rok)],
            SK_REJ: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), sk_rej)],
            SK_VIN: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), sk_vin)],
            SK_STATUS: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), sk_status)],
            SK_NAJEMCA: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), sk_najemca)],
            SK_WYBOR: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), sk_wybor)],
            SK_TYP: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), sk_typ)],
            SK_KAUCJA: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), sk_kaucja)],
            SK_START: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), sk_start_dt)],
            SK_STOP: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), sk_stop_dt)],
            SK_TERMIN: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), sk_termin)],
            SK_PLATNOSC: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), sk_platnosc)],
            SK_ZALEGLOSC: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), sk_zaleglosc)],
            SK_UWAGI: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), sk_uwagi)],
            SK_GPS: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), sk_gps)],
            SK_GPS_ID: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), sk_gps_id)],
            SK_CENA: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), sk_cena)],
            SK_PRZEBIEG: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), sk_przebieg)],
            SK_SERWIS_OST: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), sk_serwis_ost)],
            SK_SERWIS_NAST: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), sk_serwis_nast)],
            SK_RAPORT: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), sk_raport)],
            SK_UBEZP: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), sk_ubezp)],
            SK_PRZEGLAD: [MessageHandler(filters.TEXT & ~filters.Text("❌ Anuluj"), sk_final)]
        },
        fallbacks=[MessageHandler(filters.Text("❌ Anuluj"), global_cancel)]
    )

    app.add_handler(serwis_conv)
    app.add_handler(klient_conv)
    app.add_handler(finance_conv)
    app.add_handler(rental_conv)
    app.add_handler(scooters_conv)
    
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, callback=handle_message))
    
    app.run_polling()
