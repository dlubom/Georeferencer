# Generowanie według treści do osobnego katalogu (T04/T10)

Każde standardowe generowanie korzysta z tej samej obowiązkowej [walidacji T03](VALIDATION.md)
i [przypiętego źródła współrzędnych](COORDINATE_SOURCE.md). Czyta źródłowe
YAML-e i obrazy, ale niczego w nich nie zapisuje. Przykład z katalogu repozytorium:

```sh
python pipeline/02_generate_geotiff.py --cave 001131 \
  --output-dir /tmp/georeferencer-results
python pipeline/02_generate_geotiff.py --all \
  --output-dir /tmp/georeferencer-results
```

Referencyjne uruchomienie lokalne i CI używa tego samego pinu środowiska:

```sh
./scripts/build generate --changed
./scripts/build report --run-dir /build/geotiff/current --require-results
# Próba wydania, bez komunikacji z GitHub:
./scripts/build package --mode manual --run-dir /build/geotiff/current \
  --reports-dir /build/release-qa --archive /build/geotiff-tatry-local.zip
```

Wrapper montuje checkout readonly w `/workspace`, a ignorowane `build/` w
`/build`; kontener pracuje bez sieci. Bezpośredni Python domyślnie zapisuje
wyniki w `build/geotiff`, raporty w `build/qa`. Wymagane są zależności z
`pipeline/requirements.txt` oraz GDAL obsługujący
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

`--all` i `--changed` budują **pełny aktualny katalog**. `--changed` nie
używa mtime: wykonuje pełny preflight i skan treści, a poprawne wyniki kopiuje
do nowego kompletnego przebiegu. Usunięte plany znikają z nowego manifestu.
Również katalog bez YAML jest wejściem do walidacji, zamiast cichego pominięcia.
Zbiór katalogów jest kontrolowany ponownie przed atomową publikacją.
`--cave` publikuje jawny podzbiór, bez dołączania do poprzedniej partii;
nie poświadcza całego katalogu w bramce QA. `--force` pomija cache.

## Zakres Git i cache T10

W CI `build_changes.py` działa na hoście z Git. Push używa `before..after`,
a PR `merge-base(base,head)..head`, z obu końców rename (delete + add).
Uwzględnia wszystkie commity, także dokumentację w ostatnim commicie,
obrazy, nowe/usunięte plany i lokalne rejestry. Kod, środowisko, pin, wspólny
rejestr i nieznane wejście wymuszają cały katalog. Brak/niepoprawny ref,
zerowa baza, płytka historia, nieprzodkowy push lub nieznany rodzaj zdarzenia
wymusza pełne przeliczenie. Zakres jest zapisywany w `build/selection.json`
i `manifest.build.selection`; bezpośredni CLI przyjmuje `--selection-file`.
Lokalne wywołanie bez zakresu korzysta z pełnego skanu treści.

Zakres Git nigdy nie dowodzi aktualności. Fingerprint każdego planu obejmuje
surowy YAML i wszystkie obrazy, lokalny rejestr **albo jawny brak**, wspólny
rejestr, pin z hashem CSV i pełny wybrany pomiar, orientację, parametry,
źródła T02, kod pipeline/schemat, wymagania/lock/Dockerfile/wrapper oraz
wersje Python, GDAL (także build/PROJ), pyproj/PROJ i zainstalowanych pakietów.
Nie zależy od mtime, daty uruchomienia, ścieżek checkoutu ani SHA commitu.
Zmiana wspólnego wejścia unieważnia konserwatywnie wszystkie plany.

Cache odczytuje tylko raz rozwiązany `current`. Zgodny fingerprint nie zwalnia
z walidacji T03 ani rzeczywistego odczytu GeoTIFF. Brak, zły hash/JSON,
niekompletny/dodatkowy plik, duplikat albo stary manifest oznacza regenerację.
Kopie cache są zwykłymi plikami, niezależnymi od poprzednich przebiegów;
są ponownie odbierane po skopiowaniu do stagingu. Manifest `build` podaje
osobno `generated` i `reused`. Błąd późnego odbioru nie publikuje części partii.

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
obok źródłowego TIFF-a nie wybiera transformacji. T06 jawnie mapuje kliknięcia UI w układzie narożnika GDAL i C,F w układzie
środków TFW, z poprawką półpiksela. Modele północy, konwencje i tolerancje
opisuje [ORIENTATION.md](ORIENTATION.md). Historyczny `unknown` zachowuje wyłącznie
kąt T02; współrzędne i skala pozostają bieżące. Ustalony rodzaj
używa modelu T06 i nadal ma status `unverified`.

Sukces procesu `gdal_translate` nie wystarcza. `gdalinfo` i Pillow niezależnie
odczytują rzeczywisty wynik: GTiff, EPSG:2180, jeden kanał 1-bit, CCITTFAX4,
wymiary, skończona i nieosobliwa transformacja zgodna z obliczoną oraz
zdekodowane piksele zgodne ze źródłem. Porównanie pikseli uwzględnia paletę
jednobitowego TIFF-a. Obrazy źródłowe nadal podlegają rejestrowi SHA-256 T03.

## Manifest v1

T10 rozszerza v1 o `content_version: t10-content-v1`, `environment`,
`plans[].fingerprint` oraz `build.generated/reused/selection`. Stary przebieg
bez tych dowodów jest nieaktualny i wymaga regeneracji; historia pozostaje
czytelna. `implementation` używa ścieżek względem repozytorium.

