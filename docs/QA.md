# Bieżące QA i wyjątki T09

Raport opisuje **plany**, a nie liczbę jaskiń ani otworów. Katalog planu,
źródłowa jaskinia, graphics_id obrazu i object_id wybranego otworu są osobne.
Na wejściu T09 jest 814 planów: 801 crowdsourcingowych i 13 historycznie
ręcznych. Nie jest to limit QA. Każdy nieukryty katalog źródłowy, również
bez meta.yaml, musi zostać oceniony. Nowy ręczny plan T08 jest osobną kategorią.

```sh
# QA źródeł; nie wymaga wygenerowanych artefaktów
python pipeline/03_report.py --reports-dir /tmp/georeferencer-qa
# QA źródeł i konkretnego pełnego przebiegu T04
python pipeline/03_report.py --run-dir /tmp/georeferencer-results/current \
  --require-results --reports-dir /tmp/georeferencer-qa-with-results
./scripts/check
```

Kod zakończenia 0 oznacza brak problemów blokujących; 1 oznacza problem.
Domyślne raporty trafiają do `build/qa`, poza źródłami i przebiegiem.
`qa.json` zawiera wszystkie reguły, ich podstawy, wyjątki i uzgodnienie issues.
`summary.csv`, `flagged.csv` i `missing.csv` zachowują nazwy raportów,
ale ich aktualny schemat opisuje status wejść i wyników osobno.
Nie używaj starego quality.flag jako bramki. Brak wyniku w czystym checkoutcie
nie oznacza uszkodzonego wejścia. QA nigdy nie uruchamia ekstrakcji/migracji
ani generatora i nie zapisuje meta.yaml, TFW ani obrazów.

## Wejścia i wyniki

Obowiązują pełne kontrakty [T03](VALIDATION.md), [T05/T06](ORIENTATION.md),
[T07](AGGREGATION.md) i [T08](../pipeline/MANUAL_ADD.md). Źródła współrzędnych
są weryfikowane pinem. Wspólny i lokalny rejestr obrazu są odczytywane z ich
snapshotów, z jawnym snapshotem braku lokalnego pliku. Obraz, orientacja,
wymiary i pochodzenie są walidowane. QA nie nadaje statusu verified.

Bez `--run-dir`: `output_status=not_requested`. Istniejące sidecary w źródłach
nie są dowodem bieżącego wyniku. Z `--require-results` brak wskazanego
przebiegu jest błędem wyników. Z `--run-dir` QA raz rozwiązuje current,
sprawdza kompletny manifest T04 v1 i dokładny zestaw planów/pliki. Przebieg
jednego planu nie może potwierdzić kompletności całego katalogu.

Stany to `current`, `missing`, `stale`, `corrupt`. Sprawdzane są hashe
wszystkich źródeł planu, obecność/treść lokalnego rejestru, wspólny rejestr,
pin/CSV, pełny rekord pomiaru, kod pipeline/schemat, lock/Dockerfile/wrapper i wersje
środowiska (Python, GDAL/PROJ, pyproj i pakiety), fingerprint T10,
źródła T02, parametry, orientation i computed. Mtime nie uczestniczy w ocenie.
TFW i manifest muszą się zgadzać. GeoTIFF jest ponownie rzeczywiście czytany
przez GDAL/Pillow: CRS, transformacja, rozmiary, kompresja i zdekodowane
piksele. Stary wynik jest również badany wobec swojego zapisanego odbioru;
jego piksele nie są porównywane do nowego obrazu jako dowód uszkodzenia.

## Reguły interpretacyjne v1

Ważność komponentów i odrębne user_id pochodzą z T07, po jawnej klasyfikacji
TEST. Raport pokazuje osobno obserwacje/użytkowników otworu, skali przed/po
IQR oraz północy, listy dowodowe i wykluczenia. Użytkownik oznacza ID,
nie potwierdzoną osobę. Cała grupa pięciu zgłoszeń nie oznacza pięciu strzałek.

