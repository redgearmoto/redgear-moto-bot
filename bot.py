import os
import json
import asyncpg
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

MAIN_MENU = [
    ["💰 Finanse", "🛵 Rental"],
    ["🔧 Serwis", "📦 Magazyn"],
    ["👤 Klienci", "🏍 Skutery"],
    ["📊 Raport", "🤖 AI wpis"],
]

FINANCE_MENU = [
    ["➕ Dochód", "➖ Wydatek"],
    ["💼 Bilans", "⬅️ Powrót"],
]

CLIENTS_MENU = [
    ["➕ Nowy klient", "📋 Lista klientów"],
    ["⬅️ Powrót"],
]

SERVICE_MENU = [
    ["➕ Nowe zlecenie", "📋 Aktywne zlecenia"],
    ["✅ Zamknij zlecenie", "⬅️ Powrót"],
]

STOCK_MENU = [
    ["➕ Przyjęcie towaru", "➖ Wydanie towaru"],
    ["📦 Stan magazynu", "⬅️ Powrót"],
]

SCOOTERS_MENU = [
    ["➕ Dodaj skuter", "📋 Lista skuterów"],
    ["🔁 Zmień status", "⬅️ Powrót"],
]

RENTAL_MENU = [
    ["➕ Opłata rental", "➖ Koszt skutera"],
    ["📋 Płatności rental", "⬅️ Powrót"],
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
        kierunek TEXT,
        typ TEXT NOT NULL,
        kategoria TEXT,
        kwota NUMERIC(10,2) NOT NULL,
        opis TEXT,
        forma_platnosci TEXT
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
        status TEXT DEFAULT 'WOLNY',
        przebieg INTEGER DEFAULT 0,
        uwagi TEXT
    );
    """)

    await conn.execute("""
    CREATE TABLE IF NOT EXISTS service_orders (
        id SERIAL PRIMARY KEY,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        klient TEXT,
        pojazd TEXT,
        rejestracja TEXT,
        przebieg INTEGER DEFAULT 0,
        usluga TEXT,
        czesci NUMERIC(10,2) DEFAULT 0,
        robocizna NUMERIC(10,2) DEFAULT 0,
        razem NUMERIC(10,2) DEFAULT 0,
        status TEXT DEFAULT 'OTWARTE',
        forma_platnosci TEXT,
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

    await conn.close()


async def add_finance(kierunek, typ, kategoria, kwota, opis, forma):
    conn = await get_db()
    await conn.execute("""
        INSERT INTO finance (created_at, kierunek, typ, kategoria, kwota, opis, forma_platnosci)
        VALUES ($1,$2,$3,$4,$5,$6,$7)
    """, datetime.now(), kierunek, typ, kategoria, kwota, opis, forma)
    await conn.close()


async def get_balance():
    conn = await get_db()
    income = await conn.fetchval("SELECT COALESCE(SUM(kwota),0) FROM finance WHERE typ='DOCHOD'")
    expense = await conn.fetchval("SELECT COALESCE(SUM(kwota),0) FROM finance WHERE typ='WYDATEK'")
    await conn.close()
    return income, expense, income - expense


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "RedGear Assistant 🏍️\n\nWybierz dział:",
        reply_markup=keyboard(MAIN_MENU),
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if text == "💰 Finanse":
        context.user_data.clear()
        await update.message.reply_text("Finanse:", reply_markup=keyboard(FINANCE_MENU))
        return

    if text == "👤 Klienci":
        context.user_data.clear()
        await update.message.reply_text("Klienci:", reply_markup=keyboard(CLIENTS_MENU))
        return

    if text == "🔧 Serwis":
        context.user_data.clear()
        await update.message.reply_text("Serwis:", reply_markup=keyboard(SERVICE_MENU))
        return

    if text == "📦 Magazyn":
        context.user_data.clear()
        await update.message.reply_text("Magazyn:", reply_markup=keyboard(STOCK_MENU))
        return

    if text == "🏍 Skutery":
        context.user_data.clear()
        await update.message.reply_text("Skutery:", reply_markup=keyboard(SCOOTERS_MENU))
        return

    if text == "🛵 Rental":
        context.user_data.clear()
        await update.message.reply_text("Rental:", reply_markup=keyboard(RENTAL_MENU))
        return

    if text == "⬅️ Powrót":
        context.user_data.clear()
        await update.message.reply_text("Menu główne:", reply_markup=keyboard(MAIN_MENU))
        return

    if text == "➕ Dochód":
        context.user_data["mode"] = "income"
        await update.message.reply_text("Wpisz dochód:\n\n1500; SERWIS; NAPRAWA; gotówka; wymiana oleju Yamaha TDM900")
        return

    if text == "➖ Wydatek":
        context.user_data["mode"] = "expense"
        await update.message.reply_text("Wpisz wydatek:\n\n250; SERWIS; CZESCI; karta; olej Motul")
        return

    if text == "💼 Bilans":
        income, expense, balance = await get_balance()
        await update.message.reply_text(
            f"💼 Bilans RedGear Moto\n\n"
            f"Dochody: {income:.2f} zł\n"
            f"Wydatki: {expense:.2f} zł\n"
            f"Bilans: {balance:.2f} zł"
        )
        return

    if text == "➕ Nowy klient":
        context.user_data["mode"] = "new_client"
        await update.message.reply_text(
            "Wpisz klienta:\n\n"
            "Imię; Telefon; Typ; Status; Miasto; Pojazd; Rejestracja; VIN; Przebieg; Uwagi\n\n"
            "Przykład:\n"
            "Ivan;735066501;SERWIS;AKTYWNY;Wrocław;Yamaha TDM900;DW12345;JYARN181000123456;72000;wymiana oleju"
        )
        return

    if text == "📋 Lista klientów":
        conn = await get_db()
        rows = await conn.fetch("""
            SELECT imie_nazwisko, telefon, typ, status, miasto, pojazd, rejestracja, przebieg
            FROM clients
            ORDER BY id DESC
            LIMIT 20
        """)
        await conn.close()

        if not rows:
            await update.message.reply_text("Brak klientów.")
            return

        msg = "📋 Klienci\n\n"
        for r in rows:
            msg += (
                f"👤 {r['imie_nazwisko']}\n"
                f"📞 {r['telefon']}\n"
                f"📌 {r['typ']} / {r['status']}\n"
                f"🏙 {r['miasto']}\n"
                f"🏍 {r['pojazd']}\n"
                f"🔢 {r['rejestracja']}\n"
                f"📍 {r['przebieg']} km\n\n"
            )
        await update.message.reply_text(msg)
        return

    if text == "➕ Dodaj skuter":
        context.user_data["mode"] = "new_scooter"
        await update.message.reply_text("Wpisz skuter:\n\nPCX-01; DW12345; WOLNY; 12500; uwagi")
        return

    if text == "📋 Lista skuterów":
        conn = await get_db()
        rows = await conn.fetch("SELECT nazwa, rejestracja, status, przebieg, uwagi FROM scooters ORDER BY id")
        await conn.close()

        if not rows:
            await update.message.reply_text("Brak skuterów.")
            return

        msg = "🏍 Skutery\n\n"
        for r in rows:
            msg += f"{r['nazwa']} | {r['status']} | {r['rejestracja']} | {r['przebieg']} km\n"
        await update.message.reply_text(msg)
        return

    if text == "➕ Nowe zlecenie":
        context.user_data["mode"] = "new_service"
        await update.message.reply_text(
            "Wpisz zlecenie:\n\n"
            "Klient; Pojazd; Rejestracja; Przebieg; Usługa; Części; Robocizna; Forma płatności; Uwagi\n\n"
            "Przykład:\n"
            "Ivan;Yamaha TDM900;DW12345;72000;wymiana oleju;100;150;gotówka;Motul 10W40"
        )
        return

    if text == "📋 Aktywne zlecenia":
        conn = await get_db()
        rows = await conn.fetch("""
            SELECT id, klient, pojazd, rejestracja, usluga, razem, status
            FROM service_orders
            WHERE status='OTWARTE'
            ORDER BY id DESC
            LIMIT 20
        """)
        await conn.close()

        if not rows:
            await update.message.reply_text("Brak aktywnych zleceń.")
            return

        msg = "🔧 Aktywne zlecenia\n\n"
        for r in rows:
            msg += f"#{r['id']} | {r['klient']} | {r['pojazd']} | {r['usluga']} | {r['razem']} zł\n"
        await update.message.reply_text(msg)
        return

    if text == "➕ Przyjęcie towaru":
        context.user_data["mode"] = "stock_in"
        await update.message.reply_text("Wpisz przyjęcie:\n\nOlej Motul 10W40; 5; 250; dostawa")
        return

    if text == "➖ Wydanie towaru":
        context.user_data["mode"] = "stock_out"
        await update.message.reply_text("Wpisz wydanie:\n\nOlej Motul 10W40; 1; 50; do serwisu TDM900")
        return

    if text == "📦 Stan magazynu":
        conn = await get_db()
        rows = await conn.fetch("""
            SELECT nazwa,
            SUM(CASE WHEN typ_operacji='PRZYJECIE' THEN ilosc ELSE -ilosc END) AS stan
            FROM inventory
            GROUP BY nazwa
            ORDER BY nazwa
        """)
        await conn.close()

        if not rows:
            await update.message.reply_text("Magazyn pusty.")
            return

        msg = "📦 Stan magazynu\n\n"
        for r in rows:
            msg += f"{r['nazwa']}: {r['stan']} szt.\n"
        await update.message.reply_text(msg)
        return

    if text == "➕ Opłata rental":
        context.user_data["mode"] = "rental_income"
        await update.message.reply_text("Wpisz opłatę:\n\nPCX-02; Andrzej; 320; gotówka; opłata tygodniowa")
        return

    if text == "➖ Koszt skutera":
        context.user_data["mode"] = "rental_expense"
        await update.message.reply_text("Wpisz koszt:\n\nPCX-02; RedGear; 100; karta; GPS lokalizator")
        return

    if text == "📋 Płatności rental":
        conn = await get_db()
        rows = await conn.fetch("""
            SELECT skuter, klient, typ, kwota, forma_platnosci, uwagi
            FROM rental
            ORDER BY id DESC
            LIMIT 20
        """)
        await conn.close()

        if not rows:
            await update.message.reply_text("Brak płatności rental.")
            return

        msg = "🛵 Rental płatności\n\n"
        for r in rows:
            msg += f"{r['typ']} | {r['skuter']} | {r['klient']} | {r['kwota']} zł | {r['uwagi']}\n"
        await update.message.reply_text(msg)
        return

    if text == "📊 Raport":
        income, expense, balance = await get_balance()
        await update.message.reply_text(
            f"📊 Raport RedGear Moto\n\n"
            f"Dochody: {income:.2f} zł\n"
            f"Wydatki: {expense:.2f} zł\n"
            f"Netto: {balance:.2f} zł"
        )
        return

    mode = context.user_data.get("mode")

    if mode in ["income", "expense"]:
        try:
            kwota, kierunek, kategoria, forma, opis = [x.strip() for x in text.split(";", 4)]
            typ = "DOCHOD" if mode == "income" else "WYDATEK"
            await add_finance(kierunek, typ, kategoria, float(kwota.replace(",", ".")), opis, forma)

            await update.message.reply_text(
                f"✅ Zapisano\n\n{typ}\n{kwota} zł\n{kierunek} / {kategoria}\n{opis}",
                reply_markup=keyboard(FINANCE_MENU),
            )
            context.user_data.clear()
        except Exception as e:
            await update.message.reply_text(f"❌ Błąd:\n{e}")
        return

    if mode == "new_client":
        try:
            p = [x.strip() for x in text.split(";")]
            if len(p) != 10:
                raise ValueError("Musi być 10 pól oddzielonych średnikiem.")

            conn = await get_db()
            await conn.execute("""
                INSERT INTO clients
                (imie_nazwisko, telefon, typ, status, miasto, pojazd, rejestracja, vin, przebieg, uwagi)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            """, p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7], int(p[8]), p[9])
            await conn.close()

            await update.message.reply_text(f"✅ Klient dodany\n\n{p[0]}\n{p[5]}\n{p[6]}", reply_markup=keyboard(CLIENTS_MENU))
            context.user_data.clear()
        except Exception as e:
            await update.message.reply_text(f"❌ Błąd:\n{e}")
        return

    if mode == "new_scooter":
        try:
            nazwa, rej, status, przebieg, uwagi = [x.strip() for x in text.split(";")]
            conn = await get_db()
            await conn.execute("""
                INSERT INTO scooters (nazwa, rejestracja, status, przebieg, uwagi)
                VALUES ($1,$2,$3,$4,$5)
            """, nazwa, rej, status, int(przebieg), uwagi)
            await conn.close()

            await update.message.reply_text(f"✅ Skuter dodany\n\n{nazwa}\n{rej}\n{status}", reply_markup=keyboard(SCOOTERS_MENU))
            context.user_data.clear()
        except Exception as e:
            await update.message.reply_text(f"❌ Błąd:\n{e}")
        return

    if mode == "new_service":
        try:
            klient, pojazd, rej, przebieg, usluga, czesci, robocizna, forma, uwagi = [x.strip() for x in text.split(";")]
            czesci_f = float(czesci.replace(",", "."))
            robocizna_f = float(robocizna.replace(",", "."))
            razem = czesci_f + robocizna_f

            conn = await get_db()
            await conn.execute("""
                INSERT INTO service_orders
                (klient, pojazd, rejestracja, przebieg, usluga, czesci, robocizna, razem, forma_platnosci, uwagi)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            """, klient, pojazd, rej, int(przebieg), usluga, czesci_f, robocizna_f, razem, forma, uwagi)
            await conn.close()

            await add_finance("SERWIS", "DOCHOD", "NAPRAWA", razem, f"{klient} | {pojazd} | {usluga}", forma)

            await update.message.reply_text(f"✅ Zlecenie dodane\n\n{klient}\n{pojazd}\nRazem: {razem:.2f} zł", reply_markup=keyboard(SERVICE_MENU))
            context.user_data.clear()
        except Exception as e:
            await update.message.reply_text(f"❌ Błąd:\n{e}")
        return

    if mode in ["stock_in", "stock_out"]:
        try:
            nazwa, ilosc, cena, uwagi = [x.strip() for x in text.split(";")]
            typ_operacji = "PRZYJECIE" if mode == "stock_in" else "WYDANIE"

            conn = await get_db()
            await conn.execute("""
                INSERT INTO inventory (nazwa, ilosc, cena, typ_operacji, uwagi)
                VALUES ($1,$2,$3,$4,$5)
            """, nazwa, int(ilosc), float(cena.replace(",", ".")), typ_operacji, uwagi)
            await conn.close()

            if mode == "stock_in":
                await add_finance("SKLEP", "WYDATEK", "CZESCI", float(cena.replace(",", ".")), f"Zakup: {nazwa} x{ilosc}", "brak")

            await update.message.reply_text(f"✅ Magazyn zapisany\n\n{typ_operacji}\n{nazwa} x{ilosc}", reply_markup=keyboard(STOCK_MENU))
            context.user_data.clear()
        except Exception as e:
            await update.message.reply_text(f"❌ Błąd:\n{e}")
        return

    if mode in ["rental_income", "rental_expense"]:
        try:
            skuter, klient, kwota, forma, uwagi = [x.strip() for x in text.split(";")]
            typ = "DOCHOD" if mode == "rental_income" else "WYDATEK"

            conn = await get_db()
            await conn.execute("""
                INSERT INTO rental (skuter, klient, typ, kwota, forma_platnosci, uwagi)
                VALUES ($1,$2,$3,$4,$5,$6)
            """, skuter, klient, typ, float(kwota.replace(",", ".")), forma, uwagi)
            await conn.close()

            await add_finance("RENTAL", typ, "OPLATA" if typ == "DOCHOD" else "KOSZT", float(kwota.replace(",", ".")), f"{skuter} | {klient} | {uwagi}", forma)

            await update.message.reply_text(f"✅ Rental zapisany\n\n{typ}\n{skuter}\n{kwota} zł", reply_markup=keyboard(RENTAL_MENU))
            context.user_data.clear()
        except Exception as e:
            await update.message.reply_text(f"❌ Błąd:\n{e}")
        return

    await update.message.reply_text("Nie rozumiem. Wybierz przycisk z menu.", reply_markup=keyboard(MAIN_MENU))


async def post_init(app):
    await init_db()


app = Application.builder().token(TOKEN).post_init(post_init).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.run_polling()
