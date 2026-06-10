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

COMPANY_NAME = os.getenv("COMPANY_NAME", "RedGear Moto")
COMPANY_NIP = os.getenv("COMPANY_NIP", "8961641170")
COMPANY_PHONE = os.getenv("COMPANY_PHONE", "881198440")
COMPANY_INSTAGRAM = os.getenv("COMPANY_INSTAGRAM", "@redgearmoto")
COMPANY_ADDRESS = os.getenv("COMPANY_ADDRESS", "Przyjaźni 4, Wrocław")
COMPANY_CITY = os.getenv("COMPANY_CITY", "Wrocław")

LOGO_PATH = "logo.png"


MAIN_MENU = [
    ["💰 Finanse", "🛵 Rental"],
    ["🔧 Serwis", "📦 Magazyn"],
    ["👤 Klienci", "🏍 Skutery"],
    ["📊 Raport", "🤖 AI wpis"],
    ["🤖 AI Mechanik", "🤖 AI wpis"],
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


async def get_db():
    if not DATABASE_URL:
        raise RuntimeError("Brak DATABASE_URL w Railway Variables.")
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
    await conn.execute("""
        INSERT INTO finance
        (created_at, kierunek, type, kategoria, amount, description, forma_platnosci)
        VALUES ($1,$2,$3,$4,$5,$6,$7)
    """, datetime.now(), kierunek, typ, kategoria, kwota, opis, forma)
    await conn.close()


async def get_balance():
    conn = await get_db()

    income = await conn.fetchval("""
        SELECT COALESCE(SUM(amount),0)
        FROM finance
        WHERE type IN ('DOCHOD', 'income')
    """)

    expense = await conn.fetchval("""
        SELECT COALESCE(SUM(amount),0)
        FROM finance
        WHERE type IN ('WYDATEK', 'expense')
    """)

    await conn.close()
    return income, expense, income - expense


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        f"{COMPANY_NAME} Assistant 🏍️\n\nWybierz dział:",
        reply_markup=keyboard(MAIN_MENU),
    )


