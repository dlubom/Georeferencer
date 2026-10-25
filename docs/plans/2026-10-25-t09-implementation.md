# T09 — plan wykonania

Specyfikacja: [zaakceptowany plan T09](2026-10-24-jakosc-danych-i-ci.md),
issue #14 i szczegółowe polecenie odbioru po T08. Wykonanie w tej sesji,
osobna gałąź `codex/t09-qa-exceptions`, niezależny reviewer przed PR.

Cel: deterministyczne QA aktualnych źródeł i wybranego przebiegu T04,
z wyjątkami wyłącznie dla konkretnych niepewności interpretacyjnych.
Python, istniejące biblioteki i przypięty kontener; bez nowych zależności.

## 1. Raport i rejestr

- [x] Test RED: stary raport nie ma kontroli kompletnego katalogu, ważnych
  komponentów T07, rozdzielenia wejść/wyników ani egzekwowania wyjątków.
- [x] `pipeline/qa.py`: odczyt bieżących katalogów, walidacja T03/T05/T08,
  agregaty T07 i wszystkie niezależne reguły, bez użycia quality.flag.
- [x] `pipeline/qa_outputs.py`: odbiór raz rozwiązanego przebiegu T04,
  dokładny komplet, hashe, bieżące wejścia/kod/pin i rzeczywisty GeoTIFF.
- [x] `03_report.py`: CLI z reports-dir, run-dir i require-results;
  JSON oraz kompatybilne nazwy CSV summary/flagged/missing.
- [x] `data/qa/`: snapshot issues #1/#3, uzgodnienie z katalogiem i jawny
  rejestr plan/reguła/podstawa/hash/uzasadnienie/warunek zamknięcia.
- [x] Test GREEN: wyjątek konkretnej reguły, nowy problem, stara podstawa,
  błąd techniczny, wszystkie modele północy/zera/null i plan ręczny T08.

## 2. Odbiór

- [x] Zachować oryginalne bajty raportów QA T02 oddzielnie; historyczny audyt
  nadal używa pierwotnych hashy. Kod QA T02 jest już w t02-inputs.zip.
- [x] Testy stanu wyników: brak przebiegu, brak pliku, stary wynik, uszkodzony
  wynik, dodatkowy/powtórzony plan/plik, oba rejestry obrazu i ich brak.
- [x] Wspólny check egzekwuje źródłowe QA przez test; workflow bez zmian.
- [x] Raport wpływu: dokładny katalog i reguły, 0 zmian wejść i geometrii,
  deterministyczność, powiązania i źródła nierozstrzygniętych uwag.
- [x] `./scripts/check`, kontrolowana regresja w kopii, niezależne review
  i naprawy z testami.
- Dostarczenie: osobny PR z linkiem do CI końcowej rewizji. Bez merge/release.

## Miejsca szczególnej kontroli

Zmiana zestawu planów nie może zniknąć przez glob samego meta.yaml.
Zmiana lokalnego rejestru lub jego pojawienie się unieważnia wynik/wyjątek.
Wyjątek nie może rozszerzać się na inną regułę tego samego planu.
Nie wolno traktować historycznego TFW jako bieżącego wyniku ani zgadywać
północy z zera. Raport wybranej części T04 nie jest kompletem całego katalogu.
Stare uwagi wskazują niepewność interpretacji, a nie dowiedziony defekt.
