# Naprawa odczytu ZIP w workflow wydania

Baza: `20864e7111ab165f8a710c7915eeb0088104762b` (scalony PR #28).
Tag v0.7.0 już wskazuje ten zaakceptowany commit; pozostaje niezmienny.

## Potwierdzona przyczyna i minimalny zakres

[Przebieg tagu 40297131295](https://github.com/dlubom/Georeferencer/actions/runs/40297131295)
przeszedł generację i wspólną bramkę QA/ZIP. Publikujący proces hostowy
zakończył się `EACCES: permission denied, open build/geotiff-tatry-v0.7.0.zip`.
`package_release.py` używa mkstemp (0600) w kontenerze root i atomowo
podmienia nim ZIP. Użytkownik runnera ma inne UID. Docker Desktop na macOS
mapuje własność plików inaczej, więc lokalny odczyt nie ujawnił tej granicy.
Pozostał draft release 424040195 bez assetów; nie usuwamy go ani tagu.

Zmiana jest ograniczona do orkiestracji publikacji:

1. Po pełnym QA/pakowaniu przyznaj odczyt gotowego ZIP na hoście przez
   `sudo chmod a+r -- ...`. Brak pliku lub błąd chmod zatrzymuje publikację.
   Nie zmienia to bajtów archiwum ani któregokolwiek wyniku lub wejścia.
2. `overwrite_files: false` w przypiętej akcji softprops blokuje nadpisywanie
   już istniejącego assetu. Jej domyślna wartość true została potwierdzona
   w action.yml dokładnej rewizji i logu pierwszego nieudanego przebiegu.
3. Wszystkie bramki, pin, pipeline, manifest, t11-v2, nazwy i ochrona main
   pozostają bez zmian. Nie uruchamiamy kolejnej pary zimnych buildów T11.

## Regresja i odbiór

`tests/test_release_workflow.py` tworzy plik 0600 jako UID0 w przypiętym
kontenerze, potwierdza rzeczywisty PermissionError procesu UID65534,
wykonuje dokładny run kroku workflow (sudo jest passthrough, bo test
już działa jako root), a następnie odczytuje plik drugim UID i porównuje
bajty/hash oraz tryb 0644. Sprawdza kolejność QA → odczyt → publikacja.
Drugi test wymaga jawnego overwrite_files=false. RED: dwa FAIL, brak errors;
GREEN: cztery testy kontraktu workflow PASS. Pełny ./scripts/check obowiązkowy.

Niezależny review według AGENTS.md, ci/README.md i RELEASE_ACCEPTANCE.md:
przypnij bazę i head, oceń minimalny diff oraz RED/GREEN dwóch UID;
sprawdź brak zmian pipeline/źródeł i brak osłabienia QA/protekcji.
Po lokalnej kontroli i review wymagane jest terminalne CI końcowego headu
oraz chroniony merge z oczekiwanym SHA, bez bypassów.

Po sukcesie CI poprawionego main standardowy workflow_dispatch z main
otrzyma istniejący tag v0.7.0. Definicja workflow pochodzi z poprawionego
main; actions/checkout nadal pobierze dokładny tag 20864e7. Produkcyjny
kod i pomiary wydania pozostają zaakceptowane. Publiczny ZIP będzie miał
release.mode=manual. Przed startem ponownie sprawdź draft/asset listę;
nie nadpisuj istniejących assetów. Po sukcesie zastosuj wersjonowane notes,
pobierz rzeczywisty publiczny ZIP i odbierz go osobno wraz z agentem.
