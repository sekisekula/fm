import logging
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import List
import psycopg2
from app.utils import get_connection_and_cursor, close_connection

logger = logging.getLogger(__name__)

BACKUP_DIR = Path(__file__).parent.parent / 'backups'
BACKUP_DIR.mkdir(exist_ok=True)

BACKUP_INTERVAL = 24  # godziny
MAX_BACKUPS = 7  # maksymalna liczba kopii zapasowych

class BackupSystem:
    def __init__(self):
        self.last_backup: datetime = datetime.now()
        self.backup_dir = BACKUP_DIR
        
        # Sprawdź czy katalog istnieje
        if not self.backup_dir.exists():
            self.backup_dir.mkdir(parents=True, exist_ok=True)

    async def create_backup(self) -> str:
        """Tworzy kopię zapasową bazy danych."""
        if (datetime.now() - self.last_backup).total_seconds() < BACKUP_INTERVAL * 3600:
            return "Backup już został wykonany w tym okresie"

        conn, cur = get_connection_and_cursor()
        try:
            # Pobierz nazwę bazy danych
            cur.execute("SELECT current_database()")
            db_name = cur.fetchone()[0]
            
            # Utwórz nazwę pliku backupu
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = self.backup_dir / f'backup_{db_name}_{timestamp}.sql'
            
            # Użyj pg_dump do stworzenia backupu
            os.system(f'pg_dump -h {os.getenv("DB_HOST")} -p {os.getenv("DB_PORT")} -U {os.getenv("DB_USER")} {db_name} > {backup_file}')
            
            # Sprawdź czy backup został utworzony
            if not backup_file.exists():
                raise Exception("Nie udało się utworzyć kopii zapasowej")
            
            # Przywróć uprawnienia
            os.chmod(backup_file, 0o644)
            
            # Usuń najstarsze backupy, jeśli przekroczono limit
            backups = sorted(self.backup_dir.glob('backup_*.sql'), key=os.path.getctime)
            if len(backups) > MAX_BACKUPS:
                for old_backup in backups[:-MAX_BACKUPS]:
                    os.remove(old_backup)
            
            self.last_backup = datetime.now()
            return f"Backup utworzony pomyślnie: {backup_file.name}"
            
        except Exception as e:
            logger.error(f"Błąd podczas tworzenia backupu: {e}")
            raise
        finally:
            close_connection(conn, cur)

    async def restore_backup(self, backup_file: str) -> str:
        """Przywraca bazę danych z kopii zapasowej."""
        conn, cur = get_connection_and_cursor()
        try:
            # Pobierz nazwę bazy danych
            cur.execute("SELECT current_database()")
            db_name = cur.fetchone()[0]
            
            # Przywróć bazę danych
            os.system(f'psql -h {os.getenv("DB_HOST")} -p {os.getenv("DB_PORT")} -U {os.getenv("DB_USER")} {db_name} < {backup_file}')
            
            return f"Baza danych przywrócona z kopii zapasowej: {backup_file}"
            
        except Exception as e:
            logger.error(f"Błąd podczas przywracania backupu: {e}")
            raise
        finally:
            close_connection(conn, cur)

    async def list_backups(self) -> List[str]:
        """Zwraca listę dostępnych kopii zapasowych."""
        return sorted([str(f.name) for f in self.backup_dir.glob('backup_*.sql')], reverse=True)

# Singleton instance
backup_system = BackupSystem()
