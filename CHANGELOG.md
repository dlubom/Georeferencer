# Changelog

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
