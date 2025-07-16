import logging
from sqlalchemy import text
from .session import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Drop and recreate all database tables, terminating other connections and increasing statement timeout."""
    if engine is None:
        logger.error("Database engine not initialized")
        return

    try:
        with engine.connect() as connection:
            # Terminate all other non-superuser connections to the current database
            logger.info("Terminating other non-superuser database connections...")
            connection.execute(text("""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                JOIN pg_roles ON pg_stat_activity.usename = pg_roles.rolname
                WHERE datname = current_database()
                  AND pid <> pg_backend_pid()
                  AND NOT pg_roles.rolsuper;
            """))
            connection.commit()

            # Set a high statement timeout (10 minutes)
            connection.execute(text("SET statement_timeout = '10min';"))

            # Drop tables in reverse order of dependencies
            logger.info("Dropping tables...")
            connection.execute(text("DROP TABLE IF EXISTS settlements CASCADE"))
            connection.execute(text("DROP TABLE IF EXISTS manual_expenses CASCADE"))
            connection.execute(text("DROP TABLE IF EXISTS shares CASCADE"))
            connection.execute(text("DROP TABLE IF EXISTS ignored_payment_names CASCADE"))
            connection.execute(text("DROP TABLE IF EXISTS static_shares_history CASCADE"))
            connection.execute(text("DROP TABLE IF EXISTS static_shares CASCADE"))
            connection.execute(text("DROP TABLE IF EXISTS products CASCADE"))
            connection.execute(text("DROP TABLE IF EXISTS receipts CASCADE"))
            connection.execute(text("DROP TABLE IF EXISTS user_payments CASCADE"))
            connection.execute(text("DROP TABLE IF EXISTS stores CASCADE"))
            connection.execute(text("DROP TABLE IF EXISTS users CASCADE"))
            connection.commit()
            logger.info("Tables dropped successfully")

            # Read and execute create tables SQL
            logger.info("Creating tables...")
            with open("app/create_tables.sql", "r") as f:
                sql = f.read()
                connection.execute(text(sql))
            connection.commit()
            logger.info("Tables created successfully")

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        connection.rollback()

if __name__ == "__main__":
    main()
