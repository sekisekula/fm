import os
import logging
from pathlib import Path
import json
import re
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import text
from app.utils import json_serial, safe_decimal, remove_polish_diacritics
from app.db.database import (
    insert_store, insert_receipt, is_payment_name_ignored, add_ignored_payment_name,
    insert_products_bulk, get_user_id_for_payment_name,
    insert_user_payment, create_tables
)
from app.db.session import SessionLocal
from app.db.utils import transaction_scope
from typing import Optional, Dict, Any, List
import traceback
import time
from app.config import Config

os.makedirs('/app/logs', exist_ok=True)

logger = logging.getLogger(__name__)

# Set up a dedicated file handler for parser debug logs
parser_file_handler = logging.FileHandler('/app/logs/parser_debug.log', mode='a', encoding='utf-8')
parser_file_handler.setLevel(logging.DEBUG)
parser_file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
if not any(isinstance(h, logging.FileHandler) and getattr(h, 'baseFilename', None) == parser_file_handler.baseFilename for h in logger.handlers):
    logger.addHandler(parser_file_handler)

# Force a log entry to ensure the file is created
logger.info("=== Parser module imported: log file creation test ===")

TOCHECK_FOLDER = Path(Config.UPLOAD_FOLDER)
PARSED_FOLDER = (TOCHECK_FOLDER.parent / "parsed").resolve()
REJECTED_FOLDER = (TOCHECK_FOLDER.parent / "rejected").resolve()

SUFFIX = "_parsed.json"

TOCHECK_FOLDER.mkdir(parents=True, exist_ok=True)
PARSED_FOLDER.mkdir(parents=True, exist_ok=True)
REJECTED_FOLDER.mkdir(parents=True, exist_ok=True)

# No more in-memory cache - using database as single source of truth

