import os
import tempfile
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Uproszczony schemat do SQLite
SQL_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), '..', 'app', 'create_tables_sqlite.sql')

@pytest.fixture(scope="function")
def sqlite_db():
    db_fd, db_path = tempfile.mkstemp(suffix='.sqlite')
    engine = create_engine(f'sqlite:///{db_path}')
    Session = sessionmaker(bind=engine)
    session = Session()
    # Wczytaj uproszczony schemat bazy
    with open(SQL_SCHEMA_PATH, encoding='utf-8') as f:
        schema_sql = f.read()
    for stmt in schema_sql.split(';'):
        stmt = stmt.strip()
        if stmt:
            try:
                session.execute(text(stmt))
            except Exception:
                pass
    session.commit()
    yield session
    session.close()
    engine.dispose()  # Zamknij połączenie z bazą (ważne na Windowsie)
    os.close(db_fd)
    os.remove(db_path)

def test_duplicate_store(sqlite_db):
    # Dodaj sklep
    sqlite_db.execute(text("""
        INSERT INTO stores (store_name, store_address, postal_code, store_city)
        VALUES ('Biedronka', 'ul. Testowa 1', '00-001', 'Warszawa')
    """))
    sqlite_db.commit()
    # Spróbuj dodać ten sam sklep ponownie
    with pytest.raises(Exception):
        sqlite_db.execute(text("""
            INSERT INTO stores (store_name, store_address, postal_code, store_city)
            VALUES ('Biedronka', 'ul. Testowa 1', '00-001', 'Warszawa')
        """))
        sqlite_db.commit()

def test_duplicate_user_payment(sqlite_db):
    # Dodaj użytkownika
    sqlite_db.execute(text("INSERT INTO users (name) VALUES ('Jan')"))
    user_id = sqlite_db.execute(text("SELECT user_id FROM users WHERE name='Jan'")).fetchone()[0]
    sqlite_db.commit()
    # Dodaj payment_name
    sqlite_db.execute(text("""
        INSERT INTO user_payments (user_id, payment_name)
        VALUES (:uid, 'Karta123')
    """), {"uid": user_id})
    sqlite_db.commit()
    # Spróbuj dodać ten sam payment_name
    with pytest.raises(Exception):
        sqlite_db.execute(text("""
            INSERT INTO user_payments (user_id, payment_name)
            VALUES (:uid, 'Karta123')
        """), {"uid": user_id})
        sqlite_db.commit()

def test_duplicate_receipt(sqlite_db):
    # Dodaj sklep i payment_name
    sqlite_db.execute(text("INSERT INTO stores (store_name, store_address, postal_code, store_city) VALUES ('Lidl', 'ul. Testowa 2', '00-002', 'Kraków')"))
    store_id = sqlite_db.execute(text("SELECT store_id FROM stores WHERE store_name='Lidl'" )).fetchone()[0]
    sqlite_db.execute(text("INSERT INTO users (name) VALUES ('Anna')"))
    user_id = sqlite_db.execute(text("SELECT user_id FROM users WHERE name='Anna'" )).fetchone()[0]
    sqlite_db.execute(text("INSERT INTO user_payments (user_id, payment_name) VALUES (:uid, 'Karta456')"), {"uid": user_id})
    sqlite_db.commit()
    # Dodaj paragon
    sqlite_db.execute(text("""
        INSERT INTO receipts (store_id, receipt_number, date, time, final_price, payment_name)
        VALUES (:sid, '123/2024', '2024-07-01', '12:00:00', 100.00, 'Karta456')
    """), {"sid": store_id})
    sqlite_db.commit()
    # Spróbuj dodać ten sam paragon
    with pytest.raises(Exception):
        sqlite_db.execute(text("""
            INSERT INTO receipts (store_id, receipt_number, date, time, final_price, payment_name)
            VALUES (:sid, '123/2024', '2024-07-01', '12:00:00', 100.00, 'Karta456')
        """), {"sid": store_id})
        sqlite_db.commit()

