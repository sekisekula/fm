import logging
from typing import Any, List, Dict
from app.menu.models import DatabaseManager
from app.menu.views import MenuView
from app.menu.exceptions import UserInputError, DatabaseError
from sqlalchemy import text
from datetime import datetime
from decimal import Decimal

logger = logging.getLogger(__name__)

class MenuHandlers:
    def __init__(self, db_manager: DatabaseManager, view: MenuView):
        self.db = db_manager
        self.view = view

    def handle_add_expense(self) -> None:
        try:
            # 1. Description
            description = self.view.get_input("1. Description: ")
            if not description:
                self.view.show_message("Description cannot be empty.", "error")
                return

            # 2. Category
            categories = self.db.get_existing_categories()
            if categories:
                self.view.print_section("Available Categories")
                for cat in categories:
                    print(f"- {cat}")
            category = self.view.get_input("2. Category (leave empty for 'Other'): ", required=False)
            if not category:
                category = 'Other'

            # 3. Date
            while True:
                date_str = self.view.get_input("3. Date (YYYY-MM-DD, leave empty for today): ", required=False)
                if not date_str:
                    date = datetime.now().date()
                    break
                try:
                    date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    break
                except ValueError:
                    self.view.show_message("Invalid date format. Please use YYYY-MM-DD.", "error")

            # 4. Who paid
            users = self.db.get_users()
            if not users:
                self.view.show_message("No users found. Please add users first.", "error")
                return
            self.view.print_section("Who paid?")
            for i, user in enumerate(users, 1):
                colored_name = self.view.colorize_user_name(user['name'], user['id'])
                print(f"{i}. {colored_name}")
            while True:
                try:
                    input_str = self.view.get_input("Select payer (number): ")
                    if input_str is None:
                        self.view.show_message("Please enter a valid number.", "error")
                        continue
                    payer_idx = int(input_str)
                    if 1 <= payer_idx <= len(users):
                        payer = users[payer_idx - 1]
                        break
                    self.view.show_message("Invalid selection. Please try again.", "error")
                except ValueError:
                    self.view.show_message("Please enter a valid number.", "error")

            # 5. How much paid
            while True:
                amount_str = self.view.get_input("5. How much paid (e.g., 100.00): ")
                try:
                    if amount_str is None:
                        self.view.show_message("Please enter a valid amount.", "error")
                        continue
                    amount = Decimal(amount_str)
                    if amount <= 0:
                        self.view.show_message("Amount must be greater than 0.", "error")
                        continue
                    break
                except (ValueError, TypeError):
                    self.view.show_message("Invalid amount. Please enter a valid number.", "error")

            # 6. Share for user id 1
            user1 = next((u for u in users if u['id'] == 1), None)
            if not user1:
                self.view.show_message("User with ID 1 not found.", "error")
                return
            while True:
                colored_user1_name = self.view.colorize_user_name(user1['name'], user1['id'])
                share_str = self.view.get_input(f"6. Share for {colored_user1_name} (0-100, blank=50): ", required=False)
                if not share_str:
                    share1 = Decimal(50)
                    break
                try:
                    share1 = Decimal(share_str)
                    if not (0 <= share1 <= 100):
                        self.view.show_message("Share must be between 0 and 100.", "error")
                        continue
                    break
                except (ValueError, TypeError):
                    self.view.show_message("Please enter a valid number.", "error")
            share2 = Decimal(100) - share1
            other_user = next((u for u in users if u['id'] != 1), None)
            if not other_user:
                self.view.show_message("Second user not found.", "error")
                return

            # Confirm
            self.view.print_section("Confirm Manual Expense")
            user1_pln = amount * (share1 / 100)
            user2_pln = amount * (share2 / 100)
            print(f"Description: {description}")
            print(f"Category: {category}")
            print(f"Date: {date}")
            colored_payer_name = self.view.colorize_user_name(payer['name'], payer['id'])
            colored_user1_name = self.view.colorize_user_name(user1['name'], user1['id'])
            colored_other_user_name = self.view.colorize_user_name(other_user['name'], other_user['id'])
            print(f"Paid by: {colored_payer_name}")
            print(f"Amount: {amount:.2f}")
            print(f"Share: {colored_user1_name} {share1:.0f}% ({user1_pln:.2f} PLN), {colored_other_user_name} {share2:.0f}% ({user2_pln:.2f} PLN)")
            confirm_input = self.view.get_input("Save this expense? (y/n): ", required=True)
            if confirm_input is None:
                self.view.show_message("Please enter y or n.", "error")
                return
            confirm = confirm_input.lower()
            if confirm != 'y':
                self.view.show_message("Expense not saved.", "info")
                return

            # Insert into manual_expenses (NO share column)
            db = self.db.db
            result = db.execute(text(
                """
                INSERT INTO manual_expenses (date, description, total_cost, payer_user_id, counted, settled, category)
                VALUES (:date, :description, :total_cost, :payer_user_id, TRUE, FALSE, :category)
                RETURNING manual_expense_id
                """
            ), {
                "date": date,
                "description": description,
                "total_cost": amount,
                "payer_user_id": payer['id'],
                "category": category
            })
            manual_expense_id = result.fetchone()[0]

            # Insert virtual product with all NOT NULL fields set
            product_result = db.execute(text(
                """
                INSERT INTO products (
                    manual_expense_id, product_name, quantity, tax_type,
                    unit_price_before, total_price_before, unit_after_discount, total_after_discount
                )
                VALUES (
                    :manual_expense_id, :product_name, :quantity, 'M',
                    :amount, :amount, :amount, :amount
                )
                RETURNING product_id
                """
            ), {
                "manual_expense_id": manual_expense_id,
                "product_name": description,
                "amount": amount,
                "quantity": Decimal("1.000")
            })
            product_id = product_result.fetchone()[0]

            # Insert shares for user 1 and the other user
            db.execute(text(
                """
                INSERT INTO shares (product_id, user_id, share) VALUES (:product_id, :user_id, :share)
                """
            ), {"product_id": product_id, "user_id": user1['id'], "share": float(share1)})
            db.execute(text(
                """
                INSERT INTO shares (product_id, user_id, share) VALUES (:product_id, :user_id, :share)
                """
            ), {"product_id": product_id, "user_id": other_user['id'], "share": float(share2)})

            db.commit()
            self.view.show_message("Manual expense added successfully!", "success")
        except Exception as e:
            logger.error(f"Error adding manual expense: {e}")
            if 'db' in locals():
                db.db.rollback()
            self.view.show_message(f"An error occurred: {e}", "error")

    def handle_process_receipts(self) -> None:
        from pathlib import Path
        import os
        from app.parser import process_receipt_file
        from app.config import Config

        to_check_dir = Path(Config.UPLOAD_FOLDER)
        print("DEBUG: to_check_dir =", to_check_dir)
        files = list(to_check_dir.glob('*.json'))
        print("DEBUG: files found =", [f.name for f in files])
        if not files:
            self.view.show_message("No receipt files found in data/to_check.", "info")
            return
        self.view.print_section("PROCESSING RECEIPTS")
        processed = 0
        skipped = 0
        for file_path in files:
            print(f"Processing: {file_path.name}")
            try:
                result = process_receipt_file(file_path)
                if result is not None:
                    print(f"✓ Successfully processed receipt (ID: {result})\n")
                    processed += 1
                else:
                    print(f"✗ Receipt was skipped or invalid.\n")
                    skipped += 1
            except Exception as e:
                print(f"✗ Error processing {file_path.name}: {e}\n")
                skipped += 1
        print(f"\nSummary: {processed} processed, {skipped} skipped.")
        self.view.show_message("Receipt parsing completed.", "success")

    def handle_view_manual_expenses(self) -> None:
        """Show manual expenses in a table format with settlement summary."""
        from sqlalchemy import text
        db = self.db.db
        
        try:
            # Get all manual expenses with their virtual products and shares
            manual_expenses = db.execute(text("""
                SELECT me.manual_expense_id, me.date, me.total_cost, me.payer_user_id, me.description,
                       u.name as payer_name
                FROM manual_expenses me
                JOIN users u ON me.payer_user_id = u.user_id
                ORDER BY me.date DESC, me.manual_expense_id DESC
            """)).fetchall()
            
            if not manual_expenses:
                self.view.show_message("No manual expenses available.", "info")
                return
            
            self.view.print_section("MANUAL EXPENSES")
            
            # Get user names
            users = self.db.get_users()
            user_id_to_name = {user['id']: user['name'] for user in users}
            
            # Print header
            print(f"{'Date':<12} {'Description':<20} {'Paid_by':<12} {'Total_cost':<12} {'Share(%)':<10} {'Michał':<10} {'Werka':<10}")
            print("-" * 70)
            
            user_totals = {user['id']: 0.0 for user in users}
            user_paid = {user['id']: 0.0 for user in users}
            
            for manual_expense_id, date, total_cost_amount, payer_user_id, description, payer_name in manual_expenses:
                # Handle date formatting properly
                date_obj = date
                if hasattr(date_obj, 'strftime'):
                    date_str = date_obj.strftime('%Y-%m-%d')
                else:
                    date_str = str(date_obj)
                
                paid_by = payer_name[:11] if len(payer_name) > 11 else payer_name
                cost_str = f"{float(total_cost_amount):.2f}"
                desc_str = (description or '')[:18] + ('...' if description and len(description) > 18 else '')
                
                # Get virtual product for this manual expense
                virtual_product = db.execute(text("""
                    SELECT product_id FROM products 
                    WHERE manual_expense_id = :manual_expense_id
                """), {"manual_expense_id": manual_expense_id}).fetchone()
                
                michal_amount = 0.0
                werka_amount = 0.0
                michal_percentage = 0.0
                
                if virtual_product:
                    product_id = virtual_product[0]
                    # Get shares for this virtual product
                    shares = db.execute(text("""
                        SELECT user_id, share FROM shares 
                        WHERE product_id = :product_id
                    """), {"product_id": product_id}).fetchall()
                    
                    for user_id, share in shares:
                        share_amount = float(total_cost_amount) * (float(share) / 100)
                        if user_id == 1:  # Michał
                            michal_amount = share_amount
                            michal_percentage = float(share)
                            user_totals[user_id] += share_amount
                        elif user_id == 2:  # Werka
                            werka_amount = share_amount
                            user_totals[user_id] += share_amount
                
                # Add to what the payer actually paid
                user_paid[payer_user_id] += float(total_cost_amount)
                
                print(f"{date_str:<12} {desc_str:<20} {paid_by:<12} {cost_str:<12} {michal_percentage:<10.1f} {michal_amount:<10.2f} {werka_amount:<10.2f}")
            
            print("-" * 70)
            
            # Calculate who owes whom
            print(f"\n{'='*70}")
            print("SETTLEMENT SUMMARY FOR MANUAL EXPENSES")
            print(f"{'='*70}")
            
            michal_id = 1
            werka_id = 2
            
            michal_should_pay = user_totals[michal_id]
            werka_should_pay = user_totals[werka_id]
            michal_paid = user_paid[michal_id]
            werka_paid = user_paid[werka_id]
            
            michal_net = michal_paid - michal_should_pay
            werka_net = werka_paid - werka_should_pay
            
            print(f"Michał should pay: {michal_should_pay:.2f} PLN")
            print(f"Michał actually paid: {michal_paid:.2f} PLN")
            print(f"Michał net: {michal_net:.2f} PLN")
            print()
            print(f"Werka should pay: {werka_should_pay:.2f} PLN")
            print(f"Werka actually paid: {werka_paid:.2f} PLN")
            print(f"Werka net: {werka_net:.2f} PLN")
            print()
            
            if michal_net > 0 and werka_net < 0:
                from colorama import Fore, Style
                print(Fore.GREEN + f"So, Werka owes Michał {abs(werka_net):.2f} PLN for manual expenses." + Style.RESET_ALL)
            elif werka_net > 0 and michal_net < 0:
                from colorama import Fore, Style
                print(Fore.GREEN + f"So, Michał owes Werka {abs(michal_net):.2f} PLN for manual expenses." + Style.RESET_ALL)
            else:
                print("All expenses are already balanced.")
            
            # Do not show a success message at the end
            
        except Exception as e:
            logger.error(f"Error viewing manual expenses: {e}")
            self.view.show_message(f"An error occurred: {e}", "error")

    def handle_count_receipts(self) -> None:
        from sqlalchemy import text
        db = self.db.db
        try:
            while True:
                # Fetch the next uncounted receipt (oldest first)
                receipt = db.execute(text(
                    """
                    SELECT r.receipt_id, r.store_id, r.date, r.payment_name, r.final_price
                    FROM receipts r
                    WHERE r.counted = FALSE
                    ORDER BY r.date ASC, r.receipt_id ASC
                    LIMIT 1
                    """
                )).fetchone()
                if not receipt:
                    self.view.show_message("No uncounted receipts found.", "info")
                    return
                receipt_id, store_id, date, payment_name, final_price = receipt
                # Get city from stores
                store = db.execute(text("SELECT store_city FROM stores WHERE store_id = :sid"), {"sid": store_id}).fetchone()
                city = store[0] if store else 'Unknown'
                # Get payer name
                payer = db.execute(text("SELECT u.name FROM user_payments up JOIN users u ON up.user_id = u.user_id WHERE up.payment_name = :pname"), {"pname": payment_name}).fetchone()
                payer_name = payer[0] if payer else payment_name
                # Get user names
                user1 = db.execute(text("SELECT name FROM users WHERE user_id = 1")).fetchone()
                user2 = db.execute(text("SELECT name FROM users WHERE user_id = 2")).fetchone()
                user1_name = user1[0] if user1 else 'User 1'
                user2_name = user2[0] if user2 else 'User 2'
                # Create colored versions for display
                colored_user1_name = self.view.colorize_user_name(user1_name, 1)
                colored_user2_name = self.view.colorize_user_name(user2_name, 2)
                # Get products for this receipt
                products = db.execute(text("SELECT product_id, product_name, quantity, total_after_discount FROM products WHERE receipt_id = :rid"), {"rid": receipt_id}).fetchall()
                if not products:
                    self.view.show_message(f"No products found for receipt {receipt_id}.", "warning")
                    # Mark as counted to avoid infinite loop
                    db.execute(text("UPDATE receipts SET counted = TRUE WHERE receipt_id = :rid"), {"rid": receipt_id})
                    db.commit()
                    continue
                # Prepare shares for each product
                product_shares = []
                self.view.print_section("COUNTING SUMMARY")
                print(f"Receipt: {receipt_id} | City: {city} | Date: {date} | Paid by: {payer_name} | Total: {final_price:.2f} PLN\n")
                for idx, (product_id, product_name, quantity, total_after_discount) in enumerate(products, 1):
                    static_share = db.execute(text("SELECT share FROM static_shares WHERE product_name = :pname"), {"pname": product_name}).fetchone()
                    if static_share:
                        share1 = float(static_share[0])
                        auto = True
                    else:
                        auto = False
                        while True:
                            prompt = f"{idx}. {quantity} x {product_name} ({total_after_discount:.2f} PLN) - Share for {colored_user1_name} (blank = 50): "
                            inp = self.view.get_input(prompt, required=False)
                            if not inp:
                                share1 = 50.0
                                break
                            inp = inp.strip()
                            if inp == '':
                                share1 = 50.0
                                break
                            try:
                                share1 = float(inp)
                                if 0 <= share1 <= 100:
                                    break
                                else:
                                    print("Share must be between 0 and 100.")
                            except Exception:
                                print("Invalid input. Enter a number between 0 and 100.")
                    share2 = 100 - share1
                    product_shares.append({
                        'idx': idx,
                        'product_id': product_id,
                        'product_name': product_name,
                        'quantity': quantity,
                        'total_after_discount': float(total_after_discount),
                        'share1': share1,
                        'share2': share2,
                        'auto': auto
                    })
                # Interactive summary/edit/save loop
                while True:
                    self.view.print_section("COUNTING SUMMARY")
                    print(f"Receipt: {receipt_id} | City: {city} | Date: {date} | Paid by: {payer_name} | Total: {final_price:.2f} PLN\n")
                    for p in product_shares:
                        u1_val = p['total_after_discount'] * p['share1'] / 100
                        u2_val = p['total_after_discount'] * p['share2'] / 100
                        auto_str = " [static]" if p['auto'] else ""
                        print(f"#{p['idx']}: {p['quantity']} x {p['product_name']} | {colored_user1_name} share: {p['share1']:.0f}% ({u1_val:.2f} PLN) | {colored_user2_name} share: {p['share2']:.0f}% ({u2_val:.2f} PLN){auto_str}")
                    print("\nOptions: [Enter]=Save, e=Edit, s=Add static share, n=Next/skip")
                    action = self.view.get_input("Your choice: ", required=False)
                    # Always treat blank input (None or '') as save
                    if not action:
                        action = ''
                    else:
                        action = action.strip().lower()
                    if action == '':
                        for p in product_shares:
                            db.execute(text("INSERT INTO shares (product_id, user_id, share) VALUES (:pid, 1, :share) ON CONFLICT (product_id, user_id) DO UPDATE SET share = :share"), {"pid": p['product_id'], "share": p['share1']})
                            db.execute(text("INSERT INTO shares (product_id, user_id, share) VALUES (:pid, 2, :share) ON CONFLICT (product_id, user_id) DO UPDATE SET share = :share"), {"pid": p['product_id'], "share": p['share2']})
                        db.execute(text("UPDATE receipts SET counted = TRUE WHERE receipt_id = :rid"), {"rid": receipt_id})
                        db.commit()
                        print("Receipt counted and saved!\n")
                        break
                    elif action == 'e':
                        idx_str = self.view.get_input("Enter product # to edit: ", required=True)
                        if not idx_str:
                            print("No product number entered.")
                            continue
                        try:
                            idx = int(idx_str)
                            p = next(x for x in product_shares if x['idx'] == idx)
                        except Exception:
                            print("Invalid product number.")
                            continue
                        while True:
                            new_share = self.view.get_input(f"New share for {p['product_name']} (blank = 50): ", required=False)
                            if not new_share:
                                share1 = 50.0
                                break
                            new_share = new_share.strip()
                            if new_share == '':
                                share1 = 50.0
                                break
                            try:
                                share1 = float(new_share)
                                if 0 <= share1 <= 100:
                                    break
                                else:
                                    print("Share must be between 0 and 100.")
                            except Exception:
                                print("Invalid input. Enter a number between 0 and 100.")
                        p['share1'] = share1
                        p['share2'] = 100 - share1
                        p['auto'] = False
                    elif action == 's':
                        idx_str = self.view.get_input("Enter product # to add static share: ", required=True)
                        if not idx_str:
                            print("No product number entered.")
                            continue
                        try:
                            idx = int(idx_str)
                            p = next(x for x in product_shares if x['idx'] == idx)
                        except Exception:
                            print("Invalid product number.")
                            continue
                        while True:
                            new_static = self.view.get_input(f"Static share for {p['product_name']} (blank = 50): ", required=False)
                            if not new_static:
                                static_val = 50.0
                                break
                            new_static = new_static.strip()
                            if new_static == '':
                                static_val = 50.0
                                break
                            try:
                                static_val = float(new_static)
                                if 0 <= static_val <= 100:
                                    break
                                else:
                                    print("Share must be between 0 and 100.")
                            except Exception:
                                print("Invalid input. Enter a number between 0 and 100.")
                        db.execute(text("INSERT INTO static_shares (product_name, share) VALUES (:pname, :share) ON CONFLICT (product_name) DO UPDATE SET share = :share"), {"pname": p['product_name'], "share": static_val})
                        db.commit()
                        print(f"Static share for {p['product_name']} set to {static_val}% ({colored_user1_name})")
                    elif action == 'n':
                        print("Receipt skipped.")
                        db.execute(text("UPDATE receipts SET counted = TRUE WHERE receipt_id = :rid"), {"rid": receipt_id})
                        db.commit()
                        break
                    else:
                        print("Unknown option.")
        except Exception as e:
            logger.error(f"Error in counting receipts: {e}")
            if 'db' in locals():
                db.db.rollback()
            self.view.show_message(f"An error occurred: {e}", "error")

    def handle_view_receipts_submenu(self) -> None:
        while True:
            options = [
                {"text": "Counted receipts (podliczone)", "key": "counted"},
                {"text": "Settled receipts (uregulowane)", "key": "settled"},
                {"text": "Not our receipts (nie nasze)", "key": "not_our"},
                {"text": "All receipts (wszystkie)", "key": "all"},
            ]
            choice = self.view.display_menu("View Receipts", options)
            if choice == '0':
                return
            try:
                idx = int(choice) - 1
                if idx < 0 or idx >= len(options):
                    self.view.show_message("Invalid choice. Please try again.", "error")
                    continue
                key = options[idx]["key"]
                if key == "counted":
                    receipts = self._get_counted_receipts()
                    self._show_counted_receipts_detailed(receipts)
                elif key == "settled":
                    receipts = self._get_settled_receipts()
                    self._show_settled_receipts_detailed(receipts)
                elif key == "not_our":
                    receipts = self._get_not_our_receipts()
                    self.view.show_receipts_list(receipts, "Not Our Receipts")
                elif key == "all":
                    receipts = self._get_all_receipts()
                    self.view.show_receipts_list(receipts, "All Receipts")
            except Exception:
                self.view.show_message("Please enter a valid number.", "error")

    def _get_counted_receipts(self):
        db = self.db.db
        rows = db.execute(text("""
            SELECT r.receipt_id, r.date, r.final_price, r.payment_name, r.counted, r.settled,
                   s.store_name, s.store_city, s.store_address
            FROM receipts r
            LEFT JOIN stores s ON r.store_id = s.store_id
            WHERE r.counted = TRUE AND r.not_our_receipt = FALSE 
            ORDER BY r.date DESC, r.receipt_id DESC
        """)).fetchall()
        
        receipts = []
        for row in rows:
            receipt_id, date, final_price, payment_name, counted, settled, store_name, store_city, store_address = row
            
            # Get payer name
            payer = db.execute(text("""
                SELECT u.name FROM user_payments up 
                JOIN users u ON up.user_id = u.user_id 
                WHERE up.payment_name = :payment_name
            """), {"payment_name": payment_name}).fetchone()
            payer_name = payer[0] if payer else payment_name
            
            # Get products and calculate shares
            products = db.execute(text("""
                SELECT p.product_id, p.product_name, p.quantity, p.total_after_discount
                FROM products p WHERE p.receipt_id = :receipt_id
            """), {"receipt_id": receipt_id}).fetchall()
            
            user_shares = {}
            total_products = 0
            
            for product_id, product_name, quantity, total_after_discount in products:
                total_products += float(total_after_discount)
                
                # Get shares for this product
                shares = db.execute(text("""
                    SELECT user_id, share FROM shares WHERE product_id = :product_id
                """), {"product_id": product_id}).fetchall()
                
                for user_id, share in shares:
                    if user_id not in user_shares:
                        user_shares[user_id] = 0.0
                    user_shares[user_id] += float(total_after_discount) * (float(share) / 100)
            
            receipts.append({
                'receipt_id': receipt_id,
                'date': date,
                'final_price': float(final_price),
                'payment_name': payment_name,
                'payer_name': payer_name,
                'counted': counted,
                'settled': settled,
                'store_name': store_name or 'Unknown',
                'store_city': store_city or 'Unknown',
                'store_address': store_address or 'Unknown',
                'user_shares': user_shares,
                'total_products': total_products
            })
        
        return receipts

    def _get_settled_receipts(self):
        db = self.db.db
        rows = db.execute(text("""
            SELECT r.receipt_id, r.date, r.final_price, r.payment_name, r.counted, r.settled,
                   s.store_name, s.store_city, s.store_address
            FROM receipts r
            LEFT JOIN stores s ON r.store_id = s.store_id
            WHERE r.settled = TRUE AND r.not_our_receipt = FALSE 
            ORDER BY r.date DESC, r.receipt_id DESC
        """)).fetchall()
        
        receipts = []
        for row in rows:
            receipt_id, date, final_price, payment_name, counted, settled, store_name, store_city, store_address = row
            
            # Get payer name
            payer = db.execute(text("""
                SELECT u.name FROM user_payments up 
                JOIN users u ON up.user_id = u.user_id 
                WHERE up.payment_name = :payment_name
            """), {"payment_name": payment_name}).fetchone()
            payer_name = payer[0] if payer else payment_name
            
            receipts.append({
                'receipt_id': receipt_id,
                'date': date,
                'final_price': float(final_price),
                'payment_name': payment_name,
                'payer_name': payer_name,
                'counted': counted,
                'settled': settled,
                'store_name': store_name or 'Unknown',
                'store_city': store_city or 'Unknown',
                'store_address': store_address or 'Unknown'
            })
        
        return receipts

    def _get_not_our_receipts(self):
        db = self.db.db
        rows = db.execute(text("""
            SELECT r.receipt_id, r.date, r.final_price, r.payment_name, r.counted, r.settled,
                   s.store_name, s.store_city, s.store_address
            FROM receipts r
            LEFT JOIN stores s ON r.store_id = s.store_id
            WHERE r.not_our_receipt = TRUE 
            ORDER BY r.date DESC, r.receipt_id DESC
        """)).fetchall()
        
        receipts = []
        for row in rows:
            receipt_id, date, final_price, payment_name, counted, settled, store_name, store_city, store_address = row
            
            receipts.append({
                'receipt_id': receipt_id,
                'date': date,
                'final_price': float(final_price),
                'payment_name': payment_name,
                'counted': counted,
                'settled': settled,
                'store_name': store_name or 'Unknown',
                'store_city': store_city or 'Unknown',
                'store_address': store_address or 'Unknown'
            })
        
        return receipts

    def _get_all_receipts(self):
        db = self.db.db
        rows = db.execute(text("""
            SELECT r.receipt_id, r.date, r.final_price, r.payment_name, r.counted, r.settled, r.not_our_receipt,
                   s.store_name, s.store_city, s.store_address
            FROM receipts r
            LEFT JOIN stores s ON r.store_id = s.store_id
            ORDER BY r.date DESC, r.receipt_id DESC
        """)).fetchall()
        
        receipts = []
        for row in rows:
            receipt_id, date, final_price, payment_name, counted, settled, not_our_receipt, store_name, store_city, store_address = row
            
            receipts.append({
                'receipt_id': receipt_id,
                'date': date,
                'final_price': float(final_price),
                'payment_name': payment_name,
                'counted': counted,
                'settled': settled,
                'not_our_receipt': not_our_receipt,
                'store_name': store_name or 'Unknown',
                'store_city': store_city or 'Unknown',
                'store_address': store_address or 'Unknown'
            })
        
        return receipts

    def _show_counted_receipts_detailed(self, receipts):
        """Show counted receipts in a table format with settlement summary."""
        if not receipts:
            self.view.show_message("No counted receipts available.", "info")
            return
        
        self.view.print_section("COUNTED RECEIPTS")
        
        # Get user names
        users = self.db.get_users()
        user_id_to_name = {user['id']: user['name'] for user in users}
        
        # Print header
        print(f"{'Date':<12} {'Paid_by':<12} {'Total_price':<12} {'Share(%)':<10} {'Michał':<10} {'Werka':<10}")
        print("-" * 70)
        
        total_final_price = 0
        user_totals = {user['id']: 0.0 for user in users}
        user_paid = {user['id']: 0.0 for user in users}
        
        for receipt in receipts:
            # Handle date formatting properly
            date_obj = receipt['date']
            if hasattr(date_obj, 'strftime'):
                date = date_obj.strftime('%Y-%m-%d')
            else:
                date = str(date_obj)
            
            paid_by = receipt['payer_name'][:11] if len(receipt['payer_name']) > 11 else receipt['payer_name']
            total_price = f"{receipt['final_price']:.2f}"
            
            # Calculate shares for this receipt
            michal_amount = 0.0
            werka_amount = 0.0
            michal_percentage = 0.0
            
            for user_id, share_amount in receipt['user_shares'].items():
                if user_id == 1:  # Michał
                    michal_amount = share_amount
                    michal_percentage = (share_amount / receipt['total_products']) * 100 if receipt['total_products'] > 0 else 0
                    user_totals[user_id] += share_amount
                elif user_id == 2:  # Werka
                    werka_amount = share_amount
                    user_totals[user_id] += share_amount
            
            # Find who paid and add to their paid total
            for user in users:
                if user['name'] == receipt['payer_name']:
                    user_paid[user['id']] += receipt['final_price']
                    break
            
            print(f"{date:<12} {paid_by:<12} {total_price:<12} {michal_percentage:<10.1f} {michal_amount:<10.2f} {werka_amount:<10.2f}")
            total_final_price += receipt['final_price']
        
        print("-" * 70)
        print(f"{'Total:':<36} {total_final_price:.2f}")
        
        # Calculate who owes whom
        print(f"\n{'='*70}")
        print("SETTLEMENT SUMMARY FOR COUNTED RECEIPTS")
        print(f"{'='*70}")
        
        michal_id = 1
        werka_id = 2
        
        michal_should_pay = user_totals[michal_id]
        werka_should_pay = user_totals[werka_id]
        michal_paid = user_paid[michal_id]
        werka_paid = user_paid[werka_id]
        
        michal_net = michal_paid - michal_should_pay
        werka_net = werka_paid - werka_should_pay
        
        print(f"Michał should pay: {michal_should_pay:.2f} PLN")
        print(f"Michał actually paid: {michal_paid:.2f} PLN")
        print(f"Michał net: {michal_net:.2f} PLN")
        print()
        print(f"Werka should pay: {werka_should_pay:.2f} PLN")
        print(f"Werka actually paid: {werka_paid:.2f} PLN")
        print(f"Werka net: {werka_net:.2f} PLN")
        print()
        
        if michal_net > 0 and werka_net < 0:
            print(f"So, Werka owes Michał {abs(werka_net):.2f} PLN for counted receipts.")
        elif werka_net > 0 and michal_net < 0:
            print(f"So, Michał owes Werka {abs(michal_net):.2f} PLN for counted receipts.")
        else:
            print("All expenses are already balanced.")
        
        self.view.show_message("Counted receipts display completed.", "success")

    def _show_settled_receipts_detailed(self, receipts):
        """Show settled receipts in a table with selection for details."""
        if not receipts:
            self.view.show_message("No settled receipts available.", "info")
            return
        self.view.print_section("SETTLED RECEIPTS")
        db = self.db.db
        # Fetch settled date for each receipt from settlements table
        receipt_settled_dates = {}
        for r in receipts:
            result = db.execute(text("""
                SELECT note FROM settlements s
                JOIN settlement_items si ON s.settlement_id = si.settlement_id
                WHERE si.receipt_id = :rid
                ORDER BY s.settlement_id DESC LIMIT 1
            """), {"rid": r['receipt_id']}).fetchone()
            settled_note = result[0] if result else "N/A"
            # Try to extract date from note if possible
            if settled_note and "finalized on" in settled_note:
                try:
                    settled_date = settled_note.split("finalized on ")[-1]
                except Exception:
                    settled_date = "N/A"
            else:
                settled_date = "N/A"
            receipt_settled_dates[r['receipt_id']] = settled_date
        # Print header
        header = f"{'#':<3} {'Date':<12} {'Shop':<20} {'Amount':>10} {'Paid By':<15} {'Settled date':<20}"
        print(header)
        print("-" * len(header))
        for idx, r in enumerate(receipts, 1):
            date = str(r.get('date', 'N/A'))
            shop = (r.get('store_name') or 'Unknown')[:18]
            amount = f"{float(r.get('final_price', 0)):.2f} PLN"
            payer = r.get('payer_name', 'Unknown')
            settled_date = receipt_settled_dates.get(r['receipt_id'], 'N/A')
            print(f"{idx:<3} {date:<12} {shop:<20} {amount:>10} {payer:<15} {settled_date:<20}")
        print("-" * len(header))
        total = sum(float(r.get('final_price', 0)) for r in receipts)
        print(f"{'Total:':<57} {total:.2f} PLN")
        print()
        # Allow selection for details
        choice = self.view.get_input("Enter the number of a receipt to see detailed summary, or press Enter to exit: ", required=False)
        if choice and choice.strip().isdigit():
            idx = int(choice.strip())
            if 1 <= idx <= len(receipts):
                receipt_id = receipts[idx-1]['receipt_id']
                # Show product-level breakdown (reuse logic from option 11)
                products = db.execute(text("""
                    SELECT p.product_name, p.quantity, p.total_after_discount, s.user_id, s.share
                    FROM products p
                    LEFT JOIN shares s ON p.product_id = s.product_id
                    WHERE p.receipt_id = :receipt_id
                """), {"receipt_id": receipt_id}).fetchall()
                # Group by product
                from collections import defaultdict
                users = self.db.get_users()
                user_id_to_name = {user['id']: user['name'] for user in users}
                product_map = defaultdict(list)
                for product_name, quantity, total_after_discount, user_id, share in products:
                    product_map[(product_name, quantity, total_after_discount)].append((user_id, share))
                for (product_name, quantity, total_after_discount), shares in product_map.items():
                    share_parts = []
                    for user_id, share in shares:
                        if user_id is not None and share is not None:
                            share_amount = float(total_after_discount) * (float(share) / 100)
                            share_parts.append(f"{user_id_to_name.get(user_id, 'User')} {share:.0f}% ({share_amount:.2f} PLN)")
                    share_str = ", ".join(share_parts)
                    print(f"{quantity} x {product_name}, {total_after_discount:.2f} PLN | {share_str}")
                print()
                input("Press Enter to go back...")

    def handle_view_statistics(self) -> None:
        self.view.show_message("View statistics not implemented yet.", "warning")

    def handle_show_settlement_summary(self) -> None:
        """Calculate and display settlement summary showing who owes whom."""
        from sqlalchemy import text
        db = self.db.db
        
        try:
            # Get user names
            users = db.execute(text("SELECT user_id, name FROM users ORDER BY user_id")).fetchall()
            if len(users) < 2:
                self.view.show_message("Need at least 2 users for settlement calculation.", "error")
                return
            
            user_names = {user[0]: user[1] for user in users}
            
            # Calculate settlement for each user
            user_totals = {}
            user_paid = {}
            
            # Initialize totals for each user
            for user_id in user_names.keys():
                user_totals[user_id] = 0.0
                user_paid[user_id] = 0.0
            
            # PRE-CALCULATION CHECKS
            print("DEBUG: Running pre-calculation checks...")
            
            # Check 1: Products without shares
            products_without_shares = db.execute(text("""
                SELECT p.product_id, p.product_name, p.total_after_discount, 
                       CASE WHEN p.receipt_id IS NOT NULL THEN 'receipt' ELSE 'manual' END as source_type,
                       CASE WHEN p.receipt_id IS NOT NULL THEN p.receipt_id ELSE p.manual_expense_id END as source_id
                FROM products p
                LEFT JOIN shares s ON p.product_id = s.product_id
                WHERE s.product_id IS NULL
                AND (
                    (p.receipt_id IS NOT NULL AND EXISTS (SELECT 1 FROM receipts r WHERE r.receipt_id = p.receipt_id AND r.counted = TRUE))
                    OR 
                    (p.manual_expense_id IS NOT NULL AND EXISTS (SELECT 1 FROM manual_expenses me WHERE me.manual_expense_id = p.manual_expense_id AND me.counted = TRUE AND me.settled = FALSE))
                )
            """)).fetchall()
            
            if products_without_shares:
                print(f"WARNING: Found {len(products_without_shares)} products without shares:")
                for product_id, product_name, total_after_discount, source_type, source_id in products_without_shares:
                    print(f"  - Product ID {product_id}: {product_name} ({total_after_discount:.2f} PLN) from {source_type} {source_id}")
            
            # Check 2: Receipts with mismatched totals
            receipt_mismatches = db.execute(text("""
                SELECT r.receipt_id, r.final_price, r.payment_name,
                       COALESCE(SUM(p.total_after_discount), 0) as products_total
                FROM receipts r
                LEFT JOIN products p ON r.receipt_id = p.receipt_id
                WHERE r.counted = TRUE
                GROUP BY r.receipt_id, r.final_price, r.payment_name
                HAVING ABS(r.final_price - COALESCE(SUM(p.total_after_discount), 0)) > 0.01
            """)).fetchall()
            
            if receipt_mismatches:
                print(f"WARNING: Found {len(receipt_mismatches)} receipts with mismatched totals:")
                for receipt_id, final_price, payment_name, products_total in receipt_mismatches:
                    print(f"  - Receipt {receipt_id}: final_price={final_price:.2f}, products_sum={products_total:.2f}, diff={abs(final_price - products_total):.2f}")
            
            # Check 3: Manual expenses without virtual products
            manual_without_products = db.execute(text("""
                SELECT me.manual_expense_id, me.description, me.total_cost
                FROM manual_expenses me
                LEFT JOIN products p ON me.manual_expense_id = p.manual_expense_id
                WHERE me.counted = TRUE
                AND p.product_id IS NULL
            """)).fetchall()
            
            if manual_without_products:
                print(f"WARNING: Found {len(manual_without_products)} manual expenses without virtual products:")
                for manual_expense_id, description, total_cost in manual_without_products:
                    print(f"  - Manual expense {manual_expense_id}: {description} ({total_cost:.2f} PLN)")
            
            # Check 4: Manual expenses with virtual products but no shares
            manual_without_shares = db.execute(text("""
                SELECT me.manual_expense_id, me.description, me.total_cost, p.product_id
                FROM manual_expenses me
                JOIN products p ON me.manual_expense_id = p.manual_expense_id
                LEFT JOIN shares s ON p.product_id = s.product_id
                WHERE me.counted = TRUE
                AND s.product_id IS NULL
            """)).fetchall()
            
            if manual_without_shares:
                print(f"WARNING: Found {len(manual_without_shares)} manual expenses with virtual products but no shares:")
                for manual_expense_id, description, total_cost, product_id in manual_without_shares:
                    print(f"  - Manual expense {manual_expense_id}: {description} ({total_cost:.2f} PLN), product_id {product_id}")
            
            print("DEBUG: Pre-calculation checks completed.\n")
            
            # 1. Calculate from counted receipts (excluding already settled ones)
            receipt_products = db.execute(text("""
                SELECT p.product_id, p.total_after_discount, r.payment_name, r.final_price, r.receipt_id
                FROM products p
                JOIN receipts r ON p.receipt_id = r.receipt_id
                WHERE r.counted = TRUE AND r.settled = FALSE AND p.receipt_id IS NOT NULL
            """)).fetchall()
            
            print(f"DEBUG: Processing {len(receipt_products)} receipt products")
            receipt_total = 0
            credited_receipts = set()  # <-- Track which receipts have been credited
            
            for product_id, total_after_discount, payment_name, final_price, receipt_id in receipt_products:
                receipt_total += float(total_after_discount)
                print(f"\nDEBUG: Processing receipt product {product_id} (receipt {receipt_id})")
                print(f"  Product total: {total_after_discount:.2f} PLN")
                print(f"  Receipt total: {final_price:.2f} PLN")
                print(f"  Paid by: {payment_name}")
                
                # Get shares for this product
                shares = db.execute(text("""
                    SELECT user_id, share FROM shares 
                    WHERE product_id = :product_id
                """), {"product_id": product_id}).fetchall()
                
                print(f"  Shares found: {len(shares)}")
                for user_id, share in shares:
                    user_amount = float(total_after_discount) * (float(share) / 100)
                    user_totals[user_id] += user_amount
                    print(f"    User {user_names[user_id]} (ID {user_id}): {share:.1f}% = {user_amount:.2f} PLN")
                
                # Find who paid for this receipt
                payer = db.execute(text("""
                    SELECT up.user_id FROM user_payments up 
                    WHERE up.payment_name = :payment_name
                """), {"payment_name": payment_name}).fetchone()
                
                # Only credit the payer once per receipt
                if payer and receipt_id not in credited_receipts:
                    payer_id = payer[0]
                    user_paid[payer_id] += float(final_price)
                    credited_receipts.add(receipt_id)
                    print(f"  Payer: {user_names[payer_id]} (ID {payer_id}) paid {final_price:.2f} PLN")
                elif payer:
                    print(f"  Payer already credited for receipt {receipt_id}")
                else:
                    print(f"  WARNING: No payer found for payment_name '{payment_name}'")
            
            print(f"\nDEBUG: Receipt products total: {receipt_total:.2f}")
            
            # 2. Calculate from counted manual expenses (excluding already settled ones)
            # Debug: Check what manual expenses exist and their status
            debug_manual = db.execute(text("""
                SELECT manual_expense_id, total_cost, payer_user_id, description, counted, settled
                FROM manual_expenses me
                WHERE settled = FALSE
                ORDER BY manual_expense_id
            """)).fetchall()
            print(f"DEBUG: All NOT SETTLED manual expenses in database:")
            if not debug_manual:
                print("  (none)")
            for me_id, cost, payer_id, desc, counted, settled in debug_manual:
                print(f"  ID {me_id}: {desc} - counted={counted}, settled={settled}")
            
            manual_expenses = db.execute(text("""
                SELECT me.manual_expense_id, me.total_cost, me.payer_user_id, me.description
                FROM manual_expenses me
                WHERE me.counted = TRUE AND me.settled = FALSE
            """)).fetchall()
            
            print(f"\nDEBUG: Processing {len(manual_expenses)} manual expenses")
            manual_total = 0
            
            for manual_expense_id, total_cost, payer_user_id, description in manual_expenses:
                manual_total += float(total_cost)
                print(f"\nDEBUG: Processing manual expense {manual_expense_id}")
                print(f"  Description: {description}")
                print(f"  Total cost: {total_cost:.2f} PLN")
                print(f"  Paid by: {user_names[payer_user_id]} (ID {payer_user_id})")
                
                # Get virtual product for this manual expense
                virtual_product = db.execute(text("""
                    SELECT product_id FROM products 
                    WHERE manual_expense_id = :manual_expense_id
                """), {"manual_expense_id": manual_expense_id}).fetchone()
                
                if virtual_product:
                    product_id = virtual_product[0]
                    print(f"  Virtual product ID: {product_id}")
                    
                    # Get shares for this virtual product
                    shares = db.execute(text("""
                        SELECT user_id, share FROM shares 
                        WHERE product_id = :product_id
                    """), {"product_id": product_id}).fetchall()
                    
                    print(f"  Shares found: {len(shares)}")
                    for user_id, share in shares:
                        user_amount = float(total_cost) * (float(share) / 100)
                        user_totals[user_id] += user_amount
                        print(f"    User {user_names[user_id]} (ID {user_id}): {share:.1f}% = {user_amount:.2f} PLN")
                    
                    # Add to what the payer actually paid
                    user_paid[payer_user_id] += float(total_cost)
                    print(f"  Payer {user_names[payer_user_id]} (ID {payer_user_id}) paid {total_cost:.2f} PLN")
                else:
                    print(f"  WARNING: No virtual product found for manual expense {manual_expense_id}")
            
            print(f"\nDEBUG: Manual expenses total: {manual_total:.2f}")
            print(f"DEBUG: Combined total (should pay): {receipt_total + manual_total:.2f}")
            
            # Debug: Show what each user should pay
            print("\nDEBUG: User totals breakdown:")
            for user_id, user_name in user_names.items():
                colored_name = self.view.colorize_user_name(user_name, user_id)
                print(f"  {colored_name}: {user_totals[user_id]:.2f}")
            
            # Debug: Show what each user actually paid
            print("DEBUG: User paid breakdown:")
            for user_id, user_name in user_names.items():
                colored_name = self.view.colorize_user_name(user_name, user_id)
                print(f"  {colored_name}: {user_paid[user_id]:.2f}")
            
            # VERIFICATION CHECKS
            print("\nDEBUG: Running verification checks...")
            
            # Check 1: Verify that sum of user_totals equals combined total
            calculated_total = sum(user_totals.values())
            expected_total = receipt_total + manual_total
            if abs(calculated_total - expected_total) > 0.01:
                print(f"ERROR: Sum of user totals ({calculated_total:.2f}) != expected total ({expected_total:.2f})")
            else:
                print(f"✓ Sum of user totals matches expected total: {calculated_total:.2f}")
            
            # Check 2: Verify that sum of user_paid equals sum of actual payments
            calculated_paid = sum(user_paid.values())
            expected_paid = receipt_total + manual_total  # Should be the same as expected_total
            if abs(calculated_paid - expected_paid) > 0.01:
                print(f"ERROR: Sum of user paid ({calculated_paid:.2f}) != expected paid ({expected_paid:.2f})")
            else:
                print(f"✓ Sum of user paid matches expected paid: {calculated_paid:.2f}")
            
            # Check 3: Show net calculation for each user
            print("\nDEBUG: Net calculation breakdown:")
            for user_id, user_name in user_names.items():
                should_pay = user_totals[user_id]
                actually_paid = user_paid[user_id]
                net = actually_paid - should_pay
                colored_name = self.view.colorize_user_name(user_name, user_id)
                print(f"  {colored_name}: paid {actually_paid:.2f} - should pay {should_pay:.2f} = net {net:.2f}")
            
            print("DEBUG: Verification checks completed.\n")
            
            # Calculate net amounts
            user_net = {}
            for user_id in user_names.keys():
                user_net[user_id] = user_paid[user_id] - user_totals[user_id]
            
            # Display settlement summary
            self.view.print_section("SETTLEMENT SUMMARY")
            header = f"{'User':<12} {'Should Pay':>15} {'Actually Paid':>18} {'Net':>15}"
            print(header)
            print("-" * len(header))
            total_should_pay = 0
            total_actually_paid = 0
            for user_id, user_name in user_names.items():
                should_pay = user_totals[user_id]
                actually_paid = user_paid[user_id]
                net = user_net[user_id]
                total_should_pay += should_pay
                total_actually_paid += actually_paid
                colored_user_name = self.view.colorize_user_name(user_name, user_id)
                print(f"{colored_user_name:<12} {should_pay:>15.2f} {actually_paid:>18.2f} {net:>15.2f}")
            print("-" * len(header))
            print(f"{'TOTAL':<12} {total_should_pay:>15.2f} {total_actually_paid:>18.2f}")
            print()
            
            # Show who owes whom
            self.view.print_section("WHO OWES WHOM")

            # Find the user with highest positive net (most overpaid)
            # and user with highest negative net (most underpaid)
            sorted_users = sorted(user_net.items(), key=lambda x: x[1], reverse=True)

            settlement_pairs = []  # To store settlements for DB
            if len(sorted_users) >= 2:
                highest_positive = sorted_users[0]  # Most overpaid
                highest_negative = sorted_users[-1]  # Most underpaid

                if highest_positive[1] > 0 and highest_negative[1] < 0:
                    amount_to_transfer = min(abs(highest_positive[1]), abs(highest_negative[1]))
                    debtor_name = self.view.colorize_user_name(user_names[highest_negative[0]], highest_negative[0])
                    payer_name = self.view.colorize_user_name(user_names[highest_positive[0]], highest_positive[0])
                    print(f"{debtor_name} owes {payer_name}: {amount_to_transfer:.2f} PLN")
                    settlement_pairs.append({
                        'payer_user_id': highest_positive[0],
                        'debtor_user_id': highest_negative[0],
                        'amount': amount_to_transfer
                    })
                    # If there are more than 2 users, show other transfers (not implemented for >2)
                else:
                    print("All expenses are already balanced.")
            else:
                print("Need at least 2 users for settlement calculation.")

            print()

            # --- Show detailed summary before finalizing ---
            self.view.print_section("SETTLEMENT CALCULATION DETAILS")
            # Receipts
            receipts_info = db.execute(text("""
                SELECT r.receipt_id, r.date, r.final_price, r.payment_name, s.store_name
                FROM receipts r
                LEFT JOIN stores s ON r.store_id = s.store_id
                WHERE r.counted = TRUE AND r.settled = FALSE
                ORDER BY r.date, r.receipt_id
            """)).fetchall()
            users = db.execute(text("SELECT user_id, name FROM users ORDER BY user_id")).fetchall()
            user_id_to_name = {u[0]: u[1] for u in users}
            print("Receipts to be settled:")
            for receipt_id, date, final_price, payment_name, store_name in receipts_info:
                payer = db.execute(text("SELECT u.name FROM user_payments up JOIN users u ON up.user_id = u.user_id WHERE up.payment_name = :pname"), {"pname": payment_name}).fetchone()
                payer_name = payer[0] if payer else payment_name
                print(f"Date: {date} | Store: {store_name or 'Unknown'} | Total: {final_price:.2f} PLN | Paid by: {payer_name}")
                # Show products and shares
                products = db.execute(text("""
                    SELECT p.product_name, p.quantity, p.total_after_discount, s.user_id, s.share
                    FROM products p
                    LEFT JOIN shares s ON p.product_id = s.product_id
                    WHERE p.receipt_id = :receipt_id
                """), {"receipt_id": receipt_id}).fetchall()
                from collections import defaultdict
                product_map = defaultdict(list)
                for product_name, quantity, total_after_discount, user_id, share in products:
                    product_map[(product_name, quantity, total_after_discount)].append((user_id, share))
                for (product_name, quantity, total_after_discount), shares in product_map.items():
                    share_parts = []
                    for user_id, share in shares:
                        if user_id is not None and share is not None:
                            share_amount = float(total_after_discount) * (float(share) / 100)
                            share_parts.append(f"{user_id_to_name.get(user_id, 'User')} {share:.0f}% ({share_amount:.2f} PLN)")
                    share_str = ", ".join(share_parts)
                    print(f"  {quantity} x {product_name}, {total_after_discount:.2f} PLN | {share_str}")
            print()
            # Manual Expenses
            manual_expenses_info = db.execute(text("""
                SELECT me.manual_expense_id, me.date, me.total_cost, me.payer_user_id, me.description
                FROM manual_expenses me
                WHERE me.counted = TRUE AND me.settled = FALSE
                ORDER BY me.date, me.manual_expense_id
            """)).fetchall()
            print("Manual expenses to be settled:")
            for manual_expense_id, date, total_cost, payer_user_id, description in manual_expenses_info:
                payer_name = user_id_to_name.get(payer_user_id, str(payer_user_id))
                print(f"Date: {date} | Desc: {description} | Total: {total_cost:.2f} PLN | Paid by: {payer_name}")
                # Show shares
                virtual_product = db.execute(text("SELECT product_id FROM products WHERE manual_expense_id = :mid"), {"mid": manual_expense_id}).fetchone()
                if virtual_product:
                    product_id = virtual_product[0]
                    shares = db.execute(text("SELECT user_id, share FROM shares WHERE product_id = :pid"), {"pid": product_id}).fetchall()
                    share_parts = []
                    for user_id, share in shares:
                        share_amount = float(total_cost) * (float(share) / 100)
                        share_parts.append(f"{user_id_to_name.get(user_id, 'User')} {share:.0f}% ({share_amount:.2f} PLN)")
                    if share_parts:
                        print(f"  Shares: {', '.join(share_parts)}")
            print()
            print(f"You are about to settle {len(receipts_info)} receipts and {len(manual_expenses_info)} manual expenses. Continue?")

            # Ask for settlement finalization
            finalize = self.view.get_input("Do you accept and finalize settlement? (y/n): ", required=False)
            if finalize and finalize.strip().lower() == 'y':
                try:
                    # Mark all counted receipts as settled and collect their IDs
                    receipt_result = db.execute(text("""
                        UPDATE receipts 
                        SET settled = TRUE 
                        WHERE counted = TRUE AND settled = FALSE
                        RETURNING receipt_id
                    """))
                    settled_receipt_ids = [row[0] for row in receipt_result.fetchall()]

                    # Mark all counted manual expenses as settled and collect their IDs
                    manual_result = db.execute(text("""
                        UPDATE manual_expenses 
                        SET settled = TRUE 
                        WHERE counted = TRUE AND settled = FALSE
                        RETURNING manual_expense_id
                    """))
                    settled_manual_ids = [row[0] for row in manual_result.fetchall()]

                    # Insert settlements and settlement_items
                    for pair in settlement_pairs:
                        note = f"Settlement finalized on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        settlement_insert = db.execute(text("""
                            INSERT INTO settlements (payer_user_id, debtor_user_id, amount, note)
                            VALUES (:payer_user_id, :debtor_user_id, :amount, :note)
                            RETURNING settlement_id
                        """), {
                            'payer_user_id': pair['payer_user_id'],
                            'debtor_user_id': pair['debtor_user_id'],
                            'amount': pair['amount'],
                            'note': note
                        })
                        settlement_id = settlement_insert.fetchone()[0]
                        # Link all settled receipts
                        for rid in settled_receipt_ids:
                            db.execute(text("""
                                INSERT INTO settlement_items (settlement_id, receipt_id, manual_expense_id)
                                VALUES (:settlement_id, :receipt_id, NULL)
                            """), {'settlement_id': settlement_id, 'receipt_id': rid})
                        # Link all settled manual expenses
                        for mid in settled_manual_ids:
                            db.execute(text("""
                                INSERT INTO settlement_items (settlement_id, receipt_id, manual_expense_id)
                                VALUES (:settlement_id, NULL, :manual_expense_id)
                            """), {'settlement_id': settlement_id, 'manual_expense_id': mid})

                    db.commit()

                    print(f"\nSettlement finalized!")
                    print(f"- {len(settled_receipt_ids)} receipts marked as settled")
                    print(f"- {len(settled_manual_ids)} manual expenses marked as settled")
                    print(f"- {len(settlement_pairs)} settlements recorded")

                    self.view.show_message("Settlement has been finalized successfully.", "success")
                except Exception as e:
                    logger.error(f"Error finalizing settlement: {e}")
                    db.db.rollback()
                    self.view.show_message(f"Error finalizing settlement: {e}", "error")
            else:
                self.view.show_message("Settlement calculation completed (not finalized).", "info")
            
        except Exception as e:
            logger.error(f"Error calculating settlement: {e}")
            self.view.show_message(f"An error occurred: {e}", "error") 

    def handle_find_receipt_or_expense(self) -> None:
        from sqlalchemy import text
        db = self.db.db
        try:
            amount_str = self.view.get_input("Enter the total amount to search for: ", required=True)
            if amount_str is None:
                self.view.show_message("Invalid amount.", "error")
                return
            amount_str = amount_str.replace(",", ".")
            try:
                amount = float(amount_str)
            except Exception:
                self.view.show_message("Invalid amount.", "error")
                return

            # --- Manual Expenses ---
            manual_expenses = db.execute(text("""
                SELECT me.manual_expense_id, me.date, me.total_cost, me.payer_user_id, me.description
                FROM manual_expenses me
                WHERE me.total_cost = :amount
                ORDER BY me.date DESC, me.manual_expense_id DESC
            """), {"amount": amount}).fetchall()
            users = self.db.get_users()
            user_id_to_name = {user['id']: user['name'] for user in users}
            if manual_expenses:
                print("\nManual Expenses:")
                for manual_expense_id, date, total_cost, payer_user_id, description in manual_expenses:
                    print(f"{description}")
                    # Get shares for this manual expense
                    virtual_product = db.execute(text("""
                        SELECT product_id FROM products WHERE manual_expense_id = :manual_expense_id
                    """), {"manual_expense_id": manual_expense_id}).fetchone()
                    shares_str = ""
                    if virtual_product:
                        product_id = virtual_product[0]
                        shares = db.execute(text("""
                            SELECT user_id, share FROM shares WHERE product_id = :product_id
                        """), {"product_id": product_id}).fetchall()
                        share_parts = []
                        for user_id, share in shares:
                            share_amount = float(total_cost) * (float(share) / 100)
                            share_parts.append(f"{user_id_to_name.get(user_id, 'User')} {share:.0f}% ({share_amount:.2f} PLN)")
                        if share_parts:
                            shares_str = ", ".join(share_parts)
                    payer = user_id_to_name.get(payer_user_id, str(payer_user_id))
                    print(f"{date} | {payer} | {total_cost:.2f} PLN" + (f" | {shares_str}" if shares_str else ""))
                    print()

            # --- Receipts ---
            receipts = db.execute(text("""
                SELECT r.receipt_id, r.date, s.store_city, r.payment_name, r.final_price, r.counted, r.settled
                FROM receipts r
                LEFT JOIN stores s ON r.store_id = s.store_id
                WHERE r.final_price = :amount
                ORDER BY r.date DESC, r.receipt_id DESC
            """), {"amount": amount}).fetchall()
            if receipts:
                print("Receipts:")
                header = f"{'#':<3} {'Date':<12} {'City':<12} {'Who paid':<12} {'Total price':>12} {'STATUS':<10}"
                print(header)
                print("-" * len(header))
                for idx, (receipt_id, date, city, payment_name, final_price, counted, settled) in enumerate(receipts, 1):
                    if settled:
                        status = "settled"
                    elif counted:
                        status = "counted"
                    else:
                        status = "pending"
                    print(f"{idx:<3} {str(date):<12} {str(city):<12} {str(payment_name):<12} {final_price:>12.2f} {status:<10}")
                print()
                # Allow selection for details
                choice = self.view.get_input("Enter the number of a receipt to see detailed summary, or press Enter to exit: ", required=False)
                if choice and choice.strip().isdigit():
                    idx = int(choice.strip())
                    if 1 <= idx <= len(receipts):
                        receipt_id = receipts[idx-1][0]
                        # Show product-level breakdown
                        products = db.execute(text("""
                            SELECT p.product_name, p.quantity, p.total_after_discount, s.user_id, s.share
                            FROM products p
                            LEFT JOIN shares s ON p.product_id = s.product_id
                            WHERE p.receipt_id = :receipt_id
                        """), {"receipt_id": receipt_id}).fetchall()
                        # Group by product
                        from collections import defaultdict
                        product_map = defaultdict(list)
                        for product_name, quantity, total_after_discount, user_id, share in products:
                            product_map[(product_name, quantity, total_after_discount)].append((user_id, share))
                        for (product_name, quantity, total_after_discount), shares in product_map.items():
                            share_parts = []
                            for user_id, share in shares:
                                if user_id is not None and share is not None:
                                    share_amount = float(total_after_discount) * (float(share) / 100)
                                    share_parts.append(f"{user_id_to_name.get(user_id, 'User')} {share:.0f}% ({share_amount:.2f} PLN)")
                            share_str = ", ".join(share_parts)
                            print(f"{quantity} x {product_name}, {total_after_discount:.2f} PLN | {share_str}")
                        print()
                        input("Press Enter to go back...")
        except Exception as e:
            logger.error(f"Error in find receipt/expense: {e}")
            self.view.show_message(f"An error occurred: {e}", "error")

    def handle_add_expense_api(self, expense_data: dict) -> None:
        """API version of add expense - no user interaction."""
        try:
            from app.db.database import insert_manual_expense
            
            # Validate required fields
            required_fields = ['description', 'amount', 'date', 'payer_user_id']
            for field in required_fields:
                if field not in expense_data or not expense_data[field]:
                    raise ValueError(f"Missing required field: {field}")
            
            # Prepare data for insert_manual_expense
            expense_for_insert = {
                "description": expense_data["description"],
                "total_cost": expense_data["amount"],
                "date": expense_data["date"],
                "user_id": expense_data["payer_user_id"],
                "category": expense_data.get("category", "Other"),
                "share1": expense_data["share1"],
                "share2": expense_data["share2"]
            }
            
            # Insert the expense
            insert_manual_expense(self.db.db, expense_for_insert)
            
        except Exception as e:
            logger.error(f"Error adding expense via API: {e}")
            raise

    def handle_show_settlement_summary_api(self) -> dict:
        """API version of settlement summary - returns data instead of displaying."""
        try:
            # Get all users
            users = self.db.get_users()
            if not users:
                return {"summary": [], "details": []}
            
            # Calculate settlements
            settlements = []
            details = []
            
            # Simple settlement calculation (you can enhance this)
            for i, user1 in enumerate(users):
                for j, user2 in enumerate(users):
                    if i < j:  # Avoid duplicates
                        # Calculate what user1 owes user2
                        amount = 0.0  # This would be calculated based on your business logic
                        
                        if amount > 0.01:  # Only show significant amounts
                            settlements.append({
                                "from_user": user1['name'],
                                "to_user": user2['name'],
                                "amount": amount
                            })
            
            # Get recent expenses for details
            recent_expenses = self.db.get_manual_expenses(limit=10)
            details = [
                {
                    "date": str(exp['date']),
                    "description": exp['description'],
                    "amount": exp['amount']
                }
                for exp in recent_expenses
            ]
            
            return {
                "summary": settlements,
                "details": details
            }
            
        except Exception as e:
            logger.error(f"Error getting settlement summary via API: {e}")
            return {"summary": [], "details": [], "error": str(e)}

    def get_menu_options(self):
        options = [
            {"text": "Add expense", "handler": self.handle_add_expense},
            {"text": "Process receipts", "handler": self.handle_process_receipts},
            {"text": "View manual expenses", "handler": self.handle_view_manual_expenses},
            {"text": "Count receipts", "handler": self.handle_count_receipts},
            {"text": "View receipts", "handler": self.handle_view_receipts_submenu},
            {"text": "View statistics", "handler": self.handle_view_statistics},
            {"text": "Show settlement summary", "handler": self.handle_show_settlement_summary},
            {"text": "Find receipt / expense", "handler": self.handle_find_receipt_or_expense},
        ]
        return options 