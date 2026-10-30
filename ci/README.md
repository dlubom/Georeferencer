# Wspólna kontrola projektu

Z katalogu repozytorium uruchom:

```sh
./scripts/check
```

Wymagany jest działający Docker z BuildKit i obsługą `linux/amd64` (na Apple Silicon zapewnia ją Docker Desktop). Pierwszy build pobiera obraz i pakiety. Sam zestaw testów działa bez sieci. Repozytorium jest zamontowane tylko do odczytu, a pliki testowe powstają w `/tmp` kontenera. Nie jest potrzebny systemowy Python, GDAL ani sąsiedni katalog gps-kataster.

Ta sama komenda jest jedynym krokiem testowym w `.github/workflows/check.yml`. Uruchamia wszystkie testy znalezione w `tests/`; brak testów lub choć jeden błąd daje niezerowy status. T01 dostarczył 16 wcześniejszych testów, dwa testy CLI z prawdziwym GDAL i test kontraktu workflow. Kontrola obejmuje przypięte współrzędne, bieżące dane, geometrię, generację i QA. Nie odtwarza historycznych migracji ani generatorów. Aktualną liczbę testów wypisuje log kontroli. Nowe zadania dodają testy do tego samego zestawu.

Próba GDAL tworzy syntetyczny TIFF 8×6, jawny rejestr jego tożsamości i przypięty CSV współrzędnych, uruchamia generator, odczytuje wynik przez `gdalinfo` i Pillow, sprawdza EPSG:2180, kompresję, wymiary, skończoną nieosobliwą transformację i zgodność pikseli. Drugi przypadek wymaga błędu CLI dla niezgodnych wymiarów. Nie potwierdza to poprawności orientacji istniejących planów ani konwencji półpiksela — ich odbiór należy do T05/T06.

## Środowisko referencyjne

- Linux/amd64, Ubuntu 24.04, Python 3.12.3.
- GDAL 3.12.4, połączony z PROJ 9.8.1.
- Obraz OSGeo wskazany przez digest manifestu amd64 w `Dockerfile`. Tag jest jedynie opisem; o zawartości rozstrzyga digest.
- Pip 25.3 pobierany jako wheel ze sprawdzeniem SHA-256; bez `apt update` w buildzie.
- Cały graf pakietów Pythona i hashe wybranych wheeli Linux/amd64 są w `requirements.lock`. Instalacja wymaga hashy i gotowych wheeli.
- Pyproj ma własną bibliotekę PROJ. Log kontroli wypisuje osobno jej wersję, wersję PROJ używaną przez GDAL i wszystkie pakiety Pythona.