def test_duplicate_share(sqlite_db):
    # Dodaj wymagane dane
    sqlite_db.execute(text("INSERT INTO users (name) VALUES ('Jan')"))
    user_id = sqlite_db.execute(text("SELECT user_id FROM users WHERE name='Jan'")).fetchone()[0]
    sqlite_db.execute(text("INSERT INTO receipts (store_id, receipt_number, date, time, final_price, payment_name) VALUES (1, '1', '2024-07-01', '10:00:00', 10.00, 'KartaX')"))
    sqlite_db.execute(text("INSERT INTO products (receipt_id, product_name, quantity, tax_type, unit_price_before, total_price_before, unit_after_discount, total_after_discount) VALUES (1, 'Chleb', 1.0, 'A', 5.00, 5.00, 5.00, 5.00)"))
    product_id = sqlite_db.execute(text("SELECT product_id FROM products WHERE product_name='Chleb'" )).fetchone()[0]
    sqlite_db.commit()
    # Dodaj udział
    sqlite_db.execute(text("INSERT INTO shares (product_id, user_id, share) VALUES (:pid, :uid, 50.0)"), {"pid": product_id, "uid": user_id})
    sqlite_db.commit()
    # Spróbuj dodać ten sam udział
    with pytest.raises(Exception):
        sqlite_db.execute(text("INSERT INTO shares (product_id, user_id, share) VALUES (:pid, :uid, 50.0)"), {"pid": product_id, "uid": user_id})
        sqlite_db.commit()

def test_duplicate_static_share(sqlite_db):
    # Dodaj static_share
    sqlite_db.execute(text("INSERT INTO static_shares (product_name, share) VALUES ('Masło', 50.0)"))
    sqlite_db.commit()
    # Spróbuj dodać ten sam static_share
    with pytest.raises(Exception):
        sqlite_db.execute(text("INSERT INTO static_shares (product_name, share) VALUES ('Masło', 50.0)"))
        sqlite_db.commit()

def test_manual_expenses_duplicates_allowed(sqlite_db):
    # Można dodać dwa identyczne wydatki ręczne
    sqlite_db.execute(text("""
        CREATE TABLE IF NOT EXISTS manual_expenses (
            manual_expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            description TEXT,
            total_cost REAL NOT NULL,
            payer_user_id INTEGER NOT NULL,
            counted INTEGER DEFAULT 1,
            settled INTEGER DEFAULT 0,
            category TEXT DEFAULT 'Other',
            created_at TEXT,
            updated_at TEXT
        )
    """))
    sqlite_db.commit()
    sqlite_db.execute(text("INSERT INTO users (name) VALUES ('Jan')"))
    user_id = sqlite_db.execute(text("SELECT user_id FROM users WHERE name='Jan'")).fetchone()[0]
    sqlite_db.execute(text("""
        INSERT INTO manual_expenses (date, description, total_cost, payer_user_id)
        VALUES ('2024-07-01', 'Prąd', 100.00, :uid)
    """), {"uid": user_id})
    sqlite_db.execute(text("""
        INSERT INTO manual_expenses (date, description, total_cost, payer_user_id)
        VALUES ('2024-07-01', 'Prąd', 100.00, :uid)
    """), {"uid": user_id})
    sqlite_db.commit()
    count = sqlite_db.execute(text("SELECT COUNT(*) FROM manual_expenses WHERE description='Prąd' AND total_cost=100.00")).fetchone()[0]
    assert count == 2

def test_products_duplicates_allowed(sqlite_db):
    # Można dodać dwa identyczne produkty do tego samego paragonu
    sqlite_db.execute(text("INSERT INTO stores (store_name, store_address, postal_code, store_city) VALUES ('A', 'B', 'C', 'D')"))
    store_id = sqlite_db.execute(text("SELECT store_id FROM stores WHERE store_name='A'" )).fetchone()[0]
    sqlite_db.execute(text("INSERT INTO users (name) VALUES ('Jan')"))
    user_id = sqlite_db.execute(text("SELECT user_id FROM users WHERE name='Jan'")).fetchone()[0]
    sqlite_db.execute(text("INSERT INTO user_payments (user_id, payment_name) VALUES (:uid, 'KartaX')"), {"uid": user_id})
    sqlite_db.execute(text("INSERT INTO receipts (store_id, receipt_number, date, time, final_price, payment_name) VALUES (:sid, '1', '2024-07-01', '10:00:00', 10.00, 'KartaX')"), {"sid": store_id})
    receipt_id = sqlite_db.execute(text("SELECT receipt_id FROM receipts WHERE receipt_number='1'" )).fetchone()[0]
    sqlite_db.execute(text("INSERT INTO products (receipt_id, product_name, quantity, tax_type, unit_price_before, total_price_before, unit_after_discount, total_after_discount) VALUES (:rid, 'Chleb', 1.0, 'A', 5.00, 5.00, 5.00, 5.00)"), {"rid": receipt_id})
    sqlite_db.execute(text("INSERT INTO products (receipt_id, product_name, quantity, tax_type, unit_price_before, total_price_before, unit_after_discount, total_after_discount) VALUES (:rid, 'Chleb', 1.0, 'A', 5.00, 5.00, 5.00, 5.00)"), {"rid": receipt_id})
    sqlite_db.commit()
    count = sqlite_db.execute(text("SELECT COUNT(*) FROM products WHERE product_name='Chleb' AND receipt_id=:rid"), {"rid": receipt_id}).fetchone()[0]
    assert count == 2