def process_receipt_file(file_path: Path) -> Optional[int]:
    """Process a single receipt file with improved error handling and bulk operations.
    
    Args:
        file_path: Path to the receipt file to process
        
    Returns:
        int: Receipt ID if successful, None otherwise
    """
    try:
        logger.info(f"Starting to process file: {file_path.name}")
        
        # Read the JSON file
        with open(file_path, 'r', encoding='utf-8') as f:
            receipt_data = json.load(f)

        # Extract receipt number from JSON data
        receipt_number = ''
        try:
            # Try to get receipt number from fiscalFooter
            for item in receipt_data.get('body', []):
                if 'fiscalFooter' in item:
                    fiscal = item['fiscalFooter']
                    bill_number = str(fiscal.get('billNumber', ''))
                    if bill_number:
                        receipt_number = bill_number
                        logger.debug(f"Found receipt number in fiscal footer: {receipt_number}")
                        break
            
            # If not found in fiscalFooter, try to get it from header data
            if not receipt_number:
                for item in receipt_data.get('header', []):
                    if 'headerData' in item and 'docNumber' in item['headerData']:
                        receipt_number = str(item['headerData']['docNumber'])
                        logger.debug(f"Found receipt number in header data: {receipt_number}")
                        break
            
            # If still not found, try to get it from the transaction number
            if not receipt_number:
                for item in receipt_data.get('body', []):
                    if 'addLine' in item and 'data' in item['addLine']:
                        match = re.search(r'Nr transakcji:\s*<span[^>]*>(\d+)<', item['addLine']['data'])
                        if match:
                            receipt_number = match.group(1)
                            logger.debug(f"Found transaction number: {receipt_number}")
                            break
            
            # If still no receipt number, use a timestamp as fallback
            if not receipt_number:
                receipt_number = str(int(time.time()))
                logger.warning(f"Could not find receipt number in data, using timestamp: {receipt_number}")
            
            logger.info(f"Using receipt number: {receipt_number}")
            
        except Exception as e:
            logger.error(f"Error extracting receipt number: {e}")
            receipt_number = str(int(time.time()))
            logger.warning(f"Generated fallback receipt number: {receipt_number}")
        
        # Store the receipt number in the receipt data
        receipt_data['receiptNumber'] = receipt_number

        # Process payment information
        payment_name, user_id_for_payment = _process_payment_info(receipt_data, file_path.name)
        if user_id_for_payment is None:  # User chose to skip or error occurred
            return None

        # Ensure receipt number is in the receipt data
        if 'receiptNumber' not in receipt_data or not receipt_data['receiptNumber']:
            receipt_data['receiptNumber'] = str(int(time.time()))
            logger.warning(f"Generated new receipt number: {receipt_data['receiptNumber']}")

        # Parse receipt header
        receipt_header = parse_receipt(receipt_data)
        
        # Ensure receipt number is preserved in the header
        if 'receipt_number' not in receipt_header or not receipt_header['receipt_number']:
            receipt_header['receipt_number'] = receipt_data['receiptNumber']
            logger.info(f"Using receipt number from data: {receipt_header['receipt_number']}")
        if not receipt_header:
            logger.error(f"Failed to parse receipt header from {file_path.name}")
            return None

        # Extract fiscal data if available
        _extract_fiscal_data(receipt_data, receipt_header)

        # Insert store
        store_id = insert_store(receipt_header)
        if not store_id:
            raise ValueError(f"Could not insert/retrieve store ID for {receipt_header.get('store_name')}")
        logger.info(f"Store ID: {store_id} for '{receipt_header.get('store_name')}'")

        # Prepare receipt data
        receipt_header["final_price"] = safe_decimal(receipt_header.get("final_price"))
        receipt_header["total_discounts"] = safe_decimal(receipt_header.get("total_discounts", 0))
        
        # Check if this is a 'not our receipt' by checking if the user is the 'Other' user
        with SessionLocal() as db:
            other_user = db.execute(
                text("SELECT user_id FROM users WHERE name = 'Other'")
            ).fetchone()
            
            if other_user and user_id_for_payment == other_user[0]:
                not_our_receipt = True
                logger.info(f"Marking receipt as 'not ours' for payment name: {payment_name}")
            else:
                not_our_receipt = False
        
        # === ATOMIC TRANSACTION FOR RECEIPT + PRODUCTS ===
        try:
            with transaction_scope() as db:
                from app.db.duplicate_check import is_duplicate_receipt
                duplicate_data = {
                    'date': receipt_header.get('date'),
                    'time': receipt_header.get('time'),
                    'final_price': receipt_header.get('final_price')
                }
                is_dup = is_duplicate_receipt(db, duplicate_data)
                if is_dup:
                    logger.info(f"[SKIP] Duplicate receipt detected - Date: {duplicate_data['date']}, Time: {duplicate_data['time']}, Final Price: {duplicate_data['final_price']}")
                    print(f"ℹ️ Receipt was skipped (DUPLICATE)")
                    _move_file_to_folder(file_path, PARSED_FOLDER)
                    return None
                logger.info(f"Attempting to insert receipt with number: {receipt_number}")
                receipt_id = insert_receipt(receipt_header, store_id, payment_name, not_our_receipt, db=db)
                if receipt_id is None:
                    logger.warning(f"[SKIP] insert_receipt returned None. Possible reasons: already exists, DB constraint, or error. Data: {receipt_header}")
                    print(f"ℹ️ Receipt was skipped (ALREADY EXISTS or ERROR)")
                    _move_file_to_folder(file_path, PARSED_FOLDER)
                    return None
                logger.info(f"[ADD] Receipt ID: {receipt_id} for number '{receipt_header.get('receipt_number')}' - Successfully added.")
                products = receipt_header.get('products', [])
                if products:
                    insert_products_bulk(products, receipt_id, db=db)
            logger.info(f"[SUCCESS] Successfully processed and moved receipt {file_path.name}")
            print(f"✓ Successfully processed receipt (ID: {receipt_id})")
            _move_file_to_folder(file_path, PARSED_FOLDER)
            return receipt_id
        except Exception as e:
            logger.error(f"[ERROR] Error in atomic receipt+products transaction: {e}")
            logger.debug(traceback.format_exc())
            print(f"✗ Receipt was skipped (INVALID: {str(e)})")
            _move_file_to_folder(file_path, REJECTED_FOLDER)
            return None

    except json.JSONDecodeError as je:
        logger.error(f"Invalid JSON in file {file_path.name}: {str(je)}")
        print(f"ℹ️ Receipt was skipped (INVALID: Invalid JSON: {str(je)})")
        _move_file_to_folder(file_path, REJECTED_FOLDER)
    except FileNotFoundError as fnfe:
        logger.error(f"File not found: {file_path.name}: {str(fnfe)}")
        print(f"ℹ️ Receipt was skipped (INVALID: File not found: {str(fnfe)})")
        _move_file_to_folder(file_path, REJECTED_FOLDER)
    except PermissionError as pe:
        logger.error(f"Permission error processing {file_path.name}: {str(pe)}")
        print(f"ℹ️ Receipt was skipped (INVALID: Permission error: {str(pe)})")
        _move_file_to_folder(file_path, REJECTED_FOLDER)
    except Exception as e:
        logger.error(f"Unexpected error processing {file_path.name}: {str(e)}")
        logger.debug(traceback.format_exc())
        print(f"ℹ️ Receipt was skipped (INVALID: {str(e)})")
        _move_file_to_folder(file_path, REJECTED_FOLDER)
    
    return None

