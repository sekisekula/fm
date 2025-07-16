# Finance Manager - Informacje o Projekcie

## 🎯 Cel Projektu

Finance Manager to aplikacja do zarządzania finansami osobistymi, która umożliwia:
- Parsowanie paragonów z plików JSON
- Śledzenie wydatków ręcznych
- Rozliczenia między użytkownikami
- Generowanie statystyk i raportów
- Zarządzanie przez API (FastAPI) lub CLI

## 🏗️ Architektura

### Struktura Katalogów
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
├── logs/                  # Pliki logów
├── 000.bat               # Uruchomienie API w Dockerze
├── 111.bat               # Uruchomienie bazy danych
├── 222.bat               # Uruchomienie menu CLI
├── Dockerfile            # Konfiguracja Dockera
├── docker-compose.yml    # Kompozycja Dockera
└── requirements.txt      # Zależności Pythona
```

### Technologie
- **Backend:** Python 3.11, FastAPI, SQLAlchemy
- **Baza danych:** PostgreSQL
- **Konteneryzacja:** Docker, Docker Compose
- **Deployment:** Render.com (możliwy)
- **Parsing:** Custom JSON parser dla paragonów

## 🔧 Konfiguracja Importów

### Zasady Importów
**WAŻNE:** Wszystkie importy w projekcie używają prefiksu `app.`:

```python
# ✅ POPRAWNE
from app.config import Config
from app.db.session import SessionLocal
from app.parser import process_receipt_file
from app.menu.models import DatabaseManager

# ❌ NIEPOPRAWNE
from config import Config
from db.session import SessionLocal
from parser import process_receipt_file
```

### Dlaczego `app.`?
- **Uniwersalność:** Działa lokalnie, w Dockerze i na Render.com
- **Jasność:** Wyraźnie wskazuje, że import pochodzi z tego projektu
- **Unikanie konfliktów:** Nie ma kolizji z bibliotekami systemowymi
- **Spójność:** Wszystkie moduły używają tej samej konwencji

## 🚀 Uruchamianie

### Lokalnie
```bash
cd C:\Users\Acer\Desktop\fm
set PYTHONPATH=.
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### W Dockerze
```bash
000.bat  # API serwer
222.bat  # Menu CLI
```