def test_shares_multiple_users(sqlite_db):
    # Można dodać różne udziały dla różnych użytkowników do tego samego produktu
    sqlite_db.execute(text("INSERT INTO users (name) VALUES ('Jan')"))
    sqlite_db.execute(text("INSERT INTO users (name) VALUES ('Anna')"))
    user1 = sqlite_db.execute(text("SELECT user_id FROM users WHERE name='Jan'")).fetchone()[0]
    user2 = sqlite_db.execute(text("SELECT user_id FROM users WHERE name='Anna'")).fetchone()[0]
    sqlite_db.execute(text("INSERT INTO receipts (store_id, receipt_number, date, time, final_price, payment_name) VALUES (1, '1', '2024-07-01', '10:00:00', 10.00, 'KartaX')"))
    sqlite_db.execute(text("INSERT INTO products (receipt_id, product_name, quantity, tax_type, unit_price_before, total_price_before, unit_after_discount, total_after_discount) VALUES (1, 'Chleb', 1.0, 'A', 5.00, 5.00, 5.00, 5.00)"))
    product_id = sqlite_db.execute(text("SELECT product_id FROM products WHERE product_name='Chleb'" )).fetchone()[0]
    sqlite_db.execute(text("INSERT INTO shares (product_id, user_id, share) VALUES (:pid, :uid, 50.0)"), {"pid": product_id, "uid": user1})
    sqlite_db.execute(text("INSERT INTO shares (product_id, user_id, share) VALUES (:pid, :uid, 50.0)"), {"pid": product_id, "uid": user2})
    sqlite_db.commit()
    count = sqlite_db.execute(text("SELECT COUNT(*) FROM shares WHERE product_id=:pid"), {"pid": product_id}).fetchone()[0]
    assert count == 2

def test_static_shares_multiple_products(sqlite_db):
    # Można dodać różne produkty do static_shares
    sqlite_db.execute(text("INSERT INTO static_shares (product_name, share) VALUES ('Masło', 50.0)"))
    sqlite_db.execute(text("INSERT INTO static_shares (product_name, share) VALUES ('Chleb', 30.0)"))
    sqlite_db.commit()
    count = sqlite_db.execute(text("SELECT COUNT(*) FROM static_shares")).fetchone()[0]
    assert count == 2

def test_receipts_same_number_different_store(sqlite_db):
    # Można dodać dwa paragony o tym samym numerze, ale innym sklepie
    sqlite_db.execute(text("INSERT INTO stores (store_name, store_address, postal_code, store_city) VALUES ('A', 'B', 'C', 'D')"))
    sqlite_db.execute(text("INSERT INTO stores (store_name, store_address, postal_code, store_city) VALUES ('E', 'F', 'G', 'H')"))
    store1 = sqlite_db.execute(text("SELECT store_id FROM stores WHERE store_name='A'" )).fetchone()[0]
    store2 = sqlite_db.execute(text("SELECT store_id FROM stores WHERE store_name='E'" )).fetchone()[0]
    sqlite_db.execute(text("INSERT INTO users (name) VALUES ('Jan')"))
    user_id = sqlite_db.execute(text("SELECT user_id FROM users WHERE name='Jan'")).fetchone()[0]
    sqlite_db.execute(text("INSERT INTO user_payments (user_id, payment_name) VALUES (:uid, 'KartaX')"), {"uid": user_id})
    sqlite_db.execute(text("INSERT INTO receipts (store_id, receipt_number, date, time, final_price, payment_name) VALUES (:sid, '1', '2024-07-01', '10:00:00', 10.00, 'KartaX')"), {"sid": store1})
    sqlite_db.execute(text("INSERT INTO receipts (store_id, receipt_number, date, time, final_price, payment_name) VALUES (:sid, '1', '2024-07-01', '10:00:00', 10.00, 'KartaX')"), {"sid": store2})
    sqlite_db.commit()
    count = sqlite_db.execute(text("SELECT COUNT(*) FROM receipts WHERE receipt_number='1' AND date='2024-07-01' AND time='10:00:00'" )).fetchone()[0]
    assert count == 2 

