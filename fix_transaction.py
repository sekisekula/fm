import psycopg2
from psycopg2 import sql
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_failed_transaction():
    """Fix any failed transactions in the database."""
    conn = None
    try:
        # Connect to the database
        conn = psycopg2.connect(
            host='aws-0-eu-central-1.pooler.supabase.com',
            port='6543',
            dbname='postgres',
            user='postgres.dmlmtvodcliwevdxcxvr',
            password='21372137'
        )
        
        # Set autocommit to True to handle transactions manually
        conn.autocommit = True
        
        # Create a cursor
        with conn.cursor() as cur:
            # Check for any prepared transactions
            cur.execute("SELECT gid FROM pg_prepared_xacts")
            prepared_txns = cur.fetchall()
            
            if prepared_txns:
                logger.warning(f"Found {len(prepared_txns)} prepared transactions. Rolling them back...")
                for txn in prepared_txns:
                    gid = txn[0]
                    try:
                        cur.execute(sql.SQL("ROLLBACK PREPARED %s"), (gid,))
                        logger.info(f"Rolled back prepared transaction: {gid}")
                    except Exception as e:
                        logger.error(f"Error rolling back prepared transaction {gid}: {e}")
            
            # Check for any idle in transaction sessions
            cur.execute("""
                SELECT pid, query_start, state_change, state, query 
                FROM pg_stat_activity 
                WHERE state = 'idle in transaction' 
                AND pid != pg_backend_pid()
            """)
            idle_sessions = cur.fetchall()
            
            if idle_sessions:
                logger.warning(f"Found {len(idle_sessions)} idle in transaction sessions. Terminating them...")
                for session in idle_sessions:
                    pid = session[0]
                    try:
                        cur.execute(sql.SQL("SELECT pg_terminate_backend(%s)"), (pid,))
                        logger.info(f"Terminated idle session with PID: {pid}")
                    except Exception as e:
                        logger.error(f"Error terminating session {pid}: {e}")
            
            # Verify the connection is working
            cur.execute("SELECT 1")
            logger.info("Database connection is working correctly.")
            
    except Exception as e:
        logger.error(f"Error fixing transactions: {e}")
        raise
    finally:
        if conn is not None:
            conn.close()
            logger.info("Database connection closed.")

if __name__ == "__main__":
    print("Fixing database transaction state...")
    fix_failed_transaction()
    print("Done. Please try running your settlement calculation again.")