def process_receipt_data(receipt_data: dict) -> int:
    """
    Przetwarza i zapisuje paragon z dict (np. z uploadu webowego).
    Zwraca receipt_id lub rzuca wyjątek przy błędzie.
    Jeśli payment_name nie jest przypisany do user_id, paragon i tak jest zapisywany.
    """
    from app.db.duplicate_check import is_duplicate_receipt
    from app.db.database import insert_store, insert_receipt, insert_products_bulk
    from app.db.utils import transaction_scope
    from app.utils import safe_decimal
    import re, time
    # --- Extract receipt number ---
    receipt_number = ''
    try:
        for item in receipt_data.get('body', []):
            if 'fiscalFooter' in item:
                fiscal = item['fiscalFooter']
                bill_number = str(fiscal.get('billNumber', ''))
                if bill_number:
                    receipt_number = bill_number
                    break
        if not receipt_number:
            for item in receipt_data.get('header', []):
                if 'headerData' in item and 'docNumber' in item['headerData']:
                    receipt_number = str(item['headerData']['docNumber'])
                    break
        if not receipt_number:
            for item in receipt_data.get('body', []):
                if 'addLine' in item and 'data' in item['addLine']:
                    match = re.search(r'Nr transakcji:\s*<span[^>]*>(\d+)<', item['addLine']['data'])
                    if match:
                        receipt_number = match.group(1)
                        break
        if not receipt_number:
            receipt_number = str(int(time.time()))
        receipt_data['receiptNumber'] = receipt_number
    except Exception:
        receipt_data['receiptNumber'] = str(int(time.time()))
    # --- Payment info ---
    payment_name = None
    body = receipt_data.get('body', [])
    for item in body:
        if 'payment' in item and isinstance(item['payment'], dict):
            payment_name = item['payment'].get('name')
            if payment_name:
                break
    if not payment_name and 'payment' in receipt_data and isinstance(receipt_data['payment'], dict):
        payment_name = receipt_data['payment'].get('name')
    if not payment_name:
        raise ValueError('Brak payment_name w danych paragonu')
    payment_name = str(payment_name).strip()
    # --- Parse header ---
    from app.parser import parse_receipt, _extract_fiscal_data
    receipt_header = parse_receipt(receipt_data)
    if 'receipt_number' not in receipt_header or not receipt_header['receipt_number']:
        receipt_header['receipt_number'] = receipt_data['receiptNumber']
    _extract_fiscal_data(receipt_data, receipt_header)
    # --- Insert store ---
    store_id = insert_store(receipt_header)
    if not store_id:
        raise ValueError(f"Nie można dodać sklepu: {receipt_header.get('store_name')}")
    receipt_header["final_price"] = safe_decimal(receipt_header.get("final_price"))
    receipt_header["total_discounts"] = safe_decimal(receipt_header.get("total_discounts", 0))
    # --- Not our receipt? ---
    from app.db.session import SessionLocal
    with SessionLocal() as db:
        other_user = db.execute(text("SELECT user_id FROM users WHERE name = 'Other' OR name = 'Inny'"))
        not_our_receipt = False  # nie rozróżniamy na tym etapie
    # --- Transaction: insert receipt + products ---
    with transaction_scope() as db:
        from app.db.duplicate_check import is_duplicate_receipt
        duplicate_data = {
            'date': receipt_header.get('date'),
            'time': receipt_header.get('time'),
            'final_price': receipt_header.get('final_price')
        }
        is_dup = is_duplicate_receipt(db, duplicate_data)
        if is_dup:
            raise ValueError("Paragon już istnieje w bazie (duplikat)")
        # Zapisz payment_name, nawet jeśli nie ma user_id
        receipt_id = insert_receipt(receipt_header, store_id, payment_name, not_our_receipt, db=db)
        if receipt_id is None:
            raise ValueError("Nie udało się dodać paragonu (insert_receipt zwrócił None)")
        products = receipt_header.get('products', [])
        if products:
            insert_products_bulk(products, receipt_id, db=db)
    return receipt_id

