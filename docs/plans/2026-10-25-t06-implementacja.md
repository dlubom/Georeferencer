# T06 — plan implementacji geometrii

Specyfikacja: [#11](https://github.com/dlubom/Georeferencer/issues/11),
sekcja T06 [planu jakości](2026-10-24-jakosc-danych-i-ci.md) i kontrakt T05.
Baza: `0c09cfae5dbaaf54fb79a877e43fb045e4e0fe6b`.

## Projekt i decyzje implementacyjne

Rozszerzamy `orientation.py`, bez nowego silnika i bez zmiany zależności.
PROJ wyznacza zbieżność EPSG:2180; niezależnym wzorcem testowym jest
rzut dwóch punktów na południku, a nie powtórzenie wzoru produkcyjnego.
Kąt strzałki jest mierzony zgodnie z ruchem wskazówek od góry obrazu.
Dodatnia deklinacja oznacza wschód. Północ siatki odnosi się do EPSG:2180.
Nieustalona północ nadal bierze wyłącznie kąt historycznego TFW T02.

Kliknięcia UI mają początek w narożniku obrazu (`drawImage`, `toOrig`),
więc są współrzędnymi GDAL, a nie indeksami środków pikseli. TFW otrzymuje
przesunięcie +0.5 obu osi względem starego zakotwiczenia. Dotyczy to także
unknown, lecz nie zmienia jego kąta. Skala pozostaje 1/ppm w metrach siatki;
nie dodajemy korekty terenowej ani estymacji rzeczywistej dokładności planu.
Raport porównuje T05 i T06 na tych samych bieżących wejściach, osobno
położenie, obrót i skalę. Nie zapisuje wyników do danych źródłowych.

## Zadania i bramki

- [x] 1. Dodać testy RED: geographic na 17°,19°,21°, niezerowa strzałka,
  grid ignoruje zbieżność/deklinację, magnetic z ±deklinacją i źródłami.
  Dodać modele; testy mają przejść GREEN. Zachować status i decyzje T05.
- [x] 2. Test rzeczywistego GDAL: kliknięcie i drugi punkt, narożnik/środek,
  także niezerowa rotacja, rzeczywisty obraz 001131 i oba tryby CLI.
  Poprawić zakotwiczenie dopiero po dowodzie RED; tolerancje obliczać
  z precyzji TFW (10/6 miejsc), współrzędnych piksela i projekcji.
- [x] 3. Wygenerować odtwarzalny raport 814 planów przed/po z dokładnego
  generatora bazy T05. Zachować integralność całych data i parquet.
  Zaktualizować instrukcje modeli, półpiksela, granic i odtworzenia raportu.
- [x] 4. Pełny `./scripts/check`, kontrolowane regresje znaku i półpiksela,
  niezależne review całego diffu; dowody RED→GREEN i wynik odbioru zapisane
  w [odbiorze](2026-10-25-t06-odbior.md).

Dostarczenie: osobny PR z linkiem do kontroli końcowego SHA w opisie,
bez scalenia ani wydania.

Review szczególnie sprawdza: znaki deklinacji i zbieżności, konwencję
punktu piksela w obu CLI, niezmienność unknown i źródeł T02, pełne snapshoty
T04 i brak automatycznego statusu verified. Przejściowy workflow bez zmian.
