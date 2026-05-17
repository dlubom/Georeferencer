# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Zasady commitów

- **Nie dodawaj** `Co-Authored-By` ani żadnych informacji o Codex w commitach

## Opis projektu

Georeferencjer Planów Jaskiń — platforma do georeferencji zeskanowanych planów jaskiń tatrzańskich. Etap crowdsourcingowy zakończony: 4048 zgłoszeń od 89 użytkowników, 801 jaskiń z 5+ niezależnymi kliknięciami. Obecnie projekt skupia się na pipeline generacji GeoTIFF i ręcznej korekcie wyników.

**Język interfejsu:** polski (UI, README, komunikaty)

## Architektura

### Frontend (`index.html`) [ZAKOŃCZONY]
Jednoplikowa aplikacja vanilla JavaScript z HTML5 Canvas — etap crowdsourcingowy zakończony, GitHub Pages wyłączony.
- Przeglądarka obrazów oparta na Canvas z zoom/pan do precyzyjnego zaznaczania punktów
- Proj4js (EPSG:2180) do transformacji współrzędnych
- UTIF.js do obsługi obrazów TIFF

### Backend (`Code.gs`) [ZAKOŃCZONY]
Google Apps Script wdrożony jako Web App — etap crowdsourcingowy zakończony.

### Import danych (`ImportCaves.gs`)
Import danych jaskiń tatrzańskich z GitHub JSON do arkusza CAVES. Kluczowe funkcje: `importTatryCavesFromURL()`, `setupSheets()`, `showCaveStats()`.

### Analiza (`analysis.ipynb`)
Notebook Python/Jupyter do analizy statystycznej zgłoszeń. Używa pandas, numpy, matplotlib, seaborn, pyarrow. Dane z katalogu `parquet/`.

### Pipeline GeoTIFF (`pipeline/`)
Skrypty Python do generacji georeferencjonowanych TIFFów z danych crowdsourcingowych.

- `01_extract_yaml.py` — jednorazowa ekstrakcja: parquet → edytowalne YAML-e (`data/caves/{dir_id}/meta.yaml`) + kopiowanie obrazów ze scrapera. Agregacja: mediana pikseli otworu, mediana pixels_per_meter (z IQR outlier removal), mediana kąta północy.
- `02_generate_geotiff.py` — powtarzalny: YAML → render Jinja `coordinates.lat/lon` z `best-measurements.csv` → .tfw (World File) + GeoTIFF (EPSG:2180, kompresja CCITTFAX4). Weryfikuje wymiary obrazu vs YAML. CLI: `--cave ID | --all | --changed | --force`.
- `gps_kataster_coordinates.py` — obsługa `best-measurements.csv` / GeoJSON. Runtime release używa tylko jawnego `coordinates.gps_kataster_object_id`; resolver po `pig_id`/`nr_inwent` jest przeznaczony do jednorazowej migracji i raportu mapowania.
- `03_report.py` — raporty QA: summary.csv, flagged.csv, missing.csv w `data/caves/_reports/`.
- `04_find_missing.py` — porównanie rejestru PIG (JSONL) z istniejącymi jaskiniami; lista brakujących z planami, posortowana po długości.
- `05_add_cave.py` — ręczne dodanie brakującej jaskini: tworzy katalog, kopiuje obrazy ze scrapera, generuje meta.yaml. Dane georeferencji (otwór, skala, kąt północy) z konsoli Georeferencer UI. Instrukcja: [`pipeline/MANUAL_ADD.md`](pipeline/MANUAL_ADD.md).

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
  meta.yaml           # Edytowalne dane georeferencji; lat/lon to Jinja template z gps-kataster object_id
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
# Pipeline GeoTIFF
python -m venv .venv && source .venv/bin/activate
pip install -r pipeline/requirements.txt
brew install gdal                                    # macOS

python pipeline/01_extract_yaml.py                   # Jednorazowo: parquet → YAML + obrazy
python pipeline/02_generate_geotiff.py --cave 001131 \
    --gps-kataster-best-measurements ../gps-kataster-obiektow-tatr/build/exports/best-measurements.csv \
    --gps-kataster-strict                         # Jedna jaskinia z lat/lon z gps-kataster
python pipeline/02_generate_geotiff.py --all \
    --gps-kataster-best-measurements ../gps-kataster-obiektow-tatr/build/exports/best-measurements.csv \
    --gps-kataster-strict                         # Wszystkie
python pipeline/02_generate_geotiff.py --changed \
    --gps-kataster-best-measurements ../gps-kataster-obiektow-tatr/build/exports/best-measurements.csv \
    --gps-kataster-strict                         # Tylko zmienione meta.yaml
python pipeline/03_report.py                         # Raporty QA
python pipeline/04_find_missing.py                   # Lista brakujących jaskiń
python pipeline/05_add_cave.py --cave 001197 \       # Ręczne dodanie jaskini
    --entrance-x 26131.87 --entrance-y 7996.18 \
    --pixels-per-meter 23.6549 --north-angle 0.0

# Uruchomienie notebooka analizy
jupyter notebook analysis.ipynb
```

## Kluczowa konfiguracja

- Obrazy źródłowe: `../Polish-Cave-Data-Scraper/` (`caves_mono/`, `caves_upscaled/`, `caves/`)
- Aktualne współrzędne otworów: release [`dlubom/gps-kataster-obiektow-tatr`](https://github.com/dlubom/gps-kataster-obiektow-tatr), artefakt `best-measurements.csv`
- Rejestr PIG (JSONL, źródło historyczne/manualne): `../Jaskiniowy-Kataster-Tatr-Zachodnich/doc/jaskinie_polski_pig_dump.jsonl`
- Georeferencer UI (do ręcznych kliknięć): `../Polish-Cave-Data-Scraper/index.html` — loguje dane do meta.yaml w konsoli
- <!-- GitHub Pages wyłączony — etap crowdsourcingowy zakończony -->
- <!-- Backend Apps Script — etap crowdsourcingowy zakończony -->

## Schemat danych

- **ID:** UUID dla użytkowników, prefiks `A_*` dla przydziałów, `SUB_*` dla zgłoszeń
- **Zgłoszenia:** ~48 pól, w tym parametry World File (A-F)
- **Pliki parquet:** `CAVES.parquet`, `USERS.parquet`, `ASSIGNMENTS.parquet`, `SUBMISSIONS.parquet`
- **YAML:** `data/caves/{dir_id}/meta.yaml` — sekcje: cave, image, coordinates, entrance, scale, north, declination_deg, computed, quality
- **Raporty:** `data/caves/_reports/summary.csv`, `flagged.csv`, `missing.csv`
