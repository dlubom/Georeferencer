# Changelog

## Niewydane

- Poprawiono skalę Jaskini Juhaskiej `001212` (`T.D-14.01`): 194,9 →
  97,85 px/m na podstawie siatki 0/−10/−20. Plan był liniowo 1,992 razy
  za mały wskutek konfliktu siatki z podziałką „1 m”. Zachowano zakotwiczenie
  otworu i historyczny obrót; orientacja nadal `unknown/unverified`.
  [Pomiar i uzasadnienie](docs/reports/2026-10-30-juhaska-scale.md).
- Wycofano z eksportu stary plan Piwnicy Miętusiej `001459`, zachowując jego
  pliki w `data/archive/caves/001459`. W bieżącym katalogu 814 planów pozostaje
  wyłącznie nowszy plan PZA `001459-pza-2024`.

## v0.7.3 — Nowszy plan Piwnicy Miętusiej (2026-10-29)

- Dodano osobny plan Piwnicy Miętusiej `001459-pza-2024` z publikacji PZA
  *Polish Caving 2017–2025*, strona 17 (zestawienie: P. Graczyk, 2024).
  Zachowano dotychczasowy plan `001459`; katalog zawiera teraz 815 planów.
- Ręcznie wyznaczono otwór, skalę i kierunek strzałki N na nowym rastrze.
  Plan dowiązano do `MTZ-0017` z przypiętych współrzędnych gps-kataster v1.3.2;
  zapisano pochodzenie obrazu i pomiarów.
- Orientacja nowego planu pozostaje `unknown/unverified`. Jawnie przyjęty obrót
  +0,679677° względem siatki EPSG:2180 wymaga potwierdzenia rodzaju północy
  przez autora. Nie zastosowano poprawki magnetycznej.
- Naprawiono `coordinate_source.py impact`: raport aktualizacji współrzędnych
  obejmuje także nowe plany bez historycznego TFW, z zachowaniem weryfikacji
  obu źródeł CSV i walidacji przeliczeń.

## v0.7.2 — Kotwica północnego otworu Mroźnej (2026-10-26)

- Poprawiono przypisanie planu Mroźnej `001094` do otworu północnego
  (`KSW-0081` → `KSW-0256`): przesunięcie o 354,163 m, z zachowaniem
  obrazu, punktu kliknięcia, skali i obrotu.
- Rozstrzygnięto wybór otworu w QA. Orientacja planu nadal ma status
  `unknown/unverified`; wydanie nie wprowadza poprawki deklinacyjnej.
