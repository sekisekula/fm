import os
import sys
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import QueuePool
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('db_init.log')
    ]
)
logger = logging.getLogger(__name__)

# Add the app directory to the Python path
sys.path.append(str(Path(__file__).parent))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Get database connection string from environment variables
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'postgres')

# Validate required environment variables
if not all([DB_USER, DB_PASSWORD, DB_HOST]):
    logger.error("Missing required database environment variables. Please check your .env file.")
    sys.exit(1)

# Create database connection URL
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
logger.info(f"Connecting to database at {DB_HOST}")

def init_db():
    """Initialize the database by creating all tables and running migrations."""
    try:
        # Create SQLAlchemy engine with connection pooling
        engine = create_engine(
            DATABASE_URL,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800,
            echo=True  # Enable SQL query logging
        )
        
        # Create session factory
        Session = scoped_session(sessionmaker(bind=engine))
        db = Session()
        
        try:
            logger.info("Starting database initialization...")
            
            # Read and execute the SQL file
            sql_path = Path(__file__).parent / 'app' / 'create_tables.sql'
            with open(sql_path, 'r', encoding='utf-8') as f:
                sql_script = f.read()
            
            logger.info("Creating database schema...")
            with engine.connect() as connection:
                # Split the script into individual statements and execute them
                for statement in sql_script.split(';'):
                    # Skip empty statements
                    if not statement.strip():
                        continue
                    try:
                        connection.execute(text(statement))
                        connection.commit()
                    except SQLAlchemyError as e:
                        if "already exists" not in str(e):
                            logger.error(f"Error executing statement: {statement}")
                            logger.error(f"SQL Error: {e}")
            
            logger.info("Running database migrations...")
            # Import and run migrations
            from db.migrations import DatabaseMigrator
            migrator = DatabaseMigrator(db)
            if not migrator.run_migrations():
                raise Exception("Failed to run database migrations")
            
            logger.info("Database initialization completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error during database initialization: {e}")
            db.rollback()
            return False
        finally:
            db.close()
            
    except Exception as e:
        logger.critical(f"Failed to initialize database: {e}")
        return False

if __name__ == "__main__":
    try:
        if init_db():
            logger.info("Database initialization completed successfully")
            sys.exit(0)
        else:
            logger.error("Database initialization failed")
            sys.exit(1)
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}")
        sys.exit(1)
