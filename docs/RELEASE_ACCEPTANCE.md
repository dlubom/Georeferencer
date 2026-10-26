# Odtworzenie i odbiór wydania T11

Źródła prawdy: [AGENTS.md](../AGENTS.md), [kontrakt wyników](GENERATION_OUTPUT.md),
[walidacja](VALIDATION.md), [orientacja](ORIENTATION.md), [agregacja](AGGREGATION.md),
[QA](QA.md), [pin współrzędnych](COORDINATE_SOURCE.md),
[środowisko i wspólna kontrola](../ci/README.md).
Stan zadania i zależności: [issue #16](https://github.com/dlubom/Georeferencer/issues/16).
Wymagany jest Git, Python 3 hosta i działający Docker Linux/amd64.
Nie są potrzebne sąsiednie repozytoria, poprzednie build/ ani pliki ze starej sesji.

## Dwa zimne buildy jednego commitu

Z **czystego checkoutu** wybranej rewizji:

```sh
git status --porcelain
git rev-parse HEAD
./scripts/check
# Ścieżka nie może istnieć. Nie używaj starego katalogu ani current.
./scripts/reproduce --revision "$(git rev-parse HEAD)" \
  --work-dir /tmp/georeferencer-t11-odbior
```

Skrypt robi dwa niezależne `git clone --no-local --no-checkout`, checkout
tego samego pełnego SHA i dwa `generate --all`, każdy bez katalogu build/.
Nie pożycza obiektów Git i nie kopiuje wyników. Cache warstw Dockera może być
wspólny; cache **wyników planów** jest zimny. Oba buildy mają te same
wersjonowane wejścia i digest/lock środowiska. Obliczenia i kontrole działają
bez sieci, ze źródłami readonly. Początkowe pobranie obrazu wymaga sieci.
Przy ograniczonej przestrzeni dodaj `--conserve-disk`: po pełnym odbiorze
checkoutu a skrypt przenosi jego wyniki do `a-results/` i usuwa wyłącznie
utworzony przez siebie checkout a przed klonowaniem b. Zimne cache i
niezależność checkoutów pozostają; porównanie nadal czyta oba zestawy wyników.

Każdy current jest rozwiązywany raz; ta sama konkretna ścieżka trafia do QA
i pakowania obu trybów. Skrypt wykonuje lokalne próby tag/manual dla obu
checkoutów. Nie wywołuje GitHub Release ani workflow_dispatch.

Dowody w nowym katalogu odbioru:

- `a-generate.log`, `b-generate.log`: pełne generacje, 0 reused;
- `checkouts.json`: wspólna rewizja, osobne checkouty, czystość przed/po;
- `comparison.json`: dokładny katalog i każdy plan — SHA-256 bajtów TFW,
  rzeczywista geotransformacja/CRS/wymiary i SHA-256 zdekodowanych pikseli;
- `a/build/{tag,manual}.zip`, `b/build/{tag,manual}.zip`, logi pakowania
  oraz zewnętrzne `{tag,manual}-qa/qa.json` każdego checkoutu;
- `runtime.log`, `runtime-image`: identyfikacja użytego obrazu;
  pełne wersje narzędzi i hash źródła współrzędnych w comparison/manifest.

Liczba planów i niepewności wynika z katalogu/QA, nie ze stałego limitu.
Snapshot wejściowy T11: 814 planów, 1405 zaakceptowanych niepewności, 0 blokad.
Porównanie nie zastępuje odbioru semantycznego hashem ZIP ani binarnego TIFF.
Daty ZIP i run_id mogą się różnić. TFW muszą być identyczne bajtowo, geometria
i zdekodowane piksele identyczne po rzeczywistym odczycie wszystkich TIFF-ów.

## Porównanie buildów dwóch operatorów

Build autora i build niezależnego reviewera mogą stanowić parę odbioru,
jeśli oba są pełne, zimne, z czystych niezależnych checkoutów tego samego SHA.
Każdy operator wykonuje poniższy samodzielny odbiór jednego checkoutu.
Nie trzeba wtedy generować trzeciej kopii. Dowód musi wskazywać oba commity,
czystość, 0 reused, run_id oraz hashe manifestów i paczek.

Z czystego checkoutu tej wersji kodu, po wskazaniu katalogów obu przebiegów:

```sh
T11_LEFT=$(cd /tmp/t11-left/build/geotiff/current && pwd -P)
T11_RIGHT=$(cd /tmp/t11-right/build/geotiff/current && pwd -P)
mkdir -p build
docker build --platform linux/amd64 --iidfile build/t11-compare-image ci
docker run --rm --platform linux/amd64 --network none --read-only \
  --tmpfs /tmp:rw,nosuid,size=512m \
  --mount "type=bind,source=$PWD,target=/workspace,readonly" \
  --mount "type=bind,source=$T11_LEFT,target=/left,readonly" \
  --mount "type=bind,source=$T11_RIGHT,target=/right,readonly" \
  --mount "type=bind,source=$PWD/build,target=/build" \
  "$(cat build/t11-compare-image)" python pipeline/release_acceptance.py \
  --report /build/comparison.json compare --left /left --right /right
```

Podmień tylko hostowe ścieżki `/tmp/t11-left` i `/tmp/t11-right` na nowe
checkouty uczestników odbioru. Current rozwiązuje się tu raz na operatora.
Raport powstaje poza oboma przebiegami. Brak miejsca lub przerwany checkout
nie jest dowodem buildu: musi zostać pominięty w parze, a poprawnie odebrane
wcześniejsze wyniki i paczki pozostają zachowane.

## Oddzielna kontrola paczki

Z czystego checkoutu tej samej wersji kodu/wejść (ZIP umieść w jego build/):

```sh
./scripts/build accept --report /build/archive-acceptance.json \
  verify --archive /build/tag.zip
```

Odbiorca czyta wszystkie ZipInfo, odrzuca duplikaty **przed** mapowaniem nazw,
braki i dodatkowe pliki, katalogi oraz dowiązania. Sprawdza strumienie/CRC,
hashe i komplet deklarowanych artefaktów. Następnie T09 sprawdza źródła,
aktualność i rzeczywisty GeoTIFF: CRS, transformację, wymiary, jeden kanał
1-bit, CCITTFAX4, zdekodowane piksele względem źródła.

Nowe paczki mają `release.version=t11-v2`. Manifest przebiegu v1 i jego
układ wewnętrzny pozostają bez zmian. Wydanie dodaje obowiązkowe
`release.files`: dokładnie po trzy relacje na plan, każda z polami
`plan_id`, `output`, `archive_path`, `sha256`, uporządkowane po plan_id/output.
Przykład:

```json
{"plan_id":"001094","output":"image_georef.tif","archive_path":"001094_T.D-08.07_Jaskinia_Mroźna.tif","sha256":"<hash oryginalnego wyniku>"}
```

TFW i computed mają odpowiednio `metadane/001094/image.tfw` oraz
`metadane/001094/computed.json`. Nie ma wpisów katalogowych ani drugiej
kopii TIFF-a. [Dokładna reguła nazw](GENERATION_OUTPUT.md) pochodzi z
workflow v0.6.2. Odbiornik wylicza ją ponownie z aktualnych metadanych
sprawdzonych hashem `plans[].inputs["meta.yaml"]`; nie ufa ścieżce ani
przypisaniu deklarowanemu w `release.files`. Sprawdza kompletną listę,
wszystkie hashe i rzeczywisty ZIP, a dopiero potem odtwarza prywatny
przebieg do pełnego QA. Wszystkie surowe ZipInfo przechodzą kontrolę
ścieżek, typów i dowiązań **przed** tworzeniem zbioru/mapy nazw.
Kolizje obejmują NFC i casefold, a duplikaty nigdy nie są gubione.

Wersja kontraktu ZIP zmienia się, bo zmieniają się ścieżki konsumenckie
oraz wymagane dowody mapowania. Nie zmienia to bajtów trzech wyników
planu. Odbiornik nadal rozpoznaje `t11-v1` z dawnymi ścieżkami
`plan_id/{image_georef.tif,image.tfw,computed.json}` i pełnym QA/aktualnością;
nie przyjmuje nieznanych wersji. Samo rozpoznanie starego formatu nie
zwalnia archiwum ze sprawdzenia kodu, środowiska i bieżących wejść.
Historyczne dowody T11 i archiwa nie są przepisywane.

Sekcja release zachowuje tryb, pochodzenie kodu pakowania `release.code`,
run_id i SHA-256 oryginalnego manifestu przebiegu. `release.qa` zapisuje
politykę, liczniki, pełne zaakceptowane wyjątki
(plan/reguła/evidence/basis/reason/sources/close_when) oraz hashe źródeł QA.
Odbiorca usuwa wyłącznie sekcję release, odtwarza manifest przebiegu
serializerem T04 i weryfikuje jego hash.

Manifest nie jest źródłem zgody na wyjątki. Odbiór zawsze ponownie egzekwuje
**wersjonowany** `data/qa/exceptions-v1.json` i porównuje aktualne dowody.
Nowa reguła lub stara podstawa blokują kontrolę. Błędy techniczne/wyników
nie podlegają wyjątkom. Hashe wejść, wybrane pełne rekordy object_id i
measurement_id, pin CSV, kod/schemat, środowisko i fingerprinty pozostają
obowiązkowe. `code.commit/dirty` podaje wrapper na podstawie Git hosta;
produkcyjny CLI package wymaga pełnego SHA i czystego checkoutu zarówno
buildu, jak i bieżącego pakowania. SHA służy
proweniencji, nie kluczowi cache. Niskopoziomowe API służy też próbom
syntetycznym i nie poświadcza samo pochodzenia z Git.

Pakowanie odczytuje gotowy tymczasowy ZIP przez niezależny odbiornik przed
atomowym zastąpieniem paczki. Błąd zachowuje poprzednią paczkę i current.
Raporty są poza przebiegiem. Odbiór nie naprawia archiwum ani źródeł.

## Kontrolowane próby i niezależny reviewer

`./scripts/check` uruchamia również `tests/test_release_acceptance.py` oraz
`test_package_release.py`: oba tryby odrzucają braki, nadmiar, duplikaty,
stare/uszkodzone wyniki, nowe QA/stare wyjątki. Próby CRS, przesunięcia,
kompresji i pikseli aktualizują hash mutowanego pliku, aby odbiór musiał
wykryć faktyczny błąd GeoTIFF. Test błędu odbioru ZIP sprawdza zachowanie
poprzedniej paczki i current. Syntetyczne wyjątki są wyłącznie danymi testów.

Odtwarzalna próba regresji odbioru ZIP (oczekiwane: dokładnie 1 FAIL testu,
potem `Kontrolowana regresja wykryta: True`, kod skryptu 0):

```sh
docker build --platform linux/amd64 --iidfile /tmp/t11-regression-image ci
docker run --rm --platform linux/amd64 --network none --read-only \
  --tmpfs /tmp:rw,nosuid,size=512m \
  --mount "type=bind,source=$PWD,target=/workspace,readonly" \
  "$(cat /tmp/t11-regression-image)" python docs/reports/t11-controlled-regression.py
```

Skrypt mutuje tylko prywatną kopię `package_release.py` w katalogu
tymczasowym; źródła i rejestry pozostają readonly. Poprawny kod musi osobno
przechodzić `./scripts/check`; oczekiwany FAIL mutanta nie jest wynikiem
kontroli całego projektu.

Reviewer otrzymuje wyłącznie ścieżkę repozytorium, rewizję, bazę i ten
dokument. Tworzy własny świeży checkout, czyta instrukcje wersjonowane,
uruchamia kontrolę i odtwarza build/paczkę; nie używa istniejącego build/
ani wcześniejszego /tmp. Raport review zapisuje dokładne komendy, rewizję,
liczby, hashe manifestu/paczki, wyniki odbioru oraz otwarte findings.

Samodzielny odbiór jednego nowego checkoutu (bez uruchamiania dodatkowej
pary z `scripts/reproduce`) używa tych samych narzędzi:

```sh
git clone --no-local /sciezka/do/Georeferencer /tmp/t11-reviewer-checkout
cd /tmp/t11-reviewer-checkout
git checkout --detach PELNE_SHA_PR
./scripts/check
./scripts/build generate --all
T11_RUN="/build/geotiff/$(readlink build/geotiff/current)"
./scripts/build report --run-dir "$T11_RUN" --require-results
./scripts/build package --mode tag --run-dir "$T11_RUN" \
  --reports-dir /build/tag-qa --archive /build/tag.zip
./scripts/build package --mode manual --run-dir "$T11_RUN" \
  --reports-dir /build/manual-qa --archive /build/manual.zip
./scripts/build accept --report /build/archive-acceptance.json \
  verify --archive /build/tag.zip
git status --porcelain
```

Nie wolno automatycznie poprawiać YAML/obrazów, ekstrakcji, migracji,
rejestrów, podstaw wyjątków ani historii T02/T05–T10 po niepowodzeniu.
Nie wolno zmieniać unknown na grid, statusu na verified ani utożsamiać
pomiaru 0°, przyjętego obrotu 0° i null. Naprawa potwierdzonej usterki kodu
wymaga regresji; decyzja o danych wymaga osobnego uzasadnienia i PR.
Merge, tag, wydanie i produkcyjna publikacja wymagają osobnego polecenia.

## Odbiór samej prezentacji ZIP t11-v2

Dla zmiany nazw nie trzeba ponawiać dwóch zimnych buildów T11. Para T11
pozostaje dowodem historycznym generatora; teraz obowiązują pełna kontrola
aktualności i QA wszystkich planów. Konserwatywny fingerprint T10 obejmuje
cały `pipeline/*.py`, więc pierwsza zmiana kodu pakowania wymaga **jednego**
pełnego przeliczenia. Nie zawężamy fingerprintu w celu użycia starego cache.
Kolejne commity dowodów/docs mogą używać wyników sprawdzonych według treści
i środowiska, po ich rzeczywistym odczycie.

Z czystego checkoutu końcowej implementacji:

```sh
./scripts/check
./scripts/build generate --changed
RELEASE_RUN="/build/geotiff/$(readlink build/geotiff/current)"
./scripts/build report --run-dir "$RELEASE_RUN" --require-results
./scripts/build package --mode tag --run-dir "$RELEASE_RUN" \
  --reports-dir /build/readable-release/tag-qa \
  --archive /build/readable-release/tag/geotiff-tatry-local.zip
./scripts/build package --mode manual --run-dir "$RELEASE_RUN" \
  --reports-dir /build/readable-release/manual-qa \
  --archive /build/readable-release/manual/geotiff-tatry-local.zip
./scripts/build accept --report /build/readable-release/tag-acceptance.json \
  verify --archive /build/readable-release/tag/geotiff-tatry-local.zip
./scripts/build accept --report /build/readable-release/manual-acceptance.json \
  verify --archive /build/readable-release/manual/geotiff-tatry-local.zip
```

Reviewer dostaje rewizję, bazę i ten dokument oraz ścieżki do odebranych
paczek/przebiegu. Czyta wersjonowane instrukcje z własnego czystego
checkoutu (dla samej prezentacji wystarcza osobny worktree), przegląda
diff, wykonuje `./scripts/check` oraz `accept verify` obu gotowych
ZIP-ów w przypiętym środowisku. Może zamontować gotowy przebieg/paczki
readonly; nie wykonuje kolejnego zimnego buildu wyłącznie z powodu nazw.
Raporty zapisuje we własnym katalogu poza przebiegiem. Dodatkowo
niezależnie od funkcji mapowania implementacji oblicza historyczną nazwę
z YAML każdego planu; sprawdza wszystkie ZipInfo, CRC, komplet dokładnie
`1 + 3*N` wpisów, SHA-256 i identyczność bajtów trzech wyników z przebiegiem.
Raport podaje rewizję kodu/bazę, wersje środowiska, run_id, oba hashe ZIP,
wyniki i otwarte findings. Zmiana samej dokumentacji nie wymaga ponowienia
kontroli źródeł bez nowego powodu; końcowe paczki mają przejść pełny odbiór.

Kontrolowany powrót starego układu w prywatnej kopii pakującego:

```sh
docker build --platform linux/amd64 --iidfile /tmp/readable-release-image ci
docker run --rm --platform linux/amd64 --network none --read-only \
  --tmpfs /tmp:rw,nosuid,size=512m \
  --mount "type=bind,source=$PWD,target=/workspace,readonly" \
  "$(cat /tmp/readable-release-image)" python docs/reports/readable-release-controlled-regression.py
```

Oczekiwane: jeden FAIL dokładnego układu ZIP, zero błędów środowiska,
`Kontrolowana regresja wykryta: True`, kod skryptu 0. Poprawny kod musi
osobno przejść `./scripts/check`. Nie zaliczamy próby na hostowym GDAL
jako wyniku przypiętego środowiska.
