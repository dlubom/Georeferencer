# Georeferencja Planów Jaskiń Tatrzańskich

Projekt georeferencji zeskanowanych planów jaskiń tatrzańskich — przypisanie współrzędnych geograficznych do rysunków jaskiń, tak aby można je wyświetlić na mapach w programach GIS (np. QGIS, ArcGIS).

## Status

Etap crowdsourcingowy **zakończony**: **4048 zgłoszeń** od **89 użytkowników** dla **801 jaskiń** (każda z minimum 5 niezależnymi kliknięciami).

Wyniki dostępne jako GeoTIFF-y w [GitHub Releases](../../releases).

---

## Pipeline generacji GeoTIFF

Generowanie T10 zapisuje kompletny przebieg TFW, GeoTIFF, computed i manifestu
w `build/geotiff`, bez zmian źródeł. Cache wynika z zawartości i wersji
obliczeń/środowiska. [Instrukcja wyników i odbioru](docs/GENERATION_OUTPUT.md)
opisuje atomowe `current`, pełny katalog i bramki wydania.

Zebrane dane crowdsourcingowe przetwarzane są automatycznym pipeline'em:

1. **Ekstrakcja** (`01_extract_yaml.py`) — dane ze zgłoszeń agregowane do edytowalnych plików YAML (`data/caves/{dir_id}/meta.yaml`): mediana pikseli otworu, mediana skali (z usuwaniem outlierów IQR), mediana kąta północy
2. **Renderowanie współrzędnych** — `meta.yaml` trzyma Jinja placeholdery `coordinates.lat/lon` oraz jawny `coordinates.gps_kataster_object_id` wskazujący ID otworu (`object_id`) z release [`dlubom/gps-kataster-obiektow-tatr`](https://github.com/dlubom/gps-kataster-obiektow-tatr).
3. **Generacja GeoTIFF** (`02_generate_geotiff.py`) — z YAML wyliczane parametry World File (A-F) i generowany GeoTIFF w układzie EPSG:2180 (PL-1992)
4. **Raporty QA** (`03_report.py`) — automatyczne flagowanie jaskiń z wysokim rozrzutem wyników

### Edycja wyników

Każdy plik `meta.yaml` jest edytowalny — można ręcznie poprawić:
- identyfikator właściwego otworu w gps-kataster (`coordinates.gps_kataster_object_id`) — wymagany dla każdego planu
- pozycję otworu w pikselach (`entrance.x`, `entrance.y`)
- skalę (`scale.pixels_per_meter`)
- kąt północy (`north.angle_deg`)
- deklinację (`declination_deg`)

Zmiany przekazuj przez PR z wymaganą kontrolą `Kontrola projektu`. Workflow
buduje cały aktualny katalog z cache, przeprowadza QA i udostępnia artefakty
oraz raporty. Nie zapisuje commitu bota do `main`.

Współrzędne WGS84 nie są już traktowane jako lokalna prawda projektu. Każdy YAML wskazuje konkretny otwór w `gps-kataster-obiektow-tatr`, a release renderuje `lat/lon` z `best-measurements.csv`. Plan może wskazać kategorię `jaskinia_otwor` albo `sztolnia`; pozostałe kategorie mogą być obecne w katalogu. Jeśli automatyczne jednorazowe przypisanie otworu było błędne, popraw tylko `gps_kataster_object_id`. Przypadki z wieloma kandydatami są zebrane w `data/caves/_reports/gps_kataster_manual_review.csv`.

```yaml
coordinates:
  gps_kataster_object_id: KSZ-0033
  lat: "{{ gps_kataster.objects[gps_kataster_object_id].lat }}"
  lon: "{{ gps_kataster.objects[gps_kataster_object_id].lon }}"
```

### Uruchomienie lokalne

Kontrola przed PR: `./scripts/check` (wymaga działającego Dockera). Uruchamia cały zestaw testów, w tym mały GeoTIFF przez rzeczywisty GDAL, w tym samym przypiętym środowisku co CI. [Instrukcja kontroli, wersje i aktualizacja zależności](ci/README.md).

```sh
# Przypięte środowisko, źródła readonly, praca bez sieci
./scripts/build generate --changed
./scripts/build generate --cave 001131
./scripts/build generate --all --force
./scripts/build report --run-dir /build/geotiff/current --require-results
```

Pełne QA katalogu wymaga przebiegu `--all`/`--changed`. `--cave` tworzy
podzbiór do pracy nad wskazanym planem. Dla bezpośredniego Pythona użyj
`pipeline/02_generate_geotiff.py` z tymi samymi opcjami; domyślny wynik to
`build/geotiff`. Tylko wrapper gwarantuje referencyjne środowisko.

### Release

Tag `v*` i ręczne wydanie z istniejącego tagu używają tego samego przypiętego
środowiska, źródła gps-kataster **v1.3.2** oraz obowiązkowej bramki manifestu,
aktualności i pełnego QA T09. ZIP t11-v2 zawiera czytelne TIFF-y w korzeniu,
`manifest.json` z pełnym mapowaniem oraz `metadane/{plan_id}/{image.tfw,computed.json}`. Próba bez publikacji:

```sh
./scripts/build generate --all
./scripts/build package --mode manual --run-dir /build/geotiff/current \
  --reports-dir /build/release-qa --archive /build/geotiff-tatry-local.zip
```

[Źródła i historia](docs/COORDINATE_SOURCE.md),
[kontrakt wyników i paczki](docs/GENERATION_OUTPUT.md).

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

Walidacja T03 jest obowiązkowa przed generowaniem całej wybranej partii: typy,
liczby, obraz i jego SHA-256 oraz zgodność współrzędnych z jawnym ID.
Błąd wejścia pozostawia wcześniejsze artefakty bez zmian. Kontrakt i sposób
aktualizacji rejestru obrazów opisano w [docs/VALIDATION.md](docs/VALIDATION.md).