async def ask_ai_mechanic(question):
    if not OPENAI_API_KEY or OpenAI is None:
        return "AI nie jest skonfigurowane."

    client = OpenAI(api_key=OPENAI_API_KEY)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "Jesteś AI mechanikiem motocyklowym dla RedGear Moto. "
                    "Odpowiadaj po polsku, konkretnie i technicznie. "
                    "Podawaj możliwe przyczyny, kolejność diagnostyki, narzędzia i ryzyka. "
                    "Nie zgaduj numerów części, jeśli nie masz pewności."
                )
            },
            {"role": "user", "content": question}
        ],
        temperature=0.2,
    )

    return response.choices[0].message.content


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

    if text == "🏍 Skutery":
        context.user_data.clear()
        await update.message.reply_text("Skutery:", reply_markup=keyboard(SCOOTERS_MENU))
        return

    if text == "🛵 Rental":
        context.user_data.clear()
        await update.message.reply_text("Rental:", reply_markup=keyboard(RENTAL_MENU))
        return

    if text == "🔧 Serwis":
        context.user_data.clear()
        await update.message.reply_text("Serwis:", reply_markup=keyboard(SERVICE_MENU))
        return

    if text == "📦 Magazyn":
        context.user_data.clear()
        await update.message.reply_text("Magazyn:", reply_markup=keyboard(STOCK_MENU))
        return

    if text == "⬅️ Powrót":
        context.user_data.clear()
        await update.message.reply_text("Menu główne:", reply_markup=keyboard(MAIN_MENU))
        return

    if text == "➕ Dochód":
        context.user_data["mode"] = "income"
        await update.message.reply_text(
            "Wpisz dochód:\n\n"
            "Kwota; Kierunek; Kategoria; Forma płatności; Opis\n\n"
            "Przykład:\n"
            "1500; SERWIS; NAPRAWA; GOTOWKA; wymiana oleju Yamaha TDM900"
        )
        return

    if text == "➖ Wydatek":
        context.user_data["mode"] = "expense"
        await update.message.reply_text(
            "Wpisz wydatek:\n\n"
            "Kwota; Kierunek; Kategoria; Forma płatności; Opis\n\n"
            "Przykład:\n"
            "250; SERWIS; CZESCI; KARTA; olej Motul"
        )
        return

    if text == "💼 Bilans":
        income, expense, balance = await get_balance()
        await update.message.reply_text(
            f"💼 Bilans {COMPANY_NAME}\n\n"
            f"Dochody: {income:.2f} zł\n"
            f"Wydatki: {expense:.2f} zł\n"
            f"Bilans: {balance:.2f} zł"
        )
        return

    if text == "📊 Raport finansowy":
        conn = await get_db()
        rows = await conn.fetch("""
            SELECT kierunek, typ, COALESCE(SUM(kwota),0) AS suma
            FROM finance
            GROUP BY kierunek, typ
            ORDER BY kierunek, typ
        """)
        await conn.close()

        if not rows:
            await update.message.reply_text("Brak danych finansowych.")
            return

        msg = "📊 Raport finansowy\n\n"
        for r in rows:
            msg += f"{r['kierunek']} | {r['typ']}: {r['suma']:.2f} zł\n"
        await update.message.reply_text(msg)
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
            LIMIT 30
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
    if text == "🔍 Szukaj klienta":
        context.user_data["mode"] = "search_client"
        await update.message.reply_text(
            "Wpisz imię, telefon albo numer rejestracyjny klienta:"
        )
        return

    if text == "➕ Dodaj skuter":
        context.user_data["mode"] = "new_scooter"
        await update.message.reply_text(
            "Wpisz skuter:\n\n"
            "Nazwa; Rejestracja; VIN; Status; Najemca; Przebieg; Ostatni serwis; Następny serwis; GPS; Uwagi\n\n"
            "Przykład:\n"
            "PCX-01; DW12345; MLHJK05...; W NAJMIE; Andrzej; 76500; 75000; 79000; GPS-01; aktywny"
        )
        return

    if text == "📋 Lista skuterów":
        conn = await get_db()
        rows = await conn.fetch("""
            SELECT nazwa, rejestracja, status, najemca, przebieg, nastepny_serwis, gps
            FROM scooters
            ORDER BY id
        """)
        await conn.close()

        if not rows:
            await update.message.reply_text("Brak skuterów.")
            return

        msg = "🏍 Skutery\n\n"
        for r in rows:
            left = None
            if r["nastepny_serwis"] and r["przebieg"]:
                left = int(r["nastepny_serwis"]) - int(r["przebieg"])

            msg += (
                f"{r['nazwa']} | {r['status']}\n"
                f"🔢 {r['rejestracja']}\n"
                f"👤 {r['najemca']}\n"
                f"📍 {r['przebieg']} km\n"
                f"🛰 {r['gps']}\n"
            )

            if left is not None:
                msg += f"🛠 Serwis za: {left} km\n"

            msg += "\n"

        await update.message.reply_text(msg)
        return

    if text == "📍 Aktualizuj przebieg" or text == "📍 Przebieg skutera":
        context.user_data["mode"] = "update_scooter_mileage"
        await update.message.reply_text(
            "Wpisz:\n\n"
            "Skuter; Przebieg\n\n"
            "Przykład:\n"
            "PCX-02; 77500"
        )
        return

    if text == "🔁 Zmień status":
        context.user_data["mode"] = "change_scooter_status"
        await update.message.reply_text(
            "Wpisz:\n\n"
            "Skuter; Status; Najemca; Uwagi\n\n"
            "Przykład:\n"
            "PCX-02; W NAJMIE; Andrzej; opłacony tydzień"
        )
        return

    if text == "➕ Opłata rental":
        context.user_data["mode"] = "rental_income"
        await update.message.reply_text(
            "Wpisz opłatę:\n\n"
            "Skuter; Klient; Kwota; Forma płatności; Uwagi\n\n"
            "Przykład:\n"
            "PCX-02; Andrzej; 320; GOTOWKA; opłata tygodniowa"
        )
        return

    if text == "➖ Koszt skutera":
        context.user_data["mode"] = "rental_expense"
        await update.message.reply_text(
            "Wpisz koszt:\n\n"
            "Skuter; Klient; Kwota; Forma płatności; Uwagi\n\n"
            "Przykład:\n"
            "PCX-02; RedGear; 100; KARTA; GPS lokalizator"
        )
        return

    if text == "📋 Płatności rental":
        conn = await get_db()
        rows = await conn.fetch("""
            SELECT created_at, skuter, klient, typ, kwota, forma_platnosci, uwagi
            FROM rental
            ORDER BY id DESC
            LIMIT 25
        """)
        await conn.close()

        if not rows:
            await update.message.reply_text("Brak płatności rental.")
            return

        msg = "🛵 Rental płatności\n\n"
        for r in rows:
            msg += (
                f"{r['created_at'].strftime('%d.%m.%Y')} | {r['typ']}\n"
                f"{r['skuter']} | {r['klient']} | {r['kwota']:.2f} zł\n"
                f"{r['uwagi']}\n\n"
            )

        await update.message.reply_text(msg)
        return

    if text == "📊 Raport rental":
        conn = await get_db()
        income = await conn.fetchval("""
            SELECT COALESCE(SUM(kwota),0)
            FROM rental
            WHERE typ='DOCHOD'
        """)
        expense = await conn.fetchval("""
            SELECT COALESCE(SUM(kwota),0)
            FROM rental
            WHERE typ='WYDATEK'
        """)
        rows = await conn.fetch("""
            SELECT skuter,
                   COALESCE(SUM(CASE WHEN typ='DOCHOD' THEN kwota ELSE -kwota END),0) AS wynik
            FROM rental
            GROUP BY skuter
            ORDER BY skuter
        """)
        await conn.close()

        msg = (
            f"📊 Raport rental\n\n"
            f"Dochód: {income:.2f} zł\n"
            f"Koszty: {expense:.2f} zł\n"
            f"Netto: {income - expense:.2f} zł\n\n"
            f"Wynik po skuterach:\n"
        )

        for r in rows:
            msg += f"{r['skuter']}: {r['wynik']:.2f} zł\n"

        await update.message.reply_text(msg)
        return

    if text == "➕ Nowe zlecenie":
        context.user_data["mode"] = "new_service"
        await update.message.reply_text(
            "Wpisz zlecenie:\n\n"
            "Klient; Telefon; Pojazd; Rejestracja; VIN; Przebieg; Usługa; Części; Robocizna; Forma płatności; Rekomendacje; Uwagi\n\n"
            "Przykład:\n"
            "Ivan;735066501;Yamaha TDM900;DW12345;JYARN181...;72000;wymiana oleju;100;150;GOTOWKA;kontrola hamulców za 1000 km;Motul 10W40"
        )
        return

    if text == "📋 Aktywne zlecenia":
        conn = await get_db()
        rows = await conn.fetch("""
            SELECT id, klient, pojazd, rejestracja, usluga, razem, status
            FROM service_orders
            WHERE status='OTWARTE'
            ORDER BY id DESC
            LIMIT 30
        """)
        await conn.close()

        if not rows:
            await update.message.reply_text("Brak aktywnych zleceń.")
            return

        msg = "🔧 Aktywne zlecenia\n\n"
        for r in rows:
            msg += (
                f"#{r['id']} | {r['klient']}\n"
                f"{r['pojazd']} | {r['rejestracja']}\n"
                f"{r['usluga']}\n"
                f"{r['razem']:.2f} zł | {r['status']}\n\n"
            )

        await update.message.reply_text(msg)
        return

    if text == "✅ Zamknij zlecenie":
        context.user_data["mode"] = "close_service"
        await update.message.reply_text(
            "Wpisz ID zlecenia do zamknięcia:\n\n"
            "Przykład:\n"
            "12"
        )
        return

    if text == "🔍 Historia pojazdu":
        context.user_data["mode"] = "vehicle_history"
        await update.message.reply_text(
            "Wpisz numer rejestracyjny albo VIN:\n\n"
            "Przykład:\n"
            "DW12345"
        )
        return

    if text == "📄 PDF dla klienta":
        context.user_data["mode"] = "pdf_client"
        await update.message.reply_text(
            "Wpisz ID zlecenia do PDF:\n\n"
            "Przykład:\n"
            "12"
        )
        return

    if text == "➕ Przyjęcie towaru":
        context.user_data["mode"] = "stock_in"
        await update.message.reply_text(
            "Wpisz przyjęcie:\n\n"
            "Nazwa; Ilość; Wartość; Uwagi\n\n"
            "Przykład:\n"
            "Olej Motul 10W40; 5; 250; dostawa"
        )
        return

    if text == "➖ Wydanie towaru":
        context.user_data["mode"] = "stock_out"
        await update.message.reply_text(
            "Wpisz wydanie:\n\n"
            "Nazwa; Ilość; Wartość; Uwagi\n\n"
            "Przykład:\n"
            "Olej Motul 10W40; 1; 50; do serwisu TDM900"
        )
        return

    if text == "📦 Stan magazynu":
        conn = await get_db()
        rows = await conn.fetch("""
            SELECT nazwa,
            SUM(CASE WHEN typ_operacji='PRZYJECIE' THEN ilosc ELSE -ilosc END) AS stan,
            SUM(CASE WHEN typ_operacji='PRZYJECIE' THEN cena ELSE -cena END) AS wartosc
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
            msg += f"{r['nazwa']}: {r['stan']} szt. | {r['wartosc']:.2f} zł\n"

        await update.message.reply_text(msg)
        return

    if text == "🔍 Szukaj części":
        context.user_data["mode"] = "search_part"
        await update.message.reply_text("Wpisz nazwę części albo fragment nazwy:")
        return

    if text == "📊 Raport":
        income, expense, balance = await get_balance()

        conn = await get_db()
        active_scooters = await conn.fetchval("""
            SELECT COUNT(*) FROM scooters WHERE status ILIKE '%NAJMIE%'
        """)
        open_orders = await conn.fetchval("""
            SELECT COUNT(*) FROM service_orders WHERE status='OTWARTE'
        """)
        clients_count = await conn.fetchval("""
            SELECT COUNT(*) FROM clients
        """)
        await conn.close()

        await update.message.reply_text(
            f"📊 Raport {COMPANY_NAME}\n\n"
            f"Finanse netto: {balance:.2f} zł\n"
            f"Dochody: {income:.2f} zł\n"
            f"Wydatki: {expense:.2f} zł\n\n"
            f"Aktywne skutery: {active_scooters}\n"
            f"Otwarte zlecenia: {open_orders}\n"
            f"Klienci w bazie: {clients_count}"
        )
        return

    if text == "🤖 AI Mechanik":
        context.user_data["mode"] = "ai_mechanic"
        await update.message.reply_text(
            "Opisz problem motocykla:\n\n"
            "Przykład:\n"
            "Honda Transalp 700 ciężko odpala na zimnym silniku."
        )
        return
        
    if text == "🤖 AI wpis":
        context.user_data["mode"] = "ai_entry"
        await update.message.reply_text(
            "Wpisz naturalnie, co się stało.\n\n"
            "Przykłady:\n"
            "Otrzymałem 320 zł gotówką za PCX-02 od Andrzeja\n"
            "Kupiłem olej Motul za 250 zł kartą\n"
            "Zrobiłem serwis Yamaha TDM900 za 450 zł"
        )
        return
        
        
    mode = context.user_data.get("mode")

    if mode in ["income", "expense"]:
        try:
            kwota, kierunek, kategoria, forma, opis = [x.strip() for x in text.split(";", 4)]
            typ = "DOCHOD" if mode == "income" else "WYDATEK"

            await add_finance(
                kierunek.upper(),
                typ,
                kategoria.upper(),
                float(kwota.replace(",", ".")),
                opis,
                forma.upper(),
            )

            await update.message.reply_text(
                f"✅ Zapisano\n\n{typ}\n{kwota} zł\n{kierunek} / {kategoria}\n{opis}",
                reply_markup=keyboard(FINANCE_MENU),
            )
            context.user_data.clear()

        except Exception as e:
            await update.message.reply_text(f"❌ Błąd:\n{e}")

        return

    if mode == "ai_mechanic":
        answer = await ask_ai_mechanic(text)
        await update.message.reply_text(answer, reply_markup=keyboard(MAIN_MENU))
        context.user_data.clear()
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
            """, p[0], p[1], p[2].upper(), p[3].upper(), p[4], p[5], p[6], p[7], int(p[8]), p[9])
            await conn.close()

            await update.message.reply_text(
                f"✅ Klient dodany\n\n{p[0]}\n{p[5]}\n{p[6]}",
                reply_markup=keyboard(CLIENTS_MENU),
            )
            context.user_data.clear()

        except Exception as e:
            await update.message.reply_text(f"❌ Błąd:\n{e}")

        return

    if mode == "search_client":
        query = f"%{text}%"
        conn = await get_db()
        rows = await conn.fetch("""
            SELECT imie_nazwisko, telefon, pojazd, rejestracja, vin, przebieg, uwagi
            FROM clients
            WHERE imie_nazwisko ILIKE $1
               OR telefon ILIKE $1
               OR rejestracja ILIKE $1
               OR vin ILIKE $1
            ORDER BY id DESC
            LIMIT 10
        """, query)
        await conn.close()

        if not rows:
            await update.message.reply_text("Nie znaleziono klienta.")
            return

        msg = "🔍 Wyniki\n\n"
        for r in rows:
            msg += (
                f"👤 {r['imie_nazwisko']}\n"
                f"📞 {r['telefon']}\n"
                f"🏍 {r['pojazd']}\n"
                f"🔢 {r['rejestracja']}\n"
                f"VIN: {r['vin']}\n"
                f"📍 {r['przebieg']} km\n"
                f"📝 {r['uwagi']}\n\n"
            )

        await update.message.reply_text(msg)
        context.user_data.clear()
        return

    if mode == "new_scooter":
        try:
            p = [x.strip() for x in text.split(";")]
            if len(p) != 10:
                raise ValueError("Musi być 10 pól.")

            conn = await get_db()
            await conn.execute("""
                INSERT INTO scooters
                (nazwa, rejestracja, vin, status, najemca, przebieg, ostatni_serwis, nastepny_serwis, gps, uwagi)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            """, p[0], p[1], p[2], p[3].upper(), p[4], int(p[5]), int(p[6]), int(p[7]), p[8], p[9])
            await conn.close()

            await update.message.reply_text(
                f"✅ Skuter dodany\n\n{p[0]}\n{p[1]}\n{p[3]}",
                reply_markup=keyboard(SCOOTERS_MENU),
            )
            context.user_data.clear()

        except Exception as e:
            await update.message.reply_text(f"❌ Błąd:\n{e}")

        return

    if mode == "update_scooter_mileage":
        try:
            skuter, przebieg = [x.strip() for x in text.split(";")]

            conn = await get_db()
            await conn.execute("""
                UPDATE scooters
                SET przebieg=$1
                WHERE nazwa=$2
            """, int(przebieg), skuter)
            row = await conn.fetchrow("""
                SELECT nazwa, przebieg, nastepny_serwis
                FROM scooters
                WHERE nazwa=$1
            """, skuter)
            await conn.close()

            if row:
                left = int(row["nastepny_serwis"]) - int(row["przebieg"])
                msg = f"✅ Przebieg zaktualizowany\n\n{skuter}: {przebieg} km\nDo serwisu: {left} km"
                if left <= 500:
                    msg += "\n\n⚠️ UWAGA: serwis blisko."
                await update.message.reply_text(msg, reply_markup=keyboard(SCOOTERS_MENU))
            else:
                await update.message.reply_text("Nie znaleziono skutera.")

            context.user_data.clear()

        except Exception as e:
            await update.message.reply_text(f"❌ Błąd:\n{e}")

        return

    if mode == "change_scooter_status":
        try:
            skuter, status, najemca, uwagi = [x.strip() for x in text.split(";")]

            conn = await get_db()
            await conn.execute("""
                UPDATE scooters
                SET status=$1, najemca=$2, uwagi=$3
                WHERE nazwa=$4
            """, status.upper(), najemca, uwagi, skuter)
            await conn.close()

            await update.message.reply_text(
                f"✅ Status zmieniony\n\n{skuter}\n{status}\n{najemca}",
                reply_markup=keyboard(SCOOTERS_MENU),
            )
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
            """, skuter, klient, typ, float(kwota.replace(",", ".")), forma.upper(), uwagi)
            await conn.close()

            await add_finance(
                "RENTAL",
                typ,
                "OPLATA" if typ == "DOCHOD" else "KOSZT",
                float(kwota.replace(",", ".")),
                f"{skuter} | {klient} | {uwagi}",
                forma.upper(),
            )

            await update.message.reply_text(
                f"✅ Rental zapisany\n\n{typ}\n{skuter}\n{kwota} zł",
                reply_markup=keyboard(RENTAL_MENU),
            )
            context.user_data.clear()

        except Exception as e:
            await update.message.reply_text(f"❌ Błąd:\n{e}")

        return

    if mode == "new_service":
        try:
            p = [x.strip() for x in text.split(";")]
            if len(p) != 12:
                raise ValueError("Musi być 12 pól oddzielonych średnikiem.")

            klient, telefon, pojazd, rej, vin, przebieg, usluga, czesci, robocizna, forma, rekomendacje, uwagi = p
            czesci_f = float(czesci.replace(",", "."))
            robocizna_f = float(robocizna.replace(",", "."))
            razem = czesci_f + robocizna_f

            conn = await get_db()
            await conn.execute("""
                INSERT INTO service_orders
                (klient, telefon, pojazd, rejestracja, vin, przebieg, usluga, czesci, robocizna, razem, forma_platnosci, rekomendacje, uwagi)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
            """, klient, telefon, pojazd, rej, vin, int(przebieg), usluga, czesci_f, robocizna_f, razem, forma.upper(), rekomendacje, uwagi)
            await conn.close()

            await add_finance("SERWIS", "DOCHOD", "NAPRAWA", razem, f"{klient} | {pojazd} | {usluga}", forma.upper())

            await update.message.reply_text(
                f"✅ Zlecenie dodane\n\n{klient}\n{pojazd}\nRazem: {razem:.2f} zł",
                reply_markup=keyboard(SERVICE_MENU),
            )
            context.user_data.clear()

        except Exception as e:
            await update.message.reply_text(f"❌ Błąd:\n{e}")

        return

    if mode == "close_service":
        try:
            service_id = int(text.strip())
            conn = await get_db()
            await conn.execute("""
                UPDATE service_orders
                SET status='ZAMKNIETE'
                WHERE id=$1
            """, service_id)
            await conn.close()

            await update.message.reply_text(
                f"✅ Zlecenie #{service_id} zamknięte.",
                reply_markup=keyboard(SERVICE_MENU),
            )
            context.user_data.clear()

        except Exception as e:
            await update.message.reply_text(f"❌ Błąd:\n{e}")

        return

    if mode == "vehicle_history":
        query = text.strip()
        conn = await get_db()
        rows = await conn.fetch("""
            SELECT created_at, klient, pojazd, rejestracja, przebieg, usluga, razem, rekomendacje
            FROM service_orders
            WHERE rejestracja ILIKE $1 OR vin ILIKE $1
            ORDER BY created_at DESC
            LIMIT 20
        """, f"%{query}%")
        await conn.close()

        if not rows:
            await update.message.reply_text("Brak historii pojazdu.")
            return

        msg = "🔍 Historia pojazdu\n\n"
        for r in rows:
            msg += (
                f"{r['created_at'].strftime('%d.%m.%Y')}\n"
                f"👤 {r['klient']}\n"
                f"🏍 {r['pojazd']} | {r['rejestracja']}\n"
                f"📍 {r['przebieg']} km\n"
                f"🔧 {r['usluga']}\n"
                f"💰 {r['razem']:.2f} zł\n"
                f"📝 {r['rekomendacje']}\n\n"
            )

        await update.message.reply_text(msg)
        context.user_data.clear()
        return

    if mode == "pdf_client":
        try:
            service_id = int(text.strip())
            file_path = await generate_service_pdf(service_id)

            if not file_path:
                await update.message.reply_text("Nie znaleziono zlecenia.")
                return

            await update.message.reply_document(
                document=open(file_path, "rb"),
                filename=os.path.basename(file_path),
                caption="📄 Raport serwisowy RedGear Moto",
            )
            context.user_data.clear()

        except Exception as e:
            await update.message.reply_text(f"❌ Błąd PDF:\n{e}")

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
                await add_finance("SKLEP", "WYDATEK", "CZESCI", float(cena.replace(",", ".")), f"Zakup: {nazwa} x{ilosc}", "BRAK")

            await update.message.reply_text(
                f"✅ Magazyn zapisany\n\n{typ_operacji}\n{nazwa} x{ilosc}",
                reply_markup=keyboard(STOCK_MENU),
            )
            context.user_data.clear()

        except Exception as e:
            await update.message.reply_text(f"❌ Błąd:\n{e}")

        return

    if mode == "search_part":
        conn = await get_db()
        rows = await conn.fetch("""
            SELECT nazwa,
            SUM(CASE WHEN typ_operacji='PRZYJECIE' THEN ilosc ELSE -ilosc END) AS stan
            FROM inventory
            WHERE nazwa ILIKE $1
            GROUP BY nazwa
            ORDER BY nazwa
        """, f"%{text}%")
        await conn.close()

        if not rows:
            await update.message.reply_text("Nie znaleziono części.")
            return

        msg = "🔍 Części\n\n"
        for r in rows:
            msg += f"{r['nazwa']}: {r['stan']} szt.\n"

        await update.message.reply_text(msg)
        context.user_data.clear()
        return
        
    if mode == "ai_mechanic":
        try:
            answer = await ask_ai_mechanic(text)

            await update.message.reply_text(
                answer,
                reply_markup=keyboard(MAIN_MENU)
            )

            context.user_data.clear()
            return

        except Exception as e:
            await update.message.reply_text(f"❌ AI Mechanik:\n{e}")
            return
            
    if mode == "ai_entry":
        try:
            result = await process_ai_entry(text)

             if not result:
                 result = "❌ AI nie zwróciło odpowiedzi."
            
            await update.message.reply_text(
                result,
                reply_markup=keyboard(MAIN_MENU),
            )
            context.user_data.clear()

        except Exception as e:
            await update.message.reply_text(f"❌ Błąd AI:\n{e}")

        return

    await update.message.reply_text(
        "Nie rozumiem. Wybierz przycisk z menu.",
        reply_markup=keyboard(MAIN_MENU),
    )


async def process_ai_entry(text):
    if not OPENAI_API_KEY or OpenAI is None:
        return (
            "AI nie jest jeszcze skonfigurowane.\n"
            "Dodaj OPENAI_API_KEY w Railway Variables."
        )


async def ask_ai_mechanic(question):
    if not OPENAI_API_KEY or OpenAI is None:
        return "AI nie jest skonfigurowane."

    client = OpenAI(api_key=OPENAI_API_KEY)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "Jesteś doświadczonym mechanikiem motocykli. "
                    "Odpowiadaj po polsku. "
                    "Podawaj możliwe przyczyny awarii, kolejność diagnostyki i naprawy."
                )
            },
            {
                "role": "user",
                "content": question
            }
        ]
    )

    return response.choices[0].message.content

    client = OpenAI(api_key=OPENAI_API_KEY)

    prompt = f"""
