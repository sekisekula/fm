# Finance Manager

Aplikacja do zarządzania finansami osobistymi z możliwością parsowania paragonów, śledzenia wydatków i generowania raportów.

## 🚀 Szybki Start

### Lokalne uruchomienie

1. **Przejdź do katalogu głównego projektu:**
   ```bash
   cd C:\Users\Acer\Desktop\fm
   ```

2. **Ustaw zmienną środowiskową PYTHONPATH:**
   - W Command Prompt (cmd):
     ```cmd
     set PYTHONPATH=.
     ```
   - W PowerShell:
     ```powershell
     $env:PYTHONPATH = "."
     ```

3. **Uruchom API serwer:**
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

4. **Uruchom menu CLI (w nowym terminalu):**
   ```bash
   python -m app.menu.main
   ```

### Uruchomienie w Dockerze

1. **Uruchom API serwer:**
   ```bash
   000.bat
   ```

2. **Uruchom menu CLI:**
   ```bash
   222.bat
   ```

## 📁 Struktura Projektu

```
fm/
├── app/                    # Główny kod aplikacji
│   ├── main.py            # FastAPI serwer
│   ├── config.py          # Konfiguracja
│   ├── parser.py          # Parser paragonów
│   ├── add_users.py       # Zarządzanie użytkownikami
│   ├── utils.py           # Funkcje pomocnicze
│   ├── db/                # Baza danych
│   │   ├── database.py    # Operacje na bazie
│   │   ├── session.py     # Sesje bazy danych
│   │   ├── models.py      # Modele SQLAlchemy
│   │   └── utils.py       # Narzędzia bazy danych
│   ├── menu/              # Interfejs CLI
│   │   ├── main.py        # Główne menu
│   │   ├── handlers.py    # Obsługa akcji
│   │   ├── views.py       # Wyświetlanie
│   │   └── models.py      # Modele menu
│   ├── scripts/           # Skrypty pomocnicze
│   └── archive/           # Archiwum
├── data/                  # Dane aplikacji
│   ├── to_check/          # Paragony do przetworzenia
│   ├── parsed/            # Przetworzone paragony
│   └── rejected/          # Odrzucone paragony
├── 000.bat               # Uruchomienie API w Dockerze
├── 111.bat               # Uruchomienie bazy danych
├── 222.bat               # Uruchomienie menu CLI
├── Dockerfile            # Konfiguracja Dockera
├── docker-compose.yml    # Kompozycja Dockera
└── requirements.txt      # Zależności Pythona
```

## 🔧 Konfiguracja

### Zmienne środowiskowe

Utwórz plik `.env` w katalogu głównym:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=finance_manager
DB_USER=your_username
DB_PASSWORD=your_password
APP_PASSWORD=your_app_password
UPLOAD_FOLDER=data/to_check
```

### Baza danych

Aplikacja wymaga PostgreSQL. Możesz użyć:
- Lokalnej instalacji PostgreSQL
- Kontenera Docker (111.bat)
- Zdalnej bazy danych (np. na Render.com, Heroku)

## 📖 Użycie

### API Endpoints

- `GET /upload-form/` - Formularz do wrzucania paragonów
- `POST /upload/` - Endpoint do wrzucania plików JSON

### Menu CLI

Po uruchomieniu `python -m app.menu.main` lub `222.bat`:

1. **Setup Users** - Konfiguracja użytkowników
2. **Add Manual Expense** - Dodawanie wydatków ręcznych
3. **Parse Receipts** - Przetwarzanie paragonów
4. **View Receipts** - Przeglądanie paragonów
5. **View Statistics** - Statystyki wydatków
6. **Settlement** - Rozliczenia między użytkownikami

## 🐳 Docker

### Uruchomienie pełnego stosu

```bash
# Baza danych
111.bat

# API serwer
000.bat

# Menu CLI
222.bat
```

### Własne polecenia Docker

```bash
# Budowanie obrazu
docker-compose build

# Uruchomienie API
docker-compose up -d

# Logi
docker-compose logs -f

# Zatrzymanie
docker-compose down
```

## 🌐 Deployment na Render.com

### Szybki deployment (zalecany)
1. **Połącz repozytorium GitHub z Render.com**
2. **Użyj pliku `render.yaml`** - Render automatycznie wykryje konfigurację
3. **Zaktualizuj zmienne środowiskowe** w panelu Render.com:
   - `DB_HOST` - adres Twojej bazy PostgreSQL
   - `DB_NAME` - nazwa bazy danych
   - `DB_USER` - użytkownik bazy danych
   - `DB_PASSWORD` - hasło do bazy danych
   - `APP_PASSWORD` - hasło do aplikacji (możesz wygenerować w panelu)
4. **Deploy!**

### Ręczna konfiguracja
1. **Połącz repozytorium GitHub z Render.com**
2. **Skonfiguruj usługę:**
   - **Environment:** Python
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. **Dodaj zmienne środowiskowe** (DB_HOST, DB_USER, itp.)
4. **Deploy!**

### Dostęp przez internet
Po wdrożeniu dostaniesz URL, np.:
```
https://finance-manager-api.onrender.com
```

**Dostępne funkcje:**
- **Główne menu:** `https://your-app.onrender.com/`
- **Wrzucanie paragonów:** `https://your-app.onrender.com/upload-form/`
- **Dodawanie wydatków:** `https://your-app.onrender.com/add-expense-form/`
- **Statystyki:** `https://your-app.onrender.com/view-statistics/`
- **Paragony:** `https://your-app.onrender.com/view-receipts/`
- **Rozliczenia:** `https://your-app.onrender.com/settlement/`
- **Użytkownicy:** `https://your-app.onrender.com/users/`
- **API docs:** `https://your-app.onrender.com/docs`

## 🔍 Rozwiązywanie Problemów

### Błąd "ModuleNotFoundError: No module named 'app'"

**Rozwiązanie:** Upewnij się, że:
1. Jesteś w katalogu głównym projektu
2. Ustawiłeś `PYTHONPATH=.`
3. Uruchamiasz z `app.main:app`

### Błąd "No such file or directory: '/app/create_tables.sql'"

**Rozwiązanie:** Ścieżka jest już naprawiona - używa relatywnych ścieżek.

### Błąd połączenia z bazą danych

**Rozwiązanie:** Sprawdź zmienne środowiskowe w pliku `.env`.

## 📝 Logi

- **API:** Wyświetlane w terminalu
- **Parser:** `logs/parser_debug.log`
- **Aplikacja:** `finance_manager.log`

## 🤝 Współpraca

1. Fork projektu
2. Utwórz branch (`git checkout -b feature/amazing-feature`)
3. Commit zmiany (`git commit -m 'Add amazing feature'`)
4. Push do branch (`git push origin feature/amazing-feature`)
5. Otwórz Pull Request

## 📄 Licencja

Ten projekt jest prywatny.

---

**Uwaga:** Wszystkie importy w kodzie używają prefiksu `app.` (np. `from app.config import Config`), co zapewnia kompatybilność między lokalnym uruchomieniem a Dockerem/Render.com.
