from sqlalchemy.orm import Session
from sqlalchemy import text
from dotenv import load_dotenv
import logging
from app.utils import remove_polish_diacritics
from app.db.session import SessionLocal

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def add_users(db: Session):
    """Adds users to the database if they don't exist.
    
    Creates two main users and a special 'Other' user for receipts that don't belong to the main users.
    """
    try:
        # Check if any users exist
        user_count = db.execute(text("SELECT COUNT(*) FROM users")).scalar()

        if user_count == 0:
            print("\n=== User Setup Required ===")
            print("No users found in the database.")
            print("Please enter information for two main users and confirm the 'Other' user.")
            print("Receipts marked as 'not ours' will be assigned to the 'Other' user.")
            print("===========================\n")
            
            # Add two main users
            user_names = []
            for i in range(2):
                while True:
                    name = input(f"Enter name for user {i+1}: ").strip()
                    if name:
                        user_names.append(name)
                        break
                    print("Error: User name cannot be empty. Please try again.")
            
            # Add the 'Other' user
            other_user_name = "Other"
            print(f"\nA special 'Other' user will be created for receipts that don't belong to the main users.")
            custom_name = input(f"Press Enter to use '{other_user_name}' or enter a different name: ").strip()
            if custom_name:
                other_user_name = custom_name
            
            # Add all users to database
            all_users = user_names + [other_user_name]
            for name in all_users:
                name_clean = remove_polish_diacritics(name)
                db.execute(text(
                    "INSERT INTO users (name) VALUES (:name)"
                ), {"name": name_clean})
                logger.info(f"Added user: {name}")
            
            db.commit()
            print("\n=== User setup completed successfully! ===")
            print(f"Main users: {', '.join(user_names)}")
            print(f"Special user for 'not our' receipts: {other_user_name}")
            print("==========================================\n")
            logger.info("Finished adding users.")
        else:
            print("Users already exist in the database.")
            
    except Exception as e:
        logger.error(f"Database error while adding users: {e}")
        db.rollback()
        raise

def ensure_users_exist():
    """Ensures users exist in the database.
    
    Verifies that there are at least 3 users (2 main users + 1 'Other' user).
    If not, prompts to run the user setup.
    
    Returns:
        bool: True if users exist and are properly configured, False otherwise
    """
    db = None
    try:
        db = SessionLocal()
        
        # Get all users
        users = db.execute(text("SELECT user_id, name FROM users")).fetchall()
        
        if not users:
            print("\n=== ATTENTION ===")
            print("No users found in the database.")
            print("Please run 'python -m app.add_users' to set up users.")
            print("=================\n")
            return False
            
        # Check if we have at least 3 users (2 main + 1 'Other')
        if len(users) < 3:
            print("\n=== ATTENTION ===")
            print("Insufficient number of users in the database.")
            print("You need at least 2 main users and 1 'Other' user.")
            print("Please run 'python -m app.add_users' to set up users.")
            print("=================\n")
            return False
            
        # Check if we have an 'Other' user
        other_users = [user for user in users if user[1].lower() == 'other']
        if not other_users:
            print("\n=== ATTENTION ===")
            print("No 'Other' user found in the database.")
            print("This user is required for receipts that don't belong to main users.")
            print("Please run 'python -m app.add_users' to set up users.")
            print("=================\n")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"Error checking for users: {e}")
        return False
    finally:
        if db:
            db.close()

if __name__ == "__main__":
    db = SessionLocal()
    try:
        add_users(db)
    except Exception as e:
        logger.error(f"Could not add users: {e}")
        print(f"Error: {e}")
    finally:
        db.close()
