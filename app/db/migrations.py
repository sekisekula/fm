"""Database migration utilities for Finance Manager."""
import logging
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

class DatabaseMigrator:
    """Handles database schema migrations."""
    
    def __init__(self, db):
        """Initialize with a database session."""
        self.db = db
    
    def run_migrations(self):
        """Run all necessary migrations."""
        try:
            self._ensure_manual_expenses_columns()
            logger.info("Database migrations completed successfully")
            return True
        except Exception as e:
            logger.error(f"Error running migrations: {e}")
            self.db.rollback()
            return False
    
    def _ensure_manual_expenses_columns(self):
        """Ensure all required columns exist in manual_expenses table."""
        try:
            # Check and add columns in a single DO block
            self.db.execute(text("""
                DO $$
                BEGIN
                    -- Check and add share column if it doesn't exist
                    IF NOT EXISTS (
                        SELECT 1 
                        FROM information_schema.columns 
                        WHERE table_name = 'manual_expenses' 
                        AND column_name = 'share'
                    ) THEN
                        ALTER TABLE manual_expenses 
                        ADD COLUMN share DECIMAL(5,2) NOT NULL DEFAULT 50.00;
                        RAISE NOTICE 'Added share column to manual_expenses';
                    END IF;
                    
                    -- Check and add category column if it doesn't exist
                    IF NOT EXISTS (
                        SELECT 1 
                        FROM information_schema.columns 
                        WHERE table_name = 'manual_expenses' 
                        AND column_name = 'category'
                    ) THEN
                        ALTER TABLE manual_expenses 
                        ADD COLUMN category VARCHAR(100);
                        RAISE NOTICE 'Added category column to manual_expenses';
                    END IF;
                END $$;
            """))
            
            self.db.commit()
            logger.info("Verified manual_expenses table structure")
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error ensuring manual_expenses columns: {e}")
            raise
