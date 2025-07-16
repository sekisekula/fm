from sqlalchemy import text, exc
from sqlalchemy.orm import declarative_base, sessionmaker
import logging
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date, time
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, validator, ValidationError
import json
from pathlib import Path
from app.config import Config

# Import session configuration and models
from .session import SessionLocal, engine, Base
from .models import Product  # Assuming models are defined in models.py

# Configure logging
logger = logging.getLogger(__name__)

# Pydantic models for data validation
class ReceiptHeaderModel(BaseModel):
    """Model for validating receipt header data."""
    receipt_number: str
    date: str
    time: str
    final_price: float
    total_discounts: float = 0.0
    currency: str = "PLN"

    @validator('date')
    def validate_date(cls, v):
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError('Invalid date format. Expected YYYY-MM-DD')

    @validator('time')
    def validate_time(cls, v):
        try:
            datetime.strptime(v, '%H:%M:%S')
            return v
        except ValueError:
            raise ValueError('Invalid time format. Expected HH:MM:SS')

# Path to the SQL file for creating tables
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # katalog główny projektu
create_tables_path = BASE_DIR / "app" / "create_tables.sql"

# Configure logger
logger = logging.getLogger(__name__)

def create_tables():
    """Create tables using SQLAlchemy engine and SQL script (obsługa DO $$ ... $$)."""
    try:
        with engine.connect() as connection:
            with open(create_tables_path, "r") as file:
                sql_script = file.read()
                raw_conn = connection.connection
                cur = raw_conn.cursor()
                try:
                    cur.execute(sql_script)
                finally:
                    cur.close()
                raw_conn.commit()
            logger.info("Tables created or updated successfully.")
    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        raise RuntimeError(f"Failed to create tables: {e}") from e

def ensure_special_user_other(db):
    result = db.execute(
        text("SELECT user_id FROM users WHERE user_id = 100 AND name = 'Inny'")
    ).fetchone()
    if not result:
        db.execute(
            text("INSERT INTO users (user_id, name) VALUES (100, 'Inny') ON CONFLICT (user_id) DO NOTHING")
        )
        db.commit()

def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        raise
    finally:
        db.close()





def parse_date(date_str):
    # This function is now mostly handled by parse_receipt, but keeping it
    # for explicit date parsing if needed elsewhere.
    if isinstance(date_str, date): # If it's already a date object
        return date_str
    try:
        # Assuming date_str is 'YYYY-MM-DD' from isoformat()
        return datetime.fromisoformat(date_str).date()
    except ValueError as e:
        logger.warning(f"Invalid date format: {date_str} - {e}")
        return None

def parse_time(time_str):
    if isinstance(time_str, time):
        return time_str
    try:
        # Assuming time_str is 'HH:MM:SS' or 'HH:MM:SS.ffffff' from isoformat()
        return datetime.fromisoformat(f"2000-01-01T{time_str}").time()
    except ValueError as e:
        logger.warning(f"Invalid time format: {time_str} - {e}")
        return None

def insert_store(store):
    try:
        store_name = store.get("store_name")
        store_address = store.get("store_address")
        postal_code = store.get("postal_code")
        store_city = store.get("store_city")

        with SessionLocal() as db:
            result = db.execute(text(
                """
                INSERT INTO stores (store_name, store_address, postal_code, store_city)
                VALUES (:store_name, :store_address, :postal_code, :store_city)
                ON CONFLICT (store_name, store_address, postal_code) DO UPDATE
                SET store_name = EXCLUDED.store_name, -- Update name if unique conflict
                    store_city = EXCLUDED.store_city,
                    updated_at = NOW()
                RETURNING store_id
                """
            ), {
                "store_name": store_name,
                "store_address": store_address,
                "postal_code": postal_code,
                "store_city": store_city
            })
            store_id = result.fetchone()
            if store_id:
                db.commit()  # Explicit commit after store insertion
                return store_id[0]
            else:
                result = db.execute(text(
                    """
                    SELECT store_id FROM stores
                    WHERE store_name = :store_name AND store_address = :store_address 
                    AND postal_code = :postal_code
                    """
                ), {
                    "store_name": store_name,
                    "store_address": store_address,
                    "postal_code": postal_code
                })
                store_id = result.fetchone()
                if store_id:
                    db.commit()  # Commit if we found an existing store
                    return store_id[0]
                raise ValueError(f"Could not insert or retrieve store ID for {store_name}")
    except Exception as e:
        logger.error(f"Error inserting store: {e}")
        db.rollback() if db else None  # Rollback if there's an active session
        raise

