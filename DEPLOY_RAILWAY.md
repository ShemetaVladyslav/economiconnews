# Розгортання EconomiconNews на Railway

## Що вже зроблено в проекті

В папці проекту створено/змінено такі файли:

| Файл | Призначення |
|---|---|
| `requirements.txt` | Перелік Python-залежностей для Railway |
| `Procfile` | Команда запуску через Gunicorn (production WSGI-сервер) |
| `railway.json` | Конфігурація Railway (білдер, рестарти) |
| `.gitignore` | Виключення непотрібних файлів |
| `server.py` | **Змінено**: PORT/DB_PATH/JWT_SECRET тепер беруться зі змінних оточення |

---

## Покрокова інструкція

### Крок 1. Створи акаунт на Railway

1. Заходь на **https://railway.app**
2. Натисни **«Login»** → увійди через **GitHub** (зручніше) або email
3. На Hobby-плані безкоштовно дають **$5 у місяць** — цього вистачає на ~30-40 днів роботи 24/7

### Крок 2. Установи Git (якщо ще немає)

Перевір: `git --version`

Якщо немає — завантаж з https://git-scm.com/download/win і встанови (всі налаштування за замовчуванням).

### Крок 3. Завантаж проект на GitHub

#### 3.1. Створи репозиторій на GitHub
1. Зайди на **https://github.com/new**
2. **Repository name**: `economiconnews`
3. **Visibility**: `Private` (якщо не хочеш щоб усі бачили твій код)
4. **Не** ставь галочки на README/gitignore/license
5. Натисни **Create repository**

#### 3.2. Запуш проект (виконай у PowerShell)

```powershell
cd "C:\Users\BOSS\Downloads\economicon_report_site"

# Ініціалізація Git
git init
git add .
git commit -m "Initial commit: EconomiconNews ready for Railway"

# Підключи свій GitHub-репо (замість TWOEIMYA встав свій GitHub-username)
git remote add origin https://github.com/TWOEIMYA/economiconnews.git
git branch -M main
git push -u origin main
```

При push може попросити логін GitHub — введи свої дані.

> ⚠️ Якщо просить токен замість пароля — створи його тут: https://github.com/settings/tokens/new (Scopes → repo)

### Крок 4. Деплой через Railway

1. Зайди на **https://railway.app/dashboard**
2. Натисни **«New Project»**
3. Обери **«Deploy from GitHub repo»**
4. Якщо вперше — Railway попросить дозволу на твої репозиторії: **Authorize Railway → All repositories** (або тільки `economiconnews`)
5. Обери репозиторій **`economiconnews`**
6. Railway автоматично запустить білд

Через **2-3 хвилини** деплой завершиться. Якщо червоний — клікни на сервіс і подивись **Deploy Logs**.

### Крок 5. Згенеруй публічну адресу

1. У панелі Railway → твій проект → **сервіс**
2. Вкладка **«Settings» → «Networking»**
3. Натисни **«Generate Domain»**
4. Railway видасть тобі домен виду:
   ```
   https://economiconnews-production.up.railway.app
   ```

Відкрий цю адресу в браузері — сайт повинен працювати! 🎉

### Крок 6. (Важливо) Додай свої секрети

1. У панелі Railway → твій сервіс → **«Variables»**
2. Натисни **«+ New Variable»** і додай:

   | Name | Value |
   |---|---|
   | `JWT_SECRET` | згенеруй випадковий рядок (нижче як це зробити) |
   | `PYTHON_VERSION` | `3.11` |

   **Як згенерувати JWT_SECRET** (виконай локально):
   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```
   Скопіюй результат, встав у Railway.

3. Після додавання змінних Railway автоматично перезапустить сервер.

### Крок 7. (Опціонально) Persistent диск для бази даних

⚠️ Без цього кроку база `economiconnews.db` буде **скидатись** при кожному передеплої або перезапуску!

1. У панелі Railway → твій сервіс → **«Settings» → «Volumes»**
2. **«+ New Volume»**
3. **Mount Path**: `/data`
4. **Size**: 1 GB (вистачить надовго)
5. Перейди у **«Variables»** і додай:
   - `DB_PATH` = `/data/economiconnews.db`
6. Railway перезапустить сервіс, база переїде на постійний диск.

> Після цього всі зареєстровані користувачі, статті, коментарі зберігатимуться **назавжди**, поки існує volume.

### Крок 8. (Опціонально) Власний домен

1. У Railway → **«Settings» → «Networking» → «Custom Domain»**
2. Введи свій домен (наприклад, `news.tvojsite.com.ua`)
3. У DNS-провайдера (де купував домен) додай **CNAME-запис**:
   - **Name**: `news` (або як треба)
   - **Value**: значення, яке покаже Railway
4. Через 5-30 хвилин SSL-сертифікат активується автоматично.

---

## Як оновлювати сайт після змін у коді

Кожного разу, як змінив код локально:

```powershell
cd "C:\Users\BOSS\Downloads\economicon_report_site"
git add .
git commit -m "Опис змін"
git push
```

Railway помітить новий коміт і **автоматично передеплоїть** через 1-2 хвилини.

---

## Як подивитись логи (якщо щось не працює)

1. Railway → твій сервіс → вкладка **«Deployments»** → клік на останній деплой
2. **«View Logs»** — побачиш все, що пише Python (включно з помилками)

Або через CLI:
```powershell
npm install -g @railway/cli
railway login
railway link    # обери свій проект
railway logs
```

---

## Перевірочний список перед захистом

- [ ] Сайт відкривається за публічним URL
- [ ] Можна зареєструвати нового користувача
- [ ] Можна увійти як адмін: `admin@economiconnews.ua` / `Admin2026!`
- [ ] Адмін-панель доступна
- [ ] Ринкові котирування підвантажуються
- [ ] Закладки зберігаються після перезаходу (працює тільки якщо налаштовано volume)
- [ ] HTTPS у адресному рядку

---

## Можливі проблеми

### «Application failed to respond» / 502
Подивись **Deploy Logs**. Найчастіше:
- Не встановилось щось з `requirements.txt` — перевір синтаксис
- Помилка в `init_db()` — подивись traceback

### Дані пропадають після передеплою
Не налаштовано Volume (крок 7). Поки що це нормально для демо, але краще зробити.

### Метрики ринку «висять» на одних значеннях
Метрики кешуються на 5 хвилин у пам'яті процесу. При кожному cold start вони ініціалізуються наново. Це нормально.

### Адмін-пароль не підходить
Якщо змінив `JWT_SECRET` після першої ініціалізації — старі токени стали невалідні. Просто перелогінься.

---

## Скільки коштує

**Hobby plan ($5 безкоштовно щомісяця)**:
- Цього вистачає на сайт з пам'яттю ~512 МБ, що працює 24/7
- Якщо вийдеш за ліміт — Railway не зніме гроші автоматично, а зупинить сервіс до наступного місяця

**Pro plan ($20/міс)**:
- $20 кредитів + більше ресурсів
- Потрібен лише якщо реально великий трафік

Для дипломної демонстрації Hobby plan **повністю вистачає**.
