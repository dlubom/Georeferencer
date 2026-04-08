# Georeferencja Planów Jaskiń Tatrzańskich

Projekt georeferencji zeskanowanych planów jaskiń tatrzańskich — przypisanie współrzędnych geograficznych do rysunków jaskiń, tak aby można je wyświetlić na mapach w programach GIS (np. QGIS, ArcGIS).

## Status

Etap crowdsourcingowy **zakończony**: **4048 zgłoszeń** od **89 użytkowników** dla **801 jaskiń** (każda z minimum 5 niezależnymi kliknięciami).

Wyniki dostępne jako GeoTIFF-y w [GitHub Releases](../../releases).

---

## Pipeline generacji GeoTIFF

Zebrane dane crowdsourcingowe przetwarzane są automatycznym pipeline'em:

1. **Ekstrakcja** (`01_extract_yaml.py`) — dane ze zgłoszeń agregowane do edytowalnych plików YAML (`data/caves/{dir_id}/meta.yaml`): mediana pikseli otworu, mediana skali (z usuwaniem outlierów IQR), mediana kąta północy
2. **Generacja GeoTIFF** (`02_generate_geotiff.py`) — z YAML wyliczane parametry World File (A-F) i generowany GeoTIFF w układzie EPSG:2180 (PL-1992)
3. **Raporty QA** (`03_report.py`) — automatyczne flagowanie jaskiń z wysokim rozrzutem wyników

### Edycja wyników

Każdy plik `meta.yaml` jest edytowalny — można ręcznie poprawić:
- współrzędne otworu (`coordinates.lat`, `coordinates.lon`)
- pozycję otworu w pikselach (`entrance.x`, `entrance.y`)
- skalę (`scale.pixels_per_meter`)
- kąt północy (`north.angle_deg`)
- deklinację (`declination_deg`)

Po edycji i pushu na `main` — CI automatycznie przelicza World File i generuje nowy GeoTIFF.

### Uruchomienie lokalne

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r pipeline/requirements.txt
brew install gdal  # macOS

# Generacja GeoTIFF dla jednej jaskini
python pipeline/02_generate_geotiff.py --cave 001131

# Generacja dla wszystkich
python pipeline/02_generate_geotiff.py --all

# Raporty QA
python pipeline/03_report.py
```

### Release

Przy utworzeniu tagu `v*` (np. `v1.0`) GitHub Actions automatycznie generuje wszystkie GeoTIFF-y i publikuje je jako paczkę `.tar.gz` w GitHub Releases. Pliki nazywane są wg schematu: `{dir_id}_{numer_inwentarzowy}_{nazwa}.tif`.

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
