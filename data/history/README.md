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
