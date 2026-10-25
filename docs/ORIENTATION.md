# Północ, deklinacja i geometria (T05/T06)

T05 jawnie reprezentuje niewiedzę. **Żaden z 814 planów nie otrzymał
ustalonego rodzaju północy.** Dla historycznych `unknown` generacja używa wyłącznie kąta
`atan2(D, A)` z `plans[].historical_tfw.parameters` historycznego
[katalogu T02](../data/baseline/2026-10-24/catalogue.json). Hash katalogu
jest przypięty w `orientation.py`, a hash TFW i ID planu zapisane w YAML-u.
Nie odczytuje kąta z `computed`, bieżącego sidecara, sumy dawnych poprawek
ani `recalculated-v1.3.1.json`. Zgodność historyczna nie potwierdza
poprawności geodezyjnej planu.

## Pola i ich znaczenie

| Pole | Znaczenie |
| --- | --- |
| `north.reference` | `unknown`, `geographic`, `magnetic`, `grid` |
| `north.angle_deg` | Kąt strzałki; samo 0° niczego nie rozstrzyga. T08: null przy jawnym braku pomiaru nowego unknown |
| `north.angle_origin` | `measured` — pomiar, także 0°; `assumed` — przyjęcie, także 0°; `unknown` — brak dowodu pochodzenia |
| `north.evidence` | Wymagane źródło/uzasadnienie ustalonego rodzaju: np. konkretny plan, legenda, strona, opis autora |
| `declination_deg` | Zachowana liczba historyczna; aktywna deklinacja modelu magnetic wymaga udokumentowanej podstawy |
| `declination.status` | `unknown` albo `documented` |
| `declination.basis` | Źródło wartości lub opis brakującej podstawy |
| `declination.sign_convention` | Dla `documented`: `east_positive` — wschodnia dodatnia, zachodnia ujemna |
| `declination.epoch` | Dla północy magnetycznej wymagana data lub epoka źródłowej deklinacji; przy modelu podać także model i jego podstawę w `basis` |
| `orientation.mode` | `historical_tfw` przy historycznej nieustalonej północy; `reference` przy ustalonej; `assumed_grid` dla nowego unknown T08 |
| `orientation.status` | Nadal `unverified`; modele T06 nie potwierdzają źródłowych metadanych |
| `orientation.uncertainty_reason` | Jawny powód niepewności, dostępny w QA, computed i manifeście |
| `orientation.image_sha256` | SHA-256 treści TIFF-a objętego decyzją; musi odpowiadać obrazowi i rejestrowi T03 |
| `orientation.historical` | Niezmienny hash katalogu T02, ID planu i hash historycznego TFW |
| `orientation.decisions` | Jawny łańcuch zmian wejść orientacji: hash przed/po, działanie, powód i data |

Migracja oznacza `all_skipped: true` jako `angle_origin: assumed`.
Pozostałe plany dostają `unknown`: samo `all_skipped: false` ani kąt 0°
nie stanowią dowodu rodzaju północy lub pomiaru. Oryginalne pola i precyzja,
w tym ręczne korekty, pozostają bez zmian. Historyczne `declination_deg`
nie dostaje domniemanej konwencji ani epoki: status jest `unknown`,
wartość nie uczestniczy w nowej generacji historycznego kąta.

## Zmiany po migracji

Bieżące współrzędne z przypiętego CSV, kliknięcie otworu i skala pozostają
aktywne. Zmiana skali zmienia długość wektorów TFW, a zmiana współrzędnych
lub kliknięcia — ich zakotwiczenie. Żadna z nich nie zmienia historycznego
kąta, nawet gdy inna długość geograficzna dawniej zmieniałaby zbieżność.
Nie istnieje ukryta poprawka kierunku przeliczana z nowej pozycji.

Wejścia orientacji to całe sekcje `north`, `declination`, `image` i wartość
`declination_deg` oraz `orientation.image_sha256` (treść TIFF-a). Ich hash jest porównywany z migracją oryginalnego YAML-a
T02, a następnie z łańcuchem jawnych decyzji. Obraz jest objęty również
niezależną walidacją i rejestrem T03. Sama zmiana rejestru nie uprawnia
do dziedziczenia orientacji T02 przez nowy obraz: wymaga także nowego
`orientation.image_sha256` i decyzji obejmującej ten hash. Zmiana hasha/ID historycznego TFW jest
odrzucana nawet z decyzją. Nie odświeżaj archiwum, katalogu ani ich hashy.

Po edycji danych jednego planu zapisz decyzję (przed generowaniem):

```sh
python pipeline/orientation.py decide --meta data/caves/001131/meta.yaml \
  --date 2026-10-25 --reason 'Konkretne źródło i uzasadnienie zmiany; świadome zachowanie kąta T02.'
```