def _process_payment_info(receipt_data: Dict[str, Any], filename: str) -> tuple[Optional[str], Optional[int]]:
    """Process payment information from receipt data.
    
    For new payment names, prompts the user to assign to one of the main users or the 'Other' user.
    Returns a tuple of (payment_name, user_id) or (None, None) if processing should be aborted.
    """
    try:
        # Try to extract payment name from receipt data
        payment_name = None
        
        # Try to find payment in the body array
        body = receipt_data.get('body', [])
        for item in body:
            if 'payment' in item and isinstance(item['payment'], dict):
                payment_name = item['payment'].get('name')
                if payment_name:
                    break
        
        # If not found in body, try direct payment field as fallback
        if not payment_name and 'payment' in receipt_data and isinstance(receipt_data['payment'], dict):
            payment_name = receipt_data['payment'].get('name')
        
        # If still not found, prompt user
        if not payment_name:
            logger.warning(f"No payment name found in {filename}")
            payment_name = input(f"Enter payment name for {filename} (or press Enter to skip): ").strip()
            if not payment_name:
                logger.info("No payment name provided. Skipping receipt.")
                return None, None
        else:
            payment_name = str(payment_name).strip()

        # Check if payment is ignored
        if is_payment_name_ignored(payment_name):
            logger.info(f"Payment '{payment_name}' is in ignore list. Skipping...")
            return None, None
        
        # Get or assign user ID for payment
        user_id = get_user_id_for_payment_name(payment_name)
        
        if user_id is None:
            # Get available users for assignment
            with SessionLocal() as db:
                # Get all users, with 'Other' user last
                users = db.execute(text(
                    "SELECT user_id, name FROM users ORDER BY CASE WHEN name = 'Other' THEN 1 ELSE 0 END, user_id"
                )).fetchall()
                
                if not users:
                    logger.error("No users found in the database. Please run the user setup first.")
                    return None, None
                
                # Separate main users from 'Other' user
                main_users = [user for user in users if user[1].lower() != 'other']
                other_users = [user for user in users if user[1].lower() == 'other']
                
                # Prompt user for assignment
                print(f"\nPayment name not found: {payment_name}")
                print("Assign to:")
                
                # List main users
                for i, (uid, name) in enumerate(main_users, 1):
                    print(f"{i}. {name}")
                
                # Add 'Other' user option if exists
                other_option = len(main_users) + 1
                if other_users:
                    print(f"{other_option}. {other_users[0][1]} (not ours)")
                
                # Get user choice
                while True:
                    try:
                        choice = input(f"Enter your choice (1-{other_option}): ").strip()
                        if not choice.isdigit():
                            raise ValueError("Please enter a number")
                            
                        choice = int(choice)
                        if 1 <= choice <= len(users):
                            break
                        print(f"Please enter a number between 1 and {len(users)}")
                    except ValueError as ve:
                        print(f"Invalid input: {ve}. Please try again.")
                
                # Get selected user ID
                if 1 <= choice <= len(main_users):
                    user_id = main_users[choice - 1][0]
                elif other_users and choice == other_option:
                    user_id = other_users[0][0]
                else:
                    logger.info("No valid user selected. Skipping receipt.")
                    return None, None
            
            # Save the mapping for future use
            if user_id:
                insert_user_payment(user_id, payment_name)
                logger.info(f"Saved mapping: {payment_name} -> user_id {user_id}")
        
        return payment_name, user_id
        
    except Exception as e:
        logger.error(f"Error processing payment info: {str(e)}")
        logger.debug(traceback.format_exc())
        return None, None



