# Finance Manager - Instrukcja Użycia

## 🚀 Szybkie Uruchomienie

### Opcja 1: Lokalne uruchomienie (bez Dockera)

1. **Otwórz terminal w katalogu głównym projektu:**
   ```bash
   cd C:\Users\Acer\Desktop\fm
   ```

2. **Ustaw zmienną środowiskową PYTHONPATH:**
   - **Command Prompt (cmd):**
     ```cmd
     set PYTHONPATH=.
     ```
   - **PowerShell:**
     ```powershell
     $env:PYTHONPATH = "."
     ```

3. **Uruchom API serwer:**
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

4. **W nowym terminalu uruchom menu CLI:**
   ```bash
   python -m app.menu.main
   ```

### Opcja 2: Uruchomienie w Dockerze

1. **Uruchom bazę danych (jeśli potrzebna):**
   ```bash
   111.bat
   ```

2. **Uruchom API serwer:**
   ```bash
   000.bat
   ```

3. **Uruchom menu CLI:**
   ```bash
   222.bat
   ```

## 📋 Menu Główne

Po uruchomieniu menu CLI zobaczysz następujące opcje:

### 1. Setup Users
- Konfiguracja użytkowników systemu
- Tworzenie 2 głównych użytkowników + użytkownika "Other"
- **Wymagane przed pierwszym użyciem**

### 2. Add Manual Expense
- Dodawanie wydatków ręcznych
- Wybór kategorii, daty, płatnika
- Automatyczne rozliczenie między użytkownikami

### 3. Parse Receipts
- Przetwarzanie plików JSON z paragonami
- Automatyczne wykrywanie duplikatów
- Przenoszenie plików do odpowiednich folderów

### 4. Count Receipts
- Liczenie i analiza paragonów
- Podział kosztów między użytkowników

### 5. View Receipts
- Przeglądanie paragonów według różnych kryteriów
- Filtrowanie po dacie, sklepie, użytkowniku

### 6. View Statistics
- Statystyki wydatków
- Analiza miesięczna
- Podsumowania kategorii

### 7. Settlement
- Rozliczenia między użytkownikami
- Podsumowanie kto komu ile płaci

### 8. Find receipt / expense
- Wyszukiwanie paragonów i wydatków
- Filtrowanie po różnych kryteriach

## 🌐 API Endpoints

### Formularz do wrzucania paragonów
```
GET http://localhost:8000/upload-form/
```

### Endpoint do wrzucania plików
```
POST http://localhost:8000/upload/
```
**Wymagane nagłówki:**
- `X-APP-PASSWORD: your_password`

## 📁 Struktura Katalogów

```
data/
├── to_check/          # Paragony do przetworzenia
├── parsed/            # Przetworzone paragony
└── rejected/          # Odrzucone paragony (błędy)
```

## ⚙️ Konfiguracja

### Plik .env
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
Aplikacja wymaga PostgreSQL. Opcje:
- **Lokalna instalacja PostgreSQL**
- **Kontener Docker** (111.bat)
- **Zdalna baza** (Render.com, Heroku, AWS RDS)

## 🔧 Rozwiązywanie Problemów

### Błąd "ModuleNotFoundError: No module named 'app'"
**Rozwiązanie:**
1. Upewnij się, że jesteś w katalogu głównym projektu
2. Ustaw `PYTHONPATH=.`
3. Uruchamiaj zawsze z `app.main:app`

### Błąd połączenia z bazą danych
**Rozwiązanie:**
1. Sprawdź czy baza danych jest uruchomiona
2. Zweryfikuj zmienne środowiskowe w `.env`
3. Sprawdź czy port 5432 jest dostępny

### Błąd "No such file or directory"
**Rozwiązanie:**
- Ścieżki są już naprawione - używają relatywnych ścieżek
- Upewnij się, że katalogi `data/to_check`, `data/parsed`, `data/rejected` istnieją

## 📝 Logi

- **API serwer:** Wyświetlane w terminalu
- **Parser:** `logs/parser_debug.log`
- **Aplikacja:** `finance_manager.log`

## 🐳 Docker Commands

### Pełne uruchomienie
```bash
# Baza danych
111.bat

# API serwer
000.bat

# Menu CLI
222.bat
```

### Własne polecenia
```bash
# Budowanie
docker-compose build

# Uruchomienie
docker-compose up -d

# Logi
docker-compose logs -f

# Zatrzymanie
docker-compose down
```

## 🌐 Deployment na Render.com

### Konfiguracja usługi
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### Zmienne środowiskowe
Dodaj wszystkie zmienne z pliku `.env` w panelu Render.com

### Baza danych
Możesz użyć:
- Render PostgreSQL (automatyczne połączenie)
- Zewnętrznej bazy danych (podaj dane w zmiennych środowiskowych)

## 💡 Wskazówki

1. **Pierwsze uruchomienie:** Zawsze uruchom "Setup Users" przed użyciem
2. **Paragony:** Wrzucaj pliki JSON do `data/to_check/`
3. **Backup:** Regularnie rób kopie zapasowe bazy danych
4. **Logi:** Sprawdzaj logi w przypadku problemów
5. **Importy:** Wszystkie importy używają prefiksu `app.` - nie zmieniaj tego!

## 🔄 Aktualizacje

Po aktualizacji kodu:
1. Zatrzymaj aplikację (`Ctrl+C` lub `docker-compose down`)
2. Uruchom ponownie według instrukcji powyżej
3. Sprawdź logi pod kątem błędów

---

**Uwaga:** Projekt używa uniwersalnych importów pakietowych (`app.`), co zapewnia kompatybilność między lokalnym uruchomieniem, Dockerem i Render.com. 