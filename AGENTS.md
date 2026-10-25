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
- `crowdsourcing.py` / `migrate_crowdsourcing.py` — bieżąca warstwa agregacji T07: jawny rejestr TEST, liczniki komponentów/użytkowników i selektywna migracja z ochroną ręcznych korekt. Czytaj [`docs/AGGREGATION.md`](docs/AGGREGATION.md); nie uruchamiaj pełnej ekstrakcji do aktualizacji istniejącego katalogu. Historyczne raporty T05/T06 odtwarzaj na ich wejściach, wpływ T07 jest osobnym raportem.
- `02_generate_geotiff.py` — YAML i przypięty CSV → osobny przebieg TFW/GeoTIFF/computed + manifest, domyślnie `build/geotiff`. `--all`/`--changed` budują pełny katalog z cache według treści; `--cave ID` tworzy podzbiór, `--force` regeneruje. Przed zmianą selekcji/cache/pakowania przeczytaj [`docs/GENERATION_OUTPUT.md`](docs/GENERATION_OUTPUT.md). Standardowa generacja nie zapisuje do źródeł.
- `gps_kataster_coordinates.py` — obsługa `best-measurements.csv` / GeoJSON. Runtime release używa tylko jawnego `coordinates.gps_kataster_object_id`; resolver po `pig_id`/`nr_inwent` jest przeznaczony do jednorazowej migracji i raportu mapowania.
- `coordinate_source.py` — weryfikacja przypiętego release i SHA-256, odzyskanie snapshotu oraz raport wpływu aktualizacji. Build używa `data/coordinate-source/source.json`, bez automatycznego `latest`.
- `catalogue_baseline.py` — odczyt historycznego punktu odniesienia 814 planów i osobne przeliczenie audytowe bez mutowania katalogu. Przy odtwarzaniu buildu, aktualizacji CSV lub użyciu historii w T05 przeczytaj [`docs/COORDINATE_SOURCE.md`](docs/COORDINATE_SOURCE.md). T05 bierze orientację z zapisanych historycznych TFW.
- `03_report.py` — pełne QA T09, domyślnie `build/qa`; z `--run-dir` kontroluje dokładny komplet manifestu. `package_release.py` wymaga tego odbioru dla tag/manual i pakuje deklarowane pliki. Raporty i ZIP zapisuj poza przebiegiem.
- `04_find_missing.py` — porównanie rejestru PIG (JSONL) z istniejącymi jaskiniami; lista brakujących z planami, posortowana po długości.
- `05_add_cave.py` — bezpieczne dodanie jednego planu T08. Przed dodaniem lub zmianą tego narzędzia przeczytaj [`pipeline/MANUAL_ADD.md`](pipeline/MANUAL_ADD.md): rozdziela ID jaskini, grafiki, katalogu i otworu; wymaga hasha obrazu, pochodzenia parametrów i jawnej decyzji orientacji. Lokalny `image-identity.json` jest publikowany razem z planem po T03/T04. Podgląd niczego nie zapisuje; ponowienie nie nadpisuje.

### Orientacja T05 i geometria T06

Przeczytaj [`docs/ORIENTATION.md`](docs/ORIENTATION.md). `pipeline/orientation.py`
odróżnia rodzaj północy i pochodzenie kąta (także mierzone/przyjęte 0°).
Historyczna nieustalona północ zachowuje kąt `atan2(D, A)` wyłącznie z
`plans[].historical_tfw` przypiętego T02. Bieżące współrzędne, skala i otwór
pozostają aktywne. Zmiana wejść orientacji wymaga jawnej decyzji z powodem.
T06 używa modeli geographic/magnetic/grid; znaki zbieżności i deklinacji
oraz narożnikowy układ kliknięć/półpiksel opisuje `docs/ORIENTATION.md`.
Dodanie modelu zachowuje status unverified i wymogi źródeł/decyzji T05.
Nowy unknown T08 nie ma TFW T02: wymaga osobnego przyjętego obrotu
`assumed_grid` z EPSG:2180, konwencją i powodem; pozostaje unknown/unverified.
Raport wpływu T06 jest w `docs/reports/t06-geometry-impact.json`;
odtworzenie opisuje `docs/plans/2026-10-25-t06-odbior.md`.

Migrację bieżących YAML-i opisuje `data/migrations/t05-north.json`.
Oryginalne YAML-e i kod QA są w `data/history/t02-inputs.zip`; kontrola historii
sprawdza oryginalne hashe T02 i zamrożony kod oddzielnie od testów bieżących.
Nigdy nie odświeżaj odniesienia ani jego hashy w odpowiedzi na błąd kontroli.

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
- `check.yml` — każdy PR i push do `main` → `./scripts/check`; wymagana kontrola `Kontrola projektu`.
- `generate-geotiff.yml` — każdy push main/PR → pełny katalog według treści i zakresu zdarzenia, QA i artefakty (14 dni), contents:read; bez commit/push bota.
- `release-geotiff.yml` — tag `v*` lub ręcznie z istniejącego tagu → pełny katalog → wspólna bramka manifestu/aktualności/T09 → ZIP. Generacja i wydanie używają przypiętego `scripts/build`; instrukcja: [ci/README.md](ci/README.md).

