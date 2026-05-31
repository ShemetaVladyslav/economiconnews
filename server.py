"""
EconomiconNews — Flask Backend
Запуск: python server.py
Сайт: http://localhost:5000
"""

import os, sqlite3, json, time, threading, hashlib, secrets
from datetime import datetime, timedelta
from pathlib import Path

import requests
from flask import Flask, request, jsonify, send_from_directory, g
from flask_cors import CORS
import jwt
import bcrypt

# ── CONFIG ─────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
DB_PATH    = Path(os.environ.get("DB_PATH", BASE_DIR / "economiconnews.db"))
STATIC_DIR = BASE_DIR
JWT_SECRET = os.environ.get("JWT_SECRET", "economiconnews_jwt_secret_2026_ukraine")
JWT_EXP    = 24 * 3600   # 24 hours

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="")
CORS(app)

# init database on import (gunicorn doesn't run __main__)
def _bootstrap():
    try:
        init_db()
    except Exception as e:
        print(f"init_db error: {e}")

# ── DATABASE ────────────────────────────────────────────────────────────────
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db: db.close()

def init_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        email        TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        name         TEXT NOT NULL,
        role         TEXT DEFAULT 'user',
        created_at   TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS articles (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        title      TEXT NOT NULL,
        excerpt    TEXT,
        content    TEXT NOT NULL,
        category   TEXT NOT NULL,
        author     TEXT NOT NULL,
        img        TEXT,
        tags       TEXT DEFAULT '[]',
        views      INTEGER DEFAULT 0,
        status     TEXT DEFAULT 'published',
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS bookmarks (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER NOT NULL,
        article_id INTEGER NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        UNIQUE(user_id, article_id),
        FOREIGN KEY(user_id)    REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(article_id) REFERENCES articles(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS comments (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        article_id INTEGER NOT NULL,
        user_id    INTEGER NOT NULL,
        text       TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY(article_id) REFERENCES articles(id) ON DELETE CASCADE,
        FOREIGN KEY(user_id)    REFERENCES users(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS article_views (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        article_id INTEGER NOT NULL,
        viewer_key TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        UNIQUE(article_id, viewer_key)
    );
    """)

    # Seed admin user
    existing = db.execute("SELECT id FROM users WHERE email='admin@economiconnews.ua'").fetchone()
    if not existing:
        pw_hash = bcrypt.hashpw(b"Admin2026!", bcrypt.gensalt()).decode()
        db.execute("INSERT INTO users(email,password_hash,name,role) VALUES(?,?,?,?)",
                   ("admin@economiconnews.ua", pw_hash, "Адміністратор", "admin"))

    # Seed articles
    count = db.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    if count == 0:
        seed_articles = [
          ("Фондовий ринок України показав рекордне зростання: ПФТС +18% за квартал",
           "Перший квартал 2026 року став найуспішнішим для українського фондового ринку з 2018 року. Індекс ПФТС зріс на 18.3%, перевищивши позначку 610 пунктів.",
           """Перший квартал 2026 року став справжнім проривом для вітчизняного фондового ринку. Індекс ПФТС виріс на 18.3%, сягнувши позначки 610.5 пунктів — найвищого рівня з 2018 року.

Найбільшими переможцями кварталу стали акції банківського сектору: ПриватБанк (+34%), Укрексімбанк (+28%), Ощадбанк (+22%). Енергетичні компанії також демонструють позитивну динаміку завдяки зростанню цін на електроенергію в Євросоюзі.

Іноземні інвестори повернулися на ринок: чисті покупки нерезидентів у цінні папери українських компаній склали $1.2 млрд за квартал. Найбільший інтерес — до компаній агропромислового сектору та ІТ.

За базовим сценарієм аналітиків Dragon Capital, ПФТС може досягти 680-700 пунктів до кінця вересня 2026 року. Ключовими драйверами залишаються пришвидшення реконструкційних процесів та приватизаційні реформи.""",
           "Ринки", "Олег Марченко",
           "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=900&q=80",
           '["ПФТС","Фондовий ринок","Акції"]', 14820),

          ("Bitcoin пробив $103 000: аналітики прогнозують $150 000 до кінця 2026",
           "Головна криптовалюта вперше з листопада 2025 року перевищила позначку $103 000. Інституційний попит та схвалення нових Bitcoin ETF стали головними драйверами зростання.",
           """Bitcoin встановив новий рекорд у 2026 році, перетнувши позначку $103 420. За останні 30 днів курс BTC зріс на 24%, а за рік — більш ніж утричі.

Інституційні інвестори, зокрема BlackRock та Fidelity, за квітень-травень 2026 року закупили більш ніж 85 000 BTC. Схвалення SEC нових спотових Bitcoin ETF відкрило ринок для пенсійних фондів та страхових компаній. Обсяги торгів у цих інструментах вже перевищили $8 млрд на добу.

Аналітики Standard Chartered підвищили прогноз до $150 000 до грудня 2026 року. Їх аргумент — чотирирічний халвінг, який відбувся у квітні 2024, традиційно запускає бичачий цикл з 12-18-місячним лагом.

Ринок альткоїнів також у піднесенні: Ethereum тримається вище $3 800, Solana (+45% за місяць) та інші Layer-1 показують активне зростання.""",
           "Крипто", "Анна Ковальчук",
           "https://images.unsplash.com/photo-1518546305927-5a555bb7020d?w=700&q=80",
           '["Bitcoin","Крипто","ETF"]', 22340),

          ("НБУ залишив облікову ставку на рівні 15.5% і дав сигнал про пом'якшення",
           "Національний банк України на засіданні 15 травня залишив ключову ставку без змін. Регулятор прогнозує перший крок зниження у вересні за умови стабілізації інфляції.",
           """Правління НБУ прийняло рішення залишити облікову ставку на рівні 15.5%. Рішення збіглося з консенсус-прогнозом аналітиків.

Голова НБУ заявив, що регулятор спостерігає стійке зниження інфляції: у квітні 2026 вона склала 8.2% у річному вимірі порівняно з 12.4% рік тому. «Ми наближаємось до цільового коридору 5±1%».

НБУ не виключає першого кроку зниження ставки у вересні 2026 року за умови, що інфляція продовжуватиме знижуватись. Це позитивний знак для кредитного ринку та ринку ОВДП.

Банківський сектор відреагував позитивно: дохідності ОВДП на вторинному ринку знизились на 35-50 б.п.""",
           "Банки", "Сергій Бондаренко",
           "https://images.unsplash.com/photo-1554224155-8d04cb21cd6c?w=700&q=80",
           '["НБУ","Облікова ставка","Монетарна політика"]', 9410),

          ("Ринок нерухомості Києва: попит зріс на 22% у квітні, ціни тримаються",
           "Квітень 2026 показав рекордний попит на первинному ринку нерухомості Києва. Найбільший інтерес — до однокімнатних квартир у Голосіївському та Дарницькому районах.",
           """Ринок первинної нерухомості Києва демонструє значне відновлення. У квітні 2026 кількість угод зросла на 22% порівняно з квітнем 2025 року. Загалом за чотири місяці 2026 року укладено 4 120 угод — це найвищий показник з 2021 року.

Середня ціна квадратного метра у новобудовах комфорт-класу становить $1 850-2 200. Найактивніші забудовники — SAGA Development, KAN Development, Інтергал-Буд — зафіксували 35-40% зростання продажів.

Драйвери попиту: відновлення іпотечного кредитування (ставки знизились до 12-14%), збільшення програм державної підтримки «єОселя», повернення частини переселенців.

Аналітики прогнозують, що у другому півріччі первинний ринок може показати зростання цін на 7-10%.""",
           "Нерухомість", "Марія Луценко",
           "https://images.unsplash.com/photo-1560518883-ce09059eeffa?w=700&q=80",
           '["Нерухомість","Київ","Первинний ринок"]', 11250),

          ("Урядовий фонд відновлення отримав €2.1 млрд від ЄС для інфраструктури",
           "Україна отримала черговий транш від Євросоюзу в рамках програми Ukraine Facility. Кошти спрямують на відновлення енергетичної та транспортної інфраструктури.",
           """Міністерство фінансів України підтвердило отримання €2.1 млрд від Євросоюзу у рамках другого траншу програми Ukraine Facility 2026. Загальний обсяг допомоги за програмою становить €50 млрд до 2027 року.

Кошти розподілять так: енергетична інфраструктура — €800 млн, транспортна мережа — €650 млн, цифровізація — €350 млн, підтримка МСБ — €300 млн.

Міжнародні рейтингові агентства позитивно оцінили надходження: Fitch підвищило прогноз за рейтингом України зі «стабільного» до «позитивного».""",
           "Інвестиції", "Дмитро Захаренко",
           "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=700&q=80",
           '["ЄС","Інвестиції","Відновлення"]', 7890),

          ("IT-сектор України приніс $8.2 млрд валютних надходжень у 2025 році",
           "Попри складні умови, українська IT-індустрія зберегла статус ключового валютного донора. Надходження від експорту IT-послуг зросли на 11% порівняно з 2024 роком.",
           """НБУ опублікував статистику: у 2025 році IT-сектор забезпечив $8.2 млрд валютних надходжень від експорту послуг — на 11% більше, ніж у 2024 році.

Кількість IT-спеціалістів в Україні перевищила 350 000 осіб. Ключові ринки збуту — США (41%), Великобританія (18%), Німеччина (12%).

AI та Machine Learning стали найбільш затребуваними напрямками: попит на відповідних спеціалістів виріс на 65% за рік.

За прогнозами IT Ukraine Association, у 2026 році обсяг експорту може сягнути $9.5-10 млрд.""",
           "Технології", "Катерина Мельник",
           "https://images.unsplash.com/photo-1519389950473-47ba0277781c?w=700&q=80",
           '["IT","Технології","Експорт"]', 13120),

          ("ПриватБанк запустив AI-асистент для малого бізнесу з аналізом фінансів",
           "Найбільший банк України інтегрував штучний інтелект у бізнес-кабінет. Система аналізує грошові потоки, прогнозує касові розриви та рекомендує кредитні продукти.",
           """ПриватБанк офіційно запустив AI-фінансовий асистент для підприємців — «Фін-Аналітик» у застосунку Privat24 Бізнес. Інструмент доступний безкоштовно для всіх клієнтів малого бізнесу.

Асистент аналізує транзакційну історію за 12 місяців і надає прогноз грошового потоку на наступні 90 днів з точністю до 87%. Система виявляє сезонні патерни та прогнозує касові розриви.

У пілотному режимі 12 000 компаній скоротили дебіторську заборгованість у середньому на 18% завдяки своєчасним підказкам AI.""",
           "Банки", "Ігор Рева",
           "https://images.unsplash.com/photo-1563986768494-4dee2763ff3f?w=700&q=80",
           '["ПриватБанк","AI","Фінтех"]', 6340),

          ("Dragon Capital залучив $300 млн для нового фонду реконструкції України",
           "Провідна інвестиційна компанія закрила перший раунд фандрейзингу. Серед LP — пенсійні фонди Канади, Нідерландів та суверенні фонди Перської затоки.",
           """Dragon Capital оголосив про успішне закриття першого раунду залучення капіталу до нового Ukraine Reconstruction Fund II. Загальна сума становить $300 млн — вдвічі більше від первісного таргету у $150 млн.

Серед LP: Canada Pension Plan Investment Board, APG Asset Management (Нідерланди), Abu Dhabi Investment Authority, а також сімейні офіси з Великобританії та Польщі.

Фонд орієнтований: енергетика (40%), агробізнес (25%), логістика (20%), технологічні компанії (15%). Горизонт — 7 років.""",
           "Інвестиції", "Оксана Герасименко",
           "https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?w=700&q=80",
           '["Dragon Capital","Інвестиції","Фонд"]', 5670),

          ("Аграрний сектор: Україна наростила експорт зерна до 45 млн тонн",
           "Попри логістичні виклики, агропромисловий комплекс демонструє рекордні показники. Зерновий коридор забезпечив $12 млрд валютної виручки за перші 4 місяці 2026 року.",
           """За перші чотири місяці 2026 року Україна експортувала 18.4 млн тонн зернових — на 12% більше. Прогноз на весь рік — 45 млн тонн.

Валютна виручка від агроекспорту сягнула $12 млрд — це 38% від загального товарного експорту. Головні покупці: країни ЄС (28%), Єгипет (15%), Індія (12%).

Дунайські порти Рені та Ізмаїл збільшили пропускну здатність утричі завдяки інвестиціям у перевалочну інфраструктуру.""",
           "Ринки", "Василь Кравченко",
           "https://images.unsplash.com/photo-1574943320219-553eb213f72d?w=700&q=80",
           '["Агро","Експорт","Зерно"]', 8920),

          ("Мінцифри запустило пілот із цифровою гривнею: 5 банків долучились до тесту",
           "НБУ розпочав другий етап тестування е-гривні. У пілоті беруть участь ПриватБанк, Ощадбанк, monobank, Укрсиббанк та ПУМБ.",
           """НБУ розпочав другий етап пілотного проєкту цифрової гривні (е-гривні). До тестування долучились п'ять банків: ПриватБанк, Ощадбанк, monobank, Укрсиббанк та ПУМБ.

Цифрова гривня функціонує на базі дозволеного блокчейну (permissioned DLT). Ключова відмінність від безготівкових коштів — прямі зобов'язання НБУ. Розрахунок відбувається за 2-3 секунди.

У другому етапі тестуються: офлайн-платежі через NFC, програмовані гроші (e-ваучери для субсидій), розрахунки між юрособами. Масштабний запуск планується на 2027 рік.""",
           "Крипто", "Тетяна Бойченко",
           "https://images.unsplash.com/photo-1639762681485-074b7f938ba0?w=700&q=80",
           '["CBDC","Е-гривня","НБУ"]', 10440),

          ("Відновлення Харкова: $1.8 млрд інвестицій у нове житло за 2025-2026 рр.",
           "Будівельна активність у відносно безпечних районах Харкова не зупиняється. Аналіз ринку від провідних девелоперів.",
           """З початку 2025 року у Харкові та передмісті розпочато будівництво 47 нових ЖК загальною площею 2.3 млн кв. м. Загальний обсяг приватних інвестицій — $1.8 млрд.

Найактивніші райони — Немишлянський, Слободський та Холодногірський. Забудовники роблять ставку на підземне паркування, власні генератори та бомбосховища.

Середня ціна нового житла — $800-1 100 за кв. м. Аналітики прогнозують зростання цін на 15-20% у 2026-2027 роках.""",
           "Нерухомість", "Андрій Савченко",
           "https://images.unsplash.com/photo-1486325212027-8081e485255e?w=700&q=80",
           '["Нерухомість","Харків","Відновлення"]', 7130),

          ("Укрексімбанк розмістив єврооблігації на €500 млн під 6.75% річних",
           "Державний банк вперше за три роки вийшов на міжнародний ринок капіталу. Попит від іноземних інвесторів перевищив пропозицію утричі.",
           """Укрексімбанк успішно розмістив п'ятирічні єврооблігації на суму €500 млн зі ставкою купону 6.75% річних. Книга заявок перевищила €1.7 млрд.

Це перший вихід державного банку на міжнародний ринок боргового капіталу з лютого 2022 року. Організаторами виступили Deutsche Bank, JPMorgan та BNP Paribas.

Залучені кошти спрямують на фінансування експортерів та інфраструктурних проєктів відновлення.""",
           "Банки", "Роман Коваль",
           "https://images.unsplash.com/photo-1601597111158-2fceff292cdc?w=700&q=80",
           '["Укрексімбанк","Єврооблігації","Боргові ринки"]', 4980),
        ]
        for a in seed_articles:
            db.execute(
                "INSERT INTO articles(title,excerpt,content,category,author,img,tags,views) VALUES(?,?,?,?,?,?,?,?)",
                a
            )

    db.commit()
    db.close()

# ── MARKET DATA CACHE ───────────────────────────────────────────────────────
_market_cache = {}
_market_ts    = 0
_market_lock  = threading.Lock()
MARKET_TTL    = 5 * 60  # 5 minutes

# Fallback base prices (used if API fails)
_fallback = {
    "usd_uah": 41.23, "eur_uah": 44.87,
    "btc_usd": 103420, "eth_usd": 3812,
    "gold_usd": 2418, "oil_usd": 79.40,
    "pfts": 610.5
}

def fetch_market_data():
    data = dict(_fallback)

    # 1. NBU official API — USD/UAH, EUR/UAH
    try:
        resp = requests.get(
            "https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?json",
            timeout=6
        )
        if resp.ok:
            rates = {r["cc"]: r["rate"] for r in resp.json()}
            data["usd_uah"] = round(rates.get("USD", data["usd_uah"]), 4)
            data["eur_uah"] = round(rates.get("EUR", data["eur_uah"]), 4)
    except Exception as e:
        print(f"[NBU API error] {e}")

    # 2. CoinGecko — BTC, ETH
    try:
        resp = requests.get(
            "https://api.coingecko.com/api/v3/simple/price"
            "?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true",
            timeout=8,
            headers={"User-Agent": "EconomiconNews/1.0"}
        )
        if resp.ok:
            cg = resp.json()
            data["btc_usd"]     = round(cg["bitcoin"]["usd"], 0)
            data["btc_change"]  = round(cg["bitcoin"].get("usd_24h_change", 0), 2)
            data["eth_usd"]     = round(cg["ethereum"]["usd"], 0)
            data["eth_change"]  = round(cg["ethereum"].get("usd_24h_change", 0), 2)
    except Exception as e:
        print(f"[CoinGecko API error] {e}")

    # 3. metals.live — Gold spot
    try:
        resp = requests.get("https://api.metals.live/v1/spot/gold", timeout=5)
        if resp.ok:
            metals = resp.json()
            if isinstance(metals, list) and metals:
                data["gold_usd"] = round(metals[0].get("gold", data["gold_usd"]), 2)
            elif isinstance(metals, dict):
                data["gold_usd"] = round(metals.get("gold", data["gold_usd"]), 2)
    except Exception as e:
        print(f"[metals.live error] {e}")

    # 4. Oil — simulate realistic movement around base (no free API without key)
    import random
    data["oil_usd"] = round(data["oil_usd"] * (1 + random.uniform(-0.003, 0.003)), 2)
    data["pfts"]    = round(data["pfts"] * (1 + random.uniform(-0.002, 0.002)), 1)

    data["updated_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    return data

def get_market():
    global _market_cache, _market_ts
    with _market_lock:
        if time.time() - _market_ts > MARKET_TTL:
            try:
                _market_cache = fetch_market_data()
                _market_ts    = time.time()
                print(f"[Markets] Updated at {_market_cache.get('updated_at')}")
            except Exception as e:
                print(f"[Markets] Fetch error: {e}")
                if not _market_cache:
                    _market_cache = dict(_fallback)
                    _market_cache["updated_at"] = "fallback"
        return _market_cache

# ── AUTH HELPERS ────────────────────────────────────────────────────────────
def make_token(user_id, role):
    payload = {
        "sub": str(user_id),   # PyJWT 2.x requires sub to be a string
        "role": role,
        "exp": datetime.utcnow() + timedelta(seconds=JWT_EXP)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def decode_token(token):
    return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])

def current_user():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        payload = decode_token(auth.split(" ", 1)[1])
        user_id = int(payload["sub"])   # convert back to int for DB lookup
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return dict(user) if user else None
    except Exception as e:
        print(f"[auth error] {e}")
        return None

def require_auth(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*a, **kw):
        user = current_user()
        if not user:
            return jsonify({"error": "Unauthorized"}), 401
        g.user = user
        return fn(*a, **kw)
    return wrapper

def require_admin(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*a, **kw):
        user = current_user()
        if not user or user["role"] != "admin":
            return jsonify({"error": "Forbidden"}), 403
        g.user = user
        return fn(*a, **kw)
    return wrapper

# ── ROUTES: STATIC ───────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")

@app.route("/article/<int:article_id>")
def article_page(article_id):
    return send_from_directory(STATIC_DIR, "index.html")

@app.route("/profile/<path:author_name>")
def profile_page(author_name):
    return send_from_directory(STATIC_DIR, "index.html")

@app.route("/about")
def about_page():
    return send_from_directory(STATIC_DIR, "index.html")

# ── ROUTES: MARKET DATA ──────────────────────────────────────────────────────
@app.route("/api/markets")
def markets():
    return jsonify(get_market())

# ── ROUTES: AUTH ─────────────────────────────────────────────────────────────
@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.json or {}
    name  = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    pw    = (data.get("password") or "")
    if not name or not email or len(pw) < 6:
        return jsonify({"error": "Заповніть всі поля (пароль мін. 6 символів)"}), 400
    db = get_db()
    if db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone():
        return jsonify({"error": "Email вже зареєстровано"}), 409
    pw_hash = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
    cur = db.execute("INSERT INTO users(email,password_hash,name) VALUES(?,?,?)", (email, pw_hash, name))
    db.commit()
    new_id = cur.lastrowid
    token = make_token(new_id, "user")
    return jsonify({"token": token, "name": name, "role": "user", "id": new_id}), 201

@app.route("/api/auth/login", methods=["POST"])
def login():
    data  = request.json or {}
    email = (data.get("email") or "").strip().lower()
    pw    = (data.get("password") or "")
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if not user or not bcrypt.checkpw(pw.encode(), user["password_hash"].encode()):
        return jsonify({"error": "Невірний email або пароль"}), 401
    token = make_token(user["id"], user["role"])
    return jsonify({"token": token, "name": user["name"], "role": user["role"], "id": user["id"]}), 200

@app.route("/api/auth/me")
@require_auth
def me():
    u = g.user
    return jsonify({"id": u["id"], "name": u["name"], "email": u["email"], "role": u["role"]})

# ── ROUTES: ARTICLES ─────────────────────────────────────────────────────────
def article_row(row):
    d = dict(row)
    d["tags"] = json.loads(d.get("tags") or "[]")
    return d

@app.route("/api/articles")
def get_articles():
    db   = get_db()
    cat  = request.args.get("category", "")
    q    = request.args.get("q", "")
    page = max(1, int(request.args.get("page", 1)))
    per  = int(request.args.get("per", 9))

    sql    = "SELECT * FROM articles WHERE status='published'"
    params = []
    if cat:
        sql += " AND category=?"; params.append(cat)
    if q:
        sql += " AND (title LIKE ? OR excerpt LIKE ?)"; params += [f"%{q}%", f"%{q}%"]
    total  = db.execute(f"SELECT COUNT(*) FROM ({sql})", params).fetchone()[0]
    sql   += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params += [per, (page - 1) * per]
    rows   = db.execute(sql, params).fetchall()
    return jsonify({"total": total, "page": page, "per": per, "articles": [article_row(r) for r in rows]})

@app.route("/api/articles/<int:aid>")
def get_article(aid):
    db  = get_db()
    row = db.execute("SELECT * FROM articles WHERE id=?", (aid,)).fetchone()
    if not row: return jsonify({"error": "Not found"}), 404

    # ── Unique view tracking ──────────────────────────────────────
    user = current_user()
    if user:
        viewer_key = f"u_{user['id']}"
    else:
        raw_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "")
        ip = raw_ip.split(",")[0].strip()
        viewer_key = "i_" + hashlib.sha256(ip.encode()).hexdigest()[:20]

    try:
        db.execute(
            "INSERT INTO article_views(article_id, viewer_key) VALUES(?,?)",
            (aid, viewer_key)
        )
        db.execute("UPDATE articles SET views=views+1 WHERE id=?", (aid,))
    except sqlite3.IntegrityError:
        pass  # already viewed — no increment

    db.commit()

    a = article_row(row)
    # Refresh views from DB so returned count is accurate
    a["views"] = db.execute("SELECT views FROM articles WHERE id=?", (aid,)).fetchone()["views"]

    # comments
    comments = db.execute(
        "SELECT c.id, c.text, c.created_at, u.name FROM comments c JOIN users u ON c.user_id=u.id WHERE c.article_id=? ORDER BY c.id DESC",
        (aid,)
    ).fetchall()
    a["comments"] = [dict(c) for c in comments]
    return jsonify(a)

@app.route("/api/articles", methods=["POST"])
@require_admin
def create_article():
    d = request.json or {}
    db = get_db()
    cur = db.execute(
        "INSERT INTO articles(title,excerpt,content,category,author,img,tags,status) VALUES(?,?,?,?,?,?,?,?)",
        (d.get("title",""), d.get("excerpt",""), d.get("content",""),
         d.get("category",""), d.get("author",""), d.get("img",""),
         json.dumps(d.get("tags",[])), d.get("status","published"))
    )
    db.commit()
    row = db.execute("SELECT * FROM articles WHERE id=?", (cur.lastrowid,)).fetchone()
    return jsonify(article_row(row)), 201

@app.route("/api/articles/<int:aid>", methods=["PUT"])
@require_admin
def update_article(aid):
    d = request.json or {}
    db = get_db()
    db.execute(
        "UPDATE articles SET title=?,excerpt=?,content=?,category=?,author=?,img=?,tags=?,status=? WHERE id=?",
        (d.get("title"), d.get("excerpt"), d.get("content"),
         d.get("category"), d.get("author"), d.get("img"),
         json.dumps(d.get("tags",[])), d.get("status","published"), aid)
    )
    db.commit()
    return jsonify({"ok": True})

@app.route("/api/articles/<int:aid>", methods=["DELETE"])
@require_admin
def delete_article(aid):
    db = get_db()
    db.execute("DELETE FROM articles WHERE id=?", (aid,))
    db.commit()
    return jsonify({"ok": True})

# ── ROUTES: AUTHOR PROFILE ───────────────────────────────────────────────────
@app.route("/api/authors/<path:name>")
def author_profile(name):
    db = get_db()
    articles = db.execute(
        "SELECT id,title,excerpt,category,img,views,created_at,tags FROM articles "
        "WHERE author=? AND status='published' ORDER BY id DESC",
        (name,)
    ).fetchall()
    total_views = sum(r["views"] for r in articles)
    return jsonify({
        "author":       name,
        "article_count": len(articles),
        "total_views":  total_views,
        "articles":     [article_row(r) for r in articles],
    })

# ── ROUTES: TRENDING ─────────────────────────────────────────────────────────
@app.route("/api/articles/trending")
def trending():
    db   = get_db()
    rows = db.execute("SELECT id,title,category,views FROM articles WHERE status='published' ORDER BY views DESC LIMIT 5").fetchall()
    return jsonify([dict(r) for r in rows])

# ── ROUTES: BOOKMARKS ────────────────────────────────────────────────────────
@app.route("/api/bookmarks")
@require_auth
def get_bookmarks():
    db   = get_db()
    rows = db.execute(
        "SELECT a.* FROM bookmarks b JOIN articles a ON b.article_id=a.id WHERE b.user_id=? ORDER BY b.id DESC",
        (g.user["id"],)
    ).fetchall()
    return jsonify([article_row(r) for r in rows])

@app.route("/api/bookmarks/<int:aid>", methods=["POST"])
@require_auth
def add_bookmark(aid):
    db = get_db()
    try:
        db.execute("INSERT INTO bookmarks(user_id,article_id) VALUES(?,?)", (g.user["id"], aid))
        db.commit()
        return jsonify({"saved": True})
    except sqlite3.IntegrityError:
        db.execute("DELETE FROM bookmarks WHERE user_id=? AND article_id=?", (g.user["id"], aid))
        db.commit()
        return jsonify({"saved": False})

@app.route("/api/bookmarks/ids")
@require_auth
def bookmark_ids():
    db  = get_db()
    ids = db.execute("SELECT article_id FROM bookmarks WHERE user_id=?", (g.user["id"],)).fetchall()
    return jsonify([r["article_id"] for r in ids])

# ── ROUTES: COMMENTS ─────────────────────────────────────────────────────────
@app.route("/api/articles/<int:aid>/comments", methods=["POST"])
@require_auth
def add_comment(aid):
    text = (request.json or {}).get("text", "").strip()
    if not text: return jsonify({"error": "Empty"}), 400
    db = get_db()
    db.execute("INSERT INTO comments(article_id,user_id,text) VALUES(?,?,?)", (aid, g.user["id"], text))
    db.commit()
    return jsonify({"ok": True, "name": g.user["name"]})

# ── ROUTES: ADMIN STATS ──────────────────────────────────────────────────────
@app.route("/api/admin/stats")
@require_admin
def admin_stats():
    db = get_db()
    return jsonify({
        "articles": db.execute("SELECT COUNT(*) FROM articles").fetchone()[0],
        "users":    db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "views":    db.execute("SELECT SUM(views) FROM articles").fetchone()[0] or 0,
        "bookmarks":db.execute("SELECT COUNT(*) FROM bookmarks").fetchone()[0],
    })

@app.route("/api/admin/articles")
@require_admin
def admin_articles():
    db   = get_db()
    rows = db.execute("SELECT id,title,category,author,views,status,created_at FROM articles ORDER BY id DESC").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/admin/users")
@require_admin
def admin_users():
    db   = get_db()
    rows = db.execute("SELECT id,name,email,role,created_at FROM users ORDER BY id DESC").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/admin/users/<int:uid>/role", methods=["PATCH"])
@require_admin
def toggle_user_role(uid):
    # Only the super admin (id=1) can change roles
    if g.user["id"] != 1:
        return jsonify({"error": "Тільки головний адмін може змінювати ролі"}), 403
    if uid == 1:
        return jsonify({"error": "Не можна змінювати роль головного акаунту"}), 400
    db = get_db()
    user = db.execute("SELECT id, role FROM users WHERE id=?", (uid,)).fetchone()
    if not user:
        return jsonify({"error": "Користувача не знайдено"}), 404
    new_role = "admin" if user["role"] == "user" else "user"
    db.execute("UPDATE users SET role=? WHERE id=?", (new_role, uid))
    db.commit()
    return jsonify({"ok": True, "new_role": new_role})

# ── BOOTSTRAP (works under gunicorn too) ────────────────────────────────────
init_db()
try:
    get_market()  # warm up market cache (non-fatal if external APIs fail)
except Exception as e:
    print(f"warm-up get_market failed: {e}")

# ── MAIN ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("=" * 55)
    print("  EconomiconNews — запуск сервера")
    print("=" * 55)
    print(f"  База даних: {DB_PATH}")
    print(f"  Сайт: http://localhost:{port}")
    print("  Адмін: admin@economiconnews.ua / Admin2026!")
    print("=" * 55)
    app.run(host="0.0.0.0", debug=False, port=port, threaded=True)