Komenda dopisuje hash przed/po i działanie, wybiera tryb odpowiadający
zadeklarowanemu rodzajowi; nie zmienia odniesienia T02 i nie nadaje statusu
zweryfikowanego. Pusty powód, błędna data, niespójny łańcuch i brak faktycznej
zmiany są błędami. Nie jest to potwierdzenie prawdziwości dostarczonego źródła;
źródło oraz diff decyzji ocenia reviewer PR.

Przejście np. na `geographic` wymaga `north.evidence` i opisania pochodzenia
kąta, następnie decyzji. `magnetic` wymaga dodatkowo udokumentowanej wartości,
konwencji i epoki deklinacji. T06 dostarcza modele `geographic`, `magnetic` i `grid`, w obu trybach CLI.
Brak źródła, wymaganej deklinacji albo decyzji nadal blokuje preflight.
Nie stosuje się zastępczo wzoru historycznego.
Brak metadanych T05 również jest błędem. Dodanie planu bez odniesienia T02
używa osobnego kontraktu T08 opisanego niżej; nie zgaduje jego orientacji.

## Migracja i niezależna historia

[Raport migracji](../data/migrations/t05-north.json) wymienia każdy plan,
cztery dodane pola/sekcje przed i po, hashe YAML-i oraz historycznego TFW.
Osobno deklaruje brak zmiany wejść położenia i skali. Nie przypisuje nowemu
buildowi identyczności pełnych TFW: bieżący CSV i skala/otwór pozostają aktywne.
Nie zmienia `computed` ani zapisanych historycznych TFW.

Oryginalne 814 YAML-i i kod QA są zachowane bajtowo w
[data/history/t02-inputs.zip](../data/history/t02-inputs.zip), pod oryginalnymi
ścieżkami. Każdy wpis jest weryfikowany **oryginalnym** SHA-256 z katalogu T02.
Cały dotychczasowy `data/baseline/2026-10-24`, jego hashe, kopie kodu,
parquety i obrazy pozostają identyczne. Audyt i przeliczenie historii czytają
archiwum i zamrożony generator; nie zależą od bieżących YAML-i ani modelu T05.
Dla czystego checkoutu T02 bez archiwum nadal odczytywane są oryginalne ścieżki.

Raporty T05 i T06 opisują historyczne wejścia swoich etapów. Po późniejszych
edycjach katalogu, w tym agregacji T07, ich odtworzenie nie czyta bieżących
`meta.yaml`. Funkcja `migrate_north.migrated_bytes(original, plan)` odtwarza
dokładne bajty T05 ze zweryfikowanego oryginału T02 i wpisu jego katalogu;
nie odczytuje plików ani nie zapisuje danych. Test migracji odtwarza 814
oryginałów w katalogu tymczasowym, porównuje cały raport i pierwotne hashe
przed/po, a także sprawdza odmowę nadpisania późniejszej edycji. Test T06
używa tych samych odtworzonych bajtów T05 i sprawdza `meta_sha256` zapisany
w historycznym raporcie oraz wyniki geometrii. Osobno nadal badane są
bieżące YAML-e: ich walidacja, decyzje i 814 kątów względem TFW T02.

W przypiętym środowisku można ponowić odbiór bez zapisu bieżących YAML-i:

```sh
PYTHONPATH=pipeline python - <<'PY'
import json
import tempfile
from pathlib import Path
from migrate_north import migration
from orientation import load_context

with tempfile.TemporaryDirectory() as temporary:
    for plan_id, raw in load_context()['originals'].items():
        path = Path(temporary) / 'data/caves' / plan_id / 'meta.yaml'
        path.parent.mkdir(parents=True)
        path.write_bytes(raw)
    report, _ = migration(temporary)
Path('/tmp/t05-north.json').write_text(
    json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
PY
cmp /tmp/t05-north.json data/migrations/t05-north.json
python pipeline/catalogue_baseline.py verify
python pipeline/catalogue_baseline.py recalculate --output /tmp/recalculated.json
cmp /tmp/recalculated.json data/baseline/2026-10-24/recalculated-v1.3.1.json
./scripts/check
```

`--apply` jest jawną opcją zapisu migracji. Narzędzie przyjmuje tylko
oryginalne bajty lub dokładny już zmigrowany wynik i odrzuca obce edycje;
nie służy do aktualizacji planów po późniejszych decyzjach. Archiwum powstało
jednorazowo przed migracją, z kontrolą wszystkich oryginalnych hashy.

Nowy tryb T04 snapshotuje także katalog T02 i archiwum YAML-i; hashe oraz
status/powód trafiają do manifestu. Kontrola ścieżek, GeoTIFF i atomowa
publikacja pozostają obowiązkowe. QA dodaje cztery kolumny do `summary.csv`;
wersjonowane stare CSV nie są nadpisane. Przebudowa QA i wyjątków to T09,
przełączenie workflow to T10/T11. Modele i półpiksel T06 opisano poniżej.


