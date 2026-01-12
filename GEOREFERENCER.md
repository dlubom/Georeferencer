# Cave Plan Georeferencer

Narzędzie webowe do georeferencji planów jaskiń. Pozwala przekształcić skan planu jaskini w plik GeoTIFF, który można otworzyć w programach GIS (QGIS, Google Earth Pro, mapy.cz).

## Wersje aplikacji

**Crowdsourcing (produkcja):** [https://dlubom.github.io/Georeferencer/index.html](https://dlubom.github.io/Georeferencer/index.html)
- Zbieranie k=5 niezależnych wyników georeferencji dla każdej jaskini z Tatr
- Przydzielanie jaskiń użytkownikom przez system
- Zapisywanie wyników do Google Sheets

**Debug (testy):** [https://dlubom.github.io/Georeferencer/debug.html](https://dlubom.github.io/Georeferencer/debug.html)
- Ręczny wybór dowolnej jaskini z bazy
- Wszystkie regiony (nie tylko Tatry)
- Bez zapisywania do Google Sheets

---

## Crowdsourcing Mode (Tryb Współpracy)

System crowdsourcingowy zbiera 5 niezależnych wyników georeferencji dla każdej jaskini z Tatr w celu późniejszej analizy konsensusu i zapewnienia wysokiej jakości danych.

### Jak to działa?

1. **Automatyczne przydzielanie:** Kliknij "🎲 Daj mi jaskinię" - system przydzieli Ci jaskinię, której jeszcze nie georeferencjonowałeś
2. **Balansowanie obciążenia:** System preferuje jaskinie z mniejszą liczbą oddanych wyników, aby równomiernie pokryć całą bazę
3. **Czas na wykonanie:** Masz 24 godziny na wykonanie georeferencji (przydzielenie wygasa automatycznie)
4. **Postęp globalny:** Panel u góry pokazuje, ile jaskiń ma już zebrane wyniki (≥1, ≥2, ..., ≥5)
5. **Wszystkie wyniki zapisywane:** Dane trafiają do Google Sheets z pełną telemetrią dla późniejszej analizy

### Dla kontrybutorów

Jeśli chcesz pomóc w projekcie georeferencji planów jaskiń Tatr:

#### Wymagania
- Przeglądarka internetowa (Chrome, Firefox, Safari, Edge)
- Podstawowa znajomość map i planów jaskiń
- ~2-5 minut na jedną jaskinię

#### Proces (krok po kroku)

1. **Wejdź na stronę:** [index.html](https://dlubom.github.io/Georeferencer/index.html)
   - System wygeneruje Ci unikalny ID użytkownika (UUID) i zapisze w przeglądarce

2. **Kliknij "🎲 Daj mi jaskinię"**
   - System przydzieli Ci losową jaskinię z Tatr, której jeszcze nie robiłeś
   - Jaskinia zostanie automatycznie wybrana i wyświetlona w sidebarze
   - Przydzielenie wygasa po 24h jeśli nie wyślesz wyniku

3. **Załaduj plan jaskini**
   - Kliknij "📂 Załaduj Plan z GitHub"
   - Plan automatycznie się załaduje (obrazy są hostowane na GitHub)
   - Możesz wybrać inny obraz z listy dropdown, jeśli dostępnych jest kilka

4. **Wykonaj kalibrację (3-5 punktów)**

   **Zawsze potrzebne (3 punkty):**
   - Kliknij **otwór wejściowy** jaskini
   - Kliknij **początek podziałki skali** (np. "0" na linijce "0-50m")
   - Kliknij **koniec podziałki skali** (np. "50" na linijce)

   **Opcjonalnie (jeśli plan ma strzałkę północy):**
   - Odznacz "Pomiń strzałkę północy"
   - Kliknij **bazę strzałki** (gdzie zaczyna się strzałka)
   - Kliknij **grot strzałki** (czubek strzałki północy)

5. **Sprawdź wyniki**
   - W panelu "Wyniki" zobaczysz obliczoną skalę, kąt północy, itp.
   - Upewnij się, że wartości wyglądają sensownie

6. **Wyślij do Google Sheets**
   - Kliknij "📤 Wyślij do Google Sheets"
   - Potwierdź w okienku modalnym
   - Dane zostaną zapisane (50+ pól z pełną telemetrią)

7. **Następna jaskinia**
   - Kliknij ponownie "🎲 Daj mi jaskinię" i powtórz proces
   - Możesz zrobić ile chcesz, system śledzi Twój postęp

#### Jak pominąć jaskinię?

Jeśli nie możesz wykonać georeferencji (np. plan nieczytelny, brak skali, brak wejścia):

1. Kliknij "🔄 Pomiń tę jaskinię"
2. Wybierz powód z listy dropdown
3. Potwierdź - system zapisze, że ją ominąłeś i przejdzie do następnej

#### Sesja pracy

- **Zapisywanie postępu:** Jeśli zamkniesz przeglądarkę w trakcie georeferencji, Twoje aktualne przydzielenie zostanie zapamiętane (przez 24h)
- **Powrót do pracy:** Gdy wrócisz na stronę, zobaczysz ostatnio przydzieloną jaskinię i możesz kontynuować
- **Ostrzeżenie przed zamknięciem:** Przeglądarka ostrzeże Cię, jeśli będziesz próbował zamknąć kartę z niewykonaną pracą

#### Co jeśli nie działa?

**Błąd sieci / nie można połączyć z Google Sheets:**
- Aplikacja zaproponuje pobranie danych jako JSON
- Zapisz plik i wyślij go do koordynatora projektu

**Przydzielenie wygasło:**
- Po 24h przydzielenie automatycznie wygasa
- Kliknij ponownie "Daj mi jaskinię", aby dostać nową jaskinię

**Wszystkie jaskinie ukończone:**
- Jeśli wszystkie jaskinie z Tatr mają już ≥5 wyników, zobaczysz komunikat: "🎉 Wszystkie jaskinie ukończone! Dziękujemy!"

#### FAQ dla kontrybutorów

**Q: Czy muszę się rejestrować?**
A: Nie, system automatycznie wygeneruje Ci unikalny ID użytkownika przy pierwszej wizycie.

**Q: Czy mogę wybrać konkretną jaskinię?**
A: W trybie produkcyjnym nie - system przydziela losowo. Jeśli chcesz przetestować konkretną jaskinię, użyj wersji debug.html.

**Q: Co jeśli kliknę w złym miejscu?**
A: Użyj przycisku "↩️" (Cofnij ostatni punkt) w prawym górnym rogu lub "🔄 Zacznij od nowa" w panelu Wyniki.

**Q: Czy dane są publiczne?**
A: Wyniki trafiają do Google Sheets dostępnego tylko dla koordynatora projektu. Twój user_id (UUID) jest anonimowy.

**Q: Ile jaskiń powinienem zrobić?**
A: Ile chcesz! Nawet 1-2 jaskinie bardzo pomagają. System automatycznie balansuje obciążenie.

**Q: Co z jakością wyników?**
A: Zbieramy 5 niezależnych wyników na jaskinię właśnie po to, żeby później znaleźć konsensus i odrzucić potencjalne błędy.

---

## Idea (Debug Mode)

Plany jaskiń w bazach danych (np. CBDG) są zwykłymi obrazkami - nie zawierają informacji o położeniu geograficznym. Georeferencer rozwiązuje ten problem:

1. **Wskazujesz punkty kalibracyjne** na planie:
   - Otwór wejściowy (znamy jego współrzędne GPS)
   - Początek i koniec podziałki skali (znamy długość w metrach)
   - Opcjonalnie: strzałkę północy (dla planów z niestandardową orientacją)

2. **Narzędzie oblicza transformację** uwzględniając:
   - Skalę (piksele → metry)
   - Obrót (orientacja północy + konwergencja południkowa)
   - Przesunięcie (współrzędne wejścia)

3. **Generujesz pliki** do utworzenia GeoTIFF:
   - World File (`.jgw`, `.pgw`, `.tfw` - zależnie od formatu obrazu) z parametrami transformacji
   - Komendę GDAL do konwersji

## Ograniczenia

### Układ współrzędnych

Narzędzie domyślnie używa układu **PL-1992 (EPSG:2180)** z południkiem osiowym **19°E**. Oznacza to, że:

- Działa poprawnie dla większości Polski (Tatry, Sudety, Jura, Góry Świętokrzyskie)
- Dla jaskiń blisko granicy zachodniej (np. Karkonosze) błędy mogą być większe
- Można zmienić definicję PROJ4 w polu "Definicja projekcji" jeśli potrzeba innego układu

### Dokładność

Dokładność georeferencji zależy od:
- Jakości współrzędnych GPS wejścia (często ±10-50m w bazach danych)
- Precyzji kliknięcia punktów kalibracyjnych
- Dokładności podziałki skali na planie
- Deformacji skanu (rozciągnięcie, obrót)

Dla typowych planów można oczekiwać dokładności rzędu kilku-kilkunastu metrów.

## Co to jest World File?

World File to plik tekstowy zawierający 6 liczb opisujących transformację afiniczną obrazu:

```
0.1234567890    <- A: rozmiar piksela w osi X (metry) × cos(obrót)
0.0012345678    <- D: obrót w osi Y
0.0012345678    <- B: obrót w osi X
-0.1234567890   <- E: rozmiar piksela w osi Y (ujemny, bo Y rośnie w dół)
567890.123456   <- C: współrzędna X lewego górnego rogu
234567.890123   <- F: współrzędna Y lewego górnego rogu
```

**Ważne:** Rozszerzenie World File zależy od formatu obrazu:
- `.jgw` → dla `.jpg` / `.jpeg`
- `.pgw` → dla `.png`
- `.tfw` → dla `.tif` / `.tiff`
- `.gfw` → dla `.gif`
- `.bpw` → dla `.bmp`

GDAL automatycznie wykrywa World File jeśli ma taką samą nazwę jak obraz i prawidłowe rozszerzenie (np. `plan.jpg` + `plan.jgw`).

## Instalacja GDAL

### macOS (Homebrew)

```bash
brew install gdal
```

### Ubuntu/Debian

```bash
sudo apt-get install gdal-bin
```

### Windows

1. Pobierz OSGeo4W: https://trac.osgeo.org/osgeo4w/
2. Zainstaluj z opcją "GDAL"
3. Uruchom "OSGeo4W Shell" i użyj komend GDAL

### Conda

```bash
conda install -c conda-forge gdal
```

### Weryfikacja instalacji

```bash
gdal_translate --version
# GDAL 3.x.x, released ...
```

## Instalacja ImageMagick (dla GDAL mono)

ImageMagick jest wymagany tylko dla komendy "GDAL mono" (konwersja do monochromatycznego GeoTIFF).

### macOS (Homebrew)

```bash
brew install imagemagick
```

### Ubuntu/Debian

```bash
sudo apt-get install imagemagick
```

### Windows

1. Pobierz instalator: https://imagemagick.org/script/download.php#windows
2. Wybierz wersję "Win64 dynamic at 16 bits-per-pixel component"
3. Podczas instalacji zaznacz "Add application directory to your system path"
4. Uruchom ponownie terminal

Alternatywnie przez Chocolatey:
```powershell
choco install imagemagick
```

### Conda

```bash
conda install -c conda-forge imagemagick
```

### Weryfikacja instalacji

```bash
magick --version
# Version: ImageMagick 7.x.x ...
```

**Uwaga:** W starszych wersjach ImageMagick (6.x) zamiast `magick` używa się `convert`. Komenda "GDAL mono" używa `magick` (ImageMagick 7+).

## Workflow

### 1. Wybierz jaskinię i załaduj plan

Plany jaskiń są hostowane w tym repozytorium:
- `caves/` - oryginalne skany z CBDG
- `caves_upscaled/` - powiększone i odszumione (2x, waifu2x)

Możesz też wgrać własny skan z dysku (przycisk "Wgraj plan z dysku").

**Obsługiwane formaty:**
- JPG, PNG, TIFF - wszystkie przeglądarki (TIFF dekodowany przez UTIF.js)

Aplikacja obsługuje duże pliki (testowane do 50 MB / 160 megapikseli). Bardzo duże obrazy są automatycznie skalowane na podglądzie, ale obliczenia World File używają oryginalnych wymiarów.

### 2. Kliknij punkty kalibracyjne

1. **Otwór wejściowy** - punkt o znanych współrzędnych GPS
2. **Początek skali** - lewy/dolny koniec podziałki
3. **Koniec skali** - prawy/górny koniec podziałki
4. (Opcjonalnie) **Strzałka północy** - baza i grot strzałki

Współrzędne wejścia są automatycznie pobierane z bazy danych. Możesz je ręcznie poprawić jeśli masz dokładniejsze dane.

### 3. Pobierz pliki do jednego folderu

Po kalibracji kliknij:
- **Obraz** - pobiera oryginalny obraz (dla plików z GitHub: z repozytorium, dla lokalnych: kopia z prawidłową nazwą)
- **World File** - pobiera plik World File (np. `J.Olk.12.03.jgw` dla JPG)

**Oba pliki muszą być w tym samym folderze i mieć tę samą nazwę** (różne rozszerzenia). GDAL automatycznie je połączy.

Dla plików wgranych z dysku nazwa World File i obrazu będzie taka sama jak oryginalna nazwa pliku (np. `moj_plan.jpg` → `moj_plan.jgw`).

### 4. Uruchom komendę GDAL

Dostępne są dwa warianty komend:

#### Standardowy GeoTIFF (przycisk "GDAL")

Kliknij "GDAL" i skopiuj wygenerowaną komendę:

```bash
gdal_translate -of GTiff -a_srs EPSG:2180 -co COMPRESS=DEFLATE -co PREDICTOR=2 -co TILED=YES "J.Olk.12.03.jpg" "J.Olk.12.03_georef.tif"
```

Opcje:
- `-a_srs EPSG:2180` - przypisuje układ współrzędnych PL-1992
- `-co COMPRESS=DEFLATE` - kompresja bezstratna (mały rozmiar pliku)
- `-co PREDICTOR=2` - lepsza kompresja dla obrazów
- `-co TILED=YES` - kafelkowanie (szybsze wyświetlanie w GIS)

#### Monochromatyczny GeoTIFF dla WMSA (przycisk "GDAL mono")

Dla systemów WMSA wymagany jest obraz monochromatyczny (1-bit), który pozwala ustawić biały kolor jako przezroczysty bez artefaktów.

**Wymagania:**
- GDAL
- ImageMagick 7+ (`brew install imagemagick` na macOS)

Kliknij "GDAL mono" i skopiuj wygenerowaną komendę:

```bash
magick "J.Olk.12.03.jpg" -colorspace Gray -dither FloydSteinberg -monochrome -compress Group4 "J.Olk.12.03_mono_raw.tif" && cp "J.Olk.12.03.jgw" "J.Olk.12.03_mono_raw.tfw" && gdal_translate -of GTiff -a_srs EPSG:2180 -co COMPRESS=CCITTFAX4 "J.Olk.12.03_mono_raw.tif" "J.Olk.12.03_mono_georef.tif"
```

Komenda wykonuje trzy kroki:
1. **ImageMagick**: Konwersja do grayscale + Floyd-Steinberg dithering → mono TIFF
2. **cp**: Kopiowanie World File dla pliku tymczasowego
3. **GDAL**: Georeferencja z World File + kompresja CCITTFAX4

**Uwaga QGIS:** Obraz mono używa palety kolorów. Jeśli QGIS wyświetla dziwne kolory (zielono-czerwone):
1. Kliknij prawym na warstwę
2. Properties → Symbology
3. Render type: **Singleband gray**
4. Apply

Po zakończeniu możesz usunąć pliki pośrednie (`*_mono_raw.tif`, `*_mono_raw.tfw`).

### 5. Użyj w programie GIS

Wynikowy plik `.tif` można otworzyć w:
- **QGIS** - File → Open → wybierz plik
- **Google Earth Pro** - File → Import
- **mapy.cz** - Mapy → Vlastní mapy → dodaj plik

## Struktura plików

```
Polish-Cave-Data-Scraper/
├── index.html              # Aplikacja Georeferencer
├── caves/                  # Oryginalne skany (z CBDG)
│   ├── 000390/
│   │   ├── image_19_zoom_10.jpg
│   │   └── ...
│   └── ...
├── caves_upscaled/         # Powiększone skany (2x, waifu2x)
│   └── ...
└── caves_transformed.jsonl # Dane jaskiń (współrzędne, metadane)
```

## Przykład

Dla Jaskini Mylnej (J.Tat.K-01.03):

1. Wyszukaj "Mylna" w liście jaskiń
2. Wybierz plan, załaduj
3. Kliknij otwór wejściowy (przy napisie "wejście")
4. Kliknij początek i koniec podziałki "50 m"
5. Pobierz `J.Tat.K-01.03.jpg` i `J.Tat.K-01.03.jgw`
6. Uruchom:
   ```bash
   cd ~/Downloads
   gdal_translate -of GTiff -a_srs EPSG:2180 -co COMPRESS=DEFLATE -co PREDICTOR=2 -co TILED=YES "J.Tat.K-01.03.jpg" "J.Tat.K-01.03_georef.tif"
   ```
7. Otwórz `J.Tat.K-01.03_georef.tif` w QGIS

## Rozwiązywanie problemów

### "Nie można pobrać obrazu"

Niektóre przeglądarki blokują pobieranie z innych domen. Rozwiązania:
- Użyj Chrome/Firefox
- Pobierz obraz ręcznie z GitHub: https://github.com/dlubom/Polish-Cave-Data-Scraper/tree/main/caves_upscaled

### GDAL nie widzi pliku World File / obraz nie ma georeferencji

Upewnij się, że:
- Oba pliki są w tym samym folderze
- Mają identyczne nazwy (wielkość liter ma znaczenie)
- **Rozszerzenie World File odpowiada formatowi obrazu:**
  - `.jpg` wymaga `.jgw` (nie `.tfw`!)
  - `.png` wymaga `.pgw`
  - `.tif` wymaga `.tfw`

Sprawdź czy GDAL widzi georeferencję:
```bash
gdalinfo twoj_obraz.jpg
```
Jeśli widzisz `GeoTransform =` z liczbami - działa. Jeśli widzisz `Corner Coordinates: Upper Left (0.0, 0.0)` - World File nie został wykryty.

### Plan jest obrócony/przesunięty w GIS

Sprawdź:
- Czy kliknięte punkty są w prawidłowych miejscach
- Czy wartość skali jest poprawna (metry, nie centymetry)
- Czy układ współrzędnych w GDAL odpowiada definicji PROJ4

## TODO

Lista planowanych funkcjonalności i ulepszeń:

### Do zrobienia

- [ ] **Skala po siatce** - Alternatywna metoda definiowania skali dla planów z siatką metryczną:
  - Użytkownik klika dwa punkty na przecięciach siatki
  - Podaje liczbę oczek siatki w pionie i poziomie między punktami
  - Aplikacja oblicza odległość z tw. Pitagorasa i dzieli przez liczbę oczek
  - Lepsza dokładność przy dłuższych odcinkach niż przy krótkiej podziałce
  - Zachować obecną opcję z podziałką (nie wszystkie plany mają siatkę, np. Mroźna Jama)

- [ ] **Backend GDAL** - Uruchamianie komendy GDAL z poziomu przeglądarki (użytkownik otrzymuje gotowy GeoTIFF bez instalacji narzędzi). Możliwa tania implementacja przez Google Cloud Functions (odpowiednik AWS Lambda)

- [ ] **Określenie użytkownika końcowego** - Zbadać grupę docelową:
  - Kim są użytkownicy?
  - Jaki poziom techniczny? (czy znają terminal, GDAL, GIS?)
  - Na jakim sprzęcie pracują? (RAM, system operacyjny)
  - To wpłynie na decyzję o backendzie GDAL i poziomie skomplikowania UI

- [ ] **Testy automatyczne i jednostkowe** - Pokrycie testami kluczowych funkcji:
  - Obliczenia transformacji (World File parameters)
  - Konwersja współrzędnych WGS84 → PL-1992
  - Obliczenie konwergencji południkowej
  - Obliczenie kąta północy
  - Generowanie nazw plików i rozszerzeń

- [ ] **Testy akceptacyjne przez zamawiających** - Sesja testowa z użytkownikami docelowymi:
  - Przetestowanie na rzeczywistych planach jaskiń
  - Weryfikacja poprawności georeferencji w QGIS/WMSA
  - Zebranie feedbacku o UX i brakujących funkcjach

- [ ] **Rozważyć wstępne przetworzenie grafik i wsparcie formatów** - Analiza opcji uniwersalnego wsparcia:
  - Wstępne przetworzenie wszystkich planów jaskiń jako mono TIFF dla WMSA
  - Pełne wsparcie dla dowolnych formatów plików w interfejsie
  - Upewnienie się, że komendy GDAL obsługują wszystkie formaty (.jpg, .png, .tiff, .bmp, .gif)
  - Automatyczne wykrywanie i dostosowanie parametrów kompresji

### Zrobione

- [x] **Doklikanie punktów północy bez resetu** - Gdy użytkownik odznacza "Pomiń strzałkę północy" po już sklikanych punktach (otwór, skala), można doklikać punkty strzałki zamiast resetowania. Działa też odwrotnie - zaznaczenie opcji usuwa punkty północy i przelicza.
- [x] **Obsługa TIFF w przeglądarce** - Dodanie biblioteki UTIF.js do dekodowania plików TIFF we wszystkich przeglądarkach (nie tylko Safari)
- [x] **Zwijane sekcje** - Sekcje w sidebarze można zwijać/rozwijać klikając nagłówek, stan zapisywany w localStorage
- [x] **Zmiana nazwy TFW → World File** - Przycisk pokazuje "World File", dokumentacja wyjaśnia rozszerzenia (.jgw, .pgw, .tfw)
- [x] **Obsługa dużych plików lokalnych** - Użycie createObjectURL() zamiast base64, działa z plikami 50MB+
- [x] **Poprawiony komunikat błędu** - Dla plików lokalnych nie wspomina o GitHub
- [x] **Nazewnictwo plików lokalnych** - World File i obraz mają tę samą nazwę co wgrany plik
- [x] **GDAL mono** - Komenda łącząca ImageMagick (Floyd-Steinberg dithering) i GDAL dla eksportu 1-bit GeoTIFF
- [x] **Poprawka kierunku obrotu** - Naprawiono znak w obliczeniu rotacji dla strzałki północy (Jaskinia Mroźna działa poprawnie)
- [x] **Logi debugowania** - Szczegółowe logi obliczeń w konsoli przeglądarki (F12 → Console)

## Licencja

Plany jaskiń pochodzą z Centralnej Bazy Danych Geologicznych (CBDG) i są udostępniane na zasadach określonych przez Państwowy Instytut Geologiczny.