def test_shares_foreign_key_product(sqlite_db):
    # Próba dodania udziału do nieistniejącego produktu powinna się nie udać (brak produktu)
    sqlite_db.execute(text("INSERT INTO users (name) VALUES ('Jan')"))
    user_id = sqlite_db.execute(text("SELECT user_id FROM users WHERE name='Jan'")).fetchone()[0]
    with pytest.raises(Exception):
        sqlite_db.execute(text("INSERT INTO shares (product_id, user_id, share) VALUES (999, :uid, 50.0)"), {"uid": user_id})
        sqlite_db.commit()

def test_shares_foreign_key_user(sqlite_db):
    # Próba dodania udziału do nieistniejącego użytkownika powinna się nie udać (brak usera)
    sqlite_db.execute(text("INSERT INTO stores (store_name, store_address, postal_code, store_city) VALUES ('A', 'B', 'C', 'D')"))
    store_id = sqlite_db.execute(text("SELECT store_id FROM stores WHERE store_name='A'" )).fetchone()[0]
    sqlite_db.execute(text("INSERT INTO users (name) VALUES ('Jan')"))
    sqlite_db.execute(text("INSERT INTO user_payments (user_id, payment_name) VALUES (1, 'KartaX')"))
    sqlite_db.execute(text("INSERT INTO receipts (store_id, receipt_number, date, time, final_price, payment_name) VALUES (:sid, '1', '2024-07-01', '10:00:00', 10.00, 'KartaX')"), {"sid": store_id})
    sqlite_db.execute(text("INSERT INTO products (receipt_id, product_name, quantity, tax_type, unit_price_before, total_price_before, unit_after_discount, total_after_discount) VALUES (1, 'Chleb', 1.0, 'A', 5.00, 5.00, 5.00, 5.00)"))
    product_id = sqlite_db.execute(text("SELECT product_id FROM products WHERE product_name='Chleb'" )).fetchone()[0]
    with pytest.raises(Exception):
        sqlite_db.execute(text("INSERT INTO shares (product_id, user_id, share) VALUES (:pid, 999, 50.0)"), {"pid": product_id})
        sqlite_db.commit()

def test_receipt_unique_constraint(sqlite_db):
    # Nie można dodać dwóch paragonów o tych samych store_id, numerze, dacie i godzinie
    sqlite_db.execute(text("INSERT INTO stores (store_name, store_address, postal_code, store_city) VALUES ('A', 'B', 'C', 'D')"))
    store_id = sqlite_db.execute(text("SELECT store_id FROM stores WHERE store_name='A'" )).fetchone()[0]
    sqlite_db.execute(text("INSERT INTO users (name) VALUES ('Jan')"))
    user_id = sqlite_db.execute(text("SELECT user_id FROM users WHERE name='Jan'")).fetchone()[0]
    sqlite_db.execute(text("INSERT INTO user_payments (user_id, payment_name) VALUES (:uid, 'KartaX')"), {"uid": user_id})
    sqlite_db.execute(text("INSERT INTO receipts (store_id, receipt_number, date, time, final_price, payment_name) VALUES (:sid, '1', '2024-07-01', '10:00:00', 10.00, 'KartaX')"), {"sid": store_id})
    sqlite_db.commit()
    with pytest.raises(Exception):
        sqlite_db.execute(text("INSERT INTO receipts (store_id, receipt_number, date, time, final_price, payment_name) VALUES (:sid, '1', '2024-07-01', '10:00:00', 10.00, 'KartaX')"), {"sid": store_id})
        sqlite_db.commit()

