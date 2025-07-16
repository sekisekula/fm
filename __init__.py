"""
Finance Manager - Main Package Initialization
"""
import sys
from pathlib import Path

# Dodaj katalog główny projektu do ścieżki Pythona
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root)) 