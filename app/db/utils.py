"""Database utility functions and transaction management."""
from contextlib import contextmanager
from typing import Generator
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
import logging

logger = logging.getLogger(__name__)

@contextmanager
def transaction_scope() -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of database operations.
    
    Yields:
        Session: A database session object
    
    Raises:
        Exception: Any exception that occurs during the transaction
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Transaction failed: {str(e)}", exc_info=True)
        raise
    finally:
        db.close()
