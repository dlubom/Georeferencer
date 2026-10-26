# Odbiór czytelnych nazw ZIP t11-v2

Implementacja: `852d2fcac32cd7e7555eedc22f660875634b0b53`.
Baza: `addd87607b6356a8ade8fe3e0799d3472ff1af77` (aktualne origin/main przed pracą).
Końcowy commit dowodów dodaje wyłącznie dokumentację/raporty; SHA dostarczenia
i terminalne CI są w opisie osobnego PR. Nie jest wymagany nowy build
z powodu samego SHA dokumentacji: aktualność zależy od treści i środowiska.

[Wyniki testów i kontrolowane regresje](../reports/readable-release-validation.json),
[pełna generacja i zgodność z T11](../reports/readable-release-generation.json),
[wszystkie 2442 relacje i oba archiwa](../reports/readable-release-inventory.json),
[pełny niezależny review](../reports/readable-release-independent-review.json),
[osobny inwentarz reviewera](../reports/readable-release-independent-inventory.json),
[dostarczenie i ochrona main](../reports/readable-release-delivery.json).

## Wynik użytkowy i kontrakt

Przed: `001094/image_georef.tif`. Teraz:

```text
001094_T.D-08.07_Jaskinia_Mroźna.tif
manifest.json
metadane/001094/image.tfw
metadane/001094/computed.json
```

Nazwy `{dir_id}_{inventory_number}_{name}.tif` pochodzą z wersjonowanych
metadanych. Historyczna normalizacja v0.6.2: ASCII spacja i `/` na `_`,
usunięcie ASCII apostrofów/cudzysłowów. Polskie znaki, wielkość liter,
kropki, myślniki i powtarzające się `_` pozostają. Brak danych, niebezpieczna
ścieżka oraz kolizja po normalizacji/NFC/casefold blokują pakowanie.
Bez sufiksów, fallbacków, pomijania i dodatkowych kopii TIFF-a.

Nowe ścieżki konsumenckie i obowiązkowe mapowanie wymagają nowej wersji
**ZIP t11-v2**. `release.files` wiąże każdy plan/output ze ścieżką ZIP i
SHA-256. Odbiornik ponownie wylicza relacje z hashowanego YAML-a i wyników,
odtwarza pierwotny przebieg i wykonuje pełne QA. Manifest przebiegu v1
oraz układ generatora pozostają bez zmian. `t11-v1` nadal przechodzi pełną
walidację, aktualność i rzeczywisty odczyt; nieznane wersje są odrzucane.
Stare artefakty nie uzyskują automatycznej zgody po zmianie kodu.

## Kontrola i regresje

`./scripts/check`: **7 host + 209 kontener = 216 PASS**, kontener 282.210 s.
Niezależny reviewer: **216 PASS**, 335.799 s. Linux/amd64, Python 3.12.3,
GDAL 3.12.4, PROJ GDAL/pyproj 9.8.1, pyproj 3.8.0, Pillow 13.0.0.
Pełne pakiety i SHA logów znajdują się w raportach.

Przed warstwą mapowania: 7 FAIL braku funkcji, następnie PASS. Odtwarzalny
[mutant starego układu](../reports/readable-release-controlled-regression.py)
w przypiętym kontenerze: dokładnie 1 assertion FAIL, 0 ERROR, detected=True;
poprawny kod przechodzi cały zestaw. Reviewer odtworzył ten sam dowód.
Dwa dodatkowe przypadki wykryły potwierdzone błędy: katalog DOS oznaczony
atrybutem bez końcowego `/` oraz nieobsłużony błąd DEFLATE. Oba mają
regresję FAIL→PASS. Niezmieniony historyczny skrypt regresji T11 nadal
wykrywa pominięcie odbioru gotowego ZIP (dokładnie 1 oczekiwany FAIL).

## Pełny katalog i paczki

Jedna pełna generacja `./scripts/build generate --changed`:
**814 generated / 0 reused**, bez sieci i ze źródłami readonly.
Konserwatywny fingerprint obejmuje wszystkie `pipeline/*.py`, więc kod
pakowania wymagał jednego przeliczenia; nie zawężano tego zabezpieczenia.
Nie powtarzano pary zimnych buildów T11. TFW bajtowo oraz CRS, transformacje,
wymiary i zdekodowane piksele **814/814** identyczne z dowodem T11.

Raz rozwiązany przebieg: `06dd5b3f1a7249f990075114c797a34c`.
Manifest SHA-256: `1b4ed64188b11f96811f282122d3e7edd8c13c805a61268b8dea4949feac6b63`.
Build i pakowanie: `code.dirty=false`, czysty commit implementacji.
Oba tryby `./scripts/build package` użyły tego samego konkretnego run,
bez ponownego odczytu current. Każdy wykonał pełne QA i niezależny odbiór
gotowego tymczasowego ZIP przed atomową podmianą. Raporty/ZIP poza run.
QA każdego: **814 current, 1405 accepted, 0 blocking**.

| Tryb | Bajty ZIP | Wpisy | TIFF-y w korzeniu | Identyczne wyniki |
| --- | ---: | ---: | ---: | ---: |
| tag | 21568234 | 2443 | 814 | 2442 |
| manual | 21568235 | 2443 | 814 | 2442 |

SHA-256 tag: `cf018213953a749ff13d694ea9987f6b880a390a59d77b0eaed819a5ab99de13`.
SHA-256 manual: `1a07d24bf4b1f3b11d79246c3ce4948425fdb91b192f245ddc7c47b32b04b069`.

Wersjonowany [audyt wszystkich nazw i bajtów](../reports/readable-release-inventory.py)
uruchomiono osobno w przypiętym środowisku. Reviewer stworzył własny
[odrębny audyt](../reports/readable-release-review-audit.py) bez helperów
pakowania i na własnym czystym worktree wykonał oba `accept verify`.
Oba pełne odbiory PASS; wszystkie ZipInfo, CRC, nazwy, komplet i bajty
potwierdzone przez dwóch operatorów. Wyniki wszystkich relacji są
w obu inwentarzach. Manifest/current i wyniki run po pakowaniu niezmienione.

## Niezależny review i zakres

[Raport czytelny](2026-10-26-readable-release-review.md): **PASS, 0 Critical,
0 Important, 0 Minor**. Reviewer czytał instrukcje wersjonowane, historyczny
workflow i diff względem origin/main. Mounty run/ZIP były readonly, raporty
we własnym build. Nie oceniano na nowo dokładności terenowej ani istniejących
1405 niepewności; ich dopuszczenie jest nadal egzekwowane przez bieżący T09.

Diff chronionych ścieżek jest pusty: dane, obrazy, kliki, skala/orientacja,
pin GPS v1.3.1, object_id/measurement_id, wyjątki/podstawy i historia T02–T11,
generator, geometria, CI, wrappery i workflow bez zmian. Nie wykonywano
ekstrakcji, migracji ani aktualizacji GPS. Otwarty PR GPS #28 pozostaje osobny;
jego lokalny ZIP nadal ma SHA-256
`44f0d4efcffe80defb43fb3856b8582bafc3b5c9987c1e97be8df4e01579a2fc`.
Main pozostał `addd876`, ruleset 25796826 active/strict, bypass_actors=[];
nie obchodzono ochrony. Nie tworzono tagu, wydania ani produkcyjnej publikacji.
