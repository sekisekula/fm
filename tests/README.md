# Testy automatyczne – ochrona przed duplikatami

## Jak uruchomić testy?

1. **Zainstaluj pytest (jeśli nie masz):**
   
   ```bash
   pip install pytest
   ```

2. **Uruchom testy:**
   
   W katalogu głównym projektu wpisz:
   
   ```bash
   pytest
   ```
   lub (jeśli chcesz uruchomić tylko testy z katalogu `tests/`):
   ```bash
   pytest tests/
   ```

3. **Wynik zobaczysz w terminalu.**

---

## Jak to działa?
- Testy korzystają z tymczasowej bazy SQLite (plik tworzy się i usuwa automatycznie).
- Twoje dane produkcyjne są bezpieczne – testy nie dotykają Twojej bazy!
- Testy sprawdzają, czy system poprawnie blokuje duplikaty (paragony, sklepy, metody płatności, udziały, stałe udziały).

---

## Wymagania
- Python 3.8+
- pytest
- SQLAlchemy

---

**Jeśli chcesz dodać własne testy, wzoruj się na pliku `test_duplicates.py`.** 