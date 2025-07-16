# Pomysły na przyszłość: Skalowalność i obsługa wielu użytkowników

## Plan plików i koncepcji dla wersji 3+ użytkowników

### Backend
- `app/multiuser/` – katalog na eksperymentalne funkcje wieloosobowe
  - `logic.py` – logika podziału udziałów dla dowolnej liczby użytkowników
  - `validators.py` – walidacja sumy udziałów, automatyczne dopełnianie
  - `api_multiuser.py` – alternatywne endpointy dla trybu wieloosobowego
- `app/config_multiuser.py` – opcjonalna konfiguracja trybu wieloosobowego

### Frontend/CLI
- `app/menu_multiuser/` – alternatywne menu CLI dla wielu użytkowników
  - `handlers.py` – obsługa dynamicznych udziałów, generowanie pól
  - `ui_helpers.py` – szybkie akcje (podziel równo, wyzeruj, itp.)
- `web_multiuser/` – (jeśli powstanie web UI) komponenty do dynamicznego podziału udziałów

### Testy
- `tests/test_multiuser_logic.py` – testy logiki podziału udziałów
- `tests/test_multiuser_api.py` – testy endpointów

### Inne pomysły
- Tryb konfiguracyjny: przełączanie między 2-osobowym a wieloosobowym UI
- Szybkie akcje w UI: podziel równo, wyzeruj, automatyczne dopełnianie
- Kolorowe podpowiedzi i walidacja sumy udziałów
- Historia zmian udziałów dla produktów
- Architektura pod wielu użytkowników wymaga osobnych baz i dynamicznego routingu połączeń.

---

**Kolejne pomysły dopisuj poniżej:**

- 