def _extract_fiscal_data(receipt_data: Dict[str, Any], receipt_header: Dict[str, Any]) -> None:
    """Extract fiscal data from receipt if available."""
    if 'fiscal' in receipt_data:
        fiscal = receipt_data['fiscal']
        receipt_header['receipt_number'] = fiscal.get('billNumber') or ""
        receipt_header['date'] = (fiscal.get('date') or "")[:10]  # Extract date part
        receipt_header['time'] = (fiscal.get('date') or "")[11:19]  # Extract time part

def _process_products(products: List[Dict[str, Any]], receipt_id: int) -> None:
    """Process and insert products in bulk.
    
    Args:
        products: List of product dictionaries
        receipt_id: ID of the receipt these products belong to
    """
    if not products:
        logger.info("No products to process")
        return

    processed_products = []
    for product in products:
        try:
            product_name = str(product.get('product_name', '')).strip()
            if not product_name:
                logger.warning("Skipping product with empty name")
                continue
            quantity = Decimal(str(safe_decimal(product.get('quantity', 1)))).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
            unit_price_before = float(safe_decimal(product.get('unit_price_before', 0)) or 0)
            total_price_before = float(safe_decimal(product.get('total_price_before', 0)) or 0)
            unit_discount = float(safe_decimal(product.get('unit_discount', 0)) or 0)
            total_discount = float(safe_decimal(product.get('total_discount', 0)) or 0)
            unit_after_discount = float(safe_decimal(
                product.get('unit_after_discount', unit_price_before - unit_discount)
            ) or 0)
            total_after_discount = float(safe_decimal(
                product.get('total_after_discount', total_price_before - total_discount)
            ) or 0)
            tax_type = str(product.get('tax_type', 'A'))[0].upper()
            if tax_type not in ['A', 'B', 'C', 'D', 'E', 'F']:
                tax_type = 'A'
            processed_product = {
                'product_name': product_name,
                'quantity': float(quantity),
                'tax_type': tax_type,
                'unit_price_before': max(0, unit_price_before),
                'total_price_before': max(0, total_price_before),
                'unit_discount': max(0, unit_discount),
                'total_discount': max(0, total_discount),
                'unit_after_discount': max(0, unit_after_discount),
                'total_after_discount': max(0, total_after_discount)
            }
            processed_products.append(processed_product)
        except (ValueError, TypeError) as e:
            logger.error(f"Error processing product {product.get('product_name', 'unknown')}: {e}")
            continue

    if not processed_products:
        logger.warning("No valid products to insert after processing")
        return

    try:
        from app.db.utils import transaction_scope
        with transaction_scope() as db:
            insert_products_bulk(processed_products, receipt_id, db=db)
        logger.info(f"Successfully inserted {len(processed_products)} products for receipt {receipt_id}")
    except Exception as e:
        logger.error(f"Error inserting products for receipt {receipt_id}: {e}")
        raise

