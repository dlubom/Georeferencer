# Ręczne dodawanie planów (T08)

Dodawanie działa na jednym wskazanym obrazie mono i wymaga jawnego otworu
z [przypiętego katalogu](../docs/COORDINATE_SOURCE.md). Potrzebne są zależności
Pythona i GDAL z [referencyjnego środowiska](../ci/README.md).
`--scraper-dir` i `--jsonl` domyślnie wskazują sąsiednie repozytoria w `../`.
`--data-dir` domyślnie wskazuje `data/caves` tego repozytorium.

## Tożsamość i wybór

| Argument / pole | Co identyfikuje |
| --- | --- |
| `--cave` → `cave.source_cave_id` | jaskinię w źródłowym JSONL PIG |
| `--image-id` → `image.image_id` | konkretny `graphics_id` planu |
| `--plan-id` → `cave.dir_id` | nowy katalog planu, osobny dla każdego obrazu |
| `--gps-kataster-object-id` | otwór/obiekt `jaskinia_otwor` albo `sztolnia` w pinie |

Dwa plany jednej jaskini mają to samo source_cave_id, lecz odrębne plan_id
oraz graphics_id. Nie dobieraj otworu według nazwy jaskini ani kolejności CSV.
`--cave` generatora `02_` nadal oznacza **ID katalogu planu**.

Wybierany jest dokładnie `caves_mono/<cave>/image_<graphics_id>_zoom_10.tif`.
Przy jednym planie można pominąć `--image-id`; przy wielu jest obowiązkowy.
Nie ma zastępstwa pierwszym planem, przekrojem ani dowolnym TIFF-em. Powtórzone
rekordy jaskini/graphics_id, sprzeczna ścieżka lub numer inwentarzowy i wymiary
2x niezgodne z obecnymi maxWidth/maxHeight JSONL są błędami.

Podgląd istniejącego źródła, bez zapisu jakichkolwiek plików:

```sh
python pipeline/05_add_cave.py --cave 001197 --image-id 12400 --dry-run
```

Zapisz wypisany SHA-256. Otwórz **ten sam obraz mono** w sąsiednim
`Polish-Cave-Data-Scraper/index.html`, zaznacz otwór i podziałkę, a następnie
strzałkę, jeśli ją mierzysz. Współrzędne kliknięć są w układzie narożnika
obrazu: x w prawo, y w dół. Początek to (0,0), środek pierwszego piksela
(.5,.5). Kąt strzałki rośnie zgodnie z zegarem od pionu w górę obrazu.
Zapisz konkretne źródła parametrów: symbol otworu, długość i odcinek skali,
legendę/podstawę rodzaju północy. Sam komunikat UI z wartością 0 nie
rozstrzyga, czy północ została zmierzona czy pominięta.

`--image-sha256` jest obowiązkowym potwierdzeniem obrazu pomiarów.
Podmiana TIFF-a o tych samych wymiarach też jest błędem. Zmiana obrazu wymaga
nowych kliknięć i osobnego przeglądu. Nie odświeżaj hasha po błędzie.

## Orientacja

- `geographic` i `grid` wymagają zmierzonego kąta oraz `--north-source`,
  czyli konkretnej podstawy rodzaju północy i pomiaru. `grid` oznacza
  udokumentowaną północ **EPSG:2180**. Modele i znaki pochodzą z T06.
- `magnetic` wymaga także jawnej deklinacji (w tym jawnego 0), podstawy,
  epoki i konwencji `east_positive`. Nie istnieje domyślna deklinacja.
- `unknown` wymaga `--north-skipped` albo rzeczywistego `--north-angle`
  z jego źródłem; pominięcie obu jest błędem. Oddzielnie wymaga decyzji
  dopuszczającej, `--assumed-grid-angle` i `--grid-angle-convention`.
  Nie zamienia się przez to w grid.

`image_x_ccw_from_grid_east` opisuje obrót **r** osi x obrazu przeciwnie do
zegara od wschodniej osi siatki EPSG:2180: A=mpp·cos(r), D=mpp·sin(r).
To przyjęta orientacja wyniku, nie dowód północy źródłowego planu. Nie jest
kątem strzałki. Dla unknown nie stosuje się zbieżności ani deklinacji.
Kąt strzałki i przyjęty obrót mogą się różnić.

Każdy nowy plan ma status `unverified`, początkową decyzję z datą i powodem,
hash wejść orientacji oraz hash obrazu. Nowy unknown używa `assumed_grid`.
Nie ma historycznego TFW T02 ani prawa do kąta/wyjątku innego planu.
[ORIENTATION.md](../docs/ORIENTATION.md) opisuje dalsze decyzje po edycji.

## Pełne wywołania na danych syntetycznych