## Komendy deweloperskie

Przed przygotowaniem lub aktualizacją PR uruchom `./scripts/check` — tę samą kontrolę co CI, w przypiętym kontenerze Linux/Python 3.12/GDAL. Dodawaj nowe testy do `tests/`, aby były automatycznie odkrywane przez tę komendę. Do PR dołącz wynik i liczbę testów, wersje środowiska, link do CI bieżącej rewizji oraz dowód wykrycia regresji. Przy zmianie zależności, konfiguracji CI lub wymaganych checków przeczytaj [ci/README.md](ci/README.md): opisuje odtwarzanie środowiska, aktualizację locka i ochronę `main`. Próba GDAL nie potwierdza poprawności geometrii całego katalogu.

```bash
# Obowiązkowa kontrola lokalna i CI (wymaga działającego Dockera)
./scripts/check

# Pipeline GeoTIFF — referencyjne środowisko, źródła readonly
./scripts/build generate --changed
./scripts/build report --run-dir /build/geotiff/current --require-results
# Poniżej bezpośredni Python (wyniki domyślnie build/geotiff)
python -m venv .venv && source .venv/bin/activate
pip install -r pipeline/requirements.txt
brew install gdal                                    # macOS

python pipeline/coordinate_source.py copy \
    --output /tmp/georeferencer-best-measurements.csv # Zweryfikowany pin buildu
python pipeline/01_extract_yaml.py                   # Jednorazowo: parquet → YAML + obrazy
python pipeline/02_generate_geotiff.py --cave 001131 \
    --gps-kataster-best-measurements /tmp/georeferencer-best-measurements.csv \
    --gps-kataster-strict                         # Jedna jaskinia z lat/lon z gps-kataster
python pipeline/02_generate_geotiff.py --all \
    --gps-kataster-best-measurements /tmp/georeferencer-best-measurements.csv \
    --gps-kataster-strict                         # Wszystkie
python pipeline/02_generate_geotiff.py --changed \
    --gps-kataster-best-measurements /tmp/georeferencer-best-measurements.csv \
    --gps-kataster-strict                         # Tylko zmienione meta.yaml
python pipeline/03_report.py                         # Raporty QA
python pipeline/04_find_missing.py                   # Lista brakujących jaskiń
# Pełne dodanie: pipeline/MANUAL_ADD.md; poniżej wyłącznie inspekcja
python pipeline/05_add_cave.py --cave 001197 --image-id 12400 --dry-run

# Uruchomienie notebooka analizy
jupyter notebook analysis.ipynb
```

## Kluczowa konfiguracja

- Obrazy źródłowe: `../Polish-Cave-Data-Scraper/` (`caves_mono/`, `caves_upscaled/`, `caves/`)
- Współrzędne buildu: przypięty release [`dlubom/gps-kataster-obiektow-tatr v1.3.2`](https://github.com/dlubom/gps-kataster-obiektow-tatr/releases/tag/v1.3.2), artefakt `best-measurements.csv`; opis i surowy snapshot w `data/coordinate-source/`. Aktualizacja wymaga PR z raportem planów/pomiarów i wpływu zgodnie z `docs/COORDINATE_SOURCE.md`.
- Rejestr PIG (JSONL, źródło historyczne/manualne): `../Jaskiniowy-Kataster-Tatr-Zachodnich/doc/jaskinie_polski_pig_dump.jsonl`
- Georeferencer UI (do ręcznych kliknięć): `../Polish-Cave-Data-Scraper/index.html` — loguje dane do meta.yaml w konsoli
- <!-- GitHub Pages wyłączony — etap crowdsourcingowy zakończony -->
- <!-- Backend Apps Script — etap crowdsourcingowy zakończony -->

## Schemat danych

- **ID:** UUID dla użytkowników, prefiks `A_*` dla przydziałów, `SUB_*` dla zgłoszeń
- **Zgłoszenia:** ~48 pól, w tym parametry World File (A-F)
- **Pliki parquet:** `CAVES.parquet`, `USERS.parquet`, `ASSIGNMENTS.parquet`, `SUBMISSIONS.parquet`
- **YAML:** `data/caves/{dir_id}/meta.yaml` — sekcje: cave, image, coordinates, entrance, scale, north, declination_deg, computed, quality
- **Raporty:** `build/qa/{qa.json,summary.csv,flagged.csv,missing.csv}`; wydanie przez manifest w `build/geotiff/current`. Historyczne raporty pozostają w `data/history/`.