| Reguła | Podstawa |
| --- | --- |
| orientation.unknown | Nieustalony rodzaj północy; kąt tylko z TFW T02 albo przyjęcie assumed_grid T08 |
| orientation.unverified | Ustalony model z wymaganymi źródłami, nadal niezweryfikowana interpretacja |
| north.missing | Zero ważnych kompletnych strzałek T07 |
| north.low_support | 1–2 niezależne user_id ważnej północy; próg QA wynosi 3 |
| north.disagreement | Największa bezwzględna kołowa różnica par ważnych kątów >5° lub ambiguous T07 |
| scale.disagreement | CV ważnych skal po IQR >0.1 |
| entrance.disagreement | Rozrzut ważnych punktów otworu >10 px, zgodnie z metryką T07 |
| entrance.review | Nierozstrzygnięte dopasowanie z issue #3 |
| source.review | Uwaga issue #1 dopasowana do konkretnego aktualnego planu |

Progi wyznaczają kolejkę interpretacji; nie deklarują dokładności terenowej.
Progi są oceniane na niezaokrąglonych metrykach T07 (`raw_quality`);
zaokrąglona prezentacja nie może ukryć przekroczenia. Reguły działają
niezależnie, bez `elif` między skalą i otworem. Północ ma
osobno angle_origin, pomiar angle_deg (w tym 0°/null), użyty obrót wyniku,
mode, źródło historyczne/przyjęcie i status/powód. Nie zamieniamy unknown
na grid. Przyjęty obrót 0° nie jest pomiarem 0°.

## Egzekwowanie wyjątków

[data/qa/exceptions-v1.json](../data/qa/exceptions-v1.json) zawiera konkretne
wpisy plan_id + rule, evidence, basis_sha256, reason, sources i close_when.
Podstawa obejmuje regułę/progi, surowe hashe wejść planu (również lokalny
rejestr albo jego brak), rejestr wspólny, pomiar współrzędnych, orientację
i analizowany agregat. Dla crowdsourcingu obejmuje także hash parquetu
oraz klasyfikacji TEST. Zmiana któregokolwiek z tych wejść wymaga przeglądu.

Nie ma wildcardów ani wyjątku dla całego planu. Wpis bez bieżącej reguły,
ze starą podstawą lub powtórzony blokuje kontrolę. Nowy problem tego samego
planu pozostaje blokujący. Rejestr nie jest automatycznie odświeżany i CLI
nie ma trybu automatycznego dopuszczenia. Zmiana wyjątku wymaga PR z dowodem,
uzasadnieniem i warunkiem zamknięcia. Po rozstrzygnięciu usuń odpowiadający
wpis razem z udokumentowaną zmianą danych/obserwacji.

Błędy struktury, NaN/Inf, skali, brak wymaganych wejść, błędne ID/powiązanie,
hash/tożsamość obrazu, decyzje orientacji i problemy wyników są **techniczne**.
Ich reguły nie należą do listy dopuszczalnych wyjątków. Próba wpisania ich
do rejestru sama jest błędem. Znana niepewność interpretacji wyboru spośród
poprawnych otworów to inna sytuacja niż nieistniejące/niedozwolone object_id.

## Issues i historia

Snapshot aktualnych treści oraz pustych list komentarzy #1/#3 z 25.10.2026:
[data/qa/source-issues-v1.json](../data/qa/source-issues-v1.json).
[Obserwacje](../data/qa/observations-v1.json) wiążą uwagi z planami po dokładnej
nazwie (#1) lub jawnym ID (#3). Brak dopasowania nazwy nie dowodzi braku
planu w źródłowym PIG; pozostaje nierozstrzygniętym wpisem ze źródłem.
Czytelny obecny TIFF nie potwierdza interpretacji siatki/symbolu, ale dawna
awaria konwersji nie jest automatycznie obecnym błędem technicznym.
Raport nie tworzy duplikatów issues i nie zamyka żadnej ze spraw.

Oryginalne summary/flagged/missing T02 są zachowane bajtowo w
`data/history/t02-reports/`. Audyt historii sprawdza je **pierwotnymi** hashami
katalogu T02, osobno od nowych CSV. Oryginalny kod QA nadal jest w niezmiennym
`data/history/t02-inputs.zip`. Raporty T05/T06/T07/T08 i ich dowody pozostają.
T10 wymaga tego samego pełnego QA konkretnego przebiegu przed pakowaniem
tag/manual; T11 niezależnie odbiera te zabezpieczenia i odtwarzalność.