- Dalszą weryfikację rodzaju północy, daty pomiarów i zgodności z GPS
  opisano w [issue #32](https://github.com/dlubom/Georeferencer/issues/32).

## v0.7.1 — Kotwica planu Obłazkowej (2026-10-26)

- Poprawiono kotwicę wspólnego planu Mylnej i Obłazkowej `001351` na
  południowy otwór Mylnej (`KSZ-0064`): przesunięcie o 33,453 m,
  z zachowaniem obrazu, skali i obrotu.
- Historyczny test T07 odtwarza zamrożone wejścia, zachowując niezależność
  od późniejszych ręcznych korekt katalogu.
- Zapewniono odczyt odebranego ZIP-a na runnerze i ochronę istniejących
  assetów wydania przed nadpisaniem.

## v0.7.0 — Kontrolowany GeoTIFF i współrzędne Pawlikowskiego (2026-10-26)

Zmiany od opublikowanego v0.6.2.

### Współrzędne

- Jawny pin gps-kataster v1.3.2, zweryfikowany SHA-256 i wersjonowany CSV.
  Zachowano CSV/opis v1.3.1. Cztery istniejące obiekty zmieniają Best,
  cztery nowe pozostają bez automatycznych powiązań z planami.
- Względem T11 przesuwają się wyłącznie plany 001349 (Mylna),
  001351 (Obłazkowa), 001387 (Raptawicka) i 010935 (Pawlikowskiego),
  o 13.31–13.43 m, bez zmiany skali ani obrotu. Dziewięć unieważnionych
  wyjątków QA oceniono indywidualnie; pozostałe 1396 pozostaje bez zmian.

### Pipeline i format paczki — T01–T11

- Wspólna kontrola w przypiętym Linux/Python/GDAL, jawne źródła i zachowana
  historia 814 planów. Pełna walidacja ID, obrazów, parametrów i proweniencji.
- Wyniki powstają poza źródłami, z cache według treści, kompletnym manifestem
  i rzeczywistym odczytem wszystkich GeoTIFF-ów przed publikacją przebiegu.
- Jawna niepewność północy i modele geographic/magnetic/grid, poprawna
  konwencja narożnika kliknięć i półpiksela TFW/GDAL. Historyczne unknown
  zachowuje kąt TFW T02; nowe unknown wymaga osobnego assumed_grid.
- Selektywna agregacja T07 wyklucza siedem jawnych TEST, rozdziela ważne
  komponenty i zachowuje ręczne korekty. Zmieniono 12 YAML-i; brak ponownej
  ekstrakcji. Bezpieczne narzędzie dodawania planów T08 nie dodaje samo planów.
- QA rozdziela błędy techniczne od jawnie dopuszczonych niepewności;
  oba tryby wydania korzystają ze wspólnej bramki i odbioru ZIP T11.
- **Układ ZIP t11-v2:** czytelne TIFF-y bezpośrednio w korzeniu, np.
  `001094_T.D-08.07_Jaskinia_Mroźna.tif`, oraz `manifest.json` z kompletnym
  mapowaniem `plan_id/output/archive_path/sha256`. TFW i computed.json są
  w `metadane/{plan_id}/`. Zachowano historyczną normalizację nazw v0.6.2
  i nazwę archiwum `geotiff-tatry-v0.7.0.zip`. Katalog zawiera 814 planów.
  Wewnętrzny przebieg generatora nadal używa katalogów `plan_id/`.

### Granice odbioru

- PASS oznacza odbiór techniczny i egzekwowanie 1405 znanych niepewności,
  nie terenowe potwierdzenie kartografii. Wszystkie historyczne północe
  nadal są unknown/unverified; issues #1/#3 pozostają otwarte.
- Nowe Best Pawlikowskiego są nieweryfikowane i mają nieznaną dokładność.
  Obliczenia nie weryfikują terenowo progu/stacji, skali ani orientacji planu.
- [Raport wpływu](docs/reports/coordinate-source-v1.3.2-impact.json),
  [odbiór](docs/plans/2026-10-25-gps-v1.3.2-odbior.md) oraz
  [treść publikacji](docs/releases/v0.7.0-notes.md).

---

## v0.6.2 — Korekta dowiązania planów i obsługa sztolni (2026-10-24)

### Poprawki georeferencji
- **010935 — Jaskinie Pawlikowskiego:** dowiązano plan systemu do południowego otworu Jaskini Mylnej (`KSZ-0064`), oznaczonego na planie jako punkt 0,00.
- **000490 — Jaskinia Wielka Śnieżna:** dowiązano plan systemu do otworu Jaskini Śnieżnej (`MLZ-0068`, T.E-13.1), oznaczonego na planie jako punkt 0,0.
- Przeliczono parametry georeferencji obu planów i dodano uzasadnienia wyboru otworów. Usunięto zależność tych planów od zbiorczych rekordów systemów `KSZ-0009` i `MLZ-0029`.

### Generator
- Naprawiono generowanie GeoTIFF-ów dla obiektów kategorii `sztolnia`, w tym **001042 — Wojtkowa Szpara** (`CHZ-0011`).
- Rozszerzono testy obsługi kategorii obiektów i zaktualizowano dokumentację generatora.

---

## v0.6.1 — Paczka GeoTIFF w formacie ZIP (2026-05-18)

### Release
- Workflow release publikuje GeoTIFF-y jako `geotiff-tatry-v*.zip` zamiast `geotiff-tatry-v*.tar.gz`, żeby paczka była łatwiejsza do otwarcia dla użytkowników Windows i mniej technicznych odbiorców.
- Zaktualizowano README i dodano test chroniący format archiwum release.
- Domyka issue #4.

---

## v0.6.0 — Integracja współrzędnych z gps-kataster (2026-05-17)

### Integracja współrzędnych z gps-kataster
- Masowo zastąpiono lokalne `coordinates.lat/lon` w `data/caves/*/meta.yaml` Jinja placeholderami, które wskazują jawny `coordinates.gps_kataster_object_id` otworu.
- Przeliczono sekcje `computed` i pliki `image.tfw` dla pełnego zestawu 814 jaskiń na podstawie lokalnego `best-measurements.csv`.
- Workflow release i automatycznej generacji pobierają `best-measurements.csv` z GitHub Releases gps-kataster, renderują Jinja i uruchamiają generator w trybie `--gps-kataster-strict`.
- Dodano raport `data/caves/_reports/gps_kataster_manual_review.csv` z 6 przypadkami, w których automatyczne przypisanie dotyczyło wielu otworów lub wymaga ręcznego potwierdzenia.

### Narzędzia i dokumentacja
- Dodano moduł `pipeline/gps_kataster_coordinates.py`, obsługę CSV/GeoJSON `best-measurements` oraz testy dla rozwiązywania ID otworów.
- `05_add_cave.py` potrafi zapisać `coordinates.gps_kataster_object_id` i podpowiada generację w trybie strict.
- Dodano `AGENTS.md` jako repo-instrukcję dla Codex i usunięto przestarzały `CLAUDE.md`.

---

## v0.5.2 — Korekta współrzędnych: Czarna (2026-05-10)

### Korekta współrzędnych otworu (źródło: kombinacja GNSS + LIDAR)
- **001445** Jaskinia Czarna: 49.2444121431, 19.8705053667

---

## v0.5.1 — Korekta współrzędnych: Miętusia, Miętusia Wyżnia (2026-04-15)

### Korekta współrzędnych + wysokość (źródło: [RadostW/jaskinie](https://github.com/RadostW/jaskinie))
- **001197** Jaskinia Miętusia: 49.246611, 19.898750, 1270.0 m n.p.m.
- **001187** Jaskinia Miętusia Wyżnia: 49.245399, 19.894900, 1377.0 m n.p.m.

---

## v0.5 — Korekta współrzędnych WGS84 (2026-04-15)

### Korekta współrzędnych otworu
Poprawiono współrzędne WGS84 dla 2 jaskiń:
- **001665** Jaskinia Wysoka: 49.23364130, 19.88454604
- **001299** Jaskinia Bańdzioch Kominiarski: 49.24258746, 19.84957850

---

## v0.4 — Ręczne dodawanie brakujących jaskiń (2026-04-10)

### Nowe skrypty
- **04_find_missing.py** — porównanie rejestru PIG (JSONL) z istniejącymi jaskiniami; lista 27 brakujących z planami, posortowana po długości
- **05_add_cave.py** — ręczne dodanie jaskini: tworzy katalog, kopiuje obrazy ze scrapera, generuje meta.yaml z flagą `quality.flag: manual`

### Georeferencer UI
- Dodano logowanie `DANE DO META.YAML` w konsoli przeglądarki (`Polish-Cave-Data-Scraper/index.html`) — gotowe wartości otworu, skali i kąta północy do wklejenia

### Dodane jaskinie
- **001197** Jaskinia Miętusia (T.D-11.01) — 10 540 m, 283 m głębokości
- **000490** Jaskinia Wielka Śnieżna (T-Wielka Śnieżna) — 23 723 m, 808 m głębokości
- **001538** Jaskinia Śnieżna Studnia (T.E-12.08) — 12 700 m, 726 m głębokości
- **001299** Jaskinia Bańdzioch Kominiarski (T.E-07.07) — 10 010 m, 546 m głębokości
- **000491** Jaskinia Wielka Litworowa (T.E-12.01) — 7 185 m, 354 m głębokości
- **001473** Ptasia Studnia (T.E-11.06) — 6 283 m, 352 m głębokości
- **001495** Jaskinia Mała w Mułowej (T.E-11.18) — 3 863 m, 555 m głębokości
- **001274** Jaskinia Magurska (T.D-18.01) — 1 200 m, 58 m głębokości
- **001652** Jaskinia Psia (T.F-09.01) — 1 076 m, 57 m głębokości
- **004866** Jaskinia Harda (T.E-11.71) — 578 m, 126 m głębokości
- **001590** Koprowa Studnia (T.E-13.08) — 90 m, 47 m głębokości
- **001511** Jaskinia Lejbusiowa (T.E-11.48) — 83 m
- **001604** Zagonna Studnia (T.E-12.57) — 70 m, 52 m głębokości

### Dokumentacja
- `pipeline/MANUAL_ADD.md` — instrukcja ręcznego dodawania jaskiń
- Zaktualizowano `CLAUDE.md` o nowe skrypty i zależności zewnętrzne

---

## v0.3 — Korekta jakości georeferencji (2026-04-09)

### Agregacja otworu
- Zamiana niezależnej mediany X/Y na **medianę geometryczną (Weiszfeld)** — poprawna agregacja 2D minimalizująca sumę odległości euklidesowych do kliknięć
- Przeliczono 801 YAML-ów (max przesunięcie 1.13 px, mediana 0.12 px)

### Ręczna korekta kąta północy
Poprawiono `angle_deg` dla 6 jaskiń z niestandardową strzałką N na planie:
- **001189** Jaskinia Niedźwiedzia Niżnia: -90.0 (N w lewo)
- **001094** Jaskinia Mroźna: 50.0 (N obrócone ~50°)
- **000978** Okap w Kończystej Turni: 90.0 (N w prawo)
- **001179** Schron pomiędzy Żwirowymi Dziurami: 0.0 (outlier usunięty)
- **001349** Jaskinia Mylna: 60.0 (N obrócone ~60°)
- **001351** Jaskinia Obłazkowa: 60.0 (N obrócone ~60°)

### Dokumentacja
- Oznaczono etap crowdsourcingowy jako zakończony

---

## v0.2 — Płaskie nazwy w paczce Release (2025-xx-xx)

- Release GeoTIFF: zmiana struktury paczki na płaskie nazwy plików

---

## v0.1 — Pipeline GeoTIFF (2025-xx-xx)

Pierwsza wersja pipeline'u generacji georeferencjonowanych TIFFów z danych crowdsourcingowych.

- **01_extract_yaml.py** — ekstrakcja parquet → YAML + kopiowanie obrazów (801 jaskiń z 5+ zgłoszeniami)
- **02_generate_geotiff.py** — generacja .tfw (World File) + GeoTIFF (EPSG:2180, CCITTFAX4)
- **03_report.py** — raporty QA: summary.csv, flagged.csv, missing.csv
- CI/CD: automatyczna regeneracja .tfw na push, paczka GeoTIFF jako Release asset na tag
- Wygenerowano .tfw dla 801 jaskiń