def _move_file_to_folder(file_path: Path, target_folder: Path) -> None:
    try:
        target_path = target_folder / file_path.name
        file_path.replace(target_path)
    except Exception as e:
        logger.error(f"Failed to move file {file_path} to {target_folder}: {e}")

def parse_receipt(receipt_data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse receipt data and extract relevant information, including correct product discount handling."""
    from datetime import datetime
    from html import unescape
    
    # Initialize with default values
    receipt = {
        'receipt_number': str(receipt_data.get('receiptNumber', '')),
        'date': '',
        'time': '',
        'store_name': '',
        'store_address': '',
        'store_city': '',
        'postal_code': '',
        'final_price': 0.0,
        'total_discounts': 0.0,
        'vat_amount': 0.0,
        'vat_rate': 0.0,
        'currency': 'PLN',
        'products': [],
        'payment_name': '',
        'payment_type': '',
        'payment_amount': 0.0,
        'payment_currency': 'PLN'
    }
    
    # Extract store information from the receipt data
    logger.debug(f"Extracting store info from receipt data")
    
    # Try to get store info from headerText first
    for item in receipt_data.get('header', []):
        if 'headerText' in item and 'headerTextLines' in item['headerText']:
            header_text = item['headerText']['headerTextLines']
            if header_text:
                # Parse the HTML content to extract store info
                lines = []
                # Split by div elements and clean up
                parts = header_text.split('<div class="align-center ">')
                for part in parts[1:]:  # Skip first empty part
                    line = part.split('</div>')[0]  # Get content before closing div
                    line = unescape(line).replace('&nbsp;', ' ').strip()
                    if line:  # Only add non-empty lines
                        lines.append(line)
                
                # First line contains store name (e.g., "BIEDRONKA "CODZIENNIE NISKIE CENY" 7565")
                if lines and not receipt['store_name']:
                    # Extract just the store name, remove the rest
                    store_name = lines[0].split('"')[0].strip()
                    if store_name:
                        receipt['store_name'] = store_name
                
                # Second line contains address and postal code (e.g., "60-649 POZNAŃ UL. PIĄTKOWSKA 78C")
                if len(lines) > 1 and not receipt['store_address']:
                    address_line = lines[1]
                    # Extract postal code (e.g., 60-649)
                    postal_code_match = re.search(r'\b(\d{2}-\d{3})\b', address_line)
                    if postal_code_match:
                        receipt['postal_code'] = postal_code_match.group(1)
                        # Remove postal code from the address line
                        address_line = address_line.replace(receipt['postal_code'], '').strip()
                    
                    # Normalize whitespace (including non-breaking spaces)
                    address_line = re.sub(r'\s+', ' ', address_line.replace('\xa0', ' ')).strip()
                    parts = address_line.split(' ', 1)
                    if len(parts) == 2:
                        receipt['store_city'] = parts[0].strip()
                        receipt['store_address'] = parts[1].strip()
                    else:
                        receipt['store_city'] = address_line.strip()
                        receipt['store_address'] = ''
    
    # If store info not found in header, try other locations
    if not receipt['store_name'] or not receipt['store_address']:
        # Try to get store info directly from receipt_data
        if 'store' in receipt_data and isinstance(receipt_data['store'], dict):
            store = receipt_data['store']
            if not receipt['store_name']:
                receipt['store_name'] = store.get('name', '').strip()
            if not receipt['store_city']:
                receipt['store_city'] = store.get('city', '').strip().upper()
            if not receipt['store_address']:
                receipt['store_address'] = store.get('address', '').strip()
            
            # Extract postal code from address if not directly available
            if 'address' in store and not receipt['postal_code']:
                postal_code_match = re.search(r'\b\d{2}-\d{3}\b', store['address'])
                if postal_code_match:
                    receipt['postal_code'] = postal_code_match.group(0)
                    # Remove postal code from address if it's at the end
                    receipt['store_address'] = store['address'].replace(receipt['postal_code'], '').strip()
        
        # Try to find in body array as well
        for item in receipt_data.get('body', []):
            if 'store' in item and isinstance(item['store'], dict):
                store = item['store']
                if not receipt['store_name']:
                    receipt['store_name'] = store.get('name', '').strip()
                if not receipt['store_city']:
                    receipt['store_city'] = store.get('city', '').strip().upper()
                if not receipt['store_address']:
                    receipt['store_address'] = store.get('address', '').strip()
                
                # Extract postal code from address if not directly available
                if 'address' in store and not receipt['postal_code']:
                    postal_code_match = re.search(r'\b\d{2}-\d{3}\b', store['address'])
                    if postal_code_match:
                        receipt['postal_code'] = postal_code_match.group(0)
                        # Remove postal code from address if it's at the end
                        receipt['store_address'] = store['address'].replace(receipt['postal_code'], '').strip()
    
    # Clean up store name - remove any numbers at the end (like store number)
    if receipt['store_name']:
        receipt['store_name'] = re.sub(r'\s*\d+$', '', receipt['store_name']).strip()
    
    # If we still don't have a store name, try to get it from other fields
    if not receipt['store_name']:
        if 'receiptNumber' in receipt_data and isinstance(receipt_data['receiptNumber'], str):
            receipt['store_name'] = receipt_data['receiptNumber'].split('_')[0] if '_' in receipt_data['receiptNumber'] else receipt_data['receiptNumber']
        elif 'fiscal' in receipt_data and 'billNumber' in receipt_data['fiscal']:
            receipt['store_name'] = f"Store_{receipt_data['fiscal']['billNumber']}"
    
    # If we still don't have a store name, use a default value
    if not receipt['store_name']:
        receipt['store_name'] = 'Unknown Store'
        logger.warning("Could not determine store name, using default value")
    
    logger.debug(f"Extracted store info - Name: '{receipt['store_name']}', Address: '{receipt['store_address']}', "
                f"City: '{receipt['store_city']}', Postal Code: '{receipt['postal_code']}'")
    
    # Extract payment and fiscal data
    for item in receipt_data.get('body', []):
        # Extract payment information
        if 'payment' in item:
            payment = item['payment']
            if isinstance(payment, dict):
                receipt['payment_name'] = payment.get('name', '')
                receipt['payment_type'] = payment.get('type', '')
                receipt['payment_amount'] = float(safe_decimal(payment.get('amount', 0)))
                receipt['payment_currency'] = payment.get('currency', 'PLN')
        
        # Extract fiscal footer data (but don't override the receipt number here)
        if 'fiscalFooter' in item:
            fiscal = item['fiscalFooter']
            bill_number = str(fiscal.get('billNumber', ''))
            if bill_number and not receipt.get('receipt_number'):  # Only set if not already set
                receipt['receipt_number'] = bill_number
                logger.debug(f"Found bill number in fiscal footer: {bill_number}")
            
            # Parse date from ISO format
            try:
                date_str = fiscal.get('date', '')
                if date_str:
                    dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    receipt['date'] = dt.strftime('%Y-%m-%d')
                    receipt['time'] = dt.strftime('%H:%M:%S')
                    logger.debug(f"Parsed date: {receipt['date']} {receipt['time']}")
            except (ValueError, AttributeError) as e:
                logger.warning(f"Error parsing date: {e}")
    
    # Extract VAT summary
    for item in receipt_data.get('body', []):
        if 'vatSummary' in item:
            vat_summary = item['vatSummary']
            for rate in vat_summary.get('vatRatesSummary', []):
                receipt['vat_rate'] = float(safe_decimal(rate.get('vatRate', 0))) / 100  # Convert to percentage
                receipt['vat_amount'] = float(safe_decimal(rate.get('vatAmount', 0))) / 100  # Convert to currency
    
    # Extract total price and discounts
    for item in receipt_data.get('body', []):
        if 'sumInCurrency' in item:
            total = item['sumInCurrency']
            receipt['final_price'] = float(safe_decimal(total.get('fiscalTotal', 0))) / 100  # Convert to currency
            receipt['currency'] = total.get('currency', 'PLN')
        if 'discountSummary' in item:
            discounts = item['discountSummary'].get('discounts')
            if discounts is not None:
                receipt['total_discounts'] = float(safe_decimal(discounts)) / 100
                logger.debug(f"Extracted total discount: {receipt['total_discounts']}")
    
    # --- NEW PRODUCT & DISCOUNT LOGIC ---
    products = []
    pending_product = None
    for item in receipt_data.get('body', []):
        if 'sellLine' in item:
            if pending_product:
                # Round all monetary values to 2 decimal places before appending
                for k in ['unit_price_before', 'total_price_before', 'unit_discount', 'total_discount', 'unit_after_discount', 'total_after_discount']:
                    pending_product[k] = float(Decimal(str(pending_product[k])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
                products.append(pending_product)
            sell = item['sellLine']
            name_with_vat = sell.get('name', '').rstrip()
            parts = name_with_vat.rsplit(' ', 1)
            product_name = name_with_vat
            tax_type = sell.get('vatId', '')
            if len(parts) == 2 and len(parts[1]) == 1 and parts[1].isalpha():
                product_name, tax_type = parts[0].rstrip(), parts[1]
            quantity = Decimal(str(safe_decimal(sell.get('quantity', 1)))).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
            unit_price_before = Decimal(str(safe_decimal(sell.get('price', 0)))) / Decimal('100')
            total_price_before = Decimal(str(safe_decimal(sell.get('total', 0)))) / Decimal('100')
            pending_product = {
                'product_name': product_name,
                'tax_type': tax_type,
                'quantity': float(quantity),
                'unit_price_before': unit_price_before,
                'total_price_before': total_price_before,
                'unit_discount': Decimal('0.00'),
                'total_discount': Decimal('0.00'),
                'unit_after_discount': unit_price_before,
                'total_after_discount': total_price_before
            }
        elif 'discountLine' in item and pending_product:
            discount = item['discountLine']
            if discount.get('vatId') == pending_product['tax_type'] and Decimal(str(safe_decimal(discount.get('base', 0)))) / Decimal('100') == pending_product['total_price_before']:
                total_discount = Decimal(str(safe_decimal(discount.get('value', 0)))) / Decimal('100')
                pending_product['total_discount'] = total_discount
                quantity = Decimal(str(pending_product['quantity']))
                if quantity > 0:
                    pending_product['unit_discount'] = total_discount / quantity
                pending_product['unit_after_discount'] = pending_product['unit_price_before'] - pending_product['unit_discount']
                pending_product['total_after_discount'] = pending_product['total_price_before'] - pending_product['total_discount']
    if pending_product:
        for k in ['unit_price_before', 'total_price_before', 'unit_discount', 'total_discount', 'unit_after_discount', 'total_after_discount']:
            pending_product[k] = float(Decimal(str(pending_product[k])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        products.append(pending_product)
    receipt['products'] = products
    return receipt

def main():
    logger.info("Starting receipt parsing process.")
    
    try:
        create_tables()
    except Exception as e:
        logger.error(f"Failed to create database tables. Exiting. Error: {e}")
        return
    
    files_to_process = list(TOCHECK_FOLDER.glob("*.json"))
    if not files_to_process:
        logger.info(f"No JSON files found in {TOCHECK_FOLDER} to process.")
        return

    processed_count = 0
    error_count = 0
    
    for file_path in files_to_process:
        try:
            logger.info(f"Processing file: {file_path.name}")
            result = process_receipt_file(file_path)
            if result is not None:
                processed_count += 1
        except Exception as e:
            error_count += 1
            logger.error(f"Failed to process file {file_path.name}: {e}")
            logger.debug(traceback.format_exc())
    
    logger.info(f"Receipt parsing process finished. Processed: {processed_count}, Errors: {error_count}")
    
    # Note: Cache saving is now handled by the database, no need for separate cache file

if __name__ == "__main__":
    main()