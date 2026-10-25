# Oryginalne wejścia T02 zachowane przed migracją T05

`t02-inputs.zip` zawiera 814 niezmienionych `data/caves/{dir_id}/meta.yaml`
i `pipeline/03_report.py` sprzed T05, pod oryginalnymi ścieżkami. Każdy plik
porównano przed zapisem z oryginalnym hashem w
`data/baseline/2026-10-24/catalogue.json`; historycznego katalogu nie zmieniano.
Archiwum ma stałe znaczniki czasu wpisów i nie zawiera plików generowanych.

`catalogue_baseline.verify_inputs` i historyczne przeliczenie odczytują te
bajty, a nie bieżące YAML-e/kod QA. Brak zgodności z pierwotnym hashem jest
błędem. Nie aktualizować archiwum po zmianie bieżących planów. Odbiór całego
archiwum i raportu odbywa się przez `./scripts/check`.

[Model i migracja](../../docs/ORIENTATION.md),
[raport przed/po](../migrations/t05-north.json).

T08 zachowuje dodatkowo `05_add_cave-t02.py`: dokładne oryginalne bajty
`pipeline/05_add_cave.py`, SHA-256
`f025ff0aec298c78b0a68ac16db7b06ec2010133bd8cf807f11f4def0f5b077d`.
Audyt nadal porównuje je z **oryginalnym** wpisem T02; nie zmienia katalogu,
archiwum ZIP ani żadnego dawnego hasha. Bieżące dodawanie ma własne testy T08.

T08 zachowuje także `t06-code/`: cztery moduły implementacji wskazane
w niezmienionym `docs/reports/t06-geometry-impact.json`. Ich bajty są
porównywane z oryginalnymi `after_implementation_sha256` raportu T06.
Test nadal odtwarza 814 historycznych wejść T05 i sprawdza na bieżącym kodzie
wszystkie zapisane wyniki geometrii. Rozdzielenie kodu historycznego od
bieżącego nie zmienia żadnego hasha raportu, modelu ani tolerancji.

T09 zachowuje `t02-reports/{summary,flagged,missing}.csv`: dokładne oryginalne
bajty dawnych raportów spod `data/caves/_reports/`. Historyczny audyt nadal
sprawdza pierwotne hashe `other_inputs_sha256` T02. Bieżące QA nadpisuje
wyłącznie raporty robocze w `_reports`; oryginalny katalog i hashe T02,
archiwum oraz raporty T05/T06/T07/T08 pozostają nienaruszone.