### Na Render.com
```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## 📊 Funkcjonalności

### Web Interface (FastAPI)
- **Upload paragonów** - wrzucanie plików JSON z paragonami
- **Dodawanie wydatków ręcznych** - formularz do dodawania wydatków z kategoriami
- **Przeglądanie paragonów** - nowoczesny interfejs do przeglądania wszystkich paragonów z filtrami i szczegółami
- **Statystyki** - podsumowanie wydatków i paragonów
- **Rozliczenia** - podsumowanie rozliczeń między użytkownikami
- **Zarządzanie użytkownikami** - lista użytkowników w systemie
- **Podliczanie paragonów** - interfejs do podliczania paragonów

### CLI Interface
- **Setup Users** - konfiguracja użytkowników
- **Add Manual Expense** - dodawanie wydatków ręcznych
- **View Manual Expenses** - przeglądanie wydatków ręcznych
- **Parse Receipts** - przetwarzanie paragonów
- **Count Receipts** - podliczanie paragonów
- **View Receipts** - przeglądanie paragonów
- **View Statistics** - statystyki
- **Settlement** - rozliczenia
- **Find receipt / expense** - wyszukiwanie paragonów i wydatków

## 🗄️ Baza Danych

### Tabele
- `users` - Użytkownicy systemu
- `stores` - Sklepy/sklepy
- `receipts` - Paragony
- `products` - Produkty z paragonów
- `shares` - Udziały użytkowników w produktach
- `manual_expenses` - Wydatki ręczne
- `user_payments` - Metody płatności użytkowników
- `settlements` - Rozliczenia

### Relacje
- Jeden użytkownik może mieć wiele metod płatności
- Jeden paragon może mieć wiele produktów
- Każdy produkt może mieć udziały wielu użytkowników
- Wydatki ręczne są przypisane do płatnika

## 🔄 Workflow

### Przetwarzanie Paragonów
1. Plik JSON z paragonem → `data/to_check/`
2. Parser wyciąga dane (sklep, produkty, ceny, data)
3. Sprawdzenie duplikatów
4. Zapis do bazy danych
5. Przeniesienie pliku do `data/parsed/` lub `data/rejected/`

### Rozliczenia
1. Użytkownicy dodają wydatki (ręczne lub z paragonów)
2. System oblicza udziały w produktach
3. Generowanie raportu rozliczeń
4. Podsumowanie kto komu ile płaci

## 🛠️ Rozwój

### Dodawanie Nowych Funkcjonalności
1. **Importy:** Zawsze używaj `from app....`
2. **Ścieżki:** Używaj `pathlib.Path` i ścieżek relatywnych
3. **Baza danych:** Dodaj modele w `app/db/models.py`
4. **API:** Dodaj endpointy w `app/main.py`
5. **CLI:** Dodaj opcje w `app/menu/main.py`

### Debugowanie
- **Logi API:** Wyświetlane w terminalu
- **Logi parsera:** `logs/parser_debug.log`
- **Logi aplikacji:** `finance_manager.log`

## 📚 Dokumentacja

- **README.md** - Kompleksowy przewodnik
- **USAGE.md** - Instrukcja użytkownika
- **CHANGELOG.md** - Historia zmian
- **PROJECT_INFO.md** - Ten plik

## 🎯 Status Projektu

### ✅ Ukończone
- [x] Naprawa wszystkich importów na pakietowe (`app.`)
- [x] Naprawa ścieżek do plików na relatywne
- [x] Uniwersalne uruchamianie (lokalnie, Docker, Render.com)
- [x] Kompletna dokumentacja
- [x] API FastAPI z autoryzacją
- [x] Menu CLI z wszystkimi funkcjonalnościami
- [x] Parser paragonów JSON
- [x] System rozliczeń między użytkownikami
- [x] Statystyki i raporty

### 🔄 W trakcie
- [ ] Testy jednostkowe
- [ ] Optymalizacja wydajności
- [ ] Dodatkowe funkcjonalności

### 📋 Planowane
- [ ] Interfejs webowy (React/Vue)
- [ ] Eksport danych (CSV, Excel)
- [ ] Powiadomienia email
- [ ] Backup automatyczny
- [ ] API dla aplikacji mobilnej

## Zmiany

### 2024-12-19
- **Dodano nowoczesny interfejs przeglądania paragonów** - nowa funkcjonalność webowa z:
  - Filtrowaniem paragonów (wszystkie/podliczone/rozliczone)
  - Responsywnym designem z ciemnym motywem
  - Szczegółowym widokiem paragonów z produktami i rozliczeniami
  - Modalnym oknem szczegółów
  - API endpointami `/api/browse-receipts` i `/api/receipt-details/{receipt_id}`
- **Poprawiono obsługę błędów** - dodano metodę `rollback` do klasy `DatabaseManager`
- **Zoptymalizowano kod** - usunięto bezpośrednie użycie psycopg2, pełna migracja na SQLAlchemy
- **Ulepszono UX** - dodano blokadę podwójnego wysyłania formularzy, lepsze powiadomienia

### [UI/UX] Browse Receipts Modal & Table Improvements (2024-04-27)
- Widened the receipt details modal (`max-width: 1100px`) for better desktop experience.
- Increased padding in the products table and set minimum widths for 'Rabat' and 'Podział (udziały)' columns.
- Shares column now displays percentages as integers when possible (e.g., 89% instead of 89.0%).
- Slightly increased font size for the shares column for clarity.
- All changes improve readability of monetary values and shares in the modal on desktop screens.

### [UI/UX] Browse Receipts Filtering & Modal Action (2024-04-27)
- Added a new filter button 'Inne' to the receipts browser, showing only receipts for user 'Other'.
- The 'Wszystkie', 'Tylko podliczone', and 'Tylko rozliczone' filters now always exclude receipts for 'Other' (only users 1 and 2 are shown).
- Added a 'Podlicz' button in the receipt details modal for both counted and uncounted receipts, linking to the counting/editing view for that receipt.

- Pole `quantity` w tabeli `products` obsługuje liczby zmiennoprzecinkowe (`DECIMAL(10,3)`), co pozwala na zapisywanie zarówno ilości całkowitych, jak i ułamkowych (np. dla produktów na wagę).

### [Naprawa] Formularz dodawania wydatku (`/add-expense-form/`)
- Zidentyfikowano i naprawiono błąd w kodzie HTML/JS, który powodował brak wyświetlania dynamicznych pól (udziały, wybór płacącego) oraz błąd `Unexpected end of input` w konsoli przeglądarki.
- Przyczyną były niezamknięte funkcje JS, powielony kod inicjalizujący oraz brak zamknięcia tagów `<script>`, `</body>`, `</html>`.
- Po poprawkach dynamiczne elementy formularza działają prawidłowo.

---

**Ostatnia aktualizacja:** 2024-01-XX  
**Wersja:** 1.0.0  
**Status:** Produkcyjny 

# Finance Manager – Rozliczenia: kluczowe zasady i zmiany

- Użytkownik 'Other' nie jest uwzględniany w żadnych rozliczeniach, podsumowaniach, tabelach ani widokach – nie pojawia się w UI i nie jest liczony w logice rozliczeń.
- W zakładce "Rozliczenia":
  - Pod aktualnym rozliczeniem znajduje się przycisk "Sfinalizuj rozliczenie" z potwierdzeniem (modalem) przed finalizacją.
  - Po finalizacji wszystkie nierozliczone paragony i wydatki manualne są oznaczane jako rozliczone (settled=TRUE).
  - Nad historycznymi rozliczeniami widnieje nagłówek "Poprzednie rozliczenia".
  - Po kliknięciu na historyczne rozliczenie otwiera się modal ze szczegółami: lista paragonów i wydatków manualnych, z wyraźnym podziałem i kolorowaniem na czerwono dłużnika i kwoty.
- W tabeli podsumowania rozliczeń kolumny mają kolejność: Wyłożył łącznie, Powinien zapłacić, Netto.
- Kolumna "Faktycznie zapłacił" została przemianowana na "Wyłożył łącznie".
- Wszelkie podziały i wyliczenia długów są prezentowane z wyraźnym wyróżnieniem dłużnika i kwoty (kolor czerwony).
- Endpointy API:
  - `/api/finalize-settlement` – finalizuje rozliczenie (ustawia settled=TRUE dla wszystkich nierozliczonych pozycji).
  - `/api/settlement-details/{settlement_id}` – zwraca szczegóły rozliczenia (paragony, wydatki manualne, podziały).
  - `/api/manual-expenses` – zwraca wydatki ręczne do kafelków na stronie "Paragony/wydatki". 