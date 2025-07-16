"""
Functions for checking duplicate receipts in the database.
"""
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

def is_duplicate_receipt(db: Session, receipt_data: Dict[str, Any]) -> bool:
    """Check if a receipt with the same date, time, and final_price already exists.
    
    Args:
        db: Database session
        receipt_data: Dictionary containing receipt data with keys:
            - date: str (YYYY-MM-DD)
            - time: str (HH:MM:SS)
            - final_price: Decimal or float
            
    Returns:
        bool: True if a duplicate receipt exists, False otherwise
    """
    try:
        required_fields = ['date', 'time', 'final_price']
        if not all(field in receipt_data for field in required_fields):
            logger.warning("Missing required fields for duplicate check")
            return False
            
        query = text("""
            SELECT COUNT(*) 
            FROM receipts 
            WHERE date = :date 
              AND time = :time 
              AND final_price = :final_price
        """)
        
        params = {
            'date': receipt_data['date'],
            'time': receipt_data['time'],
            'final_price': receipt_data['final_price']
        }
        
        result = db.execute(query, params).scalar()
        return result > 0
        
    except Exception as e:
        logger.error(f"Error checking for duplicate receipt: {e}")
        # In case of error, assume it's not a duplicate to avoid data loss
        return False
