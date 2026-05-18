# Georeferencja Planów Jaskiń Tatrzańskich

Projekt georeferencji zeskanowanych planów jaskiń tatrzańskich — przypisanie współrzędnych geograficznych do rysunków jaskiń, tak aby można je wyświetlić na mapach w programach GIS (np. QGIS, ArcGIS).

## Status

Etap crowdsourcingowy **zakończony**: **4048 zgłoszeń** od **89 użytkowników** dla **801 jaskiń** (każda z minimum 5 niezależnymi kliknięciami).

Wyniki dostępne jako GeoTIFF-y w [GitHub Releases](../../releases).

---

## Pipeline generacji GeoTIFF

Zebrane dane crowdsourcingowe przetwarzane są automatycznym pipeline'em:

1. **Ekstrakcja** (`01_extract_yaml.py`) — dane ze zgłoszeń agregowane do edytowalnych plików YAML (`data/caves/{dir_id}/meta.yaml`): mediana pikseli otworu, mediana skali (z usuwaniem outlierów IQR), mediana kąta północy
2. **Renderowanie współrzędnych** — `meta.yaml` trzyma Jinja placeholdery `coordinates.lat/lon` oraz jawny `coordinates.gps_kataster_object_id` wskazujący ID otworu (`object_id`) z release [`dlubom/gps-kataster-obiektow-tatr`](https://github.com/dlubom/gps-kataster-obiektow-tatr).
3. **Generacja GeoTIFF** (`02_generate_geotiff.py`) — z YAML wyliczane parametry World File (A-F) i generowany GeoTIFF w układzie EPSG:2180 (PL-1992)
4. **Raporty QA** (`03_report.py`) — automatyczne flagowanie jaskiń z wysokim rozrzutem wyników

### Edycja wyników

Każdy plik `meta.yaml` jest edytowalny — można ręcznie poprawić:
- identyfikator właściwego otworu w gps-kataster (`coordinates.gps_kataster_object_id`) — potrzebny, gdy jedna jaskinia ma kilka otworów i automatyczne dopasowanie nie jest jednoznaczne
- pozycję otworu w pikselach (`entrance.x`, `entrance.y`)
- skalę (`scale.pixels_per_meter`)
- kąt północy (`north.angle_deg`)
- deklinację (`declination_deg`)

Po edycji i pushu na `main` — CI automatycznie przelicza World File i generuje nowy GeoTIFF.

Współrzędne WGS84 nie są już traktowane jako lokalna prawda projektu. Każdy YAML wskazuje konkretny otwór w `gps-kataster-obiektow-tatr`, a release renderuje `lat/lon` z `best-measurements.csv`. Jeśli automatyczne jednorazowe przypisanie otworu było błędne, popraw tylko `gps_kataster_object_id`. Przypadki z wieloma kandydatami są zebrane w `data/caves/_reports/gps_kataster_manual_review.csv`.

```yaml
coordinates:
  gps_kataster_object_id: KSZ-0033
  lat: "{{ gps_kataster.objects[gps_kataster_object_id].lat }}"
  lon: "{{ gps_kataster.objects[gps_kataster_object_id].lon }}"
```

### Uruchomienie lokalne

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r pipeline/requirements.txt
brew install gdal  # macOS

# Generacja GeoTIFF dla jednej jaskini
python pipeline/02_generate_geotiff.py --cave 001131 \
  --gps-kataster-best-measurements ../gps-kataster-obiektow-tatr/build/exports/best-measurements.csv \
  --gps-kataster-strict

# Generacja dla wszystkich
python pipeline/02_generate_geotiff.py --all \
  --gps-kataster-best-measurements ../gps-kataster-obiektow-tatr/build/exports/best-measurements.csv \
  --gps-kataster-strict

# Raporty QA
python pipeline/03_report.py
```

### Release

Przy utworzeniu tagu `v*` (np. `v1.0`) GitHub Actions pobiera `best-measurements.csv` z najnowszego release `dlubom/gps-kataster-obiektow-tatr`, renderuje Jinja placeholdery `lat/lon`, generuje wszystkie GeoTIFF-y i publikuje je jako paczkę `.zip` w GitHub Releases. Przy ręcznym uruchomieniu workflow można przypiąć konkretny tag release gps-kataster. Pliki nazywane są wg schematu: `{dir_id}_{numer_inwentarzowy}_{nazwa}.tif`.

---

<details>
<summary>Archiwum: instrukcja crowdsourcingowa (etap zakończony)</summary>

## Instrukcja krok po kroku

### 1. Wejdź na stronę

Otwórz w przeglądarce: **https://dlubom.github.io/Georeferencer/index.html**

**Poczekaj aż statystyki się załadują** - zobaczysz pasek postępu i informację ile jaskiń zostało do opracowania.

### 2. Kliknij "Daj mi jaskinię"

Po załadowaniu strony kliknij przycisk **"Daj mi jaskinię"**. System przydzieli Ci losową jaskinię do opracowania.

### 3. Wybierz plan jaskini

W praktyce zazwyczaj automatycznie załaduje się pierwszy plan z listy.

> **Uwaga:** Kilka jaskiń nie posiada planu - jeśli trafisz na taką, po prostu ją pomiń i weź kolejną.

### 4. Zaznacz otwór jaskini

Otwór jaskini na planie jest zazwyczaj oznaczony **trójkącikiem z kropką w środku**, umieszczonym na przecięciu osi siatki **0,0**.

```
        0,0
         |
         |
0,0 -----△-----
         |
```

**Wskazówki dotyczące precyzji:**
- **Przybliżaj/oddalaj** - użyj kółka myszy
- **Przesuwaj ekran** - trzymaj **Shift** i przeciągaj
- **Cofnij pomyłkę** - możesz anulować błędne kliknięcie

### 5. Określ skalę

1. **Odczytaj długość skali** z rysunku (np. "10 m", "50 m")
2. **Wpisz tę wartość** w odpowiednie pole
3. **Zaznacz skalę** - kliknij początek i koniec podziałki na rysunku

### 6. Zaznacz linię północy

Określ kierunek północy na planie. Domyślnie 0° — na 99% planów północ jest pionowo w górę.

### 7. Zaznacz punkty przecięć siatki

Zaznaczaj kolejne punkty przecięć siatki. Jeśli plan nie ma siatki — kliknij **"Brak siatki"**.

### 8. Zweryfikuj i wyślij

Sprawdź wszystkie zaznaczone punkty i kliknij **"Wyślij do Google Sheets"**.

</details>

---

## Pytania?

Jeśli masz wątpliwości lub napotkasz problem - skontaktuj się z koordynatorem projektu.

**Dziękujemy za pomoc w georeferencji polskich jaskiń!**