def insert_products_bulk(products: List[Dict[str, Any]], receipt_id: int, db=None) -> None:
    """Insert multiple products in a single transaction.
    Args:
        products: List of product dictionaries
        receipt_id: ID of the receipt these products belong to
        db: Optional database session. If not provided, a new transaction will be created.
    """
    if not products:
        return

    products_data = []
    for p in products:
        product_data = {
            'receipt_id': receipt_id,
            'product_name': p.get('product_name', '').strip(),
            'quantity': Decimal(str(p.get('quantity', 1))).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP),
            'tax_type': str(p.get('tax_type', 'A'))[0],
            'unit_price_before': float(p.get('unit_price_before', 0)),
            'total_price_before': float(p.get('total_price_before', 0)),
            'unit_discount': float(p.get('unit_discount', 0)),
            'total_discount': float(p.get('total_discount', 0)),
            'unit_after_discount': float(p.get('unit_after_discount', p.get('unit_price_before', 0))),
            'total_after_discount': float(p.get('total_after_discount', p.get('total_price_before', 0)))
        }
        products_data.append(product_data)

    if db is not None:
        db.bulk_insert_mappings(Product, products_data)
    else:
        from db.utils import transaction_scope
        with transaction_scope() as db_session:
            db_session.bulk_insert_mappings(Product, products_data)  # type: ignore

def ensure_other_payment_method(db) -> str:
    """Ensure the 'OTHER' payment method exists in user_payments.
    
    Returns:
        str: The payment name to use for 'other' receipts
    """
    other_payment_name = "OTHER"
    
    # Check if it already exists
    existing = db.execute(
        text("SELECT 1 FROM user_payments WHERE payment_name = :payment_name"),
        {"payment_name": other_payment_name}
    ).fetchone()
    
    if not existing:
        # Insert with user_id 1 (or any default user)
        db.execute(
            text("""
                INSERT INTO user_payments (user_id, payment_name)
                VALUES (1, :payment_name)
                ON CONFLICT (payment_name) DO NOTHING
            """),
            {"payment_name": other_payment_name}
        )
        db.commit()
        logger.info(f"Created 'OTHER' payment method in user_payments")
    
    return other_payment_name

def check_duplicate_receipt(db, receipt_number: str, transaction_date: str, transaction_time: str) -> Optional[int]:
    """Check if a receipt with the same receipt_number, date, and time already exists.
    
    Args:
        db: Database session
        receipt_number: Receipt number to check
        transaction_date: Transaction date in YYYY-MM-DD format
        transaction_time: Transaction time in HH:MM:SS format
        
    Returns:
        int: The receipt_id if a duplicate is found, None otherwise
    """
    if not all([receipt_number, transaction_date, transaction_time]):
        return None
        
    try:
        # Convert time to handle potential format differences (e.g., '12:34:56' vs '12:34:56.000')
        time_obj = datetime.strptime(transaction_time, '%H:%M:%S').time()
        time_str = time_obj.strftime('%H:%M:%S')
        
        # Check for existing receipt with same number, date, and time
        result = db.execute(
            text("""
                SELECT receipt_id 
                FROM receipts 
                WHERE receipt_number = :receipt_number 
                  AND transaction_date = :transaction_date 
                  AND time(transaction_time) = time(:transaction_time)
                  AND deleted_at IS NULL
            """),
            {
                "receipt_number": receipt_number,
                "transaction_date": transaction_date,
                "transaction_time": time_str
            }
        ).fetchone()
        
        return result[0] if result else None
        
    except Exception as e:
        logger.error(f"Error checking for duplicate receipt {receipt_number}: {e}")
        return None

def is_payment_name_ignored(payment_name):
    try:
        with SessionLocal() as db:
            result = db.execute(text(
                """
                SELECT 1 FROM ignored_payment_names 
                WHERE payment_name = :payment_name
                """
            ), {
                "payment_name": payment_name
            })
            return result.fetchone() is not None
    except Exception as e:
        logger.error(f"Error checking if payment name is ignored: {e}")
        raise

def add_ignored_payment_name(payment_name):
    try:
        with SessionLocal() as db:
            result = db.execute(text(
                """
                INSERT INTO ignored_payment_names (payment_name)
                VALUES (:payment_name)
                ON CONFLICT (payment_name) DO NOTHING
                """
            ), {
                "payment_name": payment_name
            })
            db.commit()
    except Exception as e:
        logger.error(f"Error adding ignored payment name: {e}")
        raise

