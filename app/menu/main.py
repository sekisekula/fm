"""
Main menu and application entry point for the Finance Manager.
"""
import os
import sys
import logging
from typing import Dict, Any, Callable, Optional

from sqlalchemy.orm import Session

from app.menu.models import DatabaseManager
from app.menu.views import MenuView
from app.menu.handlers import MenuHandlers
from app.menu.exceptions import FinanceManagerError

# Configure logging
log_file = os.path.join(os.path.dirname(__file__), '..', '..', 'finance_manager.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file)
    ]
)
logger = logging.getLogger(__name__)

class FinanceManagerMenu:
    """Main menu for the Finance Manager application."""
    
    def __init__(self, db: Session):
        """Initialize the menu with a database session."""
        self.db = db
        self.db_manager = DatabaseManager(db)
        self.view = MenuView()
        self.handlers = MenuHandlers(self.db_manager, self.view)
        
        # Menu structure
        self.main_menu = [
            # System Setup
            {"text": "Setup Users", "handler": self._setup_users},
            
            # Expense Management
            {"text": "Add Manual Expense", "handler": self.handlers.handle_add_expense},
            {"text": "View Manual Expenses", "handler": self.handlers.handle_view_manual_expenses},
            
            # Receipt Management
            {"text": "Parse Receipts", "handler": self.handlers.handle_process_receipts},
            {"text": "Count Receipts", "handler": self.handlers.handle_count_receipts},
            {"text": "View Receipts", "handler": self.handlers.handle_view_receipts_submenu},
            
            # Statistics and Maintenance
            {"text": "View Statistics", "handler": self.handlers.handle_view_statistics},
            {"text": "Manage Static Shares", "handler": self._not_implemented},
            {"text": "Database Backup", "handler": self._not_implemented},
            {"text": "Settlement", "handler": self.handlers.handle_show_settlement_summary},
            
            # New feature
            {"text": "Find receipt / expense", "handler": self.handlers.handle_find_receipt_or_expense},
            # System
            {"text": "Exit", "handler": self._exit_app}
        ]
    
    def _not_implemented(self) -> None:
        """Handler for not yet implemented features."""
        self.view.show_message("This feature is not yet implemented.", "warning")
    
    def _setup_users(self) -> None:
        """Handler for setting up users."""
        from app.add_users import add_users
        try:
            add_users(self.db)
            self.view.show_message("Users have been set up successfully!", "success")
        except KeyboardInterrupt:
            self.view.show_message("User setup cancelled by user.", "warning")
        except Exception as e:
            logger.error(f"Error setting up users: {e}")
            self.view.show_message(f"Error setting up users: {e}", "error")
    
    def _exit_app(self) -> None:
        """Exit the application."""
        self.view.show_message("Thank you for using Finance Manager. Goodbye!", "info")
        sys.exit(0)
    
    def run(self) -> None:
        """Run the main menu loop."""
        while True:
            try:
                # Add separator before showing menu
                print("\n" + "=" * 80)
                print("FINANCE MANAGER - MAIN MENU".center(80))
                print("=" * 80 + "\n")
                
                # Display menu options
                for i, item in enumerate(self.main_menu[:-1], 1):  # Exclude Exit option
                    print(f"{i}. {item['text']}")
                print("0. Exit")
                
                # Get user choice
                choice = input("\nEnter your choice: ").strip()
                
                if choice == '0':
                    self._exit_app()
                    break
                
                # Handle numeric choices
                try:
                    choice_idx = int(choice) - 1
                    if 0 <= choice_idx < len(self.main_menu) - 1:  # -1 to exclude Exit option
                        # Add separator before executing the handler
                        print("\n" + "-" * 80)
                        print(f"EXECUTING: {self.main_menu[choice_idx]['text']}".center(80))
                        print("-" * 80 + "\n")
                        
                        # Execute the handler
                        self.main_menu[choice_idx]["handler"]()
                        
                        # Add separator after handler completes
                        print("\n" + "-" * 80)
                        print(f"COMPLETED: {self.main_menu[choice_idx]['text']}".center(80))
                        print("-" * 80)
                    else:
                        self.view.show_message("Invalid choice. Please try again.", "error")
                except (ValueError, IndexError):
                    self.view.show_message("Please enter a valid number.", "error")
                    
            except KeyboardInterrupt:
                self.view.show_message("\nOperation cancelled by user.", "warning")
            except FinanceManagerError as e:
                self.view.show_message(f"Error: {e}", "error")
            except Exception as e:
                logger.exception("Unexpected error in menu:")
                self.view.show_message(f"An unexpected error occurred: {e}", "error")

def main():
    """Entry point for the Finance Manager CLI."""
    from app.db.session import SessionLocal
    from app.add_users import ensure_users_exist
    
    db = SessionLocal()
    try:
        # Check if users exist, but don't automatically create them
        if not ensure_users_exist():
            print("\n=== User Setup Required ===")
            print("No users found in the database.")
            print("Please run the 'Setup Users' option from the main menu.")
            print("===========================\n")
        
        menu = FinanceManagerMenu(db)
        menu.run()
    except Exception as e:
        logger.exception("Fatal error in Finance Manager:")
        print(f"\nA fatal error occurred: {e}")
        print("Please check the logs for more information.")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main()
