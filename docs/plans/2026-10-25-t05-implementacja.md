# T05 — plan implementacji i decyzje wykonawcze

Specyfikacja: [zaakceptowany plan T05](2026-10-24-jakosc-danych-i-ci.md#t05--jawna-niepewność-północy-i-zachowanie-orientacji-historycznej), issue #10 i wymagania odbioru użytkownika z 25.10.2026. Baza: `9542729122505e1840e8e4f4a9b558c90f01c6c9`.

Cel: jawna niepewność północy i zachowanie kąta T02 niezależnie od zmian współrzędnych, kliknięcia otworu i skali. Python, istniejący walidator i wspólny kontener, bez nowych zależności.

## Architektura i decyzje

- `pipeline/orientation.py`: metadane północy (unknown/geographic/magnetic/grid), pochodzenie kąta (measured/assumed/unknown), podstawa i konwencja deklinacji. Kąt historyczny wyłącznie z `plans[].historical_tfw` przypiętego katalogu T02.
- Nie wybieramy rodzaju północy z liczby 0 ani nie wyliczamy stałej poprawki ze starego wzoru. Zapisany TFW jest jedynym dostępnym dowodem historycznej orientacji. Modele znanych rodzajów należą do T06 i do tego czasu generacja jest blokowana.
- Zmiana wejść orientacji wymaga łańcucha decyzji: hash przed/po, powód, data, działanie. Łańcuch zaczyna się od migrowanych oryginalnych metadanych T02; nie obejmuje współrzędnych, otworu ani skali. Status pozostaje unverified.
- `pipeline/migrate_north.py`: jawna, powtarzalna migracja i raport pól przed/po. Zachowuje oryginalne YAML-e i zmieniany kod QA w osobnym archiwum `data/history/t02-inputs.zip`, kontrolowanym oryginalnymi hashami. Całe `data/baseline/2026-10-24` pozostaje identyczne.
- `validation.py`, generator i T04 korzystają z tego samego modelu. Nowe wejścia historyczne są snapshotowane i uwzględnione w kontroli ścieżek i hashach manifestu. QA dostaje status/powód bez przebudowy T09.

## Zadania i odbiór

- [x] 1. Testy regresji: 814 kątów z TFW, zmiany współrzędnych/skali/otworu, blokada niejawnych zmian i nieobsługiwanych modeli, rozróżnienie zer, walidacja źródeł/deklinacji. Uruchomić i odnotować RED.
- [x] 2. Model, walidator, integracja generatora/manifestu/QA i migracja. Zaktualizować syntetyczne wejścia wcześniejszych testów do jawnego kontraktu. Osobno odebrać integralność i reprodukcję historii.
- [x] 3. Dokumentacja i raport migracji, pełny ./scripts/check, kontrolowana mutacja dowodząca wykrycia regresji, niezależne review całego diffu i poprawki.
- [ ] 4. Osobny PR, końcowy CI dla jego SHA, link i liczba testów/wersje środowiska. Bez scalenia i wydania.

## Szczególne przypadki review

Brak metadanych nie może uruchomić starego wzoru; decyzja nie może zmieniać historycznego odniesienia; hash musi opisywać snapshot użyty w obliczeniu; niepoprawna partia nie publikuje current; historia musi działać bez bieżących YAML-i i modeli.

## Dziennik

- Stan początkowy: czysty checkout, origin/main = baza T04. GitHub CI 40191681359 success, aktywny ruleset wymagający Kontrola projektu. Lokalny ./scripts/check: 75 PASS, 49.499 s. Zależności i konfiguracja CI bez zmian.

- Implementacja/migracja: komplet 814 planów; raport odtwarzalny; obrazy, TFW i cały punkt T02 bez zmian.
- RED: 81 testów, 823 FAIL; kontrolowana mutacja: 91 testów, 3 FAIL; końcowo 93 PASS, 76.868 s.
- Niezależne review: dwa P2 (roundtrip float, powiązanie z treścią obrazu), oba odtworzone testami i poprawione RED→GREEN; szczegóły w [odbiorze](2026-10-25-t05-odbior.md).
- Publikacja PR i dowód CI końcowej rewizji są prowadzone w opisie PR.
