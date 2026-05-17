# Ręczne dodawanie brakujących jaskiń

Instrukcja dodawania jaskiń, które zostały pominięte w crowdsourcingu (za mało zgłoszeń, disabled, problem z obrazem).

## Wymagania

- Projekt `Polish-Cave-Data-Scraper` w `../Polish-Cave-Data-Scraper/` (obrazy caves_mono/, caves_upscaled/, caves/)
- JSONL z rejestrem PIG: `../Jaskiniowy-Kataster-Tatr-Zachodnich/doc/jaskinie_polski_pig_dump.jsonl` (źródło opisów i obrazów)
- `best-measurements.csv` z release `dlubom/gps-kataster-obiektow-tatr` (źródło aktualnych współrzędnych otworów)
- Aktywne venv: `source .venv/bin/activate`

## 1. Lista brakujących jaskiń

```bash
python pipeline/04_find_missing.py
```

Wypisze brakujące jaskinie tatrzańskie z planami, posortowane po długości. Raport CSV: `data/caves/_reports/missing_tatry.csv`.

## 2. Podgląd jaskini

```bash
python pipeline/05_add_cave.py --cave <CAVE_ID> --dry-run
```

Pokaże dane jaskini z JSONL, ścieżkę do obrazu mono i wymiary. Przykład:

```
Jaskinia: Jaskinia Miętusia (T.D-11.01)
  Współrzędne: 49.246333, 19.898992
  Plan: image_12400_zoom_10 (graphics_id: 12400)
  Wymiary mono: 28660×16266 px
  Obraz mono: .../caves_mono/001197/image_12400_zoom_10.tif
```

## 3. Georeferencja w przeglądarce

1. Otwórz `../Polish-Cave-Data-Scraper/index.html` w przeglądarce
2. Załaduj obraz mono (.tif) z podanej ścieżki (local upload)
3. Zaznacz kolejno:
   - **Otwór wejściowy** — kliknij na symbol otworu na planie
   - **Początek skali** — kliknij początek podziałki
   - **Koniec skali** — kliknij koniec podziałki (wpisz długość w metrach)
   - **Północ (opcjonalnie)** — kliknij podstawę i grot strzałki N
4. Oblicz — w konsoli przeglądarki (F12) pojawi się zielony blok:

```
=== DANE DO META.YAML ===
cave_id: 001197
inventory_number: T.D-11.01
name: Jaskinia Miętusia
lat: 49.246333
lon: 19.898992
entrance_x: 26131.87
entrance_y: 7996.18
pixels_per_meter: 23.6549
north_angle_deg: 0.00
declination_deg: 0
```

## 4. Dodanie jaskini

```bash
python pipeline/05_add_cave.py --cave 001197 \
    --entrance-x 26131.87 --entrance-y 7996.18 \
    --pixels-per-meter 23.6549 \
    --north-angle 0.0 \
    --gps-kataster-object-id MLZ-0000
```

Skrypt:
- Tworzy katalog `data/caves/001197/`
- Kopiuje obrazy ze scrapera (image.tif, image_upscaled.jpg, image_original.jpg)
- Generuje `meta.yaml` z flagą `quality.flag: manual`

Opcjonalne parametry: `--declination <deg>`, `--image-id <id>` (gdy wiele planów).

## 5. Generacja GeoTIFF

```bash
python pipeline/02_generate_geotiff.py --cave 001197 \
    --gps-kataster-best-measurements ../gps-kataster-obiektow-tatr/build/exports/best-measurements.csv \
    --gps-kataster-strict
```

Generator renderuje Jinja placeholdery `coordinates.lat/lon` z obiektu `jaskinia_otwor` w gps-kataster, a potem generuje `image.tfw` (World File) i `image_georef.tif` (GeoTIFF EPSG:2180). Zastąp `MLZ-0000` właściwym ID otworu z `best-measurements.csv`.

Jeśli dodajesz lub korygujesz jaskinię, ustaw w `meta.yaml` właściwy identyfikator otworu:

```yaml
coordinates:
  gps_kataster_object_id: KSZ-0033
  lat: "{{ gps_kataster.objects[gps_kataster_object_id].lat }}"
  lon: "{{ gps_kataster.objects[gps_kataster_object_id].lon }}"
```

## 6. Weryfikacja

- Sprawdź wymiary: `meta.yaml` width/height muszą odpowiadać `image.tif`
- Porównaj z istniejącymi submissionami (jeśli są) w `parquet/SUBMISSIONS.parquet`
- Otwórz GeoTIFF w QGIS — otwór powinien trafić w lokalizację jaskini

## Uwagi

- **Kliki zawsze na obrazie mono** (image.tif, 2x upscaled) — wymiary w meta.yaml muszą odpowiadać temu obrazowi
- **Współrzędne otworu** — JSONL PIG daje wartość startową, ale docelowy release powinien brać `lat/lon` z `gps-kataster-obiektow-tatr`
- **Deklinacja** — dla większości planów tatrzańskich = 0 (plany w północy magnetycznej, deklinacja bliska 0°)
- Ręcznie dodane jaskinie mają `quality.flag: manual` i `n_submissions: 0`
