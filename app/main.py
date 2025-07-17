# Standard library imports
import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager
import time
import random
import string
from datetime import datetime, date
from decimal import Decimal
import json as _json

# Third-party imports
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Depends, Request, HTTPException, status, Form, Response
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel
from sqlalchemy import text, or_

# Local imports - teraz powinny działać w obu środowiskach
from app.config import Config
from app.db.database import create_tables, ensure_special_user_other
from app.db.session import SessionLocal
from app.menu.models import DatabaseManager
from app.menu.handlers import MenuHandlers
from app.menu.views import MenuView
from app.parser import process_receipt_data

# Load environment variables early
load_dotenv()

# Konfiguracja i zmienne globalne pozostają bez zmian
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Pydantic models for API
class ManualExpenseModel(BaseModel):
    description: str
    category: str = "Other"
    amount: float
    date: str
    payer_user_id: int
    share1: int
    share2: int

class ReceiptFilterModel(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    user_id: Optional[int] = None
    store_name: Optional[str] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Logika startowa serwera
    logger.info("Application startup...")
    
    # Utworzenie tabel w bazie danych
    try:
        create_tables()
        with SessionLocal() as db:
            ensure_special_user_other(db)
        logger.info("Database tables verified/created successfully.")
    except Exception as e:
        logger.error(f"FATAL: Could not create database tables. Error: {e}")
        # W przypadku błędu bazy danych, można przerwać start
        raise RuntimeError("Database initialization failed") from e
    
    # Przetworzenie istniejących plików przy starcie
    logger.info("Processing any existing JSON files from data/to_check...")
    if os.getenv("PROCESS_TO_CHECK_ON_STARTUP", "0") == "1":
        files_to_process = list(Path(Config.UPLOAD_FOLDER).glob("*.json"))
        if not files_to_process:
            logger.info("No existing JSON files to process.")
        else:
            for file_path in files_to_process:
                try:
                    # Tutaj był wywoływany process_receipt_file(file_path), usuwamy ten kod
                    logger.info(f"(Parser disabled in API) Skipping processing for {file_path.name}")
                except Exception as e:
                    logger.error(f"Error processing existing file {file_path.name} on startup: {e}", exc_info=True)
                    logger.error(f"File path: {file_path}, Error type: {type(e).__name__}")
    else:
        logger.info("Skipping auto-processing of JSON receipts on startup (PROCESS_TO_CHECK_ON_STARTUP != 1)")

    logger.info("Application startup complete. Server is ready.")
    yield
    # Logika zamykania aplikacji (jeśli potrzebna)
    logger.info("Application shutdown.")

app = FastAPI(
    title="Finance Manager API",
    description="API for managing personal finances, including parsing receipts and web interface.",
    version="1.0.0",
    lifespan=lifespan,
)

def get_password():
    password = os.getenv("APP_PASSWORD")
    if not password:
        logger.warning("APP_PASSWORD environment variable not set. Using default password.")
        return "default_password_change_me"
    return password

def verify_password(request: Request):
    password = request.headers.get("X-APP-PASSWORD")
    if password != get_password():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password",
        )

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- ALERT O NIEPRZYPISANYCH PŁATNOŚCIACH ---
def get_unassigned_payments_alert():
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT COUNT(DISTINCT r.payment_name)
            FROM receipts r
            LEFT JOIN user_payments up ON r.payment_name = up.payment_name
            WHERE up.payment_name IS NULL
        """)).scalar()
        unassigned_count = result or 0
    finally:
        db.close()
    if unassigned_count:
        return f"""
        <div style='background:#fff3cd;color:#856404;padding:18px 24px;border-radius:8px;margin-bottom:18px;border:1px solid #ffeeba;text-align:center;font-size:1.1em;'>
            Masz <b>{unassigned_count}</b> nieprzypisanych nazw płatności!
            <a href='/assign-payments/' style='background:#007bff;color:#fff;padding:8px 18px;border-radius:6px;text-decoration:none;margin-left:18px;'>Przypisz płatności</a>
        </div>
        """
    return ""

# Main web interface
@app.get("/", response_class=HTMLResponse)
async def main_interface():
    alert_html = get_unassigned_payments_alert()
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Finance Manager</title>
        <meta name='viewport' content='width=device-width, initial-scale=1'>
        <style>
            body {{ font-family: Arial, sans-serif; background: #f5f5f5; }}
            .container {{ max-width: 700px; margin: 30px auto; background: #fff; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); padding: 24px; }}
            h1 {{ color: #222; text-align: center; margin-bottom: 0; }}
            .menu-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 18px; margin: 30px 0; }}
            .menu-item {{ background: #f8f9fa; border-radius: 8px; padding: 24px; text-align: center; font-size: 1.2em; color: #007bff; text-decoration: none; box-shadow: 0 1px 4px rgba(0,0,0,0.04); transition: background 0.2s; }}
            .menu-item:hover {{ background: #e2e6ea; }}
        </style>
    </head>
    <body>
        <div class='container'>
            {alert_html}
            <h1>💰 Finance Manager</h1>
            <p style='text-align: center; color: #666;'>Zarządzaj swoimi finansami z dowolnego urządzenia</p>
            <div class='menu-grid'>
                <a href='/upload-form/' class='menu-item'>📄 Wrzuć Paragony</a>
                <a href='/add-expense-form/' class='menu-item'>➕ Dodaj Wydatek</a>
                <a href='/view-statistics/' class='menu-item'>📊 Statystyki</a>
                <a href='/browse-receipts/' class='menu-item'>🧾 Paragony/wydatki</a>
                <a href='/settlement/' class='menu-item'>💸 Rozliczenia</a>
                <a href='/users/' class='menu-item'>👥 Użytkownicy</a>
            </div>
            <div style='text-align: center; margin-top: 30px;'>
                <p><strong>API Endpoints:</strong></p>
                <p><a href='/docs'>📚 Dokumentacja API</a></p>
                <p><a href='/upload-form/'>📤 Formularz Upload</a></p>
            </div>
        </div>
    </body>
    </html>
    """

@app.post("/upload/")
async def upload_files(files: List[UploadFile] = File(..., description="Upload up to 500 JSON files at once", max_items=500)):
    logger.info(f"Received {len(files)} files for upload.")
    if len(files) > 500:
        return JSONResponse(status_code=400, content={"detail": "You can upload up to 500 files at once."})
    results = []
    for file in files:
        if file.filename and file.filename.endswith(".json"):
            orig_filename = file.filename
            try:
                content = await file.read()
                try:
                    data = _json.loads(content)
                    process_receipt_data(data)
                    results.append({
                        "filename": orig_filename,
                        "status": "success",
                        "detail": "Paragon zapisany do bazy."
                    })
                except Exception as ve:
                    results.append({
                        "filename": orig_filename,
                        "status": "error",
                        "detail": f"Błąd: {ve}"
                    })
            except Exception as e:
                results.append({
                    "filename": orig_filename,
                    "status": "error",
                    "detail": f"Błąd przetwarzania: {e}"
                })
        else:
            results.append({
                "filename": file.filename,
                "status": "skipped",
                "detail": "Unsupported file format (expected .json)."
            })
    return JSONResponse(content={"results": results})

# Formularz do wysyłania plików (bez zmian)
UPLOAD_FORM = """
<!DOCTYPE html>
<html>
<head>
    <title>Upload Files</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
        .container { max-width: 600px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; text-align: center; }
        .form-group { margin: 15px 0; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
        button { background: #007bff; color: white; padding: 12px 20px; border: none; border-radius: 4px; cursor: pointer; width: 100%; font-size: 16px; }
        button:hover { background: #0056b3; }
        #status { margin-top: 20px; }
        .back-btn { background: #6c757d; color: white; padding: 8px 15px; border: none; border-radius: 4px; text-decoration: none; display: inline-block; margin: 10px 0; }
    </style>
</head>
<body>
    <div class="container">
        <a href="/" class="back-btn">← Powrót do menu</a>
        <h1>📄 Wrzuć Paragony</h1>
        <p>Możesz wrzucić do 500 plików JSON z paragonami na raz.</p>
        <form id="uploadForm" enctype="multipart/form-data">
            <div class="form-group">
                <label for="files">Wybierz pliki:</label>
                <input type="file" id="files" name="files" multiple accept=".json">
            </div>
            <button type="submit">Wrzuć Pliki</button>
        </form>
        <div id="status"></div>
    </div>
    <script>
    document.addEventListener('DOMContentLoaded', function() {
        document.getElementById('uploadForm').addEventListener('submit', uploadFiles);
    });
    async function uploadFiles(event) {
        event.preventDefault();
        const filesInput = document.getElementById('files');
        const statusDiv = document.getElementById('status');
        statusDiv.innerHTML = '<span style="color:blue">Wrzucanie, proszę czekać...</span>';
        const files = filesInput.files;
        if (!files.length) {
            statusDiv.innerHTML = '<span style="color:red">Proszę wybrać przynajmniej jeden plik.</span>';
            return;
        }
        if (files.length > 500) {
            statusDiv.innerHTML = '<span style="color:red">Możesz wrzucić maksymalnie 500 plików na raz.</span>';
            return;
        }
        const formData = new FormData();
        for (let i = 0; i < files.length; i++) {
            formData.append('files', files[i]);
        }
        try {
            const response = await fetch('/upload/', {
                method: 'POST',
                body: formData,
            });
            let result;
            try {
                result = await response.json();
            } catch (jsonErr) {
                statusDiv.innerHTML = '<span style="color:red">Serwer zwrócił nieprawidłową odpowiedź.</span>';
                return;
            }
            if (response.ok) {
                let msg = '<span style="color:green">Wrzucanie udane!</span><br><pre>' + JSON.stringify(result, null, 2) + '</pre>';
                statusDiv.innerHTML = msg;
            } else {
                let msg = '<span style="color:red">Błąd wrzucania: ' + (result.detail || 'Nieznany błąd') + '</span>';
                statusDiv.innerHTML = msg;
            }
        } catch (err) {
            statusDiv.innerHTML = '<span style="color:red">Błąd sieci lub serwera: ' + err + '</span>';
        }
    }
    </script>
</body>
</html>
"""

@app.get("/upload-form/", response_class=HTMLResponse)
async def upload_form():
    logger.info("Serving upload form.")
    return UPLOAD_FORM

# Nowe endpointy API dla funkcji menu