## Modele T06 i znaki

`north.angle_deg = α` to kąt strzałki zgodnie z ruchem wskazówek zegara od
pionu w górę obrazu (`atan2(dx, -dy)` w UI). Obraz ma x w prawo, y w dół.
Macierz TFW to `[[A,B],[D,E]] = mpp * [[cos r,sin r],[sin r,-cos r]]`.
Strzałka `(sin α,-cos α)` po transformacji ma azymut siatkowy `α-r`.

`γ` to zbieżność zwracana przez `Proj('EPSG:2180').get_factors(lon,lat)`
w stopniach. Na wschód od 19° jest dodatnia: północ geograficzna biegnie
ku zachodowi od pionu siatki (azymut `-γ`). `δ` jest deklinacją
`east_positive`: północ magnetyczna ma azymut geograficzny `δ`, a siatkowy
`δ-γ`. Z tych kierunków wynikają modele:

| Rodzaj | Obrót r | Używane poprawki |
| --- | --- | --- |
| geographic | `α + γ` | PROJ zamiast dawnego przybliżenia o błędnym znaku |
| magnetic | `α + γ - δ` | deklinacja z podstawą, konwencją i epoką; brak automatycznego modelu pola |
| grid | `α` | siatka **EPSG:2180**, bez ponownej zbieżności ani deklinacji |
| unknown | `atan2(D,A)` zapisanego TFW T02 | żadnej poprawki z bieżących współrzędnych |

