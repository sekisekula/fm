# Finance Manager - Docker Usage

## New Workflow (Recommended)

### 1. Start API Server
```bash
start_api_docker.bat
```
This starts the FastAPI server in Docker. The API will be available at:
- http://localhost:8000 (API)
- http://localhost:8000/upload-form/ (Upload form)

### 2. Run Interactive Menu (when needed)
```bash
run_menu_docker.bat
```
This runs the interactive menu inside the running container. You can:
- Set up users (first time only)
- Add manual expenses
- Process receipts
- View statistics
- etc.

### 3. Stop Server
```bash
docker-compose down
```

## Old Workflow (Still Available)

### Start in Menu Mode
```bash
start_menu_docker.bat
```
This starts the container in CLI mode and automatically runs the menu.

## Key Benefits of New Workflow

1. **Separation of Concerns**: API server runs independently of menu
2. **No User Input on Startup**: Container starts cleanly without requiring user interaction
3. **Flexible Access**: Run menu only when needed
4. **Better for Automation**: API can be used by other applications

## First Time Setup

When you first run the menu, you'll need to set up users:
1. Run `run_menu_docker.bat`
2. Select "Setup Users" from the menu
3. Enter names for two main users
4. Confirm the "Other" user name

## Environment Variables

- `APP_MODE=api` - Start FastAPI server (default)
- `APP_MODE=cli` - Start in menu mode (old way) 

---

## Jak naprawić?

### Opcja 1: Wykonuj cały plik naraz (z powrotem do starego podejścia)
- Możesz użyć bezpośrednio `engine.raw_connection()` i wykonać `cursor.execute(sql_script)` (czyli podejście zbliżone do psycopg2, ale przez SQLAlchemy).

### Opcja 2: Użyj narzędzi migracyjnych (np. Alembic)
- To najlepsza praktyka, ale wymaga wdrożenia migracji.

### Opcja 3: Szybka poprawka – wykonuj cały plik naraz przez `connection.connection.cursor()`
- To pozwala wykonać skrypt z blokami DO $$ ... $$.

---

## Proponowana szybka poprawka

Zmień funkcję `create_tables` na:

```python
<code_block_to_apply_changes_from>
```

**To podejście działa, bo korzysta z kursora DBAPI (psycopg2) przez SQLAlchemy, więc obsługuje bloki DO $$ ... $$ i wiele poleceń naraz.**

---

**Chcesz, żebym od razu wprowadził tę poprawkę?** 