Źródła obrazu i bootstrapu: [Dockerfile OSGeo v3.12.4](https://github.com/OSGeo/gdal/blob/v3.12.4/docker/ubuntu-small/Dockerfile), [pip 25.3 w PyPI](https://pypi.org/pypi/pip/25.3/json). Ubuntu runnera uruchamia Docker; biblioteki używane przez testy pochodzą z przypiętego obrazu. To odtwarzalność środowiska testów, nie gwarancja identyczności bajtowej obrazu zbudowanego przez Docker ani paczki ZIP wydania.

## Aktualizacja zależności

`pipeline/requirements.txt` określa wejściowe wymagania projektu; `ci/requirements.lock` zamraża ich rozwiązanie dla kontroli. Kontrola porównuje SHA-256 wymagań z nagłówkiem locka, więc zmiana wymagań bez jego aktualizacji kończy się błędem. Workflow generacji i wydania od T10 korzystają z tego samego obrazu przez `scripts/build`.
Fingerprint wyników obejmuje Dockerfile, lock i rzeczywiste wersje narzędzi.

Aktualizację wykonuj jawnie w PR. Z katalogu repozytorium:

```sh
docker build --platform linux/amd64 --target dependency-tools \
  -t georeferencer-dependency-tools ci
docker run --rm --platform linux/amd64 \
  --mount "type=bind,source=$PWD,target=/workspace" \
  georeferencer-dependency-tools python ci/resolve-requirements.py
./scripts/check
```

Resolver potrzebuje sieci i zmienia tylko lock. Pobiera metadane przez pip przypięty w obrazie, zapisuje wersje i SHA-256 zależności bez ich instalacji. Przejrzyj diff całego grafu pakietów. Zmianę digestu GDAL lub wheel pip zweryfikuj u wydawcy oraz zapisz wersje z nowego logu kontroli.

## Wymagana kontrola GitHub

Stała nazwa checka to **`Kontrola projektu`**. Workflow działa dla PR-ów i każdego pusha do `main`, bez filtrów plików i bez warunkowego pomijania joba. Gdy zmieniasz jego nazwę, równocześnie zaktualizuj wymaganą kontrolę w rulesecie GitHub, aby nie pozostawić PR-ów oczekujących na nieistniejącą nazwę.

T01 dodaje osobny aktywny ruleset dla `refs/heads/main`, wymagający tego checka od aplikacji GitHub Actions i testów względem aktualnego `main`, bez wyjątków omijających kontrolę. Przy zmianach ustawień najpierw odczytaj wszystkie istniejące rulesety i ochronę gałęzi; zachowaj ich pozostałe reguły. Stan ochrony jest konfiguracją GitHub, dlatego jego odczyt i link do udanego przebiegu na aktualnej rewizji PR należą do dowodów odbioru.

## Generacja i wydanie T10

```sh
./scripts/build generate --changed
./scripts/build report --run-dir /build/geotiff/current --require-results
./scripts/build package --mode manual --run-dir /build/geotiff/current \
  --reports-dir /build/release-qa --archive /build/geotiff-tatry-local.zip
```

Kontener używa tego samego digestu i locka co testy, bez instalacji apt/pip
w workflow, bez sieci podczas pracy. Checkout jest readonly; `build/` stanowi
osobny zapisywalny mount `/build`. Polecenie package tworzy lokalny ZIP,
nie publikuje wydania. Kontrakt manifestu/cache i obu bramek publikacji opisuje
[GENERATION_OUTPUT.md](../docs/GENERATION_OUTPUT.md).

Generacja działa dla każdego PR-a i pusha na main, bez filtrów ścieżek,
z pełną historią Git. Publikuje artefakty i raporty na 14 dni, bez zapisu bota
ani bypassów ochrony. Ręczna generacja z niepewnym zakresem wymusza pełny build.
Tag i ręczne wydanie mają tę samą bezwarunkową bramkę QA+ZIP. Brak plików,
manifestu, aktualności lub dopuszczenia T09 zatrzymuje publikację już w T10.

`./scripts/check` najpierw wykonuje `tests/host/` w systemowym Pythonie 3
(biblioteka standardowa, realny Git i wrapper Dockera), następnie cały zestaw
`tests/` w przypiętym kontenerze. Obraz GDAL nie zawiera Git; testy hostowe
sprawdzają dokładnie część uruchamianą na hoście. Oba zestawy są obowiązkowe,
a dowody podają osobno ich liczby. Odbiór bieżącej geometrii pozostaje w kontenerze.


ZIP z `mkstemp` powstaje w kontenerze root z trybem 0600. Po udanej
bramce QA/ZIP workflow przyznaje odczyt gotowej paczki użytkownikowi
runnera przez `sudo chmod a+r`, przed hostową akcją publikującą. Bajty
archiwum pozostają niezmienione. Publikująca akcja ma jawne
`overwrite_files: false`; istniejący asset nie jest zastępowany.
Regresja w przypiętym kontenerze sprawdza rzeczywisty odczyt drugim UID
przed i po tym kroku, bez zależności od mapowania UID w Docker Desktop.

## Dowody w PR

Pełny odbiór wydania, dwa czyste zimne buildy i instrukcja niezależnego
reviewera: [RELEASE_ACCEPTANCE.md](../docs/RELEASE_ACCEPTANCE.md).
`scripts/reproduce` wykonuje wyłącznie lokalne próby, bez publikacji.

Podaj wynik `./scripts/check`, liczbę testów, wersje środowiska z logu, link do CI na aktualnej rewizji oraz wynik próby z celowo wprowadzoną regresją. Dane próbne trzymaj w katalogach tymczasowych. Gdy zmiana dotyczy danych, dołącz listę planów i pól oraz uzasadnienie zgodnie z [planem prac](../docs/plans/2026-10-24-jakosc-danych-i-ci.md). Zielony smoke test nie zastępuje kryteriów konkretnego zadania.