Jesteś asystentem księgowo-operacyjnym firmy RedGear Moto.
Przetwórz wpis użytkownika na JSON.

Dostępne typy:
- finance_income
- finance_expense
- rental_income
- rental_expense
- service_income
- stock_in
- stock_out

Zwróć tylko JSON:
{{
  "action": "...",
  "kwota": 0,
  "kierunek": "SERWIS/RENTAL/SKLEP/FIRMA/PRYWATNE",
  "kategoria": "...",
  "opis": "...",
  "forma": "GOTOWKA/KARTA/PRZELEW/BLIK/BRAK",
  "skuter": "",
  "klient": "",
  "towar": "",
  "ilosc": 0
}}

Tekst użytkownika:
{text}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Zwracasz wyłącznie poprawny JSON bez komentarzy."},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )

    raw = response.choices[0].message.content.strip()
    data = json.loads(raw)

    action = data.get("action")
    kwota = float(data.get("kwota") or 0)
    kierunek = data.get("kierunek") or "FIRMA"
    kategoria = data.get("kategoria") or "INNE"
    opis = data.get("opis") or text
    forma = data.get("forma") or "BRAK"

    if action in ["finance_income", "service_income"]:
        await add_finance(kierunek, "DOCHOD", kategoria, kwota, opis, forma, source="AI")
        result = f"✅ AI zapisało dochód\n\n{kwota:.2f} zł\n{kierunek} / {kategoria}\n{opis}"

    elif action == "finance_expense":
        await add_finance(kierunek, "WYDATEK", kategoria, kwota, opis, forma, source="AI")
        result = f"✅ AI zapisało wydatek\n\n{kwota:.2f} zł\n{kierunek} / {kategoria}\n{opis}"

    elif action in ["rental_income", "rental_expense"]:
        typ = "DOCHOD" if action == "rental_income" else "WYDATEK"
        skuter = data.get("skuter") or ""
        klient = data.get("klient") or ""

        conn = await get_db()
        await conn.execute("""
            INSERT INTO rental (skuter, klient, typ, kwota, forma_platnosci, uwagi)
            VALUES ($1,$2,$3,$4,$5,$6)
        """, skuter, klient, typ, kwota, forma, opis)
        await conn.close()

        await add_finance("RENTAL", typ, "OPLATA" if typ == "DOCHOD" else "KOSZT", kwota, opis, forma, source="AI")
        result = f"✅ AI zapisało rental\n\n{typ}\n{skuter}\n{kwota:.2f} zł"

    elif action in ["stock_in", "stock_out"]:
        typ_operacji = "PRZYJECIE" if action == "stock_in" else "WYDANIE"
        towar = data.get("towar") or opis
        ilosc = int(data.get("ilosc") or 1)

        conn = await get_db()
        await conn.execute("""
            INSERT INTO inventory (nazwa, ilosc, cena, typ_operacji, uwagi)
            VALUES ($1,$2,$3,$4,$5)
        """, towar, ilosc, kwota, typ_operacji, opis)
        await conn.close()

        result = f"✅ AI zapisało magazyn\n\n{typ_operacji}\n{towar} x{ilosc}"

    else:
        result = "AI rozpoznało wpis, ale akcja nie jest jeszcze obsługiwana."

    conn = await get_db()
    await conn.execute("""
        INSERT INTO ai_logs (raw_text, parsed_json, status)
        VALUES ($1,$2,$3)
    """, text, json.dumps(data, ensure_ascii=False), "OK")
    await conn.close()

    return result