def insert_product(product, receipt_id):
    try:
        quantity = Decimal(str(product.get("quantity", 1))).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        # Ensure Decimal objects are passed and quantized
        unit_price_before = Decimal(str(product.get("unit_price_before"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total_price_before = Decimal(str(product.get("total_price_before"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        unit_discount = Decimal(str(product.get("unit_discount", 0))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total_discount = Decimal(str(product.get("total_discount", 0))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        unit_after_discount = Decimal(str(product.get("unit_after_discount"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total_after_discount = Decimal(str(product.get("total_after_discount"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        with SessionLocal() as db:
            result = db.execute(text(
                """
                INSERT INTO products (
                    receipt_id, product_name, quantity, tax_type,
                    unit_price_before, total_price_before, unit_discount,
                    total_discount, unit_after_discount, total_after_discount
                )
                VALUES (:receipt_id, :product_name, :quantity, :tax_type, 
                    :unit_price_before, :total_price_before, :unit_discount,
                    :total_discount, :unit_after_discount, :total_after_discount)
                RETURNING product_id
                """
            ), {
                "receipt_id": receipt_id,
                "product_name": product.get("product_name"),
                "quantity": quantity,
                "tax_type": product.get("tax_type"),
                "unit_price_before": unit_price_before,
                "total_price_before": total_price_before,
                "unit_discount": unit_discount,
                "total_discount": total_discount,
                "unit_after_discount": unit_after_discount,
                "total_after_discount": total_after_discount
            })
            result_row = result.fetchone()
            if result_row is None:
                raise ValueError("Failed to insert product - no ID returned")
            return result_row[0]
    except Exception as e:
        logger.error(f"Error inserting product for receipt {receipt_id}: {product.get('product_name')} - {e}")
        raise

def insert_user_payment(user_id, payment_name):
    try:
        with SessionLocal() as db:
            try:
                # First check if payment name already exists
                existing = db.execute(
                    text("SELECT user_id FROM user_payments WHERE payment_name = :payment_name"),
                    {"payment_name": payment_name}
                ).fetchone()
                
                if existing:
                    logger.info(f"Payment name '{payment_name}' already exists for user {existing[0]}")
                    return existing[0]
                
                # Insert new payment method
                result = db.execute(
                    text(
                        """
                        INSERT INTO user_payments (user_id, payment_name)
                        VALUES (:user_id, :payment_name)
                        RETURNING user_id
                        """
                    ),
                    {"user_id": user_id, "payment_name": payment_name}
                )
                db.commit()  # Explicitly commit the transaction
                logger.info(f"Successfully added payment method: {payment_name} for user {user_id}")
                return user_id
                
            except Exception as e:
                db.rollback()
                if "duplicate key value violates unique constraint" in str(e):
                    logger.warning(f"Payment name '{payment_name}' already exists (concurrent insert).")
                    # Get the existing user_id for this payment
                    existing = db.execute(
                        text("SELECT user_id FROM user_payments WHERE payment_name = :payment_name"),
                        {"payment_name": payment_name}
                    ).fetchone()
                    return existing[0] if existing else None
                logger.error(f"Error in insert_user_payment: {e}")
                raise
                
    except Exception as e:
        logger.error(f"Database error in insert_user_payment: {e}")
        raise

def get_user_id_for_payment_name(payment_name):
    if not payment_name:
        logger.warning("Empty payment name provided to get_user_id_for_payment_name")
        return None
        
    try:
        # First check if payment name is ignored
        if is_payment_name_ignored(payment_name):
            logger.debug(f"Payment name '{payment_name}' is in ignore list")
            return None  # If ignored, return None to indicate it should be skipped

        with SessionLocal() as db:
            try:
                # Use a more explicit query with proper parameter binding
                result = db.execute(
                    text(
                        """
                        SELECT up.user_id 
                        FROM user_payments up
                        WHERE up.payment_name = :payment_name
                        LIMIT 1
                        """
                    ),
                    {"payment_name": payment_name.strip()}
                ).fetchone()
                
                if result:
                    logger.debug(f"Found user_id {result[0]} for payment method '{payment_name}'")
                    return result[0]
                else:
                    logger.debug(f"No user found for payment method: {payment_name}")
                    return None
            except Exception as db_error:
                logger.error(f"Database error in get_user_id_for_payment_name for '{payment_name}': {db_error}")
                raise
                
    except Exception as e:
        logger.error(f"Unexpected error in get_user_id_for_payment_name for '{payment_name}': {e}")
        return None  # Return None instead of raising to allow processing to continue

def insert_share(product_id: int, user_id: int, share: float) -> int:
    """Insert or update a share for a product and user.
    
    Args:
        product_id: ID of the product
        user_id: ID of the user
        share: Share percentage (0-100)
        
    Returns:
        int: The ID of the inserted/updated share
    """
    try:
        with SessionLocal() as db:
            result = db.execute(
                text("""
                INSERT INTO shares (product_id, user_id, share)
                VALUES (:product_id, :user_id, :share)
                ON CONFLICT (product_id, user_id) 
                DO UPDATE SET 
                    share = EXCLUDED.share,
                    updated_at = NOW()
                RETURNING share_id
                """
                ),
                {
                    "product_id": product_id,
                    "user_id": user_id,
                    "share": share
                }
            )
            db.commit()
            result_value = result.scalar()
            if result_value is None:
                raise ValueError("Failed to insert share - no ID returned")
            return result_value
    except Exception as e:
        logger.error(f"Error inserting share: {e}")
        raise

def insert_shares_bulk(shares_data: List[Dict[str, Any]]) -> None:
    """Insert or update multiple shares in a single transaction.
    
    Args:
        shares_data: List of dictionaries containing product_id, user_id, and share
    """
    if not shares_data:
        return
        
    try:
        with SessionLocal() as db:
            for share_data in shares_data:
                db.execute(text(
                    """
                    INSERT INTO shares (product_id, user_id, share)
                    VALUES (:product_id, :user_id, :share)
                    ON CONFLICT (product_id, user_id) 
                    DO UPDATE SET 
                        share = EXCLUDED.share,
                        updated_at = NOW()
                    """
                ), share_data)
            db.commit()
    except Exception as e:
        logger.error(f"Error inserting shares in bulk: {e}")
        raise

def insert_manual_expense(db, expense: dict):
    """Persist manual expense into `manual_expenses`, create a virtual product, and insert shares for two users."""
    try:
        # Insert manual expense (no share column)
        result = db.execute(text(
            """
            INSERT INTO manual_expenses (date, description, total_cost, payer_user_id, settled, category)
            VALUES (:date, :description, :total_cost, :user_id, :settled, :category)
            RETURNING manual_expense_id
            """
        ), {
            "date": expense["date"],
            "description": expense["description"],
            "total_cost": Decimal(str(expense["total_cost"])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "user_id": expense["user_id"],
            "settled": False,
            "category": expense.get("category", "Other")
        })
        manual_expense_id = result.fetchone()[0]

        # Create virtual product for this manual expense
        product_result = db.execute(text(
            """
            INSERT INTO products (manual_expense_id, product_name, quantity, tax_type, unit_price_before, total_price_before, unit_after_discount, total_after_discount)
            VALUES (:manual_expense_id, :product_name, 1, 'M', :total_cost, :total_cost, :total_cost, :total_cost)
            RETURNING product_id
            """
        ), {
            "manual_expense_id": manual_expense_id,
            "product_name": f"Manual Expense: {expense['description']}",
            "total_cost": Decimal(str(expense["total_cost"])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        })
        product_id = product_result.fetchone()[0]

        # Insert shares dla dwóch użytkowników
        payer_user_id = expense["user_id"]
        share_payer = Decimal(str(expense["share1"])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        # ZAWSZE tylko user_id 1 lub 2 (nie 100!)
        main_user_ids = [1, 2]
        other_user_id = [uid for uid in main_user_ids if uid != payer_user_id][0]
        share_other = Decimal(str(expense["share2"])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Insert payer's share
        db.execute(text(
            """
            INSERT INTO shares (product_id, user_id, share)
            VALUES (:product_id, :user_id, :share)
            """
        ), {
            "product_id": product_id,
            "user_id": payer_user_id,
            "share": share_payer
        })
        # Insert other user's share
        db.execute(text(
            """
            INSERT INTO shares (product_id, user_id, share)
            VALUES (:product_id, :user_id, :share)
            """
        ), {
            "product_id": product_id,
            "user_id": other_user_id,
            "share": share_other
        })

        db.commit()
        logger.info("Inserted manual expense %s, virtual product %s, and shares", manual_expense_id, product_id)
        return manual_expense_id
    except Exception as e:
        db.rollback()
        logger.error("Error inserting manual expense: %s", e)
        raise

def insert_settlement(payer_user_id, debtor_user_id, receipt_id, amount):
    try:
        with SessionLocal() as db:
            db.execute(text(
                """
                INSERT INTO settlements (payer_user_id, debtor_user_id, receipt_id, amount)
                VALUES (:payer_user_id, :debtor_user_id, :receipt_id, :amount)
                ON CONFLICT DO NOTHING
                """
            ), {
                "payer_user_id": payer_user_id,
                "debtor_user_id": debtor_user_id,
                "receipt_id": receipt_id,
                "amount": amount
            })
    except Exception as e:
        logger.error(f"Error inserting settlement: {e}")
        raise

def insert_receipt(receipt_header, store_id, payment_name, not_our_receipt, db=None):
    """
    Insert a receipt into the receipts table and return the new receipt_id.
    Args:
        receipt_header (dict): Parsed receipt header fields.
        store_id (int): Store ID (foreign key).
        payment_name (str): Payment name (foreign key to user_payments).
        not_our_receipt (bool): Whether this is a 'not our' receipt.
        db: Optional database session. If not provided, a new session will be created.
    Returns:
        int: The new receipt_id, or None if insert fails or duplicate exists.
    """
    from sqlalchemy import text
    from app.db.session import SessionLocal
    import logging
    logger = logging.getLogger(__name__)
    try:
        if db is None:
            with SessionLocal() as db_session:
                # Check for duplicate
                result = db_session.execute(
                    text("""
                        SELECT receipt_id FROM receipts
                        WHERE store_id = :store_id
                          AND receipt_number = :receipt_number
                          AND date = :date
                          AND time = :time
                    """),
                    {
                        "store_id": store_id,
                        "receipt_number": receipt_header.get("receipt_number"),
                        "date": receipt_header.get("transaction_date") or receipt_header.get("date"),
                        "time": receipt_header.get("transaction_time") or receipt_header.get("time"),
                    }
                ).fetchone()
                if result:
                    return None  # Already exists
                # Insert new receipt
                insert_sql = text("""
                    INSERT INTO receipts (
                        store_id, receipt_number, date, time, final_price, total_discounts,
                        payment_name, counted, settled, not_our_receipt, created_at, updated_at, currency
                    ) VALUES (
                        :store_id, :receipt_number, :date, :time, :final_price, :total_discounts,
                        :payment_name, :counted, :settled, :not_our_receipt, NOW(), NOW(), :currency
                    ) RETURNING receipt_id
                """)
                params = {
                    "store_id": store_id,
                    "receipt_number": receipt_header.get("receipt_number"),
                    "date": receipt_header.get("transaction_date") or receipt_header.get("date"),
                    "time": receipt_header.get("transaction_time") or receipt_header.get("time"),
                    "final_price": receipt_header.get("final_price"),
                    "total_discounts": receipt_header.get("total_discounts", 0),
                    "payment_name": payment_name,
                    "counted": False,
                    "settled": False,
                    "not_our_receipt": not_our_receipt,
                    "currency": receipt_header.get("currency", "PLN"),
                }
                result = db_session.execute(insert_sql, params)
                db_session.commit()
                result_row = result.fetchone()
                if result_row is None:
                    raise ValueError("Failed to insert receipt - no ID returned")
                new_id = result_row[0]
                return new_id
        else:
            # Check for duplicate
            result = db.execute(
                text("""
                    SELECT receipt_id FROM receipts
                    WHERE store_id = :store_id
                      AND receipt_number = :receipt_number
                      AND date = :date
                      AND time = :time
                """),
                {
                    "store_id": store_id,
                    "receipt_number": receipt_header.get("receipt_number"),
                    "date": receipt_header.get("transaction_date") or receipt_header.get("date"),
                    "time": receipt_header.get("transaction_time") or receipt_header.get("time"),
                }
            ).fetchone()
            if result:
                return None  # Already exists
            # Insert new receipt
            insert_sql = text("""
                INSERT INTO receipts (
                    store_id, receipt_number, date, time, final_price, total_discounts,
                    payment_name, counted, settled, not_our_receipt, created_at, updated_at, currency
                ) VALUES (
                    :store_id, :receipt_number, :date, :time, :final_price, :total_discounts,
                    :payment_name, :counted, :settled, :not_our_receipt, NOW(), NOW(), :currency
                ) RETURNING receipt_id
            """)
            params = {
                "store_id": store_id,
                "receipt_number": receipt_header.get("receipt_number"),
                "date": receipt_header.get("transaction_date") or receipt_header.get("date"),
                "time": receipt_header.get("transaction_time") or receipt_header.get("time"),
                "final_price": receipt_header.get("final_price"),
                "total_discounts": receipt_header.get("total_discounts", 0),
                "payment_name": payment_name,
                "counted": False,
                "settled": False,
                "not_our_receipt": not_our_receipt,
                "currency": receipt_header.get("currency", "PLN"),
            }
            result = db.execute(insert_sql, params)
            # Do not commit here; let the caller handle commit/rollback
            new_id = result.fetchone()[0]
            return new_id
    except Exception as e:
        logger.error(f"Error inserting receipt: {e}")
        return None