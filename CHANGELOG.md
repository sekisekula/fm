# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]
### Added
- Przycisk "Sfinalizuj rozliczenie" z potwierdzeniem i obsługą finalizacji (endpoint `/api/finalize-settlement`).
- Modal do szczegółów historycznego rozliczenia (lista paragonów i wydatków manualnych, podział, kolorowanie dłużnika).
- Endpoint `/api/manual-expenses` do pobierania wydatków ręcznych do kafelków.

### Changed
- Użytkownik 'Other' jest całkowicie pomijany w rozliczeniach, podsumowaniach i UI.
- Kolejność kolumn w tabeli podsumowania: Wyłożył łącznie, Powinien zapłacić, Netto.
- Kolumna "Faktycznie zapłacił" przemianowana na "Wyłożył łącznie".
- Wszelkie podziały i długi są prezentowane z wyraźnym wyróżnieniem dłużnika i kwoty (kolor czerwony).
- Nad historycznymi rozliczeniami pojawia się nagłówek "Poprzednie rozliczenia".

### Fixed
- **CRITICAL BUG**: Settlement calculation was including already settled expenses/receipts, causing duplicate calculations. Fixed by adding `settled = FALSE` filter to both receipt and manual expense queries in settlement calculation.
- 000start_api_docker.bat now runs 'docker-compose down' at the start to ensure containers are stopped before starting the API server.
- Renamed 000start_api_docker.bat to 000.bat.
- Renamed 000run_menu_docker.bat to 111.bat.
- Added 'docker-compose build' after stopping containers in 000.bat.
- Improved section headers and separators for each menu and sub-menu, making them clearer and more consistent throughout the CLI.
- The 'Who paid' column now always shows the user name (not payment name) everywhere in the CLI, for consistency and clarity.
- Manual expenses and receipts are now always shown in a consistent, well-aligned tabular format throughout the CLI, improving readability and user experience.
- All lists (manual expenses, receipts, etc.) now use consistent tabular formatting throughout the CLI, ensuring a uniform and user-friendly interface.
- All user-facing lists and tables now always show user-friendly names (never raw payment names or IDs) throughout the CLI.
- After any detailed view (such as product-level breakdown for receipts), the CLI now always prompts the user with 'Press Enter to go back' before returning to the menu.
- All input prompts now allow 'b' or 'q' to go back or quit, making navigation more flexible and user-friendly throughout the CLI.
- Stack traces are now never shown to the user; all errors are logged, and only user-friendly error messages are displayed in the CLI.
- Typing '0' at any input prompt now cancels the current action and returns to the main menu, making navigation more intuitive and user-friendly.
- All user messages now use consistent color coding: Green for success, Red for errors, Yellow for warnings, Cyan for info.
- The settlement summary now shows a clear, user-friendly breakdown of every receipt and manual expense (with dates, products, shares, and payer names) before finalizing, and all debug output has been removed.
- Input prompts now show default values in [brackets] and validate each field as entered, not at the end, improving usability and data entry experience.

## [Unreleased] - 2024-04-27
### Added
- New filter button 'Inne' in receipts browser to show only receipts for user 'Other'.
- 'Podlicz' button in the receipt details modal for both counted and uncounted receipts, linking to the counting/editing view for that receipt.
### Changed
- 'Wszystkie', 'Tylko podliczone', and 'Tylko rozliczone' filters now always exclude receipts for 'Other' (only users 1 and 2 are shown).
### Changed
- Widened the receipt details modal (max-width: 1100px) for better desktop experience.
- Increased padding in the products table and set minimum widths for 'Rabat' and 'Podział (udziały)' columns.
- Shares column now displays percentages as integers when possible (e.g., 89% instead of 89.0%).
- Slightly increased font size for the shares column for clarity.
- All changes improve readability of monetary values and shares in the modal on desktop screens.

## [2024-12-19] - Nowoczesny interfejs przeglądania paragonów

### Dodano
- **Nowy interfejs webowy do przeglądania paragonów** (`/browse-receipts/`)
  - Filtrowanie paragonów: wszystkie, tylko podliczone, tylko rozliczone
  - Responsywny design z ciemnym motywem
  - Karty paragonów z podstawowymi informacjami
  - Modalne okno ze szczegółami paragonu
  - Lista produktów z cenami i rabatami
  - Informacje o rozliczeniach między użytkownikami
- **Nowe API endpointy:**
  - `GET /api/browse-receipts?filter_type={all|counted|settled}` - lista paragonów z filtrami
  - `GET /api/receipt-details/{receipt_id}` - szczegóły paragonu z produktami i rozliczeniami
- **Przycisk "Przeglądaj Paragony"** w menu głównym aplikacji webowej

