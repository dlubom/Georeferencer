# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Opis projektu

Georeferencjer Planów Jaskiń — platforma crowdsourcingowa do georeferencji zeskanowanych planów jaskiń tatrzańskich. Użytkownicy zaznaczają otwory jaskiń, skalę, kierunek północy i przecięcia siatki. Każda jaskinia wymaga k=5 niezależnych zgłoszeń w celu walidacji statystycznej.

**Język interfejsu:** polski (UI, README, komunikaty)

## Architektura

### Frontend (`index.html`)
Jednoplikowa aplikacja vanilla JavaScript z HTML5 Canvas. Brak procesu budowania, brak frameworka, brak bundlera.
- Przeglądarka obrazów oparta na Canvas z zoom/pan do precyzyjnego zaznaczania punktów
- Proj4js (EPSG:2180) do transformacji współrzędnych
- UTIF.js do obsługi obrazów TIFF
- Persystencja sesji przez LocalStorage (klucze z prefiksem `crowdsource_*`)
- Fallback: pobieranie JSON gdy wysyłka przez API się nie powiedzie

### Backend (`Code.gs`)
Google Apps Script wdrożony jako Web App. Baza danych w arkuszu z 4 zakładkami: CAVES, USERS, ASSIGNMENTS, SUBMISSIONS.
- `doPost()` jako punkt wejścia routuje do handlerów: `handlePing`, `handleAssign`, `handleSubmit`, `handleSkip`, `handleProgress`
- LockService dla bezpieczeństwa transakcji
- Użytkownicy identyfikowani przez UUID, wygasanie przydziałów po 24h
- Przydział jaskiń z load balancingiem (najmniej zgłoszeń = priorytet)

### Import danych (`ImportCaves.gs`)
Import danych jaskiń tatrzańskich z GitHub JSON do arkusza CAVES. Kluczowe funkcje: `importTatryCavesFromURL()`, `setupSheets()`, `showCaveStats()`.

### Analiza (`analysis.ipynb`)
Notebook Python/Jupyter do analizy statystycznej zgłoszeń. Używa pandas, numpy, matplotlib, seaborn, pyarrow. Dane z katalogu `parquet/`.

## Komendy deweloperskie

```bash
# Lokalny serwer frontendowy
python -m http.server 8000
# Następnie otwórz http://localhost:8000/index.html

# Uruchomienie notebooka analizy
jupyter notebook analysis.ipynb

# Backend: wdrożenie przez edytor Google Apps Script (Deploy → New deployment → Web app)
# Test backendu: uruchom funkcję testApi() w edytorze Apps Script
# Inicjalizacja bazy: uruchom setupSheets() w edytorze Apps Script
```

## Kluczowa konfiguracja

- Endpoint API: zahardkodowany w obiekcie `CROWDSOURCE_CONFIG` w `index.html` (~linia 803)
- Wdrożenie frontendu: GitHub Pages pod `https://dlubom.github.io/Georeferencer/index.html`
- Wdrożenie backendu: Google Apps Script Web App (Execute as: Me, Access: Anyone)

## Protokół API

POST JSON na endpoint Apps Script z `{action, user_id, ...}`.
- Akcje: `ping`, `assign`, `submit`, `skip`, `progress`
- Sukces: `{ok: true, ...}`
- Błąd: `{ok: false, error: 'kod', message: 'opis po polsku'}`

## Schemat danych

- **ID:** UUID dla użytkowników, prefiks `A_*` dla przydziałów, `SUB_*` dla zgłoszeń
- **Zgłoszenia:** ~48 pól, w tym parametry World File (A-F)
- **Pliki parquet:** `CAVES.parquet`, `USERS.parquet`, `ASSIGNMENTS.parquet`, `SUBMISSIONS.parquet`
