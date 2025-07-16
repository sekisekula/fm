import logging
from typing import List, Dict, Any, Optional
from sqlalchemy import text

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Database access layer for menu operations."""
    def __init__(self, db):
        self.db = db

    def get_users(self) -> List[Dict[str, Any]]:
        try:
            result = self.db.execute(text("SELECT user_id AS id, name FROM users ORDER BY user_id")).fetchall()
            return [{"id": row[0], "name": row[1]} for row in result]
        except Exception as e:
            logger.error(f"Error getting users: {e}")
            return []

    def get_manual_expenses(self, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            result = self.db.execute(text(
                "SELECT me.date, u.name as user_name, me.category, me.total_cost, me.description "
                "FROM manual_expenses me "
                "JOIN users u ON me.payer_user_id = u.user_id "
                "ORDER BY me.date DESC LIMIT :limit"
            ), {"limit": limit}).fetchall()
            return [
                {"date": row[0], "user_name": row[1], "category": row[2], "amount": row[3], "description": row[4]}
                for row in result
            ]
        except Exception as e:
            logger.error(f"Error getting manual expenses: {e}")
            return []

    def add_manual_expense_with_shares(self, description, amount, date, payer_user_id, category, user_shares) -> bool:
        try:
            self.db.execute(text(
                """
                INSERT INTO manual_expenses (description, total_cost, date, payer_user_id, category)
                VALUES (:description, :total_cost, :date, :payer_user_id, :category)
                """
            ), {
                "description": description,
                "total_cost": amount,
                "date": date,
                "payer_user_id": payer_user_id,
                "category": category
            })
            # Optionally insert shares if needed
            self.db.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding manual expense: {e}")
            self.db.rollback()
            return False

    def get_existing_categories(self) -> List[str]:
        try:
            result = self.db.execute(
                text("SELECT DISTINCT category FROM manual_expenses WHERE category IS NOT NULL ORDER BY category ASC")
            ).fetchall()
            return [row[0] for row in result if row[0]]
        except Exception as e:
            logger.error(f"Error getting categories: {e}")
            self.db.rollback()
            return []

    def settle_all_expenses(self) -> bool:
        try:
            self.db.execute(
                text("""
                UPDATE receipts SET settled = TRUE, settlement_date = CURRENT_TIMESTAMP WHERE counted = TRUE AND settled = FALSE
                """))
            self.db.execute(
                text("""
                UPDATE manual_expenses SET settled = TRUE, settlement_date = CURRENT_TIMESTAMP WHERE counted = TRUE AND settled = FALSE
                """))
            self.db.commit()
            return True
        except Exception as e:
            logger.error(f"Error settling expenses: {e}")
            self.db.rollback()
            return False

    def get_store_by_id(self, store_id: int) -> Optional[Dict[str, Any]]:
        """Get store information by store ID."""
        try:
            result = self.db.execute(text(
                "SELECT store_id, store_name, store_address, store_city FROM stores WHERE store_id = :store_id"
            ), {"store_id": store_id}).fetchone()
            if result:
                return {
                    "store_id": result[0],
                    "store_name": result[1],
                    "store_address": result[2],
                    "store_city": result[3]
                }
            return None
        except Exception as e:
            logger.error(f"Error getting store by ID {store_id}: {e}")
            return None

    def get_user_name_by_payment_name(self, payment_name: str) -> Optional[str]:
        """Get user name by payment name."""
        try:
            result = self.db.execute(text(
                "SELECT u.name FROM user_payments up JOIN users u ON up.user_id = u.user_id WHERE up.payment_name = :payment_name"
            ), {"payment_name": payment_name}).fetchone()
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting user name by payment name '{payment_name}': {e}")
            return None

    def get_products_for_receipt(self, receipt_id: int) -> List[Dict[str, Any]]:
        """Get all products for a specific receipt."""
        try:
            result = self.db.execute(text(
                "SELECT product_id, product_name, quantity, total_after_discount FROM products WHERE receipt_id = :receipt_id"
            ), {"receipt_id": receipt_id}).fetchall()
            return [
                {
                    "product_id": row[0],
                    "product_name": row[1],
                    "quantity": float(row[2]),
                    "total_after_discount": float(row[3])
                }
                for row in result
            ]
        except Exception as e:
            logger.error(f"Error getting products for receipt {receipt_id}: {e}")
            return []

    def rollback(self):
        """Rollback the current transaction."""
        self.db.rollback() 