Manifest wiąże każdy plan z hashami surowego `meta.yaml` i źródłowych obrazów,
pełnym rekordem wybranego pomiaru CSV (w tym object_id i measurement_id),
parametrami obliczenia, wynikami kontrolnego odczytu i hashami trzech artefaktów.
Zawiera pin release/asset/SHA-256 CSV, hash opisu pinu, rejestru obrazów i kodu
generatora/walidacji/schematu. `computed.json` zawiera tę samą sekcję, którą
stary tryb zapisywał do YAML-a; pełna precyzja obliczeń jest w `parameters`.
Bieżący TFW obok obrazu i poprzedni GeoTIFF nie są wejściami obliczenia.
T05 dodaje snapshoty katalogu historycznego T02 i archiwum oryginalnych YAML-i
(`orientation_sources`), hash modułu `orientation.py` oraz sekcję `orientation`
każdego planu i `computed.json`: rodzaj północy, pochodzenie kąta, status,
powód niepewności, historyczne odniesienie i decyzje. T06 dodaje sekcję `geometry` w manifeście/computed i pełne źródłowe sekcje
`north`/`declination` oraz `declination_deg` w `orientation`. Są to addytywne
rozszerzenia manifestu v1.

Przy tych samych wejściach i środowisku oczekujemy identycznego TFW oraz
zgodnej geometrii i zdekodowanych pikseli. Identyfikatory przebiegu, ścieżki,
manifest i binarny TIFF nie muszą być identyczne. Zgodność z T03 jest osobnym
testem bieżącego kodu na kopiach danych. Integralność historii T02 i jej
przeliczenie są nadal sprawdzane oddzielnie, z zamrożonym kodem i hashami.

## Migracja odbiorców i bramka wydania T10

Produkcja zapisuje wyłącznie osobny przebieg. Usunięto mutujący zapis
`computed` i TFW do źródeł; historyczne YAML/TFW nadal są zachowane.
`computed.json` zastępuje zapis wyliczonej sekcji do YAML. Modele T06,
precyzja TFW, źródło historycznego kąta i assumed_grid T08 są niezmienione.

Workflow generacji działa dla całego pusha i PR, bez filtrów plików,
w przypiętym środowisku. Publikuje manifest, komplet wyników i raporty jako
artefakty (14 dni), przy uprawnieniu contents:read. Cache Actions jest
niewiążącą optymalizacją; nie zastępuje odbioru. Nie ma commitu/pusha bota.

`package_release.py` jest jedyną wspólną bramką workflow tag/manual.
Raz rozwiązuje current, wykonuje pełne QA T09 **ze wskazanym przebiegiem**,
sprawdza aktualność kodu/środowiska/źródeł i dokładny komplet wyników.
Raporty powstają poza przebiegiem. Nowa lub stara niedopuszczona niepewność,
stary wyjątek oraz błąd techniczny/wyniku blokują ZIP. Rejestr wyjątków
pozostaje niezmieniony; narzędzie nie ma automatycznego odświeżania podstaw.

ZIP zawiera `manifest.json` i dokładnie trzy zadeklarowane pliki w każdym
katalogu `plan_id/`. To świadoma zmiana poprzedniego płaskiego archiwum TIFF:
identyfikatory i pochodzenie nie giną, a wynik ma komplet do niezależnego
odbioru. Nie ma globu po TIFF-ach. Bajty plików są sprawdzane przy zapisie ZIP,
komplet i źródła ponownie po QA; ZIP zastępuje wcześniejszą paczkę atomowo.
Workflow tworzy wydanie dopiero po sukcesie tej samej komendy dla obu zdarzeń.
Próby lokalne nigdy nie publikują. T11 niezależnie sprawdzi te bramki i doda
odbiór odtwarzalności z czystego checkoutu.

Testy regresji znajdują się w `tests/test_geotiff_output.py` i uruchamiają
się przez wspólne `./scripts/check` bez nowych zależności.


T08 dodaje wejście `image-identity.json` dla nowych ręcznych planów. Hash,
parsowanie i początkowa decyzja korzystają z tego samego snapshotu; plik
uczestniczy w `plans[].inputs`, kontroli dowiązań i zmian przed publikacją.
Brak tego wejścia jest także snapshotowany, bez późniejszego ukrytego odczytu.
Nowy unknown bez T02 używa wyłącznie jawnie przyjętego obrotu `assumed_grid`,
z EPSG:2180, konwencją i powodem zachowanymi w orientation manifestu/computed.
Nie otrzymuje statusu grid ani verified. [Kontrakt T08](ORIENTATION.md).

## Odbiór istniejącego przebiegu T09

`python pipeline/03_report.py --run-dir /tmp/georeferencer-results/current
--require-results --reports-dir /tmp/georeferencer-qa` sprawdza dokładny
komplet bieżącego katalogu, manifest, hashe i zgodność istotnych wejść oraz
ponownie odczytuje rzeczywisty GeoTIFF. Brak wyników bez wskazania przebiegu
nie oznacza błędu źródeł. Stary TFW w danych nie jest dowodem aktualności.
[Reguły, stany i wyjątki](QA.md). Workflow i pakowanie wymagają tego odbioru już w T10.