Poniższe przykłady są wykonywalnym ćwiczeniem w `/tmp`, nie dodają rzeczywistych
planów. Syntetyczny symbol otworu celowo wiążemy z KSZ-0033 z przypiętego CSV.
Przy prawdziwym dodawaniu zastąp wszystkie ID, hash, kliki i źródła danymi
wybranego planu. Powód decyzji ma uzasadniać dopuszczenie konkretnej orientacji.
Nie kopiuj źródeł syntetycznych do danych produkcyjnych.

Jednorazowo przygotuj wejścia (Python z Pillow):

```sh
export T08_DEMO=$(mktemp -d /tmp/georeferencer-t08-XXXXXX)
python - <<'PY'
import json, os
from pathlib import Path
from PIL import Image
root = Path(os.environ['T08_DEMO'])
images = []
for graphics_id in (101, 102):
    stem = f'image_{graphics_id}_zoom_10'
    path = root / 'scraper/caves_mono/t08-demo' / (stem + '.tif')
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new('1', (8, 6))
    image.putpixel((graphics_id-101, 1), 255)
    image.save(path)
    images.append({'metadata': {'graphics_id': graphics_id,
        'graphics_type_name': 'plan', 'inventory_number': 'T.TEST',
        'maxWidth': 4, 'maxHeight': 3},
        'image_path': f'caves/t08-demo/{stem}.jpg'})
(root / 'pig.jsonl').write_text(json.dumps({'cave_id': 't08-demo',
    'name': 'Plan syntetyczny T08', 'inventory_number': 'T.TEST',
    'images': images}) + '\n')
PY
T08_IMAGE_SHA=$(python -c 'import hashlib,os; from pathlib import Path; print(hashlib.sha256((Path(os.environ["T08_DEMO"])/"scraper/caves_mono/t08-demo/image_102_zoom_10.tif").read_bytes()).hexdigest())')
```

Północ geograficzna, rzeczywisty pomiar 0° w syntetycznym planie:

```sh
python pipeline/05_add_cave.py --cave t08-demo --image-id 102 --plan-id demo-geographic \
  --scraper-dir "$T08_DEMO/scraper" --jsonl "$T08_DEMO/pig.jsonl" --data-dir "$T08_DEMO/plans" \
  --image-sha256 "$T08_IMAGE_SHA" --gps-kataster-object-id KSZ-0033 \
  --entrance-x 2.25 --entrance-y 3.5 --entrance-source 'Syntetyczny symbol otworu mono' \
  --pixels-per-meter 2 --scale-source 'Syntetyczna podziałka: 2 px na 1 m' \
  --north-reference geographic --north-angle 0 --north-source 'Syntetyczna legenda: geograficzna; pomiar pionowej strzałki' \
  --decision-date 2026-10-25 --decision-reason 'Odbiór modelu geographic na planie syntetycznym'
```

Północ magnetyczna, udokumentowana deklinacja ujemna:

```sh
python pipeline/05_add_cave.py --cave t08-demo --image-id 102 --plan-id demo-magnetic \
  --scraper-dir "$T08_DEMO/scraper" --jsonl "$T08_DEMO/pig.jsonl" --data-dir "$T08_DEMO/plans" \
  --image-sha256 "$T08_IMAGE_SHA" --gps-kataster-object-id KSZ-0033 \
  --entrance-x 2.25 --entrance-y 3.5 --entrance-source 'Syntetyczny symbol otworu mono' \
  --pixels-per-meter 2 --scale-source 'Syntetyczna podziałka: 2 px na 1 m' \
  --north-reference magnetic --north-angle 12 --north-source 'Syntetyczna legenda: magnetyczna; pomiar strzałki' \
  --declination -4.5 --declination-basis 'Syntetyczna wartość dla epoki planu' \
  --declination-epoch 2001 --declination-sign-convention east_positive \
  --decision-date 2026-10-25 --decision-reason 'Odbiór modelu magnetic na planie syntetycznym'
```

Udokumentowana północ siatki EPSG:2180:

```sh
python pipeline/05_add_cave.py --cave t08-demo --image-id 102 --plan-id demo-grid \
  --scraper-dir "$T08_DEMO/scraper" --jsonl "$T08_DEMO/pig.jsonl" --data-dir "$T08_DEMO/plans" \
  --image-sha256 "$T08_IMAGE_SHA" --gps-kataster-object-id KSZ-0033 \
  --entrance-x 2.25 --entrance-y 3.5 --entrance-source 'Syntetyczny symbol otworu mono' \
  --pixels-per-meter 2 --scale-source 'Syntetyczna podziałka: 2 px na 1 m' \
  --north-reference grid --north-angle 17.25 --north-source 'Syntetyczna legenda: siatka EPSG:2180; pomiar strzałki' \
  --decision-date 2026-10-25 --decision-reason 'Odbiór modelu grid na planie syntetycznym'
```

