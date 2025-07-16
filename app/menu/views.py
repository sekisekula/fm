"""
Menu display and user interaction components for the Finance Manager.
"""
import os
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from decimal import Decimal
from sqlalchemy import text
from app.menu.models import DatabaseManager
from app.db.session import SessionLocal

# Add colorama for colored terminal output
from colorama import init, Fore, Style
init(autoreset=True)

class MenuView:
    """Handles all menu display and user interaction."""
    
    # User color constants
    USER1_COLOR = Fore.YELLOW  # Orange/Yellow for User 1
    USER2_COLOR = Fore.MAGENTA  # Pink for User 2
    OTHER_USER_COLOR = Fore.CYAN  # Cyan for Other user
    
    @staticmethod
    def colorize_user_name(user_name: str, user_id: Optional[int] = None) -> str:
        """Colorize user name based on user ID or name pattern."""
        if user_id == 1:
            return MenuView.USER1_COLOR + user_name + Style.RESET_ALL
        elif user_id == 2:
            return MenuView.USER2_COLOR + user_name + Style.RESET_ALL
        elif user_name.lower() == 'other':
            return MenuView.OTHER_USER_COLOR + user_name + Style.RESET_ALL
        else:
            # For unknown users, use default color
            return user_name
    
    @staticmethod
    def clear_screen() -> None:
        """Don't clear the screen, just add a separator."""
        print(Fore.CYAN + "\n" + "=" * 80 + "\n" + Style.RESET_ALL)
    
    @staticmethod
    def print_header(text: str, width: int = 90) -> None:
        """Print a formatted header."""
        print("\n" + "=" * width)
        print(f"{text.upper():^{width}}")
        print("=" * width + "\n")
    
    @staticmethod
    def print_section(text: str, width: int = 90) -> None:
        """Print a section header with clearer separators and spacing."""
        print("\n" + "=" * width)
        print(f"{text.upper():^{width}}")
        print("=" * width + "\n")
    
    def display_menu(self, title: str, options: List[Dict[str, Any]]) -> str:
        """Display a menu and get user selection."""
        self.print_header(title)
        
        for i, option in enumerate(options, 1):
            print(Fore.WHITE + Style.BRIGHT + f"{i}. {option['text']}")
        print(Fore.YELLOW + ("0. Back to previous menu" if title != "Main Menu" else "0. Exit") + Style.RESET_ALL)
        
        return input(Fore.YELLOW + "\nEnter your choice: " + Style.RESET_ALL).strip()
    
    def get_input(self, prompt: str, 
                 validator: Optional[Callable[[str], bool]] = None,
                 error_msg: str = "Invalid input. Please try again.",
                 required: bool = True,
                 default: Optional[str] = None) -> Optional[str]:
        """Get and validate user input. Allows 'b', 'q', or '0' to go back/cancel. Shows default in [brackets]."""
        while True:
            try:
                full_prompt = prompt
                if default is not None:
                    full_prompt = f"{prompt} [{default}]"
                value = input(Fore.YELLOW + full_prompt + Style.RESET_ALL).strip()
                if value == '0':
                    return '__CANCEL__'
                if value.lower() in ('b', 'q'):
                    return '__BACK__'
                if not value:
                    if default is not None:
                        value = default
                    elif not required:
                        return None
                    else:
                        print(Fore.RED + "This field is required." + Style.RESET_ALL)
                        continue
                if validator and not validator(value):
                    print(Fore.RED + error_msg + Style.RESET_ALL)
                    continue
                return value
            except KeyboardInterrupt:
                print(Fore.YELLOW + "\nOperation cancelled by user." + Style.RESET_ALL)
                raise
            except Exception as e:
                print(Fore.RED + f"An error occurred: {e}" + Style.RESET_ALL)
    
    def show_message(self, message: str, message_type: str = "info") -> None:
        """Display a message to the user. Consistent color coding: Green for success, Red for errors, Yellow for warnings, Cyan for info."""
        if message_type == "error":
            print(Fore.RED + f"\n[ERROR] {message}" + Style.RESET_ALL)
        elif message_type == "success":
            print(Fore.GREEN + f"\n[SUCCESS] {message}" + Style.RESET_ALL)
        elif message_type == "warning":
            print(Fore.YELLOW + f"\n[WARNING] {message}" + Style.RESET_ALL)
        else:
            print(Fore.CYAN + f"\n{message}" + Style.RESET_ALL)
        input(Fore.MAGENTA + "\nPress Enter to continue..." + Style.RESET_ALL)
    
    def show_expense_summary(self, expenses: List[Dict[str, Any]]) -> None:
        """Display a summary of expenses."""
        if not expenses:
            self.show_message("No expense data available.", "info")
            return
        
        self.print_section("Expense Summary")
        
        total = Decimal('0')
        for expense in expenses:
            amount = expense.get('amount', Decimal('0'))
            total += amount
            print(f"{expense.get('date', 'N/A')} - {expense.get('description', 'No description')}: {amount:.2f} PLN")
        
        print("\n" + "-" * 50)
        print(f"{'Total:':<20} {total:.2f} PLN")
        print("-" * 50)
    
    def show_monthly_expenses(self, monthly_data: List[Dict[str, Any]]) -> None:
        """Display monthly expenses."""
        if not monthly_data:
            self.show_message("No monthly expense data available.", "info")
            return
        
        self.print_section("Monthly Expenses")
        
        total = Decimal('0')
        for month_data in monthly_data:
            month = month_data.get('month', 'N/A')
            amount = month_data.get('amount', Decimal('0'))
            total += amount
            print(f"{month}: {amount:.2f} PLN")
        
        if monthly_data:
            avg = total / len(monthly_data)
            print("\n" + "-" * 50)
            print(f"{'Average:':<20} {avg:.2f} PLN")
            print(f"{'Total:':<20} {total:.2f} PLN")
            print("-" * 50)
    
    def show_receipts_list(self, receipts: List[Dict[str, Any]], title: str) -> None:
        """Display a list of receipts with a title."""
        if not receipts:
            self.show_message(f"No {title.lower()} available.", "info")
            return
        self.print_section(title.upper())
        # Standardized header for all receipts
        print(f"{'Date':<12} {'Shop':<20} {'Amount':>12} {'Paid By':<15} {'Status/Split':<30}")
        print("-" * 90)
        db_manager = DatabaseManager(SessionLocal())
        users = db_manager.get_users()
        user_id_to_name = {u['id']: u['name'] for u in users}
        for receipt in receipts:
            date = receipt.get('date', 'N/A')
            shop = (receipt.get('shop_name') or receipt.get('store_name') or 'Unknown')[:18]
            amount = f"{float(receipt.get('final_price', receipt.get('total_amount', 0))):.2f} PLN"
            payment_name = receipt.get('payment_name', 'Unknown')
            paid_by = db_manager.get_user_name_by_payment_name(payment_name) or payment_name
            # Determine status or split
            if title.lower() == 'counted receipts':
                # Calculate split
                products = db_manager.get_products_for_receipt(receipt['receipt_id'])
                user_totals = {u['id']: 0.0 for u in users}
                for product in products:
                    product_id = product['product_id']
                    shares = db_manager.db.execute(
                        text("SELECT user_id, share FROM shares WHERE product_id = :pid"),
                        {"pid": product_id}
                    ).fetchall()
                    for user_id, share in shares:
                        user_totals[user_id] += float(product['total_after_discount']) * (float(share) / 100)
                split_str = ', '.join([
                    f"{user_id_to_name[uid]}: {amt:.2f} PLN" for uid, amt in user_totals.items() if amt > 0.01
                ])
                print(f"{date:<12} {shop:<20} {amount:>12} {paid_by:<15} {split_str:<30}")
            else:
                if title.lower() == 'settled receipts':
                    status = f"Settled on {receipt.get('settlement_date', 'N/A')}"
                else:
                    status = "Settled" if receipt.get('is_settled') else "Pending"
                print(f"{date:<12} {shop:<20} {amount:>12} {paid_by:<15} {status:<30}")
        db_manager.db.close()
        print("-" * 90)
        total = sum(float(r.get('final_price', r.get('total_amount', 0))) for r in receipts)
        print(f"{'Total:':<49} {total:.2f} PLN")
    
    def show_manual_expenses(self, expenses: List[Dict[str, Any]]) -> None:
        """Display a list of manual expenses."""
        if not expenses:
            print("\nNo manual expenses available.")
            return
        self.print_section("MANUAL EXPENSES")
        # Standardized header for manual expenses
        print(f"{'Date':<12} {'User':<15} {'Category':<20} {'Amount':>12} {'Description':<30}")
        print("-" * 90)
        for expense in expenses:
            date = expense.get('date', 'N/A')
            user = (expense.get('user_name') or 'Unknown')[:13]
            category = (expense.get('category') or 'Other')[:18]
            amount = f"{float(expense.get('amount', 0)):.2f} PLN"
            description = (expense.get('description') or '')[:28] + ('...' if len(expense.get('description', '')) > 28 else '')
            print(f"{date:<12} {user:<15} {category:<20} {amount:>12} {description:<30}")
        print("-" * 90)
        total = sum(float(e.get('amount', 0)) for e in expenses)
        print(f"{'Total:':<49} {total:.2f} PLN")
        
        # Show expense distribution by category
        category_totals = {}
        for expense in expenses:
            category = expense.get('category') or 'Other'
            category_totals[category] = category_totals.get(category, 0) + float(expense.get('amount', 0))
        
        if category_totals:
            print("\n" + "-" * 40)
            print("EXPENSE DISTRIBUTION BY CATEGORY".center(40))
            print("-" * 40)
            
            # Sort categories by total amount (descending)
            sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
            
            for category, amount in sorted_categories:
                percentage = (amount / total) * 100 if total > 0 else 0
                print(f"{category[:25]:<25} {percentage:>5.1f}% ({amount:.2f} PLN)")
