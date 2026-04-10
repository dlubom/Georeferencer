# Changelog

## v0.4 — Ręczne dodawanie brakujących jaskiń (2026-04-10)

### Nowe skrypty
- **04_find_missing.py** — porównanie rejestru PIG (JSONL) z istniejącymi jaskiniami; lista 27 brakujących z planami, posortowana po długości
- **05_add_cave.py** — ręczne dodanie jaskini: tworzy katalog, kopiuje obrazy ze scrapera, generuje meta.yaml z flagą `quality.flag: manual`

### Georeferencer UI
- Dodano logowanie `DANE DO META.YAML` w konsoli przeglądarki (`Polish-Cave-Data-Scraper/index.html`) — gotowe wartości otworu, skali i kąta północy do wklejenia

### Dodane jaskinie
- **001197** Jaskinia Miętusia (T.D-11.01) — 10 540 m, 283 m głębokości

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
