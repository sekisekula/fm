import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

def test_connection():
    """Test database connection and list tables."""
    try:
        # Load environment variables
        load_dotenv()
        
        # Get database credentials
        db_host = os.getenv('DB_HOST')
        db_port = os.getenv('DB_PORT', '5432')
        db_name = os.getenv('DB_NAME')
        db_user = os.getenv('DB_USER')
        db_password = os.getenv('DB_PASSWORD')
        
        # Create connection string
        db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        
        # Try to connect
        print(f"Connecting to database at {db_host}...")
        engine = create_engine(db_url)
        with engine.connect() as conn:
            # Test connection
            result = conn.execute(text("SELECT version()"))
            print("Database version:", result.scalar())
            
            # List tables
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """))
            print("\nTables in the database:")
            for row in result:
                print(f"- {row[0]}")
                
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return False
    return True

if __name__ == "__main__":
    print("Testing database connection...")
    if test_connection():
        print("Database connection successful!")
    else:
        print("Database connection failed.")
