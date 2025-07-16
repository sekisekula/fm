import json
import logging
import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
from html import unescape
from bs4 import BeautifulSoup

# Configure logging for this module
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def json_serial(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

def safe_decimal(value, default=Decimal('0.00')):
    try:
        if value is None:
            return default
        if isinstance(value, (float, int)):
            return Decimal(str(round(value, 2)))
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default

def remove_polish_diacritics(text):
    if text is None:
        return None
    replacements = {
        'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n',
        'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z',
        'Ą': 'A', 'Ć': 'C', 'Ę': 'E', 'Ł': 'L', 'Ń': 'N',
        'Ó': 'O', 'Ś': 'S', 'Ź': 'Z', 'Ż': 'Z'
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text

# Cache dla często używanych danych
cache = {
    'stores': {},  # {store_id: {name: ..., city: ...}}
    'products': {},  # {product_id: {name: ..., store_id: ...}}
    'users': {},  # {user_id: {name: ...}}
    'payments': {},  # {payment_name: user_id}
    'last_update': datetime.datetime.now()
}

CACHE_TIMEOUT = datetime.timedelta(minutes=5)  # Cache wygasa po 5 minutach

async def update_cache():
    """Aktualizacja cache'ów z bazy danych."""
    conn, cur = get_connection_and_cursor()
    try:
        # Aktualizacja sklepów
        cur.execute("""
            SELECT store_id, store_name, store_city 
            FROM stores
        """)
        cache['stores'] = {row[0]: {'name': row[1], 'city': row[2]} for row in cur.fetchall()}
        
        # Aktualizacja produktów
        cur.execute("""
            SELECT product_id, product_name, store_id 
            FROM products
        """)
        cache['products'] = {row[0]: {'name': row[1], 'store_id': row[2]} for row in cur.fetchall()}
        
        # Aktualizacja użytkowników
        cur.execute("""
            SELECT user_id, user_name 
            FROM users
        """)
        cache['users'] = {row[0]: {'name': row[1]} for row in cur.fetchall()}
        
        # Aktualizacja metod płatności
        cur.execute("""
            SELECT payment_name, user_id 
            FROM user_payments
        """)
        cache['payments'] = {row[0]: row[1] for row in cur.fetchall()}
        
        cache['last_update'] = datetime.datetime.now()
        
    finally:
        close_connection(conn, cur)

async def get_store_cache():
    """Pobiera cache sklepów, aktualizując go jeśli wygasł."""
    if datetime.datetime.now() - cache['last_update'] > CACHE_TIMEOUT:
        await update_cache()
    return cache['stores']

async def get_product_cache():
    """Pobiera cache produktów, aktualizując go jeśli wygasł."""
    if datetime.datetime.now() - cache['last_update'] > CACHE_TIMEOUT:
        await update_cache()
    return cache['products']

async def get_user_cache():
    """Pobiera cache użytkowników, aktualizując go jeśli wygasł."""
    if datetime.datetime.now() - cache['last_update'] > CACHE_TIMEOUT:
        await update_cache()
    return cache['users']

async def get_payment_cache():
    """Pobiera cache metod płatności, aktualizując go jeśli wygasł."""
    if datetime.datetime.now() - cache['last_update'] > CACHE_TIMEOUT:
        await update_cache()
    return cache['payments']

def parse_receipt(data: dict) -> dict:
    """
    Parses raw receipt data (JSON) and extracts structured information.
    """
    result = {
        "receipt": {
            "store_name": "Unknown store",
            "store_address": "No address",
            "postal_code": "No postal code",
            "store_city": "No city",
            "nip": "No NIP",
            "receipt_number": None,
            "date": None,
            "time": None,
            "final_price": Decimal('0.00'),
            "total_discounts": Decimal('0.00'),
            "payment_name": None,
            "currency": None
        },
        "products": [],
    }

    body = data.get("body", [])
    header = data.get("header", [])

    # --- Parse Header for Store Info ---
    # (logika parsowania nagłówka pozostaje bez zmian)
    for item in header:
        if "headerText" in item:
            html = item["headerText"].get("headerTextLines", "")
            html = unescape(html)
            soup = BeautifulSoup(html, 'html.parser')
            lines = soup.find_all('div')

            address_lines = []
            for line in lines:
                line_text = line.text.strip()
                if "JERONIMO MARTINS" in line_text.upper():
                    break
                if "BIEDRONKA" in line_text.upper():
                    result["receipt"]["store_name"] = "BIEDRONKA"
                if re.search(r"\d{2}-\d{3}.*UL\.", line_text.upper()):
                    address_lines.append(line_text)

            if address_lines:
                address = address_lines[0]
                postal_code_match = re.search(r"(\d{2}-\d{3})", address)
                if postal_code_match:
                    result["receipt"]["postal_code"] = postal_code_match.group(1)

                city_match = re.search(r'\d{2}-\d{3}\s+([A-ZĄĆĘŁŃÓŚŹŻ\s]+)\s+UL\.', address, re.IGNORECASE)
                if city_match:
                    city_raw = city_match.group(1).strip()
                    result["receipt"]["store_city"] = remove_polish_diacritics(city_raw).upper()

                street_match = re.search(r"\d{2}-\d{3}\s+\S+\s+UL\.\s*(.+)", address, re.IGNORECASE)
                if street_match:
                    street_raw = street_match.group(1).replace("&nbsp;", " ").strip()
                    result["receipt"]["store_address"] = remove_polish_diacritics(street_raw).capitalize()

        elif "headerData" in item:
            nip = item["headerData"].get("tin")
            if nip:
                result["receipt"]["nip"] = nip
            
            date_str = item["headerData"].get("date")
            if date_str:
                try:
                    dt_obj = datetime.datetime.fromisoformat(date_str.rstrip("Z"))
                    result["receipt"]["date"] = dt_obj.date().isoformat()
                    result["receipt"]["time"] = dt_obj.time().isoformat()
                except ValueError as e:
                    logger.warning(f"Error parsing date/time from headerData: {e} for {date_str}")
            
            doc_number = item["headerData"].get("docNumber")
            if doc_number and not result["receipt"]["receipt_number"]:
                result["receipt"]["receipt_number"] = str(doc_number)

    # --- Parse Body for Products, Totals, Payments ---
    products = []
    last_sellline = None
    
    for item in body:
        if "addLine" in item:
            # (logika parsowania addLine bez zmian)
            html_text = item["addLine"]["data"]
            html_text = unescape(html_text)
            match_receipt_number = re.search(r'Numer:<span.*?>(.*?)<\/span>', html_text)
            if match_receipt_number:
                result["receipt"]["receipt_number"] = match_receipt_number.group(1).strip()
            
            # We'll get discounts from discountSummary instead of parsing HTML

        elif "sellLine" in item:
            # (logika parsowania sellLine bez zmian)
            s = item["sellLine"]
            if s.get("isStorno"):
                continue

            name_with_vat = s.get("name", "").rstrip()
            parts = name_with_vat.rsplit(" ", 1)
            product_name = name_with_vat
            tax_type = s.get("vatId", "")

            if len(parts) == 2 and len(parts[1]) == 1 and parts[1].isalpha():
                product_name, tax_type = parts[0].rstrip(), parts[1]

            # Konwersja quantity z przecinka na kropkę
            quantity_str = s.get("quantity", "1").replace(',', '.')
            quantity = safe_decimal(quantity_str)
            
            product = {
                "product_name": product_name,
                "tax_type": tax_type,
                "unit_price_before": safe_decimal(s.get("price", 0)) / Decimal('100'),
                "quantity": quantity,
                "total_price_before": safe_decimal(s.get("total", 0)) / Decimal('100'),
                "unit_discount": Decimal('0.00'),
                "total_discount": Decimal('0.00'),
                "unit_after_discount": Decimal('0.00'),
                "total_after_discount": Decimal('0.00')
            }
            products.append(product)
            last_sellline = product

        elif "discountLine" in item and last_sellline is not None:
            # (logika parsowania discountLine bez zmian)
            d = item["discountLine"]
            if d.get("isDiscount") and not d.get("isStorno"):
                discount_value = safe_decimal(d.get("value", 0)) / Decimal('100')
                last_sellline["total_discount"] = discount_value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                if last_sellline["quantity"] > 0:
                    last_sellline["unit_discount"] = (discount_value / safe_decimal(last_sellline["quantity"])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                last_sellline["unit_after_discount"] = (last_sellline["unit_price_before"] - last_sellline["unit_discount"]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                last_sellline["total_after_discount"] = (last_sellline["total_price_before"] - last_sellline["total_discount"]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        elif "sumInCurrency" in item:
            # (logika parsowania sumInCurrency bez zmian)
            final_price = safe_decimal(item["sumInCurrency"].get("fiscalTotal", 0)) / Decimal('100')
            result["receipt"]["final_price"] = final_price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            currency = item["sumInCurrency"].get("currency")
            if currency:
                result["receipt"]["currency"] = currency

        elif "discountSummary" in item:
            discounts = item["discountSummary"].get("discounts")
            if discounts is not None:
                # The discount is in grosze (e.g., 3966 means 39.66 PLN)
                discount_amount = safe_decimal(discounts) / Decimal('100')
                # Add to existing discount if any
                result["receipt"]["total_discounts"] = result["receipt"].get("total_discounts", Decimal('0.00')) + discount_amount

        elif "payment" in item:
            payment = item.get("payment", {})
            payment_name = payment.get("name")
            if payment_name:
                result["receipt"]["payment_name"] = payment_name.strip()
                result["receipt"]["currency"] = payment.get("currency", "PLN")
                break

        elif "fiscalFooter" in item:
            # (logika parsowania fiscalFooter bez zmian)
            footer = item["fiscalFooter"]
            issue_date_str = footer.get("date")
            if issue_date_str:
                try:
                    issue_date = datetime.datetime.fromisoformat(issue_date_str.rstrip("Z"))
                    if not result["receipt"]["date"] or (issue_date.date() and datetime.date.fromisoformat(result["receipt"]["date"]) != issue_date.date()):
                        result["receipt"]["date"] = issue_date.date().isoformat()
                        result["receipt"]["time"] = issue_date.time().isoformat()
                except ValueError as e:
                    logger.error(f"Date and time parsing error from fiscalFooter: {e}, issue_date_str: {issue_date_str}")
                    result["receipt"]["date"] = None
                    result["receipt"]["time"] = None

    # (logika obliczeń końcowych dla produktów bez zmian)
    for product in products:
        if product["total_after_discount"] == Decimal('0.00') and product["total_price_before"] != Decimal('0.00'):
            product["total_after_discount"] = (product["total_price_before"] - product["total_discount"]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if product["unit_after_discount"] == Decimal('0.00') and product["unit_price_before"] != Decimal('0.00'):
            product["unit_after_discount"] = (product["unit_price_before"] - product["unit_discount"]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    result["products"] = products

    return result