-- Uproszczony schemat bazy do testów na SQLite

CREATE TABLE IF NOT EXISTS stores (
    store_id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_name TEXT NOT NULL,
    store_city TEXT,
    store_address TEXT NOT NULL,
    postal_code TEXT NOT NULL,
    created_at TEXT,
    updated_at TEXT,
    UNIQUE (store_name, store_address, postal_code)
);

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS user_payments (
    user_payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    payment_name TEXT NOT NULL,
    created_at TEXT,
    updated_at TEXT,
    UNIQUE (payment_name)
);

CREATE TABLE IF NOT EXISTS receipts (
    receipt_id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id INTEGER NOT NULL,
    receipt_number TEXT NOT NULL,
    date TEXT NOT NULL,
    time TEXT NOT NULL,
    final_price REAL NOT NULL,
    total_discounts REAL,
    payment_name TEXT NOT NULL,
    counted INTEGER DEFAULT 0,
    settled INTEGER DEFAULT 0,
    not_our_receipt INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT,
    currency TEXT DEFAULT 'PLN',
    UNIQUE (store_id, receipt_number, date, time)
);

CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_id INTEGER,
    manual_expense_id INTEGER,
    product_name TEXT NOT NULL,
    quantity REAL NOT NULL,
    tax_type TEXT NOT NULL,
    updated_at TEXT,
    unit_price_before REAL NOT NULL,
    total_price_before REAL NOT NULL,
    unit_discount REAL,
    total_discount REAL,
    unit_after_discount REAL,
    total_after_discount REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS static_shares (
    share_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT NOT NULL,
    share REAL NOT NULL,
    created_at TEXT,
    updated_at TEXT,
    UNIQUE (product_name)
);

CREATE TABLE IF NOT EXISTS shares (
    share_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    share REAL NOT NULL,
    created_at TEXT,
    updated_at TEXT,
    UNIQUE (product_id, user_id)
); 