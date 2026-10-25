# Zachowane review z 24 października 2026

Źródłem jest przegląd `fad70f09992671a0da5a364dfea4a2c538f80e3d`, na którym
oparto zaakceptowany [plan T01–T11](../../../../docs/plans/2026-10-24-jakosc-danych-i-ci.md).
Skrypty zachowują logikę sond poprzedniej sesji; jedyną adaptacją jest wyznaczanie
katalogu projektu względem `__file__`. Nie korzystają ze starych katalogów
tymczasowych. Tworzą własne dane syntetyczne w `tempfile`, czytają katalog
produkcyjny bez zapisu. `data_review.original.json` i `sources.original.json`
zachowują ówczesne dowody/opis (z opisowego JSON usunięto osadzony duplikat kodu).
Pliki `*.stdout.*` i `data_review.reproduced.json` to nowe uruchomienie w
przypiętym środowisku T01; nie udają oryginalnego logu starej sesji.

| Ustalenie historyczne | Reprodukcja / źródło | Dalsza praca |
| --- | --- | --- |
| 814 YAML, 801 grup z ≥5 użytkownikami, 13 ręcznych planów | `data_review.py`, manifest katalogu | T02 |
| 7 rekordów TEST bez przydziału wpływa na 4 plany; rozrzut otworu Mroźnej 7042.09 → 1.16 px po wyłączeniu TEST | `data_review.py`, oryginalny i odtworzony JSON | T07 |
| 10 niekompletnych pomiarów północy; rozrzut >1° dla 000978, 001179, 001189 | `data_review.py` | T05/T07/T09 |
| `summary.csv` ma 801 planów, `missing.csv` ma 800 pozycji, rzeczywiste braki TIFF/TFW: 0 | `data_review.py` | T09 |
| `--image-id` zadeklarowane, ale nieczytane; wybierany pierwszy plan i zastępczy TIFF | analiza AST w `data_review.py`; kod `05_add_cave.py` z bazowego commitu | T08 |
| Strict dopuszcza numeryczne lat/lon inne niż w CSV; nie odrzuca duplikatów object_id, NaN/Inf/lat=91 w loaderze | `coordinates.py` | T03 |
| Znak zbieżności: dla 49.2°N, 19.9°E błąd kierunku wynosi ok. 1.3626°, ok. 23.78 m na 1 km; rodzaj północy niejawny | `convergence.py`, niezależny kierunek z projekcji dwóch punktów i czynniki PROJ | T05/T06 |
| GDAL i process_cave dopuszczają ujemną skalę/NaN lub tworzą wynik bez georeferencji; konwencja kliknięcia wymaga osobnego odbioru | `geometry.py` | T03/T04/T06 |
| 16 testów, brak kontroli PR; release z latest, luźne zależności | workflow/testy z bazowego commitu; `sources.original.json` | T01/T02/T11 |
| `--changed` bazuje na mtime; workflow widzi HEAD~1, mutuje YAML/TFW i próbuje commitować do main | `geometry.py` oraz bazowe `02_generate_geotiff.py` i workflow | T04/T10 |

T01 rozwiązał kontrolę PR i środowisko. T02 przypina źródło i zachowuje dowody.
Pozostałe wiersze są historycznymi ustaleniami do odpowiednich zadań; T02 ich
nie naprawia. Nie wyznaczają wyjątków dopuszczających błędy techniczne w QA.
Ręczne korekty i `computed` pozostają w oryginalnych YAML-ach zabezpieczonych
hashami i Git; różnica z agregacją nie daje podstaw do ich automatycznego cofnięcia.

Odtworzenie z checkoutu T02, po `docker build` z instrukcji
[COORDINATE_SOURCE.md](../../../../docs/COORDINATE_SOURCE.md):

```sh
audit_dir=$(mktemp -d)
for probe in data_review coordinates convergence geometry; do
  docker run --rm --platform linux/amd64 --network none \
    --mount "type=bind,source=$PWD,target=/workspace,readonly" \
    "$(cat /tmp/georeferencer-audit-image)" \
    python "data/baseline/2026-10-24/review/$probe.py" > "$audit_dir/$probe.stdout"
done
cmp "$audit_dir/data_review.stdout" data/baseline/2026-10-24/review/data_review.reproduced.json
```

`geometry.py` wypisuje ścieżki własnych losowych katalogów i zależne od czasu
liczniki changed; porównuje się wyniki przypadków, nie bajty tego logu.
W sondach celowo występują niepoprawne liczby, w tym zapisy NaN/Infinity
w diagnostyce; nie są to manifesty akceptacji danych.