async def generate_service_pdf(service_id):
    from fpdf import FPDF

    conn = await get_db()
    row = await conn.fetchrow("""
        SELECT *
        FROM service_orders
        WHERE id=$1
    """, service_id)
    await conn.close()

    if not row:
        return None

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    if os.path.exists(LOGO_PATH):
        try:
            pdf.image(LOGO_PATH, x=10, y=8, w=35)
        except Exception:
            pass

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, COMPANY_NAME, ln=True, align="R")

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"NIP: {COMPANY_NIP}", ln=True, align="R")
    pdf.cell(0, 6, f"Tel: {COMPANY_PHONE}", ln=True, align="R")
    pdf.cell(0, 6, f"Instagram: {COMPANY_INSTAGRAM}", ln=True, align="R")
    pdf.cell(0, 6, f"Adres: {COMPANY_ADDRESS}", ln=True, align="R")

    pdf.ln(15)

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Raport serwisowy", ln=True)

    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"Data: {row['created_at'].strftime('%d.%m.%Y')}", ln=True)
    pdf.cell(0, 8, f"Klient: {row['klient']}", ln=True)
    pdf.cell(0, 8, f"Telefon: {row['telefon']}", ln=True)
    pdf.cell(0, 8, f"Pojazd: {row['pojazd']}", ln=True)
    pdf.cell(0, 8, f"Rejestracja: {row['rejestracja']}", ln=True)
    pdf.cell(0, 8, f"VIN: {row['vin']}", ln=True)
    pdf.cell(0, 8, f"Przebieg: {row['przebieg']} km", ln=True)

    pdf.ln(5)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Wykonane prace:", ln=True)

    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 8, str(row["usluga"] or ""))

    pdf.ln(3)

    pdf.cell(0, 8, f"Czesci: {row['czesci']:.2f} zl", ln=True)
    pdf.cell(0, 8, f"Robocizna: {row['robocizna']:.2f} zl", ln=True)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, f"Razem: {row['razem']:.2f} zl", ln=True)

    pdf.ln(5)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Rekomendacje:", ln=True)

    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 8, str(row["rekomendacje"] or "Brak dodatkowych rekomendacji."))

    pdf.ln(5)

    pdf.set_font("Helvetica", "I", 9)
    pdf.multi_cell(
        0,
        6,
        "Dokument wygenerowany automatycznie przez system RedGear Moto Assistant."
    )

    file_name = f"raport_serwisowy_{service_id}.pdf"
    pdf.output(file_name)

    return file_name


async def post_init(app):
    await init_db()


app = Application.builder().token(TOKEN).post_init(post_init).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.run_polling()
