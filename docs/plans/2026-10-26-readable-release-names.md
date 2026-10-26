# Czytelne nazwy GeoTIFF w ZIP — plan implementacji

> Wykonanie w osobnym worktree; TDD i niezależny review całej zmiany.

**Cel:** przywrócić `{dir_id}_{inventory_number}_{name}.tif` w korzeniu ZIP przy zachowaniu T03–T11.
**Specyfikacja:** polecenie użytkownika z 26.10.2026; kontrakty GENERATION_OUTPUT.md, RELEASE_ACCEPTANCE.md i QA.md.
**Architektura:** `t11-v2` dodaje wyłącznie `release.files`: relacje plan_id/output/archive_path/sha256. Przebieg i jego manifest pozostają w układzie T04. Odbiornik oblicza oczekiwane mapowanie z metadanych sprawdzonych hashem wejścia, rekonstruuje przebieg i wykonuje T09. Stary `t11-v1` nadal podlega pełnej kontroli aktualności.
**Technologie:** istniejący Python, PyYAML, zipfile, GDAL/Pillow, przypięty Docker.

## Granice

- Baza origin/main addd87607b6356a8ade8fe3e0799d3472ff1af77. PR GPS #28 i jego artefakty pozostają nietknięte.
- Brak zmian danych, pinu v1.3.1, wyjątków QA, geometrii, generatora, historii i dowodów T11.
- Normalizacja historyczna: spacja i / na _, usunięcie ASCII apostrofu/cudzysłowu; bez transliteracji, zmiany wielkości i zwijania znaków.
- Nazwa/inwentarz wymagane. Niebezpieczne ścieżki, kolizje po NFC/casefold i powtórzone relacje blokują ZIP, bez fallbacków.
- Jedna wspólna bramka tag/manual, jednorazowe rozwiązanie current, raporty i atomowy ZIP poza przebiegiem.
- Aktualny fingerprint obejmuje wszystkie pipeline/*.py, więc zmiana pakowania unieważni dotychczasowy cache. Zachowujemy ten konserwatywny kontrakt: jeden pełny build aktualnego kodu, potem cache według treści; nie powtarzamy dwóch zimnych buildów.

## Alternatywy

1. Wybrano wersjonowane mapowanie w release: nazwy użytkowe i pełny odbiór bez zmiany układu generatora.
2. Zmiana manifestu przebiegu lub drugie kopie TIFF w ZIP naruszałyby wymagania.
3. Tylko zmiana nazw bez mapowania traciłaby sprawdzalne powiązanie wyników z planami.

## Kryteria review

Surowe ZipInfo przed mapami/zbiorami; Unicode/casefold i niebezpieczne ścieżki; metadane zmienione wobec manifestu; podmienione relacje pomiędzy planami; pełne QA i zachowanie poprzedniej paczki/current po błędzie.

## Zadanie 1 — nowy układ i niezależny odbiór

Pliki: pipeline/release_layout.py (nowy kontrakt/derywacja nazw), package_release.py (zapis), release_acceptance.py (odczyt v1/v2), tests/test_release_layout.py oraz istniejące testy pakowania/odbioru.

- [x] Napisać testy nazw, mapowania i układu, uruchomić na starym kodzie i zapisać oczekiwane FAIL.
- [x] Wdrożyć minimalne v2, zachowując odczyt v1 i wszystkie bramki T11; testy PASS.
- [x] Dodać próby podmiany relacji/plików, ZipInfo, CRC, obu trybów i atomowości; RED→GREEN dla nowych usterek.
- [x] Zaktualizować instrukcje ZIP/odbioru i uruchomić ./scripts/check; commit implementacji bez Co-Authored-By.

## Zadanie 2 — pełny odbiór i dostarczenie

- [x] Z czystego commitu wykonać jeden pełny katalog w przypiętym środowisku, pełne QA i lokalne paczki tag/manual z jednego konkretnego run.
- [x] Niezależnie porównać wszystkie historyczne nazwy, ZipInfo, komplet wpisów i bajty 2442 wyników; accept verify obu archiwów.
- [x] Zlecić świeżemu agentowi review źródeł i odbiór gotowych paczek według zaktualizowanej instrukcji; poprawić potwierdzone błędy z regresją.
- [ ] Zapisać nowe dowody osobno od T11, ponowić wymagane kontrole po zmianach, wypchnąć końcowy commit i utworzyć PR.
- [ ] Poczekać na terminalny wynik CI końcowej rewizji. Bez merge/tag/release/publikacji.
