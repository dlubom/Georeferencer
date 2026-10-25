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

Manifest ZIP ma sekcję `release.version=t11-v1`, tryb, run_id i SHA-256
oryginalnego manifestu przebiegu. `release.qa` zapisuje politykę, liczniki,
pełne zaakceptowane wyjątki (plan/reguła/evidence/basis/reason/sources/close_when)
oraz hashe źródeł QA. Odbiorca odtwarza manifest przebiegu serializerem T04
i weryfikuje jego hash. To addytywny kontrakt wydania; trzy pliki planu
oraz manifest przebiegu v1 nie zmieniają układu.

Manifest nie jest źródłem zgody na wyjątki. Odbiór zawsze ponownie egzekwuje
**wersjonowany** `data/qa/exceptions-v1.json` i porównuje aktualne dowody.
Nowa reguła lub stara podstawa blokują kontrolę. Błędy techniczne/wyników
nie podlegają wyjątkom. Hashe wejść, wybrane pełne rekordy object_id i
measurement_id, pin CSV, kod/schemat, środowisko i fingerprinty pozostają
obowiązkowe. `code.commit/dirty` podaje wrapper na podstawie Git hosta;
produkcyjny CLI package wymaga pełnego SHA i czystego checkoutu. SHA służy
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
