# Core Files Overview

## app/parser.py
- **process_receipt_file**: Main entry for processing a receipt JSON file. Handles reading, parsing, and inserting receipt and product data into the database.
- **parse_receipt**: Parses raw receipt JSON, extracts header, store, payment, and product information. Handles product-discount matching logic.

## app/db/database.py
- **insert_products_bulk**: Inserts multiple products for a receipt into the database.
- **insert_product**: Inserts a single product into the database.
- **insert_receipt**: Inserts a receipt record into the database.
- **check_duplicate_receipt**: Checks for duplicate receipts before insertion.

## app/menu/main.py
- **FinanceManagerMenu**: Main menu class for the CLI application. Handles user interaction and menu navigation.

## app/menu/handlers.py
- **MenuHandlers**: Contains handler functions for each menu action, including viewing, parsing, and processing receipts and expenses.

## app/menu/models.py
- **DatabaseManager**: Provides database access methods for receipts, expenses, and related queries used by the menu handlers.

## app/utils.py
- **parse_receipt**: (Legacy/alternative) Parses receipt data, used in some contexts for extracting structured information.

---

This file is maintained by the AI assistant. Update as new core files or major functionalities are added. 