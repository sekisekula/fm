import psycopg2
from psycopg2 import sql
import logging
from tabulate import tabulate

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_database():
    """Check database schema and sample data."""
    conn_params = {
        'host': 'aws-0-eu-central-1.pooler.supabase.com',
        'port': '6543',
        'dbname': 'postgres',
        'user': 'postgres.dmlmtvodcliwevdxcxvr',
        'password': '21372137'
    }
    
    try:
        conn = psycopg2.connect(**conn_params)
        conn.autocommit = True
        
        with conn.cursor() as cur:
            # Check if users table exists and get count
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'users'
                )
            """)
            users_table_exists = cur.fetchone()[0]
            
            if not users_table_exists:
                print("\n[ERROR] 'users' table does not exist in the database.")
                return
                
            # Get users count
            cur.execute("SELECT COUNT(*) FROM users")
            users_count = cur.fetchone()[0]
            
            # Get sample users
            cur.execute("SELECT user_id, name FROM users ORDER BY user_id LIMIT 5")
            sample_users = cur.fetchall()
            
            # Check manual_expenses table
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'manual_expenses'
                )
            """)
            expenses_table_exists = cur.fetchone()[0]
            
            expenses_count = 0
            sample_expenses = []
            
            if expenses_table_exists:
                # Get expenses count
                cur.execute("SELECT COUNT(*) FROM manual_expenses")
                expenses_count = cur.fetchone()[0]
                
                # Get sample expenses
                cur.execute("""
                    SELECT 
                        manual_expense_id, 
                        payer_user_id, 
                        total_cost, 
                        share,
                        date
                    FROM manual_expenses 
                    ORDER BY date DESC 
                    LIMIT 5
                """)
                sample_expenses = cur.fetchall()
            
            # Print summary
            print("\n" + "="*80)
            print("DATABASE STATUS".center(80))
            print("="*80)
            
            print(f"\n{'Users table exists:':<25} {users_table_exists}")
            print(f"{'Number of users:':<25} {users_count}")
            print(f"\n{'Expenses table exists:':<25} {expenses_table_exists}")
            print(f"{'Number of expenses:':<25} {expenses_count}")
            
            if sample_users:
                print("\nSample Users:")
                print(tabulate(
                    [("ID", "Name")] + sample_users,
                    headers="firstrow",
                    tablefmt="grid"
                ))
            
            if sample_expenses:
                print("\nSample Expenses:")
                print(tabulate(
                    [("ID", "Payer ID", "Amount", "Share", "Date")] + sample_expenses,
                    headers="firstrow",
                    tablefmt="grid"
                ))
            
            print("\n" + "="*80)
            
    except Exception as e:
        print(f"\n[ERROR] Database error: {e}")
        logger.exception("Error checking database")
    finally:
        if 'conn' in locals() and conn is not None:
            conn.close()

if __name__ == "__main__":
    check_database()
