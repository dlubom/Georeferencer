# Generowanie do osobnego katalogu (T04)

Nowy tryb korzysta z tej samej obowiązkowej [walidacji T03](VALIDATION.md)
i [przypiętego źródła współrzędnych](COORDINATE_SOURCE.md). Czyta źródłowe
YAML-e i obrazy, ale niczego w nich nie zapisuje. Przykład z katalogu repozytorium:

```sh
python pipeline/02_generate_geotiff.py --cave 001131 \
  --output-dir /tmp/georeferencer-results
python pipeline/02_generate_geotiff.py --all \
  --output-dir /tmp/georeferencer-results
```

Wymagane są zależności z `pipeline/requirements.txt` oraz GDAL obsługujący
`gdal_translate -a_gt`; odbiór odbywa się w przypiętym środowisku
`./scripts/check`: GDAL 3.12.4, Linux/amd64. Jawny CSV, jeśli podany, musi
być zgodny z pinem T02; `--gps-kataster-strict` pozostaje opcją zgodności.

## Układ i publikacja

```text
/tmp/georeferencer-results/
  current -> runs/<id>
  runs/<id>/
    manifest.json
    001131/
      image.tfw
      image_georef.tif
      computed.json
```

Przebieg zawiera dokładnie wybrany zestaw planów. `--cave` nie dołącza planu
do poprzedniej partii; publikuje nowy komplet dla tego wyboru. Dla odbioru całego
katalogu użyj `--all`. Przed pierwszym zapisem cały wybrany zestaw przechodzi
preflight T03. Nowy tryb nie obsługuje `--changed` — wybór według zawartości
jest zakresem T10. `--force` nie zmienia zachowania: każde wywołanie nowego
trybu generuje nowy przebieg.

Pin, CSV i rejestr obrazu są weryfikowane i odczytywane z prywatnych snapshotów
tych samych bajtów. Hash YAML-a i jego parsowanie korzystają z jednego odczytu.
GDAL oraz kontrola pikseli używają roboczej kopii TIFF-a sprawdzonej hashem
rejestru T03. Kopia jest usuwana przed publikacją. Dodatkowe hashe przed/po
wykrywają edycję źródeł w czasie generowania; zmiana A→B→A nie przypisuje
hasha A do obliczenia B.

Artefakty powstają w `.staging-<id>`. Dopiero po poprawnym odczycie wszystkich
TIFF-ów i ponownej kontroli hashy wejść powstaje manifest `status: complete`,
staging zostaje przeniesiony do `runs/<id>`, a dowiązanie `current` jest
atomowo podmieniane. Dla spójnego odczytu odbiorca raz rozwiązuje `current`
do konkretnego katalogu przebiegu i korzysta z tej ścieżki dla wszystkich plików.

Błąd GDAL, kontrolnego odczytu albo publikacji zwraca niezerowy status,
usuwa roboczy staging i zachowuje poprzedni poprawny przebieg oraz `current`.
Przy przerwaniu procesu mogą pozostać nieopublikowane katalogi; odbiorca
korzysta wyłącznie z `current`, nigdy ze znalezionego stagingu albo najnowszej
nazwy w `runs`. Poprzednie przebiegi nie są automatycznie usuwane. Mechanizm
opiera się na lokalnym filesystemie z atomowym rename i dowiązaniami; nie
deklaruje trwałości po awarii zasilania ani transakcji na zdalnym magazynie.
Równoległe poprawne przebiegi zachowują własne katalogi; `current` wskazuje
ostatnią udaną podmianę.

Katalog wyników nie może pokrywać się ze źródłowym katalogiem danych ani
zawierać go lub leżeć w nim (także przez dowiązanie). `runs` nie może być
dowiązaniem; istniejący zwykły plik/katalog `current` jest odrzucany.
Każdy krok łańcucha dowiązań plików wejściowych, CSV, pinu i rejestru również
musi leżeć poza katalogiem wyników. Dotyczy to także przejścia przez `current`
do pliku zewnętrznego: publikacja mogłaby wtedy zmienić wejście.

## Co sprawdza odbiór

Generator zapisuje świeżo obliczony TFW z precyzją T03 i przekazuje GDAL
jawną geotransformację odpowiadającą odczytowi **tego** TFW. Stary TFW
obok źródłowego TIFF-a nie wybiera transformacji. Zachowana jest istniejąca
konwersja środka piksela TFW do narożnika GDAL; T04 jej nie zmienia ani nie
rozstrzyga jej poprawności kartograficznej. Obliczenia północy i orientacji
pozostają bez zmian.

Sukces procesu `gdal_translate` nie wystarcza. `gdalinfo` i Pillow niezależnie
odczytują rzeczywisty wynik: GTiff, EPSG:2180, jeden kanał 1-bit, CCITTFAX4,
wymiary, skończona i nieosobliwa transformacja zgodna z obliczoną oraz
zdekodowane piksele zgodne ze źródłem. Porównanie pikseli uwzględnia paletę
jednobitowego TIFF-a. Obrazy źródłowe nadal podlegają rejestrowi SHA-256 T03.

## Manifest v1

Manifest wiąże każdy plan z hashami surowego `meta.yaml` i źródłowych obrazów,
pełnym rekordem wybranego pomiaru CSV (w tym object_id i measurement_id),
parametrami obliczenia, wynikami kontrolnego odczytu i hashami trzech artefaktów.
Zawiera pin release/asset/SHA-256 CSV, hash opisu pinu, rejestru obrazów i kodu
generatora/walidacji/schematu. `computed.json` zawiera tę samą sekcję, którą
stary tryb zapisywał do YAML-a; pełna precyzja obliczeń jest w `parameters`.
Stary TFW i poprzedni GeoTIFF nie są wejściami nowego obliczenia.

Przy tych samych wejściach i środowisku oczekujemy identycznego TFW oraz
zgodnej geometrii i zdekodowanych pikseli. Identyfikatory przebiegu, ścieżki,
manifest i binarny TIFF nie muszą być identyczne. Zgodność z T03 jest osobnym
testem bieżącego kodu na kopiach danych. Integralność historii T02 i jej
przeliczenie są nadal sprawdzane oddzielnie, z zamrożonym kodem i hashami.

## Przejście do T10

Bez `--output-dir` CLI nadal obsługuje dotychczasowy zapis TFW/GeoTIFF i sekcji
`computed` w źródłowym katalogu. Ten tryb pozostaje mutujący i nie otrzymuje
gwarancji transakcyjnych nowego trybu. Istniejące workflow i wydanie pozostają
przy dotychczasowym kontrakcie; ich przełączenie/wycofanie należy do T10/T11.

Testy regresji znajdują się w `tests/test_geotiff_output.py` i uruchamiają
się przez wspólne `./scripts/check` bez nowych zależności.
