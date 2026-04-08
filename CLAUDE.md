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

### Pipeline GeoTIFF (`pipeline/`)
Skrypty Python do generacji georeferencjonowanych TIFFów z danych crowdsourcingowych.

- `01_extract_yaml.py` — jednorazowa ekstrakcja: parquet → edytowalne YAML-e (`data/caves/{dir_id}/meta.yaml`) + kopiowanie obrazów ze scrapera. Agregacja: mediana pikseli otworu, mediana pixels_per_meter (z IQR outlier removal), mediana kąta północy.
- `02_generate_geotiff.py` — powtarzalny: YAML → .tfw (World File) + GeoTIFF (EPSG:2180, kompresja CCITTFAX4). Weryfikuje wymiary obrazu vs YAML. CLI: `--cave ID | --all | --changed | --force`.
- `03_report.py` — raporty QA: summary.csv, flagged.csv, missing.csv w `data/caves/_reports/`.

Matematyka World File (A-F) replikuje `index.html:2277-2370`:
```
world_x, world_y = transform(lon, lat)  # WGS84 → EPSG:2180
mpp = 1 / pixels_per_meter
convergence = (19.0 - lon) * sin(radians(lat))
total_deg = north_angle + declination + convergence
rot = radians(total_deg)
A = mpp * cos(rot),  D = mpp * sin(rot)
B = mpp * sin(rot),  E = -mpp * cos(rot)
C = world_x - (A * entrance_x + B * entrance_y)
F = world_y - (D * entrance_x + E * entrance_y)
```

### Dane (`data/caves/`)
801 jaskiń z 5+ niezależnymi zgłoszeniami. Struktura per jaskinia:
```
data/caves/{dir_id}/
  meta.yaml           # Edytowalne dane georeferencji
  image.tif           # Mono TIFF 1-bit (2x upscaled, z caves_mono)
  image_upscaled.jpg  # JPG upscaled waifu2x
  image_original.jpg  # Oryginalny JPG z CBDG
  image.tfw           # World File (generowany przez 02_)
  image_georef.tif    # GeoTIFF (generowany, w .gitignore)
```

**Ważne:** Kliki zostały wykonane na obrazach mono (rozdzielczość 2x upscaled). Wymiary w YAML muszą odpowiadać image.tif. Zmiana obrazu wymaga nowych kliknięć.

### CI/CD (`.github/workflows/`)
- `generate-geotiff.yml` — na push do main gdy zmieni się `meta.yaml` → regeneruje .tfw + GeoTIFF → commit `[skip ci]`
- `release-geotiff.yml` — na tag `v*` → generuje wszystkie GeoTIFF-y → tar.gz jako Release asset

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

# Pipeline GeoTIFF
python -m venv .venv && source .venv/bin/activate
pip install -r pipeline/requirements.txt
brew install gdal                                    # macOS

python pipeline/01_extract_yaml.py                   # Jednorazowo: parquet → YAML + obrazy
python pipeline/02_generate_geotiff.py --cave 001131 # Jedna jaskinia
python pipeline/02_generate_geotiff.py --all         # Wszystkie
python pipeline/02_generate_geotiff.py --changed     # Tylko zmienione meta.yaml
python pipeline/03_report.py                         # Raporty QA
```

## Kluczowa konfiguracja

- Endpoint API: zahardkodowany w obiekcie `CROWDSOURCE_CONFIG` w `index.html` (~linia 803)
- Wdrożenie frontendu: GitHub Pages pod `https://dlubom.github.io/Georeferencer/index.html`
- Wdrożenie backendu: Google Apps Script Web App (Execute as: Me, Access: Anyone)
- Obrazy źródłowe: `../Polish-Cave-Data-Scraper/` (`caves_mono/`, `caves_upscaled/`, `caves/`)

## Protokół API

POST JSON na endpoint Apps Script z `{action, user_id, ...}`.
- Akcje: `ping`, `assign`, `submit`, `skip`, `progress`
- Sukces: `{ok: true, ...}`
- Błąd: `{ok: false, error: 'kod', message: 'opis po polsku'}`

## Schemat danych

- **ID:** UUID dla użytkowników, prefiks `A_*` dla przydziałów, `SUB_*` dla zgłoszeń
- **Zgłoszenia:** ~48 pól, w tym parametry World File (A-F)
- **Pliki parquet:** `CAVES.parquet`, `USERS.parquet`, `ASSIGNMENTS.parquet`, `SUBMISSIONS.parquet`
- **YAML:** `data/caves/{dir_id}/meta.yaml` — sekcje: cave, image, coordinates, entrance, scale, north, declination_deg, computed, quality
- **Raporty:** `data/caves/_reports/summary.csv`, `flagged.csv`, `missing.csv`
