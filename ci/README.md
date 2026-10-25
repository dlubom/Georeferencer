# Wspólna kontrola projektu

Z katalogu repozytorium uruchom:

```sh
./scripts/check
```

Wymagany jest działający Docker z BuildKit i obsługą `linux/amd64` (na Apple Silicon zapewnia ją Docker Desktop). Pierwszy build pobiera obraz i pakiety. Sam zestaw testów działa bez sieci. Repozytorium jest zamontowane tylko do odczytu, a pliki testowe powstają w `/tmp` kontenera. Nie jest potrzebny systemowy Python, GDAL ani sąsiedni katalog gps-kataster.

Ta sama komenda jest jedynym krokiem testowym w `.github/workflows/check.yml`. Uruchamia wszystkie testy znalezione w `tests/`; brak testów lub choć jeden błąd daje niezerowy status. T01 dostarczył 16 wcześniejszych testów, dwa testy CLI z prawdziwym GDAL i test kontraktu workflow. T02 rozszerza zestaw o weryfikację przypiętego CSV, raport aktualizacji, integralność 814 historycznych planów i odtwarzalność ich oddzielnego przeliczenia. T03 dodaje walidację całego bieżącego katalogu i przypadków błędnych; historyczne przeliczenie używa zamrożonych kopii starego kodu, kontrolowanych hashami T02. Aktualną liczbę testów wypisuje log kontroli. Nowe zadania dodają testy do tego samego zestawu.

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

`pipeline/requirements.txt` określa wejściowe wymagania projektu; `ci/requirements.lock` zamraża ich rozwiązanie dla kontroli. Kontrola porównuje SHA-256 wymagań z nagłówkiem locka, więc zmiana wymagań bez jego aktualizacji kończy się błędem. Dotychczasowe workflow generacji i wydania nadal korzystają z własnego środowiska; ich przełączenie jest zakresem T10/T11.

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

**Okres przejściowy do T10:** stary `generate-geotiff.yml` próbuje dopisać commit bota bez testów na `main`; obowiązkowa kontrola blokuje taki push. Jeśli generator wyliczy różnice, aktualizacja TFW/metadanych wymaga sprawdzonego PR. Nie dodawaj obejścia dla bota. T10 zastępuje ten workflow generacją wyników poza danymi źródłowymi. Bez zmian pozostaje workflow wydania, którego utwardzenie odbiera T11.

## Dowody w PR

Podaj wynik `./scripts/check`, liczbę testów, wersje środowiska z logu, link do CI na aktualnej rewizji oraz wynik próby z celowo wprowadzoną regresją. Dane próbne trzymaj w katalogach tymczasowych. Gdy zmiana dotyczy danych, dołącz listę planów i pól oraz uzasadnienie zgodnie z [planem prac](../docs/plans/2026-10-24-jakosc-danych-i-ci.md). Zielony smoke test nie zastępuje kryteriów konkretnego zadania.