Nieustalona północ i brak pomiaru strzałki, jawnie przyjęty obrót 17.25°:

```sh
python pipeline/05_add_cave.py --cave t08-demo --image-id 102 --plan-id demo-unknown \
  --scraper-dir "$T08_DEMO/scraper" --jsonl "$T08_DEMO/pig.jsonl" --data-dir "$T08_DEMO/plans" \
  --image-sha256 "$T08_IMAGE_SHA" --gps-kataster-object-id KSZ-0033 \
  --entrance-x 2.25 --entrance-y 3.5 --entrance-source 'Syntetyczny symbol otworu mono' \
  --pixels-per-meter 2 --scale-source 'Syntetyczna podziałka: 2 px na 1 m' \
  --north-reference unknown --north-skipped --assumed-grid-angle 17.25 \
  --grid-angle-convention image_x_ccw_from_grid_east \
  --decision-date 2026-10-25 --decision-reason 'Dopuszczono niezweryfikowany obrót syntetyczny 17.25°; brak podstawy rodzaju północy'
```

Nieustalony rodzaj przy zmierzonej pionowej strzałce 0° i osobnym przyjęciu
obrotu wyniku 17.25°:

```sh
python pipeline/05_add_cave.py --cave t08-demo --image-id 102 --plan-id demo-unknown-zero \
  --scraper-dir "$T08_DEMO/scraper" --jsonl "$T08_DEMO/pig.jsonl" --data-dir "$T08_DEMO/plans" \
  --image-sha256 "$T08_IMAGE_SHA" --gps-kataster-object-id KSZ-0033 \
  --entrance-x 2.25 --entrance-y 3.5 --entrance-source 'Syntetyczny symbol otworu mono' \
  --pixels-per-meter 2 --scale-source 'Syntetyczna podziałka: 2 px na 1 m' \
  --north-reference unknown --north-angle 0 --north-source 'Syntetyczna pionowa strzałka; nieznany rodzaj' \
  --assumed-grid-angle 17.25 --grid-angle-convention image_x_ccw_from_grid_east \
  --decision-date 2026-10-25 --decision-reason 'Pomiar strzałki nie ustala rodzaju; dopuszczono niezweryfikowany obrót 17.25°'
```

Do pełnego wywołania dodaj `--dry-run`, aby przeprowadzić T03 i wypisać YAML
bez zapisu. Inspekcja i pełny podgląd nie uruchamiają GDAL. Niepełne dane
w normalnym wywołaniu zwracają błąd, nie tworzą planu produkcyjnego.

## Zapis i kontrola

Skrypt sprawdza pin, obraz i metadane; buduje prywatny staging w katalogu
danych. Zawiera on `image.tif`, `meta.yaml`, `image-identity.json` oraz
opcjonalne JPG dokładnie tej grafiki. Następnie przeprowadza rzeczywisty T04
ze snapshotami, kontrolą pikseli/CRS/transformacji i wynikami poza źródłami.
Dopiero sukces publikuje cały katalog atomowym rename bez zastępowania celu
(Linux renameat2 / macOS renamex_np). Brak wsparcia filesystemu jest błędem;
nie uruchamia zwykłego rename jako zastępstwa. Kontrolne GeoTIFF-y są usuwane razem
z prywatnym katalogiem wyników. Zapisane źródła są gotowe do powtarzalnej generacji:

```sh
python pipeline/02_generate_geotiff.py --data-dir "$T08_DEMO/plans" \
  --cave demo-unknown --output-dir "$T08_DEMO/results"
./scripts/check
```

Brak obrazu, hash, błędne wejście, awaria GDAL lub publikacji oznaczają błąd
i sprzątnięcie stagingu. Istniejący katalog, plik lub dowiązanie docelowe
zawsze blokują dodawanie. Ponowienie nie aktualizuje planu ani ręcznych korekt;
nie ma `--force`. Istniejące plany edytuj osobno w PR z raportem wpływu.
Blokada `.manual-add.lock` serializuje dodawanie. Po przerwaniu procesu może
pozostać blokada/staging; po upewnieniu się, że poprzedni proces zakończył się,
usuń wyłącznie jego nieopublikowane ślady. Nie przejmuj aktywnej blokady.

Nowy wpis rejestru jest wersjonowany **wraz z planem**. Nie dopisuj tego samego
planu do wspólnego `images-v1.json`: konflikt jest błędem. Do PR dołącz cały
nowy katalog źródeł, pochodzenie parametrów, decyzję, wynik T04 i raport wpływu.
[Walidacja](../docs/VALIDATION.md) i [generacja](../docs/GENERATION_OUTPUT.md)
obejmują oba rodzaje rejestru. Stary CLI bez `--output-dir` pozostaje mutujący
do T10. Samo wdrożenie T08 nie dodaje rzeczywistych planów ani nie migruje katalogu.