def test_static_shares_unique_constraint(sqlite_db):
    # Nie można dodać static_shares o tej samej nazwie produktu
    sqlite_db.execute(text("INSERT INTO static_shares (product_name, share) VALUES ('Masło', 50.0)"))
    sqlite_db.commit()
    with pytest.raises(Exception):
        sqlite_db.execute(text("INSERT INTO static_shares (product_name, share) VALUES ('Masło', 60.0)"))
        sqlite_db.commit()

def test_shares_unique_constraint(sqlite_db):
    # Nie można dodać shares o tym samym product_id i user_id
    sqlite_db.execute(text("INSERT INTO users (name) VALUES ('Jan')"))
    user_id = sqlite_db.execute(text("SELECT user_id FROM users WHERE name='Jan'")).fetchone()[0]
    sqlite_db.execute(text("INSERT INTO receipts (store_id, receipt_number, date, time, final_price, payment_name) VALUES (1, '1', '2024-07-01', '10:00:00', 10.00, 'KartaX')"))
    sqlite_db.execute(text("INSERT INTO products (receipt_id, product_name, quantity, tax_type, unit_price_before, total_price_before, unit_after_discount, total_after_discount) VALUES (1, 'Chleb', 1.0, 'A', 5.00, 5.00, 5.00, 5.00)"))
    product_id = sqlite_db.execute(text("SELECT product_id FROM products WHERE product_name='Chleb'" )).fetchone()[0]
    sqlite_db.execute(text("INSERT INTO shares (product_id, user_id, share) VALUES (:pid, :uid, 50.0)"), {"pid": product_id, "uid": user_id})
    sqlite_db.commit()
    with pytest.raises(Exception):
        sqlite_db.execute(text("INSERT INTO shares (product_id, user_id, share) VALUES (:pid, :uid, 60.0)"), {"pid": product_id, "uid": user_id})
        sqlite_db.commit()

def test_shares_different_products_same_user(sqlite_db):
    # Można dodać shares dla różnych produktów i tych samych userów
    sqlite_db.execute(text("INSERT INTO users (name) VALUES ('Jan')"))
    user_id = sqlite_db.execute(text("SELECT user_id FROM users WHERE name='Jan'")).fetchone()[0]
    sqlite_db.execute(text("INSERT INTO receipts (store_id, receipt_number, date, time, final_price, payment_name) VALUES (1, '1', '2024-07-01', '10:00:00', 10.00, 'KartaX')"))
    sqlite_db.execute(text("INSERT INTO products (receipt_id, product_name, quantity, tax_type, unit_price_before, total_price_before, unit_after_discount, total_after_discount) VALUES (1, 'Chleb', 1.0, 'A', 5.00, 5.00, 5.00, 5.00)"))
    sqlite_db.execute(text("INSERT INTO products (receipt_id, product_name, quantity, tax_type, unit_price_before, total_price_before, unit_after_discount, total_after_discount) VALUES (1, 'Masło', 1.0, 'A', 7.00, 7.00, 7.00, 7.00)"))
    pid1 = sqlite_db.execute(text("SELECT product_id FROM products WHERE product_name='Chleb'" )).fetchone()[0]
    pid2 = sqlite_db.execute(text("SELECT product_id FROM products WHERE product_name='Masło'" )).fetchone()[0]
    sqlite_db.execute(text("INSERT INTO shares (product_id, user_id, share) VALUES (:pid, :uid, 50.0)"), {"pid": pid1, "uid": user_id})
    sqlite_db.execute(text("INSERT INTO shares (product_id, user_id, share) VALUES (:pid, :uid, 60.0)"), {"pid": pid2, "uid": user_id})
    sqlite_db.commit()
    count = sqlite_db.execute(text("SELECT COUNT(*) FROM shares WHERE user_id=:uid"), {"uid": user_id}).fetchone()[0]
    assert count == 2

def test_static_shares_different_products_same_share(sqlite_db):
    # Można dodać static_shares dla różnych produktów, nawet z tą samą wartością share
    sqlite_db.execute(text("INSERT INTO static_shares (product_name, share) VALUES ('Masło', 50.0)"))
    sqlite_db.execute(text("INSERT INTO static_shares (product_name, share) VALUES ('Chleb', 50.0)"))
    sqlite_db.commit()
    count = sqlite_db.execute(text("SELECT COUNT(*) FROM static_shares WHERE share=50.0")).fetchone()[0]
    assert count == 2 