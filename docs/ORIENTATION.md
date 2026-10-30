# Północ, deklinacja i geometria (T05/T06)

T05 jawnie reprezentuje niewiedzę. **Żaden z 814 planów nie otrzymał
ustalonego rodzaju północy.** Dla historycznych `unknown` generacja używa wyłącznie kąta
`atan2(D, A)` z `plans[].historical_tfw.parameters` historycznego
[katalogu T02](../data/baseline/2026-10-24/catalogue.json). Katalog jest zwykłym źródłem danych, bez blokady edycji przez przypięty hash.
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
| `orientation.image_sha256` | SHA-256 treści TIFF-a; musi odpowiadać obrazowi i rejestrowi T03 |
| `orientation.historical`, `orientation.decisions` | Zachowane informacje dawnych migracji; nie blokują edycji |

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

Orientację edytuj bezpośrednio w YAML-u, z uzasadnieniem w opisie PR.
Przy ustalonym rodzaju północy ustaw `orientation.mode: reference` oraz
`north.reference` i źródło w `north.evidence`. Model magnetyczny wymaga
wartości, konwencji i epoki deklinacji. Dla nieustalonej północy możesz
zachować `historical_tfw` albo podać `assumed_grid` i `grid_assumption`.
Sama zmiana `north.angle_deg` przy `historical_tfw` nie zmienia obrotu.

Nie ma polecenia `decide` ani walidacji łańcucha hashy. Pliki dawnych
migracji i raporty pozostają archiwum; ich odtwarzanie nie jest częścią
bieżącej kontroli. Build używa katalogu kątów, bez ZIP-a oryginalnych YAML-i.
Hash bieżącej treści katalogu pozostaje w manifeście i kluczu cache.
Walidacja danych, obrazu i wynikowego GeoTIFF-u nadal obowiązuje.

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
Raport pozostaje zapisem odbioru T06; nie jest odtwarzany przez bieżące CI.

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
opisanej w legendzie strzałki rzeczywistego planu. Historyczny odbiór:
[2026-10-25-t06-odbior.md](plans/2026-10-25-t06-odbior.md).

## Nowy plan T08 bez odniesienia historycznego

Nowy plan ma odrębne `cave.dir_id` (katalog), `cave.source_cave_id` (jaskinia
PIG), `image.image_id` (graphics_id) i object_id otworu. Nie jest wpisem T02.
`orientation.origin` opisuje pochodzenie dodanego planu. Nie tworzy blokady
późniejszych edycji; uzasadnienie poprawki należy do PR.

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

Późniejsze zmiany wykonuj bezpośrednio w YAML-u. Przy przejściu na ustalony
rodzaj usuń `grid_assumption` i ustaw `orientation.mode: reference`.
Pełne wywołania i zapis: [MANUAL_ADD.md](../pipeline/MANUAL_ADD.md).