Skala jest lokalną skalą podobieństwa `mpp=1/pixels_per_meter` w metrach
EPSG:2180. T06 nie zmienia ppm, nie modeluje deformacji planu, wysokości,
redukcji terenowych ani dokładności źródłowego pomiaru. Model jest lokalny
w punkcie otworu; nie jest nieliniowym przekształceniem całego planu.
Podstawa: [API pyproj get_factors](https://pyproj4.github.io/pyproj/stable/api/proj.html#pyproj.Proj.get_factors).

## Kliknięcie, narożnik i środek piksela

UI rysuje obraz przez `drawImage(...,0,0,width,height)` i dzieli współrzędne
kliknięć przez skalę wyświetlania (`index.html`, `toOrig`). Początek `(0,0)`
jest narożnikiem obrazu, a środek pierwszego piksela ma `(.5,.5)`. To układ
[GDAL](https://gdal.org/en/stable/tutorials/geotransforms_tut.html).
TFW opisuje środek pierwszego piksela jako `(C,F)` z indeksami `(0,0)`.
Dla kliknięcia UI `(x,y)` i jego współrzędnych `(X,Y)`:

```
C = X - A*(x-.5) - B*(y-.5)
F = Y - D*(x-.5) - E*(y-.5)
GT = [C-.5*A-.5*B, A, B, F-.5*D-.5*E, D, E]
```

Generator najpierw zaokrągla TFW (A,D,B,E: 10 miejsc, C,F: 6 miejsc),
a GDAL dostaje geotransformację tego zapisu. W przejściowym CLI GDAL
odczytuje ten sam sidecar. Nie dodajemy kolejnego półpiksela do kliknięcia.
Testy odczytują rzeczywisty GeoTIFF i sprawdzają otwór, drugi punkt oraz
relację `GDAL(.5,.5) = TFW(0,0)`, również przy obrocie.

T05 utożsamiał kliknięcie z indeksem środka piksela. T06 przesuwa C,F o
`(.5*(A+B), .5*(D+E))`, także dla `unknown`, zachowując jego **kąt**,
bieżący otwór, kliknięcie i skalę. Nie migruje YAML-i ani źródłowych TFW.
[Raport 814 planów](reports/t06-geometry-impact.json) porównuje wyniki
obu generatorów na identycznych wejściach zapisanych po migracji T05.
Po T07 zachowuje pierwotne hashe i wyniki; test odtwarza jego wejścia z T02,
nie zastępuje ich aktualnymi YAML-ami. Polecenie `geometry_impact.py`
z [odbioru T06](plans/2026-10-25-t06-odbior.md) czyta katalog danego checkoutu;
po zmianach T07 opisuje nowe wejścia i nie służy do nadpisania raportu T06.
Zgodność historycznego
kąta jest odrębna od testu poprawnej geometrii modelu ustalonej północy.

## Tolerancje i dowody T06

Dla punktu UI `(x,y)` błąd każdej współrzędnej z zaokrągleń TFW nie przekracza
`0.5e-6 + (abs(x-.5)+abs(y-.5))*0.5e-10` metra. Test dodaje `2e-9 m` na
odczyt GDAL i działania double na współrzędnych PL-1992. To kontrola błędu
numerycznego, nie deklaracja terenowej dokładności planu.

Niezależny wzorzec kierunku to znormalizowana różnica projekcji dwóch
punktów `(lon,lat±0.0001°)` na tym samym południku; test nie wywołuje
`get_factors`. Symetryczna sieczna ma błąd drugiego rzędu kroku; dopuszczamy
`2e-8` w komponencie wektora jednostkowego (2 µm na 100 m), uwzględniając
odejmowanie współrzędnych rzędu 500 km i numeryczne pochodne PROJ. Sprawdzamy
17°, 19° i 21°, także z niezerową strzałką. Dla magnetycznej wzorzec południka
obracamy o jawną dodatnią lub ujemną deklinację. Test halfpixel nie używa
produkcyjnej funkcji konwersji TFW jako wzorca.

Manifest i computed zawierają addytywną sekcję `geometry` z wersją modelu,
konwencją piksela i jednostką skali. `orientation` zachowuje również pełne
`north`, `declination` i `declination_deg`, w tym źródło, podstawę, konwencję
i epokę. Status pozostaje `unverified`; udany test modelu nie weryfikuje
opisanej w legendzie strzałki rzeczywistego planu. Odbiór i odtworzenie raportu:
[2026-10-25-t06-odbior.md](plans/2026-10-25-t06-odbior.md).

## Nowy plan T08 bez odniesienia historycznego

Nowy plan ma odrębne `cave.dir_id` (katalog), `cave.source_cave_id` (jaskinia
PIG), `image.image_id` (graphics_id) i object_id otworu. Nie jest wpisem T02.
`orientation.historical` jest niedozwolone, również skopiowane z innego planu.
Istniejący plan T02 nie może zastąpić swojej podstawy przez `origin` T08.

Początkowe `orientation.origin` zawiera `kind: manual_t08`, plan_id, datę,
powód i hash początkowych wejść orientacji. Ten sam korzeń jest utrwalony
w `image-identity.json`, publikowanym razem z obrazem i YAML-em; różnica
korzeni lub konflikt z rejestrem wspólnym blokuje T03. To wersjonowany dowód
decyzji operatora podlegający review, nie podpis ani automatyczna weryfikacja
źródłowej północy. Nie jest automatycznie odświeżany przy edycji.

Nowy `unknown` ma `orientation.mode: assumed_grid` i osobną mapę
`orientation.grid_assumption`: skończony `rotation_deg`, `crs: EPSG:2180`,
`convention: image_x_ccw_from_grid_east` i niepusty `reason`.
W tej konwencji r to kąt osi x obrazu przeciwnie do zegara od wschodu siatki:
A=mpp*cos(r), D=mpp*sin(r). Nie jest to kąt strzałki północy.
**Przyjęcie obrotu względem siatki nie dowodzi rodzaju źródłowej północy.**
`north.reference` pozostaje unknown, status pozostaje unverified. Nie dodaje
się zbieżności ani deklinacji; współrzędne, ppm i kliknięcie pozostają aktywne.

`--north-skipped` zapisuje `angle_deg: null`, `angle_origin: unknown`,
`all_skipped: true`. Zmierzona pionowa strzałka to jawne `angle_deg: 0.0`,
`angle_origin: measured`, `all_skipped: false` ze źródłem, także przy
nieustalonym rodzaju. Osobne przyjęcie r może mieć wartość 0° lub dowolny
skończony kąt; żadne z tych zer nie jest domyślnym pomiarem.

Nowe geographic/grid/magnetic używają modeli T06, ze źródłem rodzaju oraz
pomiaru. Magnetic dodatkowo wymaga dokumentowanej deklinacji, konwencji
i epoki. Wszystkie pozostają unverified. Nie mają historycznego TFW.

Późniejsze zmiany wejść wymagają `orientation.py decide` tak samo jak w T05.
`grid_assumption` uczestniczy w hashu, a działaniem dla nowego unknown jest
`accept_grid_assumption`. Przejście na ustalony rodzaj wymaga usunięcia
przyjęcia, podania dowodów i decyzji `establish_reference`; korzeń początkowy
pozostaje. Nie wolno zmieniać korzenia zamiast dopisać decyzji.
Pełne wywołania i zapis: [MANUAL_ADD.md](../pipeline/MANUAL_ADD.md).

Kod opisany oryginalnymi hashami raportu T06 jest zachowany osobno
w `data/history/t06-code/`; test sprawdza te bajty hashami raportu oraz
niezależnie porównuje bieżącą geometrię wszystkich 814 historycznych wejść.
Aktualizacja kodu T08 nie przepisuje raportu ani hashy T06.