### Poprawiono
- **Obsługa błędów** - dodano metodę `rollback` do klasy `DatabaseManager`
- **Optymalizacja kodu** - pełna migracja z psycopg2 na SQLAlchemy
- **UX formularzy** - blokada podwójnego wysyłania, lepsze powiadomienia

### Zmieniono
- **Struktura menu głównego** - dodano nowy przycisk "🔍 Przeglądaj Paragony"
- **Dokumentacja** - zaktualizowano PROJECT_INFO.md z nowymi funkcjonalnościami

## [2024-05-18]
### Added
- Created `PROJECT_INFO.md` and `CHANGELOG.md` for documentation and change tracking.

### Changed
- Organized imports in `app/main.py` according to PEP 8.
- Improved error handling in `lifespan` function.
- Removed unused variables and imports.

### Fixed
- FastAPI and uvicorn import errors by ensuring dependencies are installed.
- Updated docker-compose.yml to mount the local data directory as a bind mount for the app service, ensuring receipt files in data/to_check are visible to the container.

## [2024-01-XX] - Naprawa importów i ścieżek - Uniwersalne uruchamianie

### 🎯 Główne zmiany
- **Naprawiono wszystkie importy** - teraz używają prefiksu `app.` (np. `from app.config import Config`)
- **Naprawiono ścieżki do plików** - używają relatywnych ścieżek z `pathlib.Path`
- **Uniwersalne uruchamianie** - projekt działa identycznie lokalnie, w Dockerze i na Render.com

### 🔧 Techniczne zmiany
- Zmieniono wszystkie importy lokalne na pakietowe:
  - `from config import Config` → `from app.config import Config`
  - `from db.session import SessionLocal` → `from app.db.session import SessionLocal`
  - `from parser import process_receipt_file` → `from app.parser import process_receipt_file`
  - `from utils import ...` → `from app.utils import ...`
  - `from menu.models import ...` → `from app.menu.models import ...`
- Naprawiono ścieżkę do `create_tables.sql`:
  - Stara: `/app/create_tables.sql` (absolutna)
  - Nowa: `BASE_DIR / "app" / "create_tables.sql"` (relatywna)
- Usunięto manipulacje `sys.path` z kodu
- Dodano plik `__init__.py` w katalogu głównym projektu

### 📋 Instrukcje uruchamiania
#### Lokalnie:
```bash
cd C:\Users\Acer\Desktop\fm
set PYTHONPATH=.
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

#### W Dockerze:
```bash
000.bat  # API serwer
222.bat  # Menu CLI
```

#### Na Render.com:
```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### 📚 Zaktualizowana dokumentacja
- **README.md** - kompleksowa instrukcja uruchamiania
- **USAGE.md** - szczegółowy przewodnik użytkownika
- Dodano sekcje rozwiązywania problemów
- Dodano instrukcje deploymentu na Render.com

### ✅ Naprawione pliki
- `app/main.py`
- `app/config.py`
- `app/parser.py`
- `app/add_users.py`
- `app/utils.py`
- `app/db/database.py`
- `app/db/session.py`
- `app/db/utils.py`
- `app/db/__init__.py`
- `app/menu/main.py`
- `app/menu/handlers.py`
- `app/menu/views.py`
- `app/menu/models.py`
- `app/menu/__init__.py`
- `app/scripts/backup.py`
- `__init__.py` (nowy plik)

### 🎉 Korzyści
- **Jedna konfiguracja** - działa wszędzie bez zmian
- **Brak błędów importów** - wszystkie moduły są poprawnie rozpoznawane
- **Łatwiejsze debugowanie** - spójne środowisko uruchomieniowe
- **Prostszy deployment** - identyczne polecenia startowe
- **Lepsza dokumentacja** - jasne instrukcje dla wszystkich scenariuszy

---

## [Earlier]
- See git history for previous changes. 

- Changed: /upload-form/ no longer requires a password to view the upload form; password is only required for uploading files.
- Added: Upload endpoint now allows up to 500 files per upload; clear error message if limit is exceeded.
- Improved: Upload form now displays a note about the 500 file limit. 

- Zmieniono typ pola `quantity` w tabeli `products` z `INT` na `DECIMAL(10,3)` (oraz w modelu ORM).
- Zaktualizowano całą obsługę insertów, parsera, endpointów i CLI, aby ilość produktu mogła być liczbą zmiennoprzecinkową (np. dla produktów na wagę). 

- Naprawiono krytyczny błąd w kodzie HTML/JS formularza dodawania wydatku (`/add-expense-form/`), który powodował błąd `Unexpected end of input` w przeglądarce i brak wyświetlania dynamicznych pól (udziały, wybór płacącego). Błąd wynikał z niezamkniętych funkcji JS i tagów HTML. Poprawiono zamknięcia funkcji, usunięto powielony kod, domknięto tagi `<script>`, `</body>`, `</html>`. Dynamiczne pola wyświetlają się i działają poprawnie. 