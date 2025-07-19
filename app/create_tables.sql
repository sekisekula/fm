-- Create table stores
CREATE TABLE IF NOT EXISTS stores (
    store_id SERIAL PRIMARY KEY,
    store_name VARCHAR(255) NOT NULL,
    store_city VARCHAR(255),
    store_address VARCHAR(255) NOT NULL,
    postal_code VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (store_name, store_address, postal_code)
);

-- Create table users
CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create table user_payments
-- This table maps "payment_name" from receipt to user_id.
-- One user can have MULTIPLE payment_names.
CREATE TABLE IF NOT EXISTS user_payments (
    user_payment_id SERIAL PRIMARY KEY, -- New primary key for record uniqueness
    user_id INT NOT NULL REFERENCES users(user_id), -- Foreign key to users table
    payment_name VARCHAR(255) NOT NULL, -- This is a unique payment name from receipt
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (payment_name) -- Ensures payment name uniqueness to map to only one user_payment_id
);

-- Create table receipts
CREATE TABLE IF NOT EXISTS receipts (
    receipt_id SERIAL PRIMARY KEY,
    store_id INT NOT NULL REFERENCES stores(store_id),
    receipt_number VARCHAR(255) NOT NULL,
    date DATE NOT NULL,
    time TIME NOT NULL,
    final_price DECIMAL(10, 2) NOT NULL,
    total_discounts DECIMAL(10, 2),
    -- `payment_name` tutaj będzie kluczem obcym do `user_payments`
    payment_name VARCHAR(255), -- już bez FOREIGN KEY
    counted BOOLEAN DEFAULT FALSE,    -- Czy paragon został już podliczony
    settled BOOLEAN DEFAULT FALSE,    -- Czy paragon został już rozliczony i nie powinien być uwzględniany w podsumowaniach
    not_our_receipt BOOLEAN DEFAULT FALSE, -- Czy paragon nie należy do nas
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    currency CHAR(3) NOT NULL DEFAULT 'PLN',
    UNIQUE (store_id, receipt_number, date, time) -- Zapewnia unikalność paragonu
);

-- Create table manual_expenses
CREATE TABLE IF NOT EXISTS manual_expenses (
    manual_expense_id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    description TEXT,
    total_cost DECIMAL(10, 2) NOT NULL,
    payer_user_id INT NOT NULL REFERENCES users(user_id),
    counted BOOLEAN DEFAULT TRUE,
    settled BOOLEAN DEFAULT FALSE,
    category VARCHAR(255) DEFAULT 'Other',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create table products
CREATE TABLE IF NOT EXISTS products (
    product_id SERIAL PRIMARY KEY,
    receipt_id INT REFERENCES receipts(receipt_id),
    manual_expense_id INT REFERENCES manual_expenses(manual_expense_id), -- For virtual products from manual expenses
    product_name VARCHAR(255) NOT NULL,
    quantity DECIMAL(10, 3) NOT NULL,
    tax_type CHAR(1) NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW(),
    unit_price_before DECIMAL(10, 2) NOT NULL,
    total_price_before DECIMAL(10, 2) NOT NULL,
    unit_discount DECIMAL(10, 2),
    total_discount DECIMAL(10, 2),
    unit_after_discount DECIMAL(10, 2),
    total_after_discount DECIMAL(10, 2) NOT NULL
);

-- Create table static_shares
CREATE TABLE IF NOT EXISTS static_shares (
    share_id SERIAL PRIMARY KEY,
    product_name VARCHAR(255) NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(user_id),
    share DECIMAL(5,2) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (product_name, user_id)
);

CREATE TABLE IF NOT EXISTS static_shares_history (
    history_id SERIAL PRIMARY KEY,
    share_id INTEGER NOT NULL REFERENCES static_shares(share_id),
    old_share DECIMAL(5,2),
    new_share DECIMAL(5,2) NOT NULL,
    changed_by VARCHAR(255) NOT NULL,
    changed_at TIMESTAMP DEFAULT NOW(),
    change_reason TEXT,
    FOREIGN KEY (share_id) REFERENCES static_shares(share_id)
);

-- Create table for ignored payment names
CREATE TABLE IF NOT EXISTS ignored_payment_names (
    id SERIAL PRIMARY KEY,
    payment_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (payment_name)
);

-- Create table shares
-- This table stores percentage shares for each product (including virtual products for manual expenses) per user
CREATE TABLE IF NOT EXISTS shares (
    share_id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    share DECIMAL(5,2) NOT NULL CHECK (share >= 0 AND share <= 100),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (product_id, user_id)
);

-- Create settlements table (summary settlements)
CREATE TABLE IF NOT EXISTS settlements (
    settlement_id SERIAL PRIMARY KEY,
    payer_user_id INT NOT NULL REFERENCES users(user_id),
    debtor_user_id INT NOT NULL REFERENCES users(user_id),
    amount DECIMAL(10,2) NOT NULL,
    note TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    finalized_by INT REFERENCES users(user_id), -- who finalized
    finalized_at TIMESTAMP,                    -- when finalized
    CHECK (payer_user_id != debtor_user_id)
);

-- Linking table: which receipts/manual_expenses are included in each settlement
CREATE TABLE IF NOT EXISTS settlement_items (
    settlement_item_id SERIAL PRIMARY KEY,
    settlement_id INT NOT NULL REFERENCES settlements(settlement_id) ON DELETE CASCADE,
    receipt_id INT REFERENCES receipts(receipt_id),
    manual_expense_id INT REFERENCES manual_expenses(manual_expense_id),
    -- amount DECIMAL(10,2), -- (optional, for partial settlements)
    CHECK (
        (receipt_id IS NOT NULL AND manual_expense_id IS NULL)
        OR (receipt_id IS NULL AND manual_expense_id IS NOT NULL)
    ),
    UNIQUE (settlement_id, receipt_id, manual_expense_id)
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE constraint_name = 'stores_unique_name_address_postal'
          AND table_name = 'stores'
    ) THEN
        ALTER TABLE stores
        ADD CONSTRAINT stores_unique_name_address_postal UNIQUE (store_name, store_address, postal_code);
    END IF;
END $$;

INSERT INTO users (user_id, name)
SELECT 100, 'Inny'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE user_id = 100);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE constraint_name = 'unique_receipt'
          AND table_name = 'receipts'
    ) THEN
        ALTER TABLE receipts
        ADD CONSTRAINT unique_receipt UNIQUE (receipt_number, date, store_id);
    END IF;
END $$;