@app.get("/add-expense-form/", response_class=HTMLResponse)
async def add_expense_form():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dodaj Wydatek</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
            .container { max-width: 600px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h1 { color: #333; text-align: center; }
            .form-group { margin: 15px 0; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input, select, textarea { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
            button { background: #28a745; color: white; padding: 12px 20px; border: none; border-radius: 4px; cursor: pointer; width: 100%; font-size: 16px; }
            button:hover { background: #218838; }
            .back-btn { background: #6c757d; color: white; padding: 8px 15px; border: none; border-radius: 4px; text-decoration: none; display: inline-block; margin: 10px 0; }
            #result { margin-top: 20px; }
            .alert { background:#fff3cd;color:#856404;padding:18px 24px;border-radius:8px;margin-bottom:18px;border:1px solid #ffeeba;text-align:center;font-size:1.1em; }
        </style>
    </head>
    <body>
        <div class="container">
            <a href="/" class="back-btn">← Powrót do menu</a>
            <div id="userAlert"></div>
            <h1>➕ Dodaj Wydatek</h1>
            <form id="expenseForm">
                <div class="form-group">
                    <label for="description">Opis:</label>
                    <input type="text" id="description" name="description" required>
                </div>
                <div class="form-group">
                    <label for="category">Kategoria:</label>
                    <input type="text" id="category" name="category" value="Other">
                    <div id="category-buttons" style="margin-top: 5px;"></div>
                </div>
                <div class="form-group">
                    <label for="amount">Kwota (PLN):</label>
                    <input type="number" id="amount" name="amount" step="0.01" required>
                </div>
                <div class="form-group">
                    <label for="date">Data:</label>
                    <input type="date" id="date" name="date" required>
                </div>
                <div class="form-group">
                    <label for="payer">Kto zapłacił:</label>
                    <div id="payer-buttons" style="display: flex; gap: 10px; flex-wrap: wrap;"></div>
                    <input type="hidden" id="payer_user_id" name="payer_user_id" required>
                    <div id="payer-warning" style="color: var(--danger); margin-top: 5px;"></div>
                </div>
                <div class="form-group" id="shares-group">
                    <!-- Dynamic shares fields -->
                </div>
                <div class="form-group">
                    <div id="shares-summary" style="margin-top: 10px; font-weight: bold;"></div>
                </div>
                <button type="submit" id="submit-btn">
                    <span id="submit-text">Dodaj Wydatek</span>
                    <span id="spinner" style="display:none; margin-left:8px; vertical-align:middle;">
                        <svg width="20" height="20" viewBox="0 0 50 50"><circle cx="25" cy="25" r="20" fill="none" stroke="#007bff" stroke-width="5" stroke-linecap="round" stroke-dasharray="31.4 31.4" transform="rotate(-90 25 25)"><animateTransform attributeName="transform" type="rotate" from="0 25 25" to="360 25 25" dur="1s" repeatCount="indefinite"/></circle></svg>
                    </span>
                </button>
            </form>
            <div id="result"></div>
        </div>
        <script>
        let canAddExpense = false;
        async function checkUsers() {
            const res = await fetch('/api/users');
            const users = await res.json();
            let has1 = false, has2 = false;
            users.forEach(u => { if (u.id === 1) has1 = true; if (u.id === 2) has2 = true; });
            const alertDiv = document.getElementById('userAlert');
            const submitBtn = document.getElementById('submit-btn');
            if (!has1 || !has2) {
                alertDiv.innerHTML = `<div class='alert'>Brakuje wymaganych użytkowników (ID 1 i 2)! Dodaj ich, aby móc dodawać wydatki.</div>`;
                canAddExpense = false;
                submitBtn.disabled = true;
            } else {
                alertDiv.innerHTML = '';
                canAddExpense = true;
                submitBtn.disabled = false;
            }
        }
        document.addEventListener('DOMContentLoaded', function() {
            checkUsers();
            loadUserNamesForShares();
            loadPayerButtons();
            // Ustaw dzisiejszą datę jako domyślną
            const dateInput = document.getElementById('date');
            if (dateInput) {
                const today = new Date();
                const yyyy = today.getFullYear();
                const mm = String(today.getMonth() + 1).padStart(2, '0');
                const dd = String(today.getDate()).padStart(2, '0');
                dateInput.value = `${yyyy}-${mm}-${dd}`;
            }
            // Obsługa submit formularza Dodaj Wydatek
            const form = document.getElementById('expenseForm');
            if (form) {
                form.onsubmit = async function(e) {
                    e.preventDefault();
                    if (!document.getElementById('payer_user_id').value) {
                        alert('Wybierz kto zapłacił!');
                        return;
                    }
                    const formData = new FormData(form);
                    const data = {};
                    for (const [key, value] of formData.entries()) {
                        data[key] = value;
                    }
                    try {
                        const res = await fetch('/api/add-expense', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(data)
                        });
                        const result = await res.json();
                        if (res.ok) {
                            alert('Wydatek został dodany!');
                            form.reset();
                        } else {
                            alert('Błąd: ' + (result.detail || 'Nie udało się dodać wydatku.'));
                        }
                    } catch (err) {
                        alert('Błąd połączenia z serwerem.');
                    }
                }
            }
        });
        async function loadUserNamesForShares() {
            const res = await fetch('/api/users');
            const users = await res.json();
            const user1 = users.find(u => u.id === 1);
            const user2 = users.find(u => u.id === 2);
            const group = document.getElementById('shares-group');
            if (!user1 || !user2) {
                group.innerHTML = '<div style="color:#dc3545;">Brak wymaganych użytkowników (ID 1 i 2).</div>';
                return;
            }
            group.innerHTML = `
                <div style="display:flex; gap:16px; align-items:center;">
                    <div style="flex:1;">
                        <label for='share1'>Udział dla <b>${user1.name}</b> (%):</label>
                        <input type='number' id='share1' name='share1' min='0' max='100' value='50' required style='width:100%;'>
                    </div>
                    <div style="flex:1;">
                        <label for='share2'>Udział dla <b>${user2.name}</b> (%):</label>
                        <input type='number' id='share2' name='share2' min='0' max='100' value='50' required style='width:100%;' readonly>
                    </div>
                </div>
                <div id='shares-pln' style='margin-top:8px;color:#555;font-size:1.08em;'></div>
            `;
            // Automatyczne uzupełnianie udziału drugiego użytkownika
            const share1 = document.getElementById('share1');
            const share2 = document.getElementById('share2');
            const amountInput = document.getElementById('amount');
            const sharesPln = document.getElementById('shares-pln');
            function updateSharesPln() {
                const amount = parseFloat(amountInput.value.replace(',', '.'));
                const s1 = parseFloat(share1.value.replace(',', '.'));
                const s2 = parseFloat(share2.value.replace(',', '.'));
                if (!isNaN(amount) && amount > 0 && !isNaN(s1) && !isNaN(s2)) {
                    const v1 = Math.round(amount * s1) / 100;
                    const v2 = Math.round(amount * s2) / 100;
                    sharesPln.innerHTML = `${user1.name}: <b>${v1.toFixed(2)} PLN</b> &nbsp;&nbsp; ${user2.name}: <b>${v2.toFixed(2)} PLN</b>`;
                } else {
                    sharesPln.innerHTML = '';
                }
            }
            share1.addEventListener('input', function() {
                let val = parseFloat(share1.value.replace(',', '.'));
                if (isNaN(val) || val < 0) val = 0;
                if (val > 100) val = 100;
                share1.value = val;
                share2.value = Math.max(0, Math.min(100, 100 - val));
                updateSharesPln();
            });
            amountInput.addEventListener('input', updateSharesPln);
            // Inicjalizacja na starcie
            updateSharesPln();
        }
        // ...reszta kodu...
        async function loadPayerButtons() {
            const res = await fetch('/api/users');
            const users = await res.json();
            const user1 = users.find(u => u.id === 1);
            const user2 = users.find(u => u.id === 2);
            const payerDiv = document.getElementById('payer-buttons');
            const payerInput = document.getElementById('payer_user_id');
            if (!user1 || !user2) {
                payerDiv.innerHTML = '<div style="color:#dc3545;">Brak wymaganych użytkowników (ID 1 i 2).</div>';
                payerInput.value = '';
                return;
            }
            payerDiv.innerHTML = `
                <label style='display:flex;align-items:center;gap:8px;'>
                    <input type='radio' name='payer_radio' value='${user1.id}'> ${user1.name}
                </label>
                <label style='display:flex;align-items:center;gap:8px;'>
                    <input type='radio' name='payer_radio' value='${user2.id}'> ${user2.name}
                </label>
            `;
            // Obsługa wyboru
            payerDiv.querySelectorAll('input[type=radio][name=payer_radio]').forEach(radio => {
                radio.addEventListener('change', function() {
                    payerInput.value = this.value;
                });
            });
        }
        // --- Poprawiona pojedyncza inicjalizacja ---
        document.addEventListener('DOMContentLoaded', function() {
            checkUsers();
            loadUserNamesForShares();
            loadPayerButtons();
            // Ustaw dzisiejszą datę jako domyślną
            const dateInput = document.getElementById('date');
            if (dateInput) {
                const today = new Date();
                const yyyy = today.getFullYear();
                const mm = String(today.getMonth() + 1).padStart(2, '0');
                const dd = String(today.getDate()).padStart(2, '0');
                dateInput.value = `${yyyy}-${mm}-${dd}`;
            }
            // Obsługa submit formularza Dodaj Wydatek
            const form = document.getElementById('expenseForm');
            if (form) {
                form.onsubmit = async function(e) {
                    e.preventDefault();
                    if (!document.getElementById('payer_user_id').value) {
                        alert('Wybierz kto zapłacił!');
                        return;
                    }
                    const formData = new FormData(form);
                    const data = {};
                    for (const [key, value] of formData.entries()) {
                        data[key] = value;
                    }
                    try {
                        const res = await fetch('/api/add-expense', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(data)
                        });
                        const result = await res.json();
                        if (res.ok) {
                            alert('Wydatek został dodany!');
                            form.reset();
                        } else {
                            alert('Błąd: ' + (result.detail || 'Nie udało się dodać wydatku.'));
                        }
                    } catch (err) {
                        alert('Błąd połączenia z serwerem.');
                    }
                }
            }
        });
        </script>
    </body>
    </html>
    """

@app.get("/view-statistics/", response_class=HTMLResponse)
async def view_statistics_page():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Statystyki</title>
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
        <script src=\"https://cdn.jsdelivr.net/npm/chart.js\"></script>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
            .container { max-width: 900px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h1 { color: #333; text-align: center; }
            .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }
            .stat-card { background: #f8f9fa; padding: 15px; border-radius: 5px; text-align: center; }
            .stat-value { font-size: 24px; font-weight: bold; color: #007bff; }
            .back-btn { background: #6c757d; color: white; padding: 8px 15px; border: none; border-radius: 4px; text-decoration: none; display: inline-block; margin: 10px 0; }
            .form-group { margin: 15px 0; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
            button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
            button:hover { background: #0056b3; }
            #statsResult { margin-top: 20px; }
            .quick-range-btn { margin-right: 8px; margin-bottom: 8px; padding: 6px 14px; border-radius: 4px; border: 1px solid #007bff; background: #fff; color: #007bff; cursor: pointer; font-size: 13px; }
            .quick-range-btn.active, .quick-range-btn:hover { background: #007bff; color: #fff; }
            .chart-container { margin: 30px 0; background: #f8f9fa; border-radius: 8px; padding: 20px; }
            .category-table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            .category-table th, .category-table td { border: 1px solid #ddd; padding: 8px; text-align: center; }
            .category-table th { background: #f0f0f0; }
        </style>
    </head>
    <body>
        <div class=\"container\">
            <a href=\"/\" class=\"back-btn\">← Powrót do menu</a>
            <h1>📊 Statystyki Wydatków</h1>
            <div class=\"form-group\">
                <label>Zakres dat:</label>
                <input type=\"date\" id=\"startDate\" style=\"width:auto;display:inline-block;\"> do
                <input type=\"date\" id=\"endDate\" style=\"width:auto;display:inline-block;\">
                <div style=\"margin-top:8px;\">
                    <button class=\"quick-range-btn\" data-range=\"this-month\">Bieżący miesiąc</button>
                    <button class=\"quick-range-btn\" data-range=\"last-month\">Poprzedni miesiąc</button>
                    <button class=\"quick-range-btn\" data-range=\"this-year\">Bieżący rok</button>
                    <button class=\"quick-range-btn\" data-range=\"all\">Wszystko</button>
                </div>
            </div>
            <button onclick=\"loadStatistics()\">Załaduj Statystyki</button>
            <div id=\"statsResult\"></div>
            <div class=\"chart-container\">
                <canvas id=\"categoryPie\" height=\"48\"></canvas>
            </div>
            <div class=\"chart-container\">
                <canvas id=\"userBar\" height=\"120\"></canvas>
            </div>
            <div id=\"categoryTable\"></div>
        </div>
        <script>
        // ... date range logic as before ...
        function getDateRange(range) { /* ... unchanged ... */ }
        document.querySelectorAll('.quick-range-btn').forEach(btn => { /* ... unchanged ... */ });
        document.getElementById('startDate').addEventListener('change', () => loadStatistics());
        document.getElementById('endDate').addEventListener('change', () => loadStatistics());
        let categoryPie, userBar;
        async function loadStatistics() {
            const start = document.getElementById('startDate').value;
            const end = document.getElementById('endDate').value;
            let url = '/api/statistics';
            const params = [];
            if (start) params.push('start_date=' + encodeURIComponent(start));
            if (end) params.push('end_date=' + encodeURIComponent(end));
            if (params.length) url += '?' + params.join('&');
            try {
                const response = await fetch(url);
                const stats = await response.json();
                const resultDiv = document.getElementById('statsResult');
                if (response.ok) {
                    resultDiv.innerHTML = `
                        <div class=\"stats-grid\">
                            <div class=\"stat-card\">
                                <div class=\"stat-value\">${stats.total_receipts || 0}</div>
                                <div>Wszystkie paragony</div>
                            </div>
                            <div class=\"stat-card\">
                                <div class=\"stat-value\">${stats.total_expenses || 0}</div>
                                <div>Wszystkie wydatki</div>
                            </div>
                            <div class=\"stat-card\">
                                <div class=\"stat-value\">${(stats.total_amount || 0).toFixed(2)} PLN</div>
                                <div>Łączna kwota</div>
                            </div>
                        </div>
                        <h3>Ostatnie wydatki:</h3>
                        <div style=\"max-height: 300px; overflow-y: auto;\">
                            ${(stats.recent_expenses || []).map(exp => `
                                <div style=\"padding: 10px; border-bottom: 1px solid #eee;\">
                                    <strong>${exp.date}</strong> - ${exp.description} (${exp.amount} PLN)
                                </div>
                            `).join('')}
                        </div>
                    `;
                    // Wykres kołowy wg kategorii (manual_expenses)
                    const catLabels = Object.keys(stats.category_sums || {});
                    const catData = Object.values(stats.category_sums || {});
                    if (categoryPie) categoryPie.destroy();
                    categoryPie = new Chart(document.getElementById('categoryPie').getContext('2d'), {
                        type: 'pie',
                        data: { labels: catLabels, datasets: [{ data: catData, backgroundColor: [
                            '#007bff','#28a745','#ffc107','#dc3545','#17a2b8','#6c757d','#6610f2','#fd7e14','#20c997','#e83e8c'] }] },
                        options: { plugins: { legend: { position: 'bottom' } }, responsive: true }
                    });
                    // Wykres słupkowy użytkownik 1 vs 2
                    if (userBar) userBar.destroy();
                    userBar = new Chart(document.getElementById('userBar').getContext('2d'), {
                        type: 'bar',
                        data: { labels: ['Użytkownik 1', 'Użytkownik 2'], datasets: [{ label: 'Suma wydatków', data: stats.user_sums || [0,0], backgroundColor: ['#007bff','#28a745'] }] },
                        options: { plugins: { legend: { display: false } }, responsive: true }
                    });
                    // Tabela udziałów procentowych kategorii i użytkowników
                    let tableHtml = `<table class='category-table'><thead><tr><th>Kategoria</th><th>Udział %</th><th>Użytkownik 1</th><th>Użytkownik 2</th></tr></thead><tbody>`;
                    (stats.category_shares || []).forEach(row => {
                        tableHtml += `<tr><td>${row.category}</td><td>${row.percent.toFixed(1)}%</td><td>${row.user1.toFixed(2)} PLN</td><td>${row.user2.toFixed(2)} PLN</td></tr>`;
                    });
                    tableHtml += '</tbody></table>';
                    document.getElementById('categoryTable').innerHTML = tableHtml;
                } else {
                    resultDiv.innerHTML = '<div style="color: red; padding: 10px; background: #f8d7da; border-radius: 4px;">Błąd: ' + (stats.detail || 'Nieznany błąd') + '</div>';
                }
            } catch (error) {
                document.getElementById('statsResult').innerHTML = '<div style="color: red; padding: 10px; background: #f8d7da; border-radius: 4px;">Błąd sieci: ' + error.message + '</div>';
            }
        }
        window.onload = function() { const {start, end} = getDateRange('this-month'); document.getElementById('startDate').value = start; document.getElementById('endDate').value = end; document.querySelector('.quick-range-btn[data-range="this-month"]').classList.add('active'); loadStatistics(); };
        </script>
    </body>
    </html>
    """

@app.get("/view-receipts/", response_class=HTMLResponse)
async def view_receipts_page():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Paragony</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
            .container { max-width: 1000px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h1 { color: #333; text-align: center; }
            .back-btn { background: #6c757d; color: white; padding: 8px 15px; border: none; border-radius: 4px; text-decoration: none; display: inline-block; margin: 10px 0; }
            .form-group { margin: 15px 0; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input, select { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
            button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
            button:hover { background: #0056b3; }
            .receipts-table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            .receipts-table th, .receipts-table td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
            .receipts-table th { background-color: #f8f9fa; font-weight: bold; }
            #receiptsResult { margin-top: 20px; }
        </style>
    </head>
    <body>
        <div class="container">
            <a href="/" class="back-btn">← Powrót do menu</a>
            <h1>🧾 Paragony</h1>
            
            <button onclick="loadReceipts()">Załaduj Paragony</button>
            
            <div id="receiptsResult"></div>
        </div>
        <script>
        async function loadReceipts() {
            try {
                const response = await fetch('/api/receipts');
                
                const receipts = await response.json();
                const resultDiv = document.getElementById('receiptsResult');
                
                if (response.ok) {
                    resultDiv.innerHTML = `
                        <table class="receipts-table">
                            <thead>
                                <tr>
                                    <th>Data</th>
                                    <th>Sklep</th>
                                    <th>Kwota</th>
                                    <th>Kto zapłacił</th>
                                    <th>Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${(receipts || []).map(receipt => `
                                    <tr>
                                        <td>${receipt.date || 'N/A'}</td>
                                        <td>${receipt.store_name || 'N/A'}</td>
                                        <td>${(receipt.final_price || 0).toFixed(2)} PLN</td>
                                        <td>${receipt.payment_name || 'N/A'}</td>
                                        <td>${receipt.is_settled ? 'Rozliczony' : 'Oczekujący'}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    `;
                } else {
                    resultDiv.innerHTML = '<div style="color: red; padding: 10px; background: #f8d7da; border-radius: 4px;">Błąd: ' + (receipts.detail || 'Nieznany błąd') + '</div>';
                }
            } catch (error) {
                document.getElementById('receiptsResult').innerHTML = '<div style="color: red; padding: 10px; background: #f8d7da; border-radius: 4px;">Błąd sieci: ' + error.message + '</div>';
            }
        }
        </script>
    </body>
    </html>
    """

@app.get("/settlement/", response_class=HTMLResponse)
async def settlement_page():
    with open("app/templates/settlement_summary.html", encoding="utf-8") as f:
        summary_html = f.read()
    # --- USUWANIE 'Other' z podsumowań i tabelek ---
    # (Zakładam, że summary_html generowane jest w Pythonie, więc należy tam usunąć wiersze z 'Other')
    # Jeśli summary_html generowane jest po stronie JS, to filtruj w JS.
    # Jeśli nie masz wpływu na summary_html, to musisz poprawić generowanie tego pliku.
    # Poniżej poprawki w JS dla nierozliczonych paragonów i wydatków manualnych:
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Rozliczenia</title>
        <meta name='viewport' content='width=device-width, initial-scale=1'>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
            .container {{ max-width: 900px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            h1 {{ color: #333; text-align: center; }}
            .back-btn {{ background: #6c757d; color: white; padding: 8px 15px; border: none; border-radius: 4px; text-decoration: none; display: inline-block; margin: 10px 0; }}
        </style>
    </head>
    <body>
        <div class='container'>
            <a href='/' class='back-btn'>← Powrót do menu</a>
            <h1>💸 Rozliczenia</h1>
            {summary_html}
        </div>
    </body>
    </html>
"""

@app.get("/browse-receipts/", response_class=HTMLResponse)
async def browse_receipts_page():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Paragony/wydatki</title>
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
        <style>
            :root {
                --primary: #007bff;
                --success: #28a745;
                --warning: #ffc107;
                --danger: #dc3545;
                --info: #17a2b8;
                --bg: #f5f5f5;
                --text: #222;
                --card: #fff;
                --border: #ddd;
                --shadow: 0 2px 10px rgba(0,0,0,0.08);
            }
            .dark {
                --primary: #3399ff;
                --success: #4fd18b;
                --warning: #ffd54f;
                --danger: #ff5c5c;
                --info: #4dd0e1;
                --bg: #181a1b;
                --text: #f1f1f1;
                --card: #23272b;
                --border: #444;
                --shadow: 0 2px 10px rgba(0,0,0,0.25);
            }
            * {
                box-sizing: border-box;
            }
            html, body {
                background: var(--bg);
                color: var(--text);
                font-family: 'Segoe UI', Arial, sans-serif;
                margin: 0;
                padding: 0;
                min-height: 100vh;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
            }
            .header {
                background: var(--card);
                padding: 20px;
                border-radius: 12px;
                box-shadow: var(--shadow);
                margin-bottom: 20px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                flex-wrap: wrap;
                gap: 15px;
            }
            h1 {
                color: var(--primary);
                margin: 0;
                font-size: 1.8em;
            }
            .back-btn {
                background: #6c757d;
                color: #fff;
                padding: 10px 20px;
                border: none;
                border-radius: 8px;
                text-decoration: none;
                display: inline-block;
                font-size: 14px;
                transition: background 0.2s;
            }
            .back-btn:hover {
                background: #495057;
            }
            .theme-toggle-btn {
                background: var(--card);
                color: var(--primary);
                border: 1px solid var(--primary);
                border-radius: 50%;
                width: 45px;
                height: 45px;
                font-size: 20px;
                cursor: pointer;
                box-shadow: var(--shadow);
                transition: all 0.2s;
            }
            .theme-toggle-btn:hover {
                background: var(--primary);
                color: #fff;
            }
            .filters {
                background: var(--card);
                padding: 20px;
                border-radius: 12px;
                box-shadow: var(--shadow);
                margin-bottom: 20px;
            }
            .filter-buttons {
                display: flex;
                gap: 10px;
                flex-wrap: wrap;
            }
            .filter-btn {
                background: var(--card);
                color: var(--text);
                border: 2px solid var(--border);
                border-radius: 8px;
                padding: 10px 20px;
                cursor: pointer;
                transition: all 0.2s;
                font-size: 14px;
                font-weight: 500;
            }
            .filter-btn.active {
                background: var(--primary);
                color: #fff;
                border-color: var(--primary);
            }
            .filter-btn:hover:not(.active) {
                border-color: var(--primary);
                color: var(--primary);
            }
            .receipts-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
                gap: 20px;
                margin-top: 20px;
            }
            .receipt-card {
                background: var(--card);
                border-radius: 12px;
                padding: 20px;
                box-shadow: var(--shadow);
                transition: transform 0.2s, box-shadow 0.2s;
                cursor: pointer;
                border: 1px solid var(--border);
            }
            .receipt-card:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            }
            .receipt-header {
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                margin-bottom: 15px;
            }
            .receipt-date {
                font-size: 0.9em;
                color: var(--text);
                opacity: 0.8;
            }
            .receipt-amount {
                font-size: 1.4em;
                font-weight: bold;
                color: var(--primary);
            }
            .receipt-store {
                font-weight: 600;
                margin-bottom: 8px;
                color: var(--text);
            }
            .receipt-address {
                font-size: 0.9em;
                color: var(--text);
                opacity: 0.7;
                margin-bottom: 10px;
            }
            .receipt-payment {
                font-size: 0.9em;
                color: var(--text);
                opacity: 0.8;
            }
            .receipt-status {
                display: flex;
                gap: 8px;
                margin-top: 12px;
            }
            .status-badge {
                padding: 4px 8px;
                border-radius: 6px;
                font-size: 0.8em;
                font-weight: 500;
            }
            .status-counted {
                background: var(--success);
                color: #fff;
            }
            .status-settled {
                background: var(--info);
                color: #fff;
            }
            .status-pending {
                background: var(--warning);
                color: #000;
            }
            .loading {
                text-align: center;
                padding: 40px;
                color: var(--text);
                opacity: 0.7;
            }
            .spinner {
                display: inline-block;
                width: 30px;
                height: 30px;
                border: 3px solid var(--border);
                border-radius: 50%;
                border-top-color: var(--primary);
                animation: spin 1s ease-in-out infinite;
            }
            @keyframes spin {
                to { transform: rotate(360deg); }
            }
            .no-receipts {
                text-align: center;
                padding: 40px;
                color: var(--text);
                opacity: 0.7;
            }
            .receipt-details-modal {
                display: none;
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0,0,0,0.5);
                z-index: 1000;
                overflow-y: auto;
            }
            .modal-content {
                background: var(--card);
                margin: 20px auto;
                max-width: 1100px; /* was 800px */
                border-radius: 12px;
                box-shadow: 0 4px 30px rgba(0,0,0,0.3);
                position: relative;
            }
            .modal-header {
                padding: 20px;
                border-bottom: 1px solid var(--border);
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .modal-title {
                font-size: 1.4em;
                font-weight: 600;
                color: var(--text);
                margin: 0;
            }
            .close-btn {
                background: none;
                border: none;
                font-size: 24px;
                cursor: pointer;
                color: var(--text);
                opacity: 0.7;
                transition: opacity 0.2s;
            }
            .close-btn:hover {
                opacity: 1;
            }
            .modal-body {
                padding: 20px;
                max-height: 70vh;
                overflow-y: auto;
            }
            .products-table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 15px;
            }
            .products-table th,
            .products-table td {
                padding: 16px; /* was 12px */
                text-align: left;
                border-bottom: 1px solid var(--border);
            }
            .products-table th:nth-child(4),
            .products-table td:nth-child(4) {
                min-width: 120px; /* Rabat */
            }
            .products-table th:nth-child(6),
            .products-table td:nth-child(6) {
                min-width: 220px; /* Podział (udziały) */
                font-size: 1.08em;
            }
            .products-table th {
                background: var(--bg);
                font-weight: 600;
                color: var(--text);
            }
            .settlements-section {
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid var(--border);
            }
            .settlement-item {
                background: var(--bg);
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 10px;
                border-left: 4px solid var(--primary);
            }
            @media (max-width: 768px) {
                .container { padding: 10px; }
                .header { flex-direction: column; align-items: stretch; }
                .receipts-grid { grid-template-columns: 1fr; }
                .filter-buttons { justify-content: center; }
                .modal-content { margin: 10px; }
            }
        </style>
    </head>
    <body>
        <div class="theme-toggle-container" style="position: fixed; top: 20px; right: 20px; z-index: 100;">
            <button id="theme-toggle" class="theme-toggle-btn" title="Przełącz tryb jasny/ciemny">🌙</button>
        </div>
        
        <div class="container">
            <div class="header">
                <div>
                    <h1>🧾 Paragony/wydatki</h1>
                    <p style="margin: 5px 0 0 0; opacity: 0.7;">Przeglądaj i filtruj wszystkie paragony i wydatki w systemie</p>
                </div>
                <a href="/" class="back-btn">← Powrót do menu</a>
            </div>
            
            <div class="filters">
                <h3 style="margin: 0 0 15px 0; color: var(--text);">Filtry:</h3>
                <div class="filter-buttons" style="justify-content: space-between;">
                    <div style="display: flex; gap: 10px;">
                        <button class="filter-btn active" data-filter="all">Wszystkie</button>
                        <button class="filter-btn" data-filter="counted">Tylko podliczone</button>
                        <button class="filter-btn" data-filter="settled">Tylko rozliczone</button>
                    </div>
                    <button class="filter-btn" data-filter="inne" style="margin-left:auto;">Inne</button>
                </div>
            </div>
            
            <div id="receipts-container">
                <div class="loading">
                    <div class="spinner"></div>
                    <p>Ładowanie paragonów i wydatków...</p>
                </div>
            </div>
        </div>
        
        <!-- Modal dla szczegółów paragonu -->
        <div id="receipt-modal" class="receipt-details-modal">
            <div class="modal-content">
                <div class="modal-header">
                    <h2 class="modal-title">Szczegóły paragonu</h2>
                    <button class="close-btn" onclick="closeModal()">&times;</button>
                </div>
                <div class="modal-body" id="modal-body">
                    <!-- Zawartość będzie ładowana dynamicznie -->
                </div>
            </div>
        </div>
        
        <script>
        // Motyw ciemny/jasny
        function setTheme(dark) {
            document.documentElement.classList.toggle('dark', dark);
            localStorage.setItem('theme', dark ? 'dark' : 'light');
            document.getElementById('theme-toggle').textContent = dark ? '☀️' : '🌙';
        }
        
        document.addEventListener('DOMContentLoaded', function() {
            // Motyw z localStorage lub systemowy
            const savedTheme = localStorage.getItem('theme');
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            setTheme(savedTheme === 'dark' || (!savedTheme && prefersDark));
            
            document.getElementById('theme-toggle').onclick = function() {
                setTheme(!document.documentElement.classList.contains('dark'));
            };
            
            // Załaduj paragony i wydatki manualne równocześnie
            loadReceipts('all');
            
            // Obsługa filtrów
            document.querySelectorAll('.filter-btn').forEach(btn => {
                btn.addEventListener('click', function() {
                    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                    this.classList.add('active');
                    loadReceipts(this.dataset.filter);
                });
            });
        });
        
        async function loadReceipts(filterType) {
            const container = document.getElementById('receipts-container');
            container.innerHTML = '<div class="loading"><div class="spinner"></div><p>Ładowanie paragonów i wydatków...</p></div>';
            try {
                // Pobierz paragony i wydatki manualne równocześnie
                const [receiptsResp, manualResp] = await Promise.all([
                    fetch(`/api/browse-receipts?filter_type=all`),
                    fetch(`/api/manual-expenses?filter_type=all`)
                ]);
                let receipts = await receiptsResp.json();
                let manualExpenses = await manualResp.json();
                if (receiptsResp.ok && manualResp.ok) {
                    // Filtrowanie jak dotychczas
                    if (filterType === 'all') {
                        receipts = receipts.filter(r => r.user_name !== 'Other');
                        manualExpenses = manualExpenses.filter(m => m.user_name !== 'Other');
                    } else if (filterType === 'inne') {
                        receipts = receipts.filter(r => r.user_name === 'Other');
                        manualExpenses = manualExpenses.filter(m => m.user_name === 'Other');
                    } else if (filterType === 'counted') {
                        receipts = receipts.filter(r => r.counted && r.user_name !== 'Other');
                        manualExpenses = manualExpenses.filter(m => m.counted && m.user_name !== 'Other');
                    } else if (filterType === 'settled') {
                        receipts = receipts.filter(r => r.settled && r.user_name !== 'Other');
                        manualExpenses = manualExpenses.filter(m => m.settled && m.user_name !== 'Other');
                    }
                    if (receipts.length === 0 && manualExpenses.length === 0) {
                        container.innerHTML = '<div class="no-receipts"><p>Brak paragonów ani wydatków spełniających kryteria.</p></div>';
                        return;
                    }
                    container.innerHTML = `
                        <div class="receipts-grid">
                            ${receipts.map(receipt => createReceiptCard(receipt)).join('')}
                            ${manualExpenses.map(exp => createManualExpenseCard(exp)).join('')}
                        </div>
                    `;
                } else {
                    container.innerHTML = '<div class="no-receipts"><p>Błąd: ' + ((receipts.detail || manualExpenses.detail) || 'Nieznany błąd') + '</p></div>';
                }
            } catch (error) {
                container.innerHTML = '<div class="no-receipts"><p>Błąd sieci: ' + error.message + '</p></div>';
            }
        }
        
        function createReceiptCard(receipt) {
            const statusBadges = [];
            if (receipt.counted) {
                statusBadges.push('<span class="status-badge status-counted">Podliczony</span>');
            } else {
                statusBadges.push('<span class="status-badge status-pending">Niepodliczony</span>');
            }
            
            if (receipt.settled) {
                statusBadges.push('<span class="status-badge status-settled">Rozliczony</span>');
            }
            
            return `
                <div class="receipt-card" onclick="showReceiptDetails(${receipt.receipt_id})">
                    <div class="receipt-header">
                        <div class="receipt-date">${receipt.date} ${receipt.time}</div>
                        <div class="receipt-amount">${receipt.final_price.toFixed(2)} PLN</div>
                    </div>
                    <div class="receipt-store">${receipt.store_name}</div>
                    <div class="receipt-address">${receipt.store_address}</div>
                    <div class="receipt-payment">Zapłacił: ${receipt.user_name}</div>
                    <div class="receipt-status">
                        ${statusBadges.join('')}
                    </div>
                </div>
            `;
        }
        
        function createManualExpenseCard(exp) {
            // Styl podobny do createReceiptCard
            const statusBadges = [];
            if (exp.counted) {
                statusBadges.push('<span class="status-badge status-counted">Podliczony</span>');
            } else {
                statusBadges.push('<span class="status-badge status-pending">Niepodliczony</span>');
            }
            if (exp.settled) {
                statusBadges.push('<span class="status-badge status-settled">Rozliczony</span>');
            }
            return `
                <div class="receipt-card manual-expense-card">
                    <div class="receipt-header">
                        <div class="receipt-date">${exp.date}</div>
                        <div class="receipt-amount">${exp.total_cost.toFixed(2)} PLN</div>
                    </div>
                    <div class="receipt-store">${exp.description}</div>
                    <div class="receipt-address">Kategoria: ${exp.category}</div>
                    <div class="receipt-payment">Zapłacił: ${exp.user_name}</div>
                    <div class="receipt-status">
                        ${statusBadges.join('')}
                    </div>
                </div>
            `;
        }
        
        async function showReceiptDetails(receiptId) {
            const modal = document.getElementById('receipt-modal');
            const modalBody = document.getElementById('modal-body');
            
            modalBody.innerHTML = '<div class="loading"><div class="spinner"></div><p>Ładowanie szczegółów...</p></div>';
            modal.style.display = 'block';
            
            try {
                const response = await fetch(`/api/receipt-details/${receiptId}`);
                const data = await response.json();
                
                if (response.ok) {
                    modalBody.innerHTML = createReceiptDetailsHTML(data);
                } else {
                    modalBody.innerHTML = '<div class="no-receipts"><p>Błąd: ' + (data.detail || 'Nieznany błąd') + '</p></div>';
                }
            } catch (error) {
                modalBody.innerHTML = '<div class="no-receipts"><p>Błąd sieci: ' + error.message + '</p></div>';
            }
        }
        
        function createReceiptDetailsHTML(data) {
            const receipt = data.receipt;
            const products = data.products;
            const settlements = data.settlements;
            function formatPercent(val) {
                return (Math.round(val) === val) ? `${val.toFixed(0)}%` : `${val.toFixed(1)}%`;
            }
            let productsHTML = '';
            if (products.length > 0) {
                productsHTML = `
                    <h3>Produkty:</h3>
                    <table class="products-table">
                        <thead>
                            <tr>
                                <th>Nazwa produktu</th>
                                <th>Ilość</th>
                                <th>Cena jednostkowa</th>
                                <th>Rabat</th>
                                <th>Cena po rabacie</th>
                                <th>Podział (udziały)</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${products.map(product => {
                                let shares = (product.shares || []).filter(s => s.user_name !== 'Other');
                                if (shares.length === 2) {
                                    if (shares[0].share === 100) shares = [shares[0]];
                                    else if (shares[1].share === 100) shares = [shares[1]];
                                }
                                return `
                                    <tr>
                                        <td>${product.product_name}</td>
                                        <td>${product.quantity}</td>
                                        <td>${product.unit_price_before.toFixed(2)} PLN</td>
                                        <td>${product.total_discount > 0 ? product.total_discount.toFixed(2) + ' PLN' : '-'}</td>
                                        <td>${product.total_after_discount.toFixed(2)} PLN</td>
                                        <td>
                                            ${shares && shares.length > 0 ?
                                                shares.map(share =>
                                                    `<div><strong>${share.user_name}</strong>: ${formatPercent(share.share)} (${share.amount.toFixed(2)} PLN)</div>`
                                                ).join('')
                                                : '<span style="opacity:0.7;">Brak udziałów</span>'
                                            }
                                        </td>
                                    </tr>
                                `;
                            }).join('')}
                        </tbody>
                    </table>
                `;
            }
            let settlementsHTML = '';
            if (settlements.length > 0) {
                settlementsHTML = `
                    <div class="settlements-section">
                        <h3>Rozliczenia:</h3>
                        ${settlements.map(settlement => `
                            <div class="settlement-item">
                                <strong>${settlement.payer_name}</strong> → <strong>${settlement.debtor_name}</strong>: 
                                ${settlement.amount.toFixed(2)} PLN
                                ${settlement.settled ? ' (Rozliczone)' : ' (Oczekujące)'}
                            </div>
                        `).join('')}
                    </div>
                `;
            }
            let actionBtn = '';
            if (receipt.user_name === 'Other') {
                actionBtn = `<button class='btn' id='assignPayerBtn' style='margin:18px 0 0 0;'>Przypisz płacącego</button><div id='assignPayerBox'></div>`;
            } else {
                actionBtn = `<button class='btn' style='margin:18px 0 0 0;' onclick='window.location="/count-receipt/${receipt.receipt_id}"'>Podlicz</button>`;
            }
            setTimeout(() => {
                const btn = document.getElementById('assignPayerBtn');
                if (btn) {
                    btn.onclick = async function() {
                        btn.style.display = 'none';
                        const box = document.getElementById('assignPayerBox');
                        box.innerHTML = 'Ładowanie użytkowników...';
                        const resp = await fetch('/api/users');
                        const users = await resp.json();
                        const filtered = users.filter(u => u.name !== 'Other');
                        box.innerHTML = `<select id='payerSelect'>${filtered.map(u => `<option value='${u.id}'>${u.name}</option>`).join('')}</select> <button class='btn' id='savePayerBtn'>Zapisz</button>`;
                        document.getElementById('savePayerBtn').onclick = async function() {
                            const newPayer = document.getElementById('payerSelect').value;
                            const res = await fetch(`/api/assign-payer/${receipt.receipt_id}`, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ user_id: newPayer })
                            });
                            if (res.ok) {
                                box.innerHTML = '<span style="color:green;">Zapisano! Odśwież stronę.</span>';
                            } else {
                                box.innerHTML = '<span style="color:red;">Błąd zapisu.</span>';
                            }
                        };
                    };
                }
            }, 0);
            return `
                <div>
                    <h3>Informacje o paragonie [receipt_id: ${receipt.receipt_id}]:</h3>
                    <p><strong>Data:</strong> ${receipt.date} ${receipt.time}</p>
                    <p><strong>Sklep:</strong> ${receipt.store_name}</p>
                    <p><strong>Adres:</strong> ${receipt.store_address}</p>
                    <p><strong>Kwota:</strong> ${receipt.final_price.toFixed(2)} PLN</p>
                    <p><strong>Rabaty:</strong> ${receipt.total_discounts.toFixed(2)} PLN</p>
                    <p><strong>Zapłacił:</strong> ${receipt.user_name}</p>
                    <p><strong>Status:</strong> 
                        ${receipt.counted ? 'Podliczony' : 'Niepodliczony'} / 
                        ${receipt.settled ? 'Rozliczony' : 'Nierozliczony'}
                    </p>
                    ${actionBtn}
                    ${productsHTML}
                    ${settlementsHTML}
                </div>
            `;
        }
        
        function closeModal() {
            document.getElementById('receipt-modal').style.display = 'none';
        }
        
        // Zamykanie modala po kliknięciu poza nim
        document.getElementById('receipt-modal').addEventListener('click', function(e) {
            if (e.target === this) {
                closeModal();
            }
        });
        
        // Zamykanie modala klawiszem Escape
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                closeModal();
            }
        });
        </script>
    </body>
    </html>
    """

# API endpoints dla funkcji menu

@app.get("/api/users")
async def get_users():
    """Pobierz listę użytkowników."""
    db = SessionLocal()
    try:
        db_manager = DatabaseManager(db)
        users = db_manager.get_users()
        return users
    finally:
        db.close()

@app.post("/api/add-expense")
async def add_expense_api(expense: ManualExpenseModel):
    """Dodaj wydatek ręczny."""
    db = SessionLocal()
    try:
        db_manager = DatabaseManager(db)
        view = MenuView()
        handlers = MenuHandlers(db_manager, view)
        
        # Konwertuj string date na date object
        expense_date = datetime.strptime(expense.date, "%Y-%m-%d").date()
        
        # Przygotuj dane wydatku
        expense_data = {
            "description": expense.description,
            "category": expense.category,
            "amount": expense.amount,
            "date": expense_date,
            "payer_user_id": expense.payer_user_id,
            "share1": expense.share1,
            "share2": expense.share2
        }
        
        # Dodaj wydatek
        handlers.handle_add_expense_api(expense_data)
        
        return {"message": "Wydatek został dodany pomyślnie"}
    except Exception as e:
        logger.error(f"Error adding expense: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/api/statistics")
async def get_statistics(start_date: Optional[str] = None, end_date: Optional[str] = None):
    """Pobierz statystyki z opcjonalnym filtrem dat."""
    db = SessionLocal()
    try:
        db_manager = DatabaseManager(db)
        # Filtry dat
        date_filter_receipts = ""
        date_filter_manual = ""
        params = {}
        if start_date:
            date_filter_receipts += " AND r.date >= :start_date"
            date_filter_manual += " AND me.date >= :start_date"
            params['start_date'] = start_date
        if end_date:
            date_filter_receipts += " AND r.date <= :end_date"
            date_filter_manual += " AND me.date <= :end_date"
            params['end_date'] = end_date
        # Paragony
        receipts = db.execute(text(f"SELECT COUNT(*) FROM receipts r WHERE 1=1 {date_filter_receipts}"), params).scalar()
        receipts_sum = db.execute(text(f"SELECT COALESCE(SUM(final_price), 0) FROM receipts r WHERE 1=1 {date_filter_receipts}"), params).scalar()
        # Manualne wydatki
        manual_expenses = db.execute(text(f"SELECT me.date, me.description, me.total_cost as amount, me.category, me.payer_user_id FROM manual_expenses me WHERE me.counted=TRUE {date_filter_manual} ORDER BY me.date DESC LIMIT 100"), params).fetchall()
        manual_sum = db.execute(text(f"SELECT COALESCE(SUM(total_cost), 0) FROM manual_expenses me WHERE me.counted=TRUE {date_filter_manual}"), params).scalar()
        # Suma łączna
        total_amount = float(receipts_sum or 0) + float(manual_sum or 0)
        # Suma wg kategorii (manual_expenses)
        cat_rows = db.execute(text(f"SELECT category, COALESCE(SUM(total_cost),0) FROM manual_expenses me WHERE me.counted=TRUE {date_filter_manual} GROUP BY category ORDER BY SUM(total_cost) DESC"), params).fetchall()
        category_sums = {row[0] or 'Brak': float(row[1]) for row in cat_rows}
        # Suma użytkownika 1 i 2 (manual_expenses + paragony)
        user1_sum = db.execute(text(f"SELECT COALESCE(SUM(final_price),0) FROM receipts r WHERE 1=1 {date_filter_receipts} AND r.payment_name=(SELECT payment_name FROM user_payments WHERE user_id=1 LIMIT 1)"), params).scalar() or 0
        user2_sum = db.execute(text(f"SELECT COALESCE(SUM(final_price),0) FROM receipts r WHERE 1=1 {date_filter_receipts} AND r.payment_name=(SELECT payment_name FROM user_payments WHERE user_id=2 LIMIT 1)"), params).scalar() or 0
        user1_manual = db.execute(text(f"SELECT COALESCE(SUM(total_cost),0) FROM manual_expenses me WHERE me.counted=TRUE {date_filter_manual} AND me.payer_user_id=1"), params).scalar() or 0
        user2_manual = db.execute(text(f"SELECT COALESCE(SUM(total_cost),0) FROM manual_expenses me WHERE me.counted=TRUE {date_filter_manual} AND me.payer_user_id=2"), params).scalar() or 0
        user_sums = [float(user1_sum)+float(user1_manual), float(user2_sum)+float(user2_manual)]
        # Udział procentowy kategorii i udział użytkowników w każdej kategorii (manual_expenses)
        total_manual = sum(category_sums.values()) or 1
        category_shares = []
        for cat, cat_sum in category_sums.items():
            user1 = db.execute(text(f"SELECT COALESCE(SUM(total_cost),0) FROM manual_expenses me WHERE me.counted=TRUE {date_filter_manual} AND me.category=:cat AND me.payer_user_id=1"), {**params, 'cat': cat}).scalar() or 0
            user2 = db.execute(text(f"SELECT COALESCE(SUM(total_cost),0) FROM manual_expenses me WHERE me.counted=TRUE {date_filter_manual} AND me.category=:cat AND me.payer_user_id=2"), {**params, 'cat': cat}).scalar() or 0
            category_shares.append({
                'category': cat,
                'percent': 100*cat_sum/total_manual,
                'user1': float(user1),
                'user2': float(user2)
            })
        return {
            "total_receipts": receipts,
            "total_expenses": len(manual_expenses),
            "total_amount": total_amount,
            "recent_expenses": [dict(date=row[0], description=row[1], amount=float(row[2])) for row in manual_expenses[:10]],
            "category_sums": category_sums,
            "user_sums": user_sums,
            "category_shares": category_shares
        }
    finally:
        db.close()

@app.get("/api/receipts")
async def get_receipts():
    """Pobierz listę paragonów."""
    db = SessionLocal()
    try:
        receipts = db.execute(text("""
            SELECT r.date, r.final_price, r.payment_name, r.is_settled, s.store_name
            FROM receipts r
            LEFT JOIN stores s ON r.store_id = s.store_id
            ORDER BY r.date DESC
            LIMIT 50
        """)).fetchall()
        
        return [
            {
                "date": str(receipt[0]) if receipt[0] else "N/A",
                "final_price": float(receipt[1]) if receipt[1] else 0,
                "payment_name": receipt[2] or "N/A",
                "is_settled": bool(receipt[3]),
                "store_name": receipt[4] or "N/A"
            }
            for receipt in receipts
        ]
    finally:
        db.close()

@app.get("/api/settlement")
async def get_settlement():
    db = SessionLocal()
    try:
        # Pobierz użytkowników
        users = db.execute(text("SELECT user_id, name FROM users ORDER BY user_id")).fetchall()
        user_ids = [u[0] for u in users]
        user_names = {u[0]: u[1] for u in users}
        # Paragony: counted=TRUE, settled=FALSE
        receipts = db.execute(text("""
            SELECT r.receipt_id, r.date, r.final_price, r.payment_name, s.store_name
            FROM receipts r
            LEFT JOIN stores s ON r.store_id = s.store_id
            WHERE r.counted=TRUE AND r.settled=FALSE
            ORDER BY r.date, r.receipt_id
        """)).fetchall()
        receipts_list = []
        user_totals = {uid: 0.0 for uid in user_ids}
        user_paid = {uid: 0.0 for uid in user_ids}
        for row in receipts:
            receipt_id, date, final_price, payment_name, store_name = row
            # Kto płacił
            payer = db.execute(text("SELECT u.user_id, u.name FROM user_payments up JOIN users u ON up.user_id = u.user_id WHERE up.payment_name = :pname"), {"pname": payment_name}).fetchone()
            payer_id = payer[0] if payer else None
            payer_name = payer[1] if payer else payment_name
            # Produkty i udziały
            products = db.execute(text("SELECT product_id, product_name, total_after_discount FROM products WHERE receipt_id = :rid"), {"rid": receipt_id}).fetchall()
            shares_sum = {uid: 0.0 for uid in user_ids}
            for prod in products:
                product_id, product_name, total_after_discount = prod
                shares = db.execute(text("SELECT user_id, share FROM shares WHERE product_id = :pid"), {"pid": product_id}).fetchall()
                for uid, share in shares:
                    shares_sum[uid] += float(total_after_discount) * float(share) / 100
            # Dodaj do sumy "powinien zapłacić"
            for uid in user_ids:
                user_totals[uid] += shares_sum[uid]
            # Dodaj do sumy "faktycznie zapłacił"
            if payer_id:
                user_paid[payer_id] += float(final_price)
            receipts_list.append({
                "receipt_id": receipt_id,
                "date": str(date),
                "final_price": float(final_price),
                "store_name": store_name,
                "payer_name": payer_name,
                "shares": shares_sum
            })
        # Manualne wydatki: counted=TRUE, settled=FALSE
        manual_expenses = db.execute(text("""
            SELECT me.manual_expense_id, me.date, me.total_cost, me.payer_user_id, me.description
            FROM manual_expenses me
            WHERE me.counted=TRUE AND me.settled=FALSE
            ORDER BY me.date, me.manual_expense_id
        """)).fetchall()
        manual_list = []
        for row in manual_expenses:
            mid, date, total_cost, payer_user_id, description = row
            # Wirtualny produkt i udziały
            product = db.execute(text("SELECT product_id FROM products WHERE manual_expense_id = :mid"), {"mid": mid}).fetchone()
            shares_sum = {uid: 0.0 for uid in user_ids}
            if product:
                product_id = product[0]
                shares = db.execute(text("SELECT user_id, share FROM shares WHERE product_id = :pid"), {"pid": product_id}).fetchall()
                for uid, share in shares:
                    shares_sum[uid] += float(total_cost) * float(share) / 100
            # Dodaj do sumy "powinien zapłacić"
            for uid in user_ids:
                user_totals[uid] += shares_sum[uid]
            # Dodaj do sumy "faktycznie zapłacił"
            user_paid[payer_user_id] += float(total_cost)
            manual_list.append({
                "manual_expense_id": mid,
                "date": str(date),
                "total_cost": float(total_cost),
                "payer_name": user_names.get(payer_user_id, str(payer_user_id)),
                "description": description,
                "shares": shares_sum
            })
        # Podsumowanie tabelaryczne
        summary_table = []
        for uid in user_ids:
            summary_table.append({
                "user_id": uid,
                "user_name": user_names[uid],
                "should_pay": round(user_totals[uid], 2),
                "actually_paid": round(user_paid[uid], 2),
                "net": round(user_paid[uid] - user_totals[uid], 2)
            })
        # Całościowe podsumowanie "kto komu wisi"
        sorted_users = sorted(summary_table, key=lambda x: x['net'], reverse=True)
        if len(sorted_users) >= 2:
            highest_positive = sorted_users[0]
            highest_negative = sorted_users[-1]
            if highest_positive['net'] > 0 and highest_negative['net'] < 0:
                amount_to_transfer = min(abs(highest_positive['net']), abs(highest_negative['net']))
                settlement_text = f"{highest_negative['user_name']} wisi {highest_positive['user_name']} {amount_to_transfer:.2f} PLN"
            else:
                settlement_text = "Wszystko rozliczone."
        else:
            settlement_text = "Brak wystarczającej liczby użytkowników."
        return {
            "users": [{"user_id": uid, "user_name": user_names[uid]} for uid in user_ids],
            "receipts": receipts_list,
            "manual_expenses": manual_list,
            "summary_table": summary_table,
            "settlement_text": settlement_text
        }
    finally:
        db.close()

@app.get("/api/categories")
async def get_categories():
    """Zwraca listę unikalnych kategorii wydatków."""
    db = SessionLocal()
    try:
        db_manager = DatabaseManager(db)
        categories = db_manager.get_existing_categories()
        return categories
    finally:
        db.close()

@app.get("/api/browse-receipts")
async def browse_receipts(filter_type: str = "all"):
    """Zwraca listę paragonów z możliwością filtrowania."""
    db = SessionLocal()
    try:
        # Buduj zapytanie SQL w zależności od filtra
        base_query = """
            SELECT r.receipt_id, r.date, r.time, r.final_price, r.counted, r.settled,
                   s.store_name, s.store_address, up.payment_name, u.name as user_name, u.user_id
            FROM receipts r
            JOIN stores s ON r.store_id = s.store_id
            JOIN user_payments up ON r.payment_name = up.payment_name
            JOIN users u ON up.user_id = u.user_id
        """
        where = []
        if filter_type == "counted":
            where.append("r.counted = true")
        elif filter_type == "settled":
            where.append("r.settled = true")
        if filter_type == "inne":
            where.append("(u.user_id = 100 OR lower(u.name) IN ('inny','other'))")
        else:
            where.append("NOT (u.user_id = 100 OR lower(u.name) IN ('inny','other'))")
        query = base_query
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY r.date DESC, r.time DESC"
        result = db.execute(text(query))
        receipts = []
        for row in result:
            receipts.append({
                "receipt_id": row.receipt_id,
                "date": row.date.strftime("%Y-%m-%d") if row.date else None,
                "time": row.time,
                "final_price": float(row.final_price) if row.final_price else 0,
                "counted": row.counted,
                "settled": row.settled,
                "store_name": row.store_name,
                "store_address": row.store_address,
                "payment_name": row.payment_name,
                "user_name": row.user_name
            })
        return receipts
    finally:
        db.close()

@app.get("/api/receipt-details/{receipt_id}")
async def get_receipt_details(receipt_id: int):
    """Zwraca szczegóły paragonu z produktami i rozliczeniami, w tym udziały użytkowników dla każdego produktu."""
    db = SessionLocal()
    try:
        # Pobierz podstawowe informacje o paragonie
        receipt_query = text("""
            SELECT r.receipt_id, r.date, r.time, r.final_price, r.total_discounts, 
                   r.counted, r.settled, r.currency,
                   s.store_name, s.store_address, s.store_city,
                   r.payment_name
            FROM receipts r
            JOIN stores s ON r.store_id = s.store_id
            WHERE r.receipt_id = :receipt_id
        """)
        receipt_result = db.execute(receipt_query, {"receipt_id": receipt_id})
        receipt_row = receipt_result.fetchone()
        if not receipt_row:
            raise HTTPException(status_code=404, detail="Paragon nie został znaleziony")

        # Pobierz imię płacącego
        payer_name = db.execute(text("""
            SELECT u.name FROM user_payments up JOIN users u ON up.user_id = u.user_id WHERE up.payment_name = :pname
        """), {"pname": receipt_row[10]}).scalar() or receipt_row[10]

        # Pobierz użytkowników
        users = db.execute(text("SELECT user_id, name FROM users")).fetchall()
        user_id_to_name = {u[0]: u[1] for u in users}

        # Pobierz produkty
        products_query = text("""
            SELECT product_id, product_name, quantity, unit_price_before, 
                   total_price_before, unit_discount, total_discount,
                   unit_after_discount, total_after_discount, tax_type
            FROM products
            WHERE receipt_id = :receipt_id
            ORDER BY product_id
        """)
        products_result = db.execute(products_query, {"receipt_id": receipt_id})
        products = []
        for row in products_result:
            product_id = row[0]
            # Pobierz udziały dla produktu
            shares = db.execute(text("SELECT user_id, share FROM shares WHERE product_id = :pid"), {"pid": product_id}).fetchall()
            shares_list = [
                {"user_id": uid, "user_name": user_id_to_name.get(uid, str(uid)), "share": float(share)}
                for uid, share in shares
            ]
            products.append({
                "product_id": product_id,
                "product_name": row[1],
                "quantity": float(row[2]),
                "unit_price_before": float(row[3]),
                "total_price_before": float(row[4]),
                "unit_discount": float(row[5]) if row[5] is not None else None,
                "total_discount": float(row[6]) if row[6] is not None else None,
                "unit_after_discount": float(row[7]) if row[7] is not None else None,
                "total_after_discount": float(row[8]),
                "tax_type": row[9],
                "shares": shares_list
            })

        # Pobierz rozliczenia (settlements)
        settlements_query = text("""
            SELECT s.settlement_id, s.amount,
                   payer.name as payer_name, debtor.name as debtor_name
            FROM settlements s
            JOIN settlement_items si ON s.settlement_id = si.settlement_id
            JOIN users payer ON s.payer_user_id = payer.user_id
            JOIN users debtor ON s.debtor_user_id = debtor.user_id
            WHERE si.receipt_id = :receipt_id
            ORDER BY s.settlement_id
        """)
        settlements_result = db.execute(settlements_query, {"receipt_id": receipt_id})
        settlements = []
        for row in settlements_result:
            settlements.append({
                "settlement_id": row.settlement_id,
                "amount": float(row.amount) if row.amount else 0,
                "payer_name": row.payer_name,
                "debtor_name": row.debtor_name
            })

        return {
            "receipt": {
                "receipt_id": receipt_row[0],
                "date": str(receipt_row[1]),
                "time": str(receipt_row[2]),
                "final_price": float(receipt_row[3]),
                "total_discounts": float(receipt_row[4]) if receipt_row[4] is not None else None,
                "counted": receipt_row[5],
                "settled": receipt_row[6],
                "currency": receipt_row[7],
                "store_name": receipt_row[8],
                "store_address": receipt_row[9],
                "store_city": receipt_row[10],
                "payment_name": receipt_row[11],
                "payer_name": payer_name  # <-- imię użytkownika płacącego
            },
            "products": products,
            "settlements": settlements
        }
    finally:
        db.close()

@app.get("/count-receipts/", response_class=HTMLResponse)
async def count_receipts_page():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Podlicz Paragony</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
            .container { max-width: 900px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h1 { color: #333; text-align: center; }
            .back-btn { background: #6c757d; color: white; padding: 8px 15px; border: none; border-radius: 4px; text-decoration: none; display: inline-block; margin: 10px 0; }
            .form-group { margin: 15px 0; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input, select { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
            button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
            button:hover { background: #0056b3; }
            .receipts-table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            .receipts-table th, .receipts-table td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
            .receipts-table th { background-color: #f8f9fa; font-weight: bold; }
            #receiptsResult { margin-top: 20px; }
        </style>
    </head>
    <body>
        <div class="container">
            <a href="/" class="back-btn">← Powrót do menu</a>
            <h1>🧮 Podlicz Paragony</h1>
            <div class="form-group">
                <label for="password">Hasło:</label>
                <input type="password" id="password" name="password" required>
            </div>
            <button onclick="loadUncountedReceipts()">Załaduj niepodliczone paragony</button>
            <div id="receiptsResult"></div>
        </div>
        <script>
        async function loadUncountedReceipts() {
            const password = document.getElementById('password').value;
            if (!password) {
                alert('Proszę wprowadzić hasło');
                return;
            }
            try {
                const response = await fetch('/api/uncounted-receipts');
                const receipts = await response.json();
                const resultDiv = document.getElementById('receiptsResult');
                if (response.ok) {
                    if (!receipts.length) {
                        resultDiv.innerHTML = '<div style="color: green; padding: 10px; background: #d4edda; border-radius: 4px;">Brak niepodliczonych paragonów.</div>';
                        return;
                    }
                    let html = `<table class="receipts-table"><thead><tr><th>Data</th><th>Sklep</th><th>Kwota</th><th>Kto zapłacił</th><th>Akcja</th></tr></thead><tbody>`;
                    receipts.forEach(receipt => {
                        html += `<tr><td>${receipt.date || 'N/A'}</td><td>${receipt.store_name || 'N/A'}</td><td>${(receipt.final_price || 0).toFixed(2)} PLN</td><td>${receipt.payment_name || 'N/A'}</td><td><button onclick="window.location='/count-receipt/' + ${receipt.receipt_id}">Podlicz</button></td></tr>`;
                    });
                    html += '</tbody></table>';
                    resultDiv.innerHTML = html;
                } else {
                    resultDiv.innerHTML = '<div style="color: red; padding: 10px; background: #f8d7da; border-radius: 4px;">Błąd: ' + (receipts.detail || 'Nieznany błąd') + '</div>';
                }
            } catch (error) {
                document.getElementById('receiptsResult').innerHTML = '<div style="color: red; padding: 10px; background: #f8d7da; border-radius: 4px;">Błąd sieci: ' + error.message + '</div>';
            }
        }
        </script>
    </body>
    </html>
    """

@app.get("/count-receipt/{receipt_id}", response_class=HTMLResponse)
async def count_receipt_detail(receipt_id: int):
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Podlicz paragon {receipt_id}</title>
        <meta name='viewport' content='width=device-width, initial-scale=1'>
        <style>
            body {{ font-family: Arial, sans-serif; background: #f5f5f5; margin: 0; }}
            .container {{ max-width: 800px; margin: 30px auto; background: #fff; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); padding: 24px; }}
            h1 {{ color: #007bff; text-align: center; }}
            .back-btn {{ background: #6c757d; color: #fff; padding: 8px 15px; border: none; border-radius: 4px; text-decoration: none; display: inline-block; margin: 10px 0; }}
            .back-btn:hover {{ background: #495057; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th, td {{ padding: 10px; border-bottom: 1px solid #eee; text-align: left; }}
            th {{ background: #f8f9fa; }}
            .share-input {{ width: 60px; padding: 5px; border: 1px solid #ccc; border-radius: 4px; text-align: right; }}
            .user-header {{ font-size: 0.95em; color: #555; }}
            .error-msg {{ color: #dc3545; margin: 10px 0; }}
            .success-msg {{ color: #28a745; margin: 10px 0; }}
            .btn {{ background: #007bff; color: #fff; border: none; border-radius: 4px; padding: 8px 18px; cursor: pointer; margin: 8px 0; }}
            .btn:disabled {{ opacity: 0.7; cursor: not-allowed; }}
            .btn-secondary {{ background: #6c757d; }}
            .btn-secondary:hover {{ background: #495057; }}
            .btn:hover {{ background: #0056b3; }}
            @media (max-width: 700px) {{ .container {{ padding: 8px; }} th, td {{ padding: 6px; }} }}
        </style>
    </head>
    <body>
        <div class='container'>
            <a href='/count-receipts/' class='back-btn'>← Powrót</a>
            <h1>Podlicz paragon #{receipt_id}</h1>
            <div id='form-section'>
                <div class='loading'>Ładowanie danych...</div>
            </div>
        </div>
        <script>
        let users = [];
        let products = [];
        document.addEventListener('DOMContentLoaded', async function() {{
            await loadData();
        }});
        async function loadData() {{
            try {{
                const [usersResp, receiptResp] = await Promise.all([
                    fetch('/api/users'),
                    fetch(`/api/receipt-details/{receipt_id}`)
                ]);
                users = await usersResp.json();
                const receiptData = await receiptResp.json();
                products = receiptData.products;
                renderForm();
            }} catch (err) {{
                document.getElementById('form-section').innerHTML = `<div class='error-msg'>Błąd ładowania danych: ${{err.message}}</div>`;
            }}
        }}
        function renderForm() {{
            if (!users.length || !products.length) {{
                document.getElementById('form-section').innerHTML = `<div class='error-msg'>Brak użytkowników lub produktów.</div>`;
                return;
            }}
            // Only use first two users for shares
            const mainUsers = users.slice(0, 2);
            let tableRows = products.map((prod, pi) => {{
                // Sprawdź czy są static_share
                let staticShare = prod.static_share && Array.isArray(prod.static_share) ? prod.static_share : null;
                let staticMap = {{}};
                if (staticShare) {{
                    staticShare.forEach(s => {{ staticMap[s.user_id] = s.share; }});
                }}
                // Przygotuj pola udziałów
                let shareInputs = mainUsers.map((u, ui) => {{
                    let val = staticMap[u.id] !== undefined ? staticMap[u.id] : 50;
                    return `<td><input type='text' class='share-input' min='0' max='100' step='0.01' value='${{val}}' data-prod='${{pi}}' data-user='${{ui}}' oninput='onShareInput(event, ${{pi}}, ${{ui}})'></td>`;
                }}).join('');
                // Podświetlenie wiersza jeśli static_share
                let rowStyle = staticShare ? "background: #eaffea;" : "";
                return `
                <tr style='${{rowStyle}}'>
                    <td>${{prod.product_name}}</td>
                    <td>${{prod.quantity}}</td>
                    <td>${{prod.unit_price_before.toFixed(2)}} PLN</td>
                    <td>${{prod.total_after_discount.toFixed(2)}} PLN</td>
                    ${{shareInputs}}
                    <td style='text-align:center;'><input type='checkbox' class='static-share-checkbox' data-prod='${{pi}}'></td>
                </tr>
                `;
            }}).join('');
            let userHeaders = mainUsers.map(u => `<th class='user-header'>${{u.name}}<br>(%)</th>`).join('');
            document.getElementById('form-section').innerHTML = `
                <form id='sharesForm' onsubmit='return submitShares(event)'>
                    <table>
                        <thead>
                            <tr>
                                <th>Produkt</th><th>Ilość</th><th>Cena jedn.</th><th>Wartość</th>
                                ${{userHeaders}}
                                <th>Stały udział</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${{tableRows}}
                        </tbody>
                    </table>
                    <div style='margin: 18px 0;'>
                        <button type='button' class='btn btn-secondary' onclick='setDefaultShares(50)'>Ustaw 50/50</button>
                        <button type='button' class='btn btn-secondary' onclick='setDefaultShares(100)'>100% dla pierwszego</button>
                    </div>
                    <div id='form-error' class='error-msg' style='display:none;'></div>
                    <div id='form-success' class='success-msg' style='display:none;'></div>
                    <button type='submit' class='btn'>Zapisz udziały</button>
                </form>
            `;
            // Add dynamic logic for shares
            window.onShareInput = function(e, pi, ui) {{
                let val = e.target.value.replace(',', '.');
                if (val === '') val = '0';
                let num = Math.max(0, Math.min(100, parseFloat(val)));
                num = Math.round(num * 100) / 100;
                e.target.value = num;
                // Dopełnij drugiego użytkownika do 100%
                const otherUi = ui === 0 ? 1 : 0;
                const otherInput = document.querySelector(`.share-input[data-prod='${{pi}}'][data-user='${{otherUi}}']`);
                if (otherInput) {{
                    let otherVal = Math.round((100 - num) * 100) / 100;
                    otherInput.value = otherVal;
                }}
            }};
        }}
        function defaultShareValue(pi, ui) {{
            // Always default to 50/50 for two users
            return 50;
        }}
        function setDefaultShares(val) {{
            document.querySelectorAll('.share-input').forEach(inp => {{
                inp.value = val;
            }});
            updateSummary();
        }}
        function updateSummary() {{
            products.forEach((prod, pi) => {{
                let sum = 0;
                users.forEach((u, ui) => {{
                    const inp = document.querySelector(`.share-input[data-prod='${{pi}}'][data-user='${{ui}}']`);
                    sum += parseFloat(inp.value) || 0;
                }});
                const cell = document.getElementById(`sum-prod-${{pi}}`);
                cell.textContent = sum + '%';
                cell.style.color = (sum === 100 ? '#28a745' : '#dc3545');
            }});
        }}
        async function submitShares(e) {{
            e.preventDefault();
            let valid = true;
            let sharesData = [];
            let staticShares = [];
            products.forEach((prod, pi) => {{
                let prodShares = [];
                // Only two users
                for (let ui = 0; ui < 2; ++ui) {{
                    const inp = document.querySelector(`.share-input[data-prod='${{pi}}'][data-user='${{ui}}']`);
                    let val = inp.value.replace(',', '.');
                    let num = Math.max(0, Math.min(100, parseFloat(val)));
                    num = Math.round(num * 100) / 100;
                    prodShares.push({{ user_id: users[ui].id, share: num }});
                }}
                // Check if static share checkbox is checked
                const staticCheckbox = document.querySelector(`.static-share-checkbox[data-prod='${{pi}}']`);
                if (staticCheckbox && staticCheckbox.checked) {{
                    staticShares.push({{ product_name: prod.product_name, shares: prodShares }});
                }}
                // Validate sum
                const sum = prodShares.reduce((a, b) => a + b.share, 0);
                if (Math.abs(sum - 100) > 0.01) valid = false;
                sharesData.push({{ product_id: prod.product_id, shares: prodShares }});
            }});
            if (!valid) {{
                document.getElementById('form-error').textContent = 'Suma udziałów dla każdego produktu musi wynosić 100%.';
                document.getElementById('form-error').style.display = '';
                document.getElementById('form-success').style.display = 'none';
                return false;
            }}
            document.getElementById('form-error').style.display = 'none';
            // Wysyłka do backendu
            try {{
                const resp = await fetch(`/api/count-receipt/{receipt_id}`, {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ shares: sharesData, static_shares: staticShares }})
                }});
                const result = await resp.json();
                if (resp.ok) {{
                    document.getElementById('form-success').textContent = 'Udziały zostały zapisane!';
                    document.getElementById('form-success').style.display = '';
                }} else {{
                    document.getElementById('form-error').textContent = result.detail || 'Błąd zapisu udziałów.';
                    document.getElementById('form-error').style.display = '';
                }}
            }} catch (err) {{
                document.getElementById('form-error').textContent = 'Błąd sieci: ' + err.message;
                document.getElementById('form-error').style.display = '';
            }}
            return false;
        }}
        </script>
    </body>
    </html>
    """.format(receipt_id=receipt_id)

@app.get("/api/uncounted-receipts")
async def get_uncounted_receipts():
    db = SessionLocal()
    try:
        receipts = db.execute(text("""
            SELECT r.receipt_id, r.date, r.final_price, r.payment_name, s.store_name
            FROM receipts r
            LEFT JOIN stores s ON r.store_id = s.store_id
            WHERE r.counted = FALSE
            ORDER BY r.date ASC, r.receipt_id ASC
            LIMIT 50
        """)).fetchall()
        return [
            {
                "receipt_id": r[0],
                "date": str(r[1]) if r[1] else "N/A",
                "final_price": float(r[2]) if r[2] else 0,
                "payment_name": r[3] or "N/A",
                "store_name": r[4] or "N/A"
            }
            for r in receipts
        ]
    finally:
        db.close()

@app.post("/api/count-receipt/{receipt_id}")
async def save_receipt_shares(receipt_id: int, request: Request):
    """
    Zapisz udziały użytkowników dla każdego produktu na paragonie.
    Walidacja: suma udziałów dla każdego produktu = 100, każdy udział 0-100, user_id istnieje.
    Oczekuje JSON: { shares: [ { product_id, shares: [ {user_id, share}, ... ] }, ... ] }
    """
    db = SessionLocal()
    try:
        data = await request.json()
        shares_data = data.get("shares", [])
        static_shares_data = data.get("static_shares", [])
        if not shares_data:
            return JSONResponse({"detail": "Brak danych udziałów."}, status_code=status.HTTP_400_BAD_REQUEST)
        # Pobierz listę user_id z bazy
        user_ids = set(row[0] for row in db.execute(text("SELECT user_id FROM users")).fetchall())
        # Walidacja udziałów
        for prod in shares_data:
            product_id = prod.get("product_id")
            user_shares = prod.get("shares", [])
            if product_id is None or not user_shares:
                return JSONResponse({"detail": f"Brak udziałów dla produktu {product_id}"}, status_code=status.HTTP_400_BAD_REQUEST)
            sum_shares = 0.0
            for us in user_shares:
                user_id = us.get("user_id")
                share = us.get("share")
                if user_id is None or share is None:
                    return JSONResponse({"detail": f"Brak user_id lub udziału dla produktu {product_id}"}, status_code=status.HTTP_400_BAD_REQUEST)
                if user_id not in user_ids:
                    return JSONResponse({"detail": f"Nieprawidłowy user_id {user_id} dla produktu {product_id}"}, status_code=status.HTTP_400_BAD_REQUEST)
                if not (0 <= float(share) <= 100):
                    return JSONResponse({"detail": f"Udział {share} dla użytkownika {user_id} poza zakresem 0-100% (produkt {product_id})"}, status_code=status.HTTP_400_BAD_REQUEST)
                sum_shares += float(share)
            if abs(sum_shares - 100.0) > 0.01:
                return JSONResponse({"detail": f"Suma udziałów dla produktu {product_id} wynosi {sum_shares:.2f}%, powinna być 100%"}, status_code=status.HTTP_400_BAD_REQUEST)
        # Jeśli walidacja OK, zapisuj udziały do shares
        for prod in shares_data:
            product_id = prod.get("product_id")
            user_shares = prod.get("shares", [])
            for us in user_shares:
                user_id = us.get("user_id")
                share = us.get("share")
                db.execute(text("""
                    INSERT INTO shares (product_id, user_id, share)
                    VALUES (:product_id, :user_id, :share)
                    ON CONFLICT (product_id, user_id)
                    DO UPDATE SET share = EXCLUDED.share, updated_at = NOW()
                """), {"product_id": product_id, "user_id": user_id, "share": share})
        # Obsługa static_shares (stałe udziały)
        for static in static_shares_data:
            product_name = static.get("product_name")
            shares = static.get("shares", [])
            for s in shares:
                user_id = s.get("user_id")
                share = s.get("share")
                db.execute(text("""
                    INSERT INTO static_shares (product_name, user_id, share, created_at, updated_at)
                    VALUES (:product_name, :user_id, :share, NOW(), NOW())
                    ON CONFLICT (product_name, user_id)
                    DO UPDATE SET share = :share, updated_at = NOW()
                """), {"product_name": product_name, "user_id": user_id, "share": share})
        db.execute(text("UPDATE receipts SET counted = TRUE WHERE receipt_id = :rid"), {"rid": receipt_id})
        db.commit()
        return {"message": "Udziały zostały zapisane."}
    except Exception as e:
        db.rollback()
        return JSONResponse({"detail": str(e)}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        db.close()

@app.get("/api/settlements")
async def api_settlements():
    db = SessionLocal()
    try:
        rows = db.execute(text("""
            SELECT s.settlement_id, s.amount, s.created_at, payer.name as payer_name, debtor.name as debtor_name
            FROM settlements s
            JOIN users payer ON s.payer_user_id = payer.user_id
            JOIN users debtor ON s.debtor_user_id = debtor.user_id
            ORDER BY s.created_at DESC, s.settlement_id DESC
        """)).fetchall()
        return [
            dict(settlement_id=row[0], amount=float(row[1]), created_at=str(row[2])[:19], payer_name=row[3], debtor_name=row[4])
            for row in rows
        ]
    finally:
        db.close()

@app.get("/api/settlement-details/{settlement_id}")
async def api_settlement_details(settlement_id: int):
    db = SessionLocal()
    try:
        # Paragony
        receipts = db.execute(text("""
            SELECT r.receipt_id, r.date, r.final_price, s.store_name
            FROM settlement_items si
            JOIN receipts r ON si.receipt_id = r.receipt_id
            JOIN stores s ON r.store_id = s.store_id
            WHERE si.settlement_id = :sid
        """), {'sid': settlement_id}).fetchall()
        receipts_list = []
        for row in receipts:
            receipt_id, date, final_price, store_name = row
            # Pobierz płacącego
            payer = db.execute(text(
                """
                SELECT u.name FROM receipts r
                JOIN user_payments up ON r.payment_name = up.payment_name
                JOIN users u ON up.user_id = u.user_id
                WHERE r.receipt_id = :rid
                """
            ), {'rid': receipt_id}).scalar()
            # Pobierz produkty i udziały
            products = db.execute(text("SELECT product_id, total_after_discount FROM products WHERE receipt_id = :rid"), {'rid': receipt_id}).fetchall()
            shares_sum = {}
            for product_id, total_after_discount in products:
                shares = db.execute(text("SELECT u.name, share FROM shares JOIN users u ON shares.user_id = u.user_id WHERE product_id = :pid"), {'pid': product_id}).fetchall()
                for user_name, share in shares:
                    shares_sum[user_name] = shares_sum.get(user_name, 0) + float(total_after_discount) * float(share) / 100
            receipts_list.append(dict(
                receipt_id=receipt_id,
                date=str(date),
                final_price=float(final_price),
                store_name=store_name,
                payer_name=payer,
                shares=shares_sum
            ))
        # Manualne wydatki (bez zmian)
        manual_expenses = db.execute(text("""
            SELECT me.manual_expense_id, me.date, me.description, me.category, me.total_cost
            FROM settlement_items si
            JOIN manual_expenses me ON si.manual_expense_id = me.manual_expense_id
            WHERE si.settlement_id = :sid
        """), {'sid': settlement_id}).fetchall()
        manual_list = []
        for row in manual_expenses:
            # Udziały użytkowników
            product = db.execute(text("SELECT product_id FROM products WHERE manual_expense_id = :mid"), {'mid': row[0]}).fetchone()
            user1_share = user2_share = 0.0
            if product:
                shares = db.execute(text("SELECT user_id, share FROM shares WHERE product_id = :pid"), {'pid': product[0]}).fetchall()
                for uid, share in shares:
                    amount = float(row[4]) * float(share) / 100
                    if uid == 1:
                        user1_share = amount
                    elif uid == 2:
                        user2_share = amount
            manual_list.append(dict(
                manual_expense_id=row[0], date=str(row[1]), description=row[2], category=row[3], total_cost=float(row[4]), user1_share=user1_share, user2_share=user2_share
            ))
        return { 'receipts': receipts_list, 'manual_expenses': manual_list }
    finally:
        db.close()

@app.post("/api/assign-payer/{receipt_id}")
async def assign_payer(receipt_id: int, request: Request):
    db = SessionLocal()
    try:
        data = await request.json()
        user_id = int(data.get('user_id'))
        # Pobierz payment_name dla user_id
        payment_name = db.execute(text("SELECT payment_name FROM user_payments WHERE user_id = :uid LIMIT 1"), {'uid': user_id}).scalar()
        if not payment_name:
            return JSONResponse({'detail': 'Nie znaleziono payment_name dla usera.'}, status_code=400)
        db.execute(text("UPDATE receipts SET payment_name = :pname WHERE receipt_id = :rid"), {'pname': payment_name, 'rid': receipt_id})
        db.commit()
        return {'message': 'OK'}
    except Exception as e:
        db.rollback()
        return JSONResponse({'detail': str(e)}, status_code=500)
    finally:
        db.close()

@app.get("/api/manual-expenses")
async def api_manual_expenses(filter_type: str = "all"):
    """Zwraca listę wydatków ręcznych do wyświetlenia w kafelkach na stronie browse-receipts."""
    db = SessionLocal()
    try:
        # Pobierz wydatki manualne wraz z nazwą użytkownika
        query = """
            SELECT me.manual_expense_id, me.date, me.description, me.category, me.total_cost, me.counted, me.settled, u.name as user_name
            FROM manual_expenses me
            JOIN users u ON me.payer_user_id = u.user_id
        """
        where_clauses = []
        params = {}
        if filter_type == "counted":
            where_clauses.append("me.counted = TRUE")
        elif filter_type == "settled":
            where_clauses.append("me.settled = TRUE")
        elif filter_type == "inne":
            where_clauses.append("u.name = :other")
            params['other'] = 'Other'
        # domyślnie all
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        query += " ORDER BY me.date DESC, me.manual_expense_id DESC"
        result = db.execute(text(query), params)
        expenses = []
        for row in result:
            expenses.append({
                "manual_expense_id": row.manual_expense_id,
                "date": row.date.strftime("%Y-%m-%d") if row.date else None,
                "description": row.description,
                "category": row.category,
                "total_cost": float(row.total_cost) if row.total_cost else 0,
                "counted": row.counted,
                "settled": row.settled,
                "user_name": row.user_name
            })
        return expenses
    finally:
        db.close()

# 1. Endpoint do finalizacji rozliczenia
@app.post("/api/finalize-settlement")
async def finalize_settlement(request: Request):
    db = SessionLocal()
    try:
        data = await request.json()
        payer_user_id = int(data.get('payer_user_id'))
        debtor_user_id = int(data.get('debtor_user_id'))
        amount = float(data.get('amount'))
        note = data.get('note', None)
        finalized_by = payer_user_id  # Placeholder, in the future use current user from session/auth

        # Insert new settlement
        settlement_row = db.execute(
            text("""
                INSERT INTO settlements (payer_user_id, debtor_user_id, amount, note, finalized_by, finalized_at)
                VALUES (:payer, :debtor, :amount, :note, :finalized_by, NOW())
                RETURNING settlement_id, created_at
            """),
            {
                "payer": payer_user_id,
                "debtor": debtor_user_id,
                "amount": amount,
                "note": note,
                "finalized_by": finalized_by
            }
        ).fetchone()
        if settlement_row is None:
            db.rollback()
            return Response(status_code=400, content="Failed to create settlement (check input data and constraints).")
        settlement_id = settlement_row[0]
        created_at = settlement_row[1]

        # Link all unsettled receipts
        receipts = db.execute(text("SELECT receipt_id FROM receipts WHERE counted=TRUE AND settled=FALSE")).fetchall()
        for r in receipts:
            db.execute(
                text("INSERT INTO settlement_items (settlement_id, receipt_id) VALUES (:sid, :rid) ON CONFLICT DO NOTHING"),
                {"sid": settlement_id, "rid": r[0]}
            )
            db.execute(text("UPDATE receipts SET settled=TRUE WHERE receipt_id=:rid"), {"rid": r[0]})

        # Link all unsettled manual_expenses
        manual_expenses = db.execute(text("SELECT manual_expense_id FROM manual_expenses WHERE counted=TRUE AND settled=FALSE")).fetchall()
        for m in manual_expenses:
            db.execute(
                text("INSERT INTO settlement_items (settlement_id, manual_expense_id) VALUES (:sid, :mid) ON CONFLICT DO NOTHING"),
                {"sid": settlement_id, "mid": m[0]}
            )
            db.execute(text("UPDATE manual_expenses SET settled=TRUE WHERE manual_expense_id=:mid"), {"mid": m[0]})

        db.commit()
        return {
            "message": "Rozliczenie sfinalizowane.",
            "settlement_id": settlement_id,
            "created_at": str(created_at),
            "receipts_count": len(receipts),
            "manual_expenses_count": len(manual_expenses)
        }
    except Exception as e:
        db.rollback()
        return Response(status_code=500, content=str(e))
    finally:
        db.close()

# 2. Popraw wyświetlanie historycznych rozliczeń (szczegóły)
# (Załóżmy, że endpoint /api/settlement-details/{settlement_id} już zwraca receipts i manual_expenses dla danego rozliczenia)
# Dodaj JS na stronie, by po kliknięciu na historyczne rozliczenie pokazywał modal/szczegóły z podziałem i kolorowaniem dłużnika i kwoty (analogicznie jak w szczegółach paragonu)
# (Kod JS i HTML do obsługi modala/historycznych rozliczeń dodaj w settlement_summary.html)

@app.post("/api/add-user")
async def add_user(request: Request):
    db = SessionLocal()
    try:
        data = await request.json()
        name = data.get('name')
        if not name or not name.strip():
            return JSONResponse({'detail': 'Imię jest wymagane.'}, status_code=400)
        # Dodaj użytkownika
        db.execute(text("INSERT INTO users (name) VALUES (:name)"), {'name': name.strip()})
        db.commit()
        return {'message': 'Użytkownik dodany.'}
    except Exception as e:
        db.rollback()
        return JSONResponse({'detail': str(e)}, status_code=500)
    finally:
        db.close()

@app.get("/users/", response_class=HTMLResponse)
async def users_page():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Użytkownicy</title>
        <meta name='viewport' content='width=device-width, initial-scale=1'>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
            .container { max-width: 600px; margin: 0 auto; background: white; padding: 24px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h1 { color: #333; text-align: center; }
            .back-btn { background: #6c757d; color: white; padding: 8px 15px; border: none; border-radius: 4px; text-decoration: none; display: inline-block; margin: 10px 0; }
            .form-group { margin: 15px 0; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
            button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
            button:hover { background: #0056b3; }
            .user-list { margin-top: 24px; }
            .user-item { padding: 10px 0; border-bottom: 1px solid #eee; display: flex; align-items: center; gap: 10px; }
            .user-id { color: #888; font-size: 0.95em; }
            .warn { color: #dc3545; font-weight: bold; margin: 10px 0; }
            .success { color: #28a745; font-weight: bold; margin: 10px 0; }
        </style>
    </head>
    <body>
        <div class='container'>
            <a href='/' class='back-btn'>← Powrót do menu</a>
            <h1>👥 Użytkownicy</h1>
            <form id='addUserForm'>
                <div class='form-group'>
                    <label for='name'>Imię użytkownika:</label>
                    <input type='text' id='name' name='name' required autocomplete='off'>
                </div>
                <button type='submit'>Dodaj użytkownika</button>
                <div id='formMsg'></div>
            </form>
            <div id='warnMsg' class='warn'></div>
            <div class='user-list' id='userList'></div>
        </div>
        <script>
        async function loadUsers() {
            const res = await fetch('/api/users');
            const users = await res.json();
            const list = document.getElementById('userList');
            list.innerHTML = '';
            let has1 = false, has2 = false;
            users.forEach(u => {
                if (u.id === 1) has1 = true;
                if (u.id === 2) has2 = true;
                list.innerHTML += `<div class='user-item'><span class='user-id'>ID: ${u.id}</span> <span>${u.name}</span></div>`;
            });
            const warn = document.getElementById('warnMsg');
            if (!has1 || !has2) {
                warn.textContent = 'Brakuje użytkowników o ID 1 lub 2! Dodaj ich, aby rozliczenia działały poprawnie.';
            } else {
                warn.textContent = '';
            }
        }
        document.getElementById('addUserForm').onsubmit = async function(e) {
            e.preventDefault();
            const name = document.getElementById('name').value.trim();
            const msg = document.getElementById('formMsg');
            msg.textContent = '';
            if (!name) {
                msg.textContent = 'Imię jest wymagane.';
                msg.className = 'warn';
                return;
            }
            const btn = this.querySelector('button[type="submit"]');
            btn.disabled = true;
            try {
                const resp = await fetch('/api/add-user', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name })
                });
                const result = await resp.json();
                if (resp.ok) {
                    msg.textContent = 'Użytkownik dodany!';
                    msg.className = 'success';
                    this.reset();
                    await loadUsers();
                } else {
                    msg.textContent = result.detail || 'Błąd dodawania użytkownika.';
                    msg.className = 'warn';
                }
            } catch (e) {
                msg.textContent = 'Błąd sieci: ' + e.message;
                msg.className = 'warn';
            } finally {
                btn.disabled = false;
            }
        };
        window.onload = loadUsers;
        </script>
    </body>
    </html>
    """

@app.get("/assign-payments/", response_class=HTMLResponse)
async def assign_payments_page():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Przypisz płatności</title>
        <meta name='viewport' content='width=device-width, initial-scale=1'>
        <style>
            body { font-family: Arial, sans-serif; background: #f5f5f5; }
            .container { max-width: 600px; margin: 0 auto; background: white; padding: 24px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h1 { color: #333; text-align: center; }
            .back-btn { background: #6c757d; color: white; padding: 8px 15px; border: none; border-radius: 4px; text-decoration: none; display: inline-block; margin: 10px 0; }
            .payment-list { margin-top: 24px; }
            .payment-item { padding: 12px 0; border-bottom: 1px solid #eee; display: flex; align-items: center; gap: 10px; }
            .payment-name { font-weight: bold; min-width: 120px; }
            .assign-btn { background: #007bff; color: white; border: none; border-radius: 4px; padding: 6px 14px; cursor: pointer; margin-left: 10px; }
            .assign-btn:disabled { opacity: 0.6; }
            .success { color: #28a745; font-weight: bold; margin: 10px 0; }
            .warn { color: #dc3545; font-weight: bold; margin: 10px 0; }
            .alert { background:#fff3cd;color:#856404;padding:18px 24px;border-radius:8px;margin-bottom:18px;border:1px solid #ffeeba;text-align:center;font-size:1.1em; }
        </style>
    </head>
    <body>
        <div class='container'>
            <a href='/' class='back-btn'>← Powrót do menu</a>
            <div id='userAlert'></div>
            <h1>Przypisz płatności</h1>
            <div id='msg'></div>
            <div class='payment-list' id='paymentList'></div>
        </div>
        <script>
        let canAssign = false;
        async function checkUsers() {
            const res = await fetch('/api/users');
            const users = await res.json();
            let has1 = false, has2 = false;
            users.forEach(u => { if (u.id === 1) has1 = true; if (u.id === 2) has2 = true; });
            const alertDiv = document.getElementById('userAlert');
            if (!has1 || !has2) {
                alertDiv.innerHTML = `<div class='alert'>Brakuje wymaganych użytkowników (ID 1 i 2)! Dodaj ich, aby móc przypisywać płatności.</div>`;
                canAssign = false;
            } else {
                alertDiv.innerHTML = '';
                canAssign = true;
            }
        }
        async function loadPayments() {
            await checkUsers();
            const res = await fetch('/api/unassigned-payments');
            const data = await res.json();
            // Pobierz użytkowników
            const usersRes = await fetch('/api/users');
            const users = await usersRes.json();
            const list = document.getElementById('paymentList');
            list.innerHTML = '';
            if (!data.length) {
                list.innerHTML = '<div class="success">Wszystkie płatności są przypisane!</div>';
                return;
            }
            data.forEach(item => {
                const div = document.createElement('div');
                div.className = 'payment-item';
                // Buduj select z imionami użytkowników (ID 1, 2, 100)
                let selectHtml = '<select>';
                // Zawsze pokaż 1, 2, 100 jeśli istnieją w bazie
                [1,2,100].forEach(uid => {
                    const u = users.find(x => x.id === uid);
                    if (u) selectHtml += `<option value='${u.id}'>${u.name}</option>`;
                });
                selectHtml += '</select>';
                div.innerHTML = `<span class='payment-name'>${item.payment_name}</span>
                    ${selectHtml}
                    <button class='assign-btn'>Przypisz</button>`;
                const select = div.querySelector('select');
                const btn = div.querySelector('button');
                btn.onclick = async function() {
                    if (!canAssign) return;
                    btn.disabled = true;
                    const user_id = select.value;
                    const resp = await fetch('/api/assign-payment', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ payment_name: item.payment_name, user_id: parseInt(user_id) })
                    });
                    if (resp.ok) {
                        div.innerHTML = `<span class='success'>Przypisano do użytkownika ID ${user_id}</span>`;
                        loadPayments();
                    } else {
                        const result = await resp.json();
                        div.innerHTML += `<span class='warn'>Błąd: ${result.detail || 'Nieznany błąd'}</span>`;
                    }
                };
                if (!canAssign) btn.disabled = true;
                list.appendChild(div);
            });
        }
        window.onload = loadPayments;
        </script>
    </body>
    </html>
    """

@app.get("/api/unassigned-payments")
async def api_unassigned_payments():
    db = SessionLocal()
    try:
        # payment_name z receipts, których nie ma w user_payments
        result = db.execute(text("""
            SELECT DISTINCT r.payment_name
            FROM receipts r
            LEFT JOIN user_payments up ON r.payment_name = up.payment_name
            WHERE up.payment_name IS NULL
        """)).fetchall()
        return [{"payment_name": row[0]} for row in result]
    finally:
        db.close()

@app.post("/api/assign-payment")
async def api_assign_payment(request: Request):
    db = SessionLocal()
    try:
        data = await request.json()
        payment_name = data.get('payment_name')
        user_id = data.get('user_id')
        if not payment_name or not user_id:
            return JSONResponse({'detail': 'Brak danych.'}, status_code=400)
        # Dodaj do user_payments
        db.execute(text("INSERT INTO user_payments (user_id, payment_name) VALUES (:user_id, :payment_name) ON CONFLICT (payment_name) DO NOTHING"), {"user_id": user_id, "payment_name": payment_name})
        db.commit()
        return {"message": "Przypisano."}
    except Exception as e:
        db.rollback()
        return JSONResponse({'detail': str(e)}, status_code=500)
    finally:
        db.close()

@app.post("/api/upload-receipt")
async def upload_receipt(file: UploadFile = File(...)):
    db = SessionLocal()
    try:
        content = await file.read()
        try:
            data =_json.loads(content)
            # Walidacja i zapis do bazy (przykład, dostosuj do swojego modelu)
            # validate_and_save_receipt(data)  # <- tu Twoja funkcja walidująca i zapisująca
            # ...
            # Jeśli OK:
            return {"message": "Paragon zapisany do bazy."}
        except Exception as ve:
            # Loguj błąd do upload_errors
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS upload_errors (
                    id SERIAL PRIMARY KEY,
                    filename VARCHAR(255),
                    error_message TEXT,
                    timestamp TIMESTAMP,
                    raw_content TEXT
                )
            """))
            db.execute(text("""
                INSERT INTO upload_errors (filename, error_message, timestamp, raw_content)
                VALUES (:filename, :error_message, :timestamp, :raw_content)
            """), {
                "filename": file.filename,
                "error_message": str(ve),
                "timestamp": datetime.utcnow(),
                "raw_content": content.decode(errors='replace')[:10000]  # ogranicz długość
            })
            db.commit()
            return JSONResponse({"detail": f"Błąd walidacji: {ve}"}, status_code=400)
    except Exception as e:
        db.rollback()
        return JSONResponse({"detail": f"Błąd przetwarzania: {e}"}, status_code=500)
    finally:
        db.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)