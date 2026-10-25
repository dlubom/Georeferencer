# T03 — plan implementacji

Specyfikacja: [T03 zaakceptowanego planu](2026-10-24-jakosc-danych-i-ci.md), issue #8.
Baza: main `3a7e00651c298444e6ed8d7a012c9c82658f8e4b`.

Cel: odrzucenie błędnych i niejednoznacznych wejść przed pierwszym zapisem.
Stos: obecny Python/PyYAML/Pillow, bez nowych zależności.

Decyzje implementacyjne: wspólny walidator i deklaratywny schemat JSON v1;
oddzielny wersjonowany rejestr obrazu wiąże plan, filename, image_id i SHA-256.
Nie trzeba migrować 814 YAML-i. Lat/lon może być kanonicznym placeholderem
albo zgodną liczbą; do obliczeń zawsze trafia rekord jawnego object_id.
CLI zawsze sprawdza pin T02; funkcje niskopoziomowe pozostają dostępne dla
syntetycznych testów i jawnego porównania kandydatów źródła.

Alternatywy: dopisywanie hashy do każdego YAML wymuszałoby migrację wszystkich
metadanych; używanie samego historycznego manifestu jako bieżącego rejestru
mieszałoby historię z kontraktem nowych wejść. Osobny rejestr zachowuje granicę.

## Kroki

- [ ] Testy negatywne loadera katalogu, schematu, obrazu i produkcyjnego CLI;
  sprawdzenie błędu przed poprawką wspólnym `./scripts/check`.
- [ ] Walidacja katalogu przed filtrowaniem kategorii, niezależność kolejności.
- [ ] `pipeline/validation.py` + `pipeline/meta-schema-v1.json`: typy, wymagane
  pola, liczby, granice obrazu, tożsamość i hash, jawne współrzędne.
- [ ] Generator: preflight całego wybranego zestawu przed zapisem; obowiązkowy
  pin w CLI, diagnostyka plan/pole/reguła. Bez zmian wzoru i organizacji wyników.
- [ ] Zamrożone źródła dwóch zmienianych modułów z bazy T02 i weryfikacja ich
  oryginalnymi hashami; historyczne przeliczenie używa tych kopii. Bieżąca
  implementacja ma osobne testy. Manifesty i wyniki T02 pozostają bez zmian.
- [ ] Pełna kontrola, próba celowej regresji, instrukcja i zapis odbioru,
  niezależne review, osobny PR i CI końcowej rewizji.

## Szczególne ryzyka i testy

Duplikat z niedozwoloną kategorią nie może zniknąć przy filtrowaniu; niepoprawny
niepowiązany rekord też blokuje katalog. Poprawny pierwszy plan i błędny drugi
nie mogą częściowo nadpisać wyników. `--changed` nie zwalnia wybranego planu
z walidacji. Podmiana obrazu o tych samych wymiarach musi zmienić wynik kontroli.
Błąd YAML, powtórzone klucze, bool zamiast liczby i szablon innego ID są błędami.

Granice: bez korekty orientacji, półpiksela, agregacji, QA i zadań T04–T11.
Surowe parquety, obrazy, YAML-e, istniejące TFW i historyczne hashe bez zmian.
