# Północ, deklinacja i zachowanie orientacji (T05)

T05 jawnie reprezentuje niewiedzę. **Żaden z 814 planów nie otrzymał
ustalonego rodzaju północy.** Obecna generacja używa wyłącznie kąta
`atan2(D, A)` z `plans[].historical_tfw.parameters` historycznego
[katalogu T02](../data/baseline/2026-10-24/catalogue.json). Hash katalogu
jest przypięty w `orientation.py`, a hash TFW i ID planu zapisane w YAML-u.
Nie odczytuje kąta z `computed`, bieżącego sidecara, sumy dawnych poprawek
ani `recalculated-v1.3.1.json`. Zgodność historyczna nie potwierdza
poprawności geodezyjnej planu.

## Pola i ich znaczenie

| Pole | Znaczenie |
| --- | --- |
| `north.reference` | `unknown`, `geographic`, `magnetic`, `grid` |
| `north.angle_deg` | Zachowana dotychczasowa wartość kąta strzałki; samo 0° niczego nie rozstrzyga |
| `north.angle_origin` | `measured` — pomiar, także 0°; `assumed` — przyjęcie, także 0°; `unknown` — brak dowodu pochodzenia |
| `north.evidence` | Wymagane źródło/uzasadnienie ustalonego rodzaju: np. konkretny plan, legenda, strona, opis autora |
| `declination_deg` | Zachowana liczba historyczna; aktywna deklinacja w przyszłym modelu wymaga udokumentowanej podstawy |
| `declination.status` | `unknown` albo `documented` |
| `declination.basis` | Źródło wartości lub opis brakującej podstawy |
| `declination.sign_convention` | Dla `documented`: `east_positive` — wschodnia dodatnia, zachodnia ujemna |
| `declination.epoch` | Dla północy magnetycznej wymagana data lub epoka źródłowej deklinacji; przy modelu podać także model i jego podstawę w `basis` |
| `orientation.mode` | `historical_tfw` przy nieustalonej północy; `reference` przy ustalonej |
| `orientation.status` | W T05 zawsze `unverified`; samo ustalenie rodzaju nie weryfikuje geometrii |
| `orientation.uncertainty_reason` | Jawny powód niepewności, dostępny w QA, computed i manifeście |
| `orientation.image_sha256` | SHA-256 treści TIFF-a objętego decyzją; musi odpowiadać obrazowi i rejestrowi T03 |
| `orientation.historical` | Niezmienny hash katalogu T02, ID planu i hash historycznego TFW |
| `orientation.decisions` | Jawny łańcuch zmian wejść orientacji: hash przed/po, działanie, powód i data |

Migracja oznacza `all_skipped: true` jako `angle_origin: assumed`.
Pozostałe plany dostają `unknown`: samo `all_skipped: false` ani kąt 0°
nie stanowią dowodu rodzaju północy lub pomiaru. Oryginalne pola i precyzja,
w tym ręczne korekty, pozostają bez zmian. Historyczne `declination_deg`
nie dostaje domniemanej konwencji ani epoki: status jest `unknown`,
wartość nie uczestniczy w nowej generacji historycznego kąta.

## Zmiany po migracji

Bieżące współrzędne z przypiętego CSV, kliknięcie otworu i skala pozostają
aktywne. Zmiana skali zmienia długość wektorów TFW, a zmiana współrzędnych
lub kliknięcia — ich zakotwiczenie. Żadna z nich nie zmienia historycznego
kąta, nawet gdy inna długość geograficzna dawniej zmieniałaby zbieżność.
Nie istnieje ukryta poprawka kierunku przeliczana z nowej pozycji.

Wejścia orientacji to całe sekcje `north`, `declination`, `image` i wartość
`declination_deg` oraz `orientation.image_sha256` (treść TIFF-a). Ich hash jest porównywany z migracją oryginalnego YAML-a
T02, a następnie z łańcuchem jawnych decyzji. Obraz jest objęty również
niezależną walidacją i rejestrem T03. Sama zmiana rejestru nie uprawnia
do dziedziczenia orientacji T02 przez nowy obraz: wymaga także nowego
`orientation.image_sha256` i decyzji obejmującej ten hash. Zmiana hasha/ID historycznego TFW jest
odrzucana nawet z decyzją. Nie odświeżaj archiwum, katalogu ani ich hashy.

Po edycji danych jednego planu zapisz decyzję (przed generowaniem):

```sh
python pipeline/orientation.py decide --meta data/caves/001131/meta.yaml \
  --date 2026-10-25 --reason 'Konkretne źródło i uzasadnienie zmiany; świadome zachowanie kąta T02.'
```

Komenda dopisuje hash przed/po i działanie, wybiera tryb odpowiadający
zadeklarowanemu rodzajowi; nie zmienia odniesienia T02 i nie nadaje statusu
zweryfikowanego. Pusty powód, błędna data, niespójny łańcuch i brak faktycznej
zmiany są błędami. Nie jest to potwierdzenie prawdziwości dostarczonego źródła;
źródło oraz diff decyzji ocenia reviewer PR.

Przejście np. na `geographic` wymaga `north.evidence` i opisania pochodzenia
kąta, następnie decyzji. `magnetic` wymaga dodatkowo udokumentowanej wartości,
konwencji i epoki deklinacji. **W T05 każda generacja `geographic`, `magnetic`
lub `grid` kończy się błędem „brak modelu … wymagany T06”.** Nie stosuje
zastępczo wzoru historycznego, także w przejściowym CLI bez `--output-dir`.
Brak metadanych T05 również jest błędem. Dodanie planu bez odniesienia T02
wymaga rozstrzygnięcia w T08; ten etap nie zgaduje jego orientacji.

## Migracja i niezależna historia

[Raport migracji](../data/migrations/t05-north.json) wymienia każdy plan,
cztery dodane pola/sekcje przed i po, hashe YAML-i oraz historycznego TFW.
Osobno deklaruje brak zmiany wejść położenia i skali. Nie przypisuje nowemu
buildowi identyczności pełnych TFW: bieżący CSV i skala/otwór pozostają aktywne.
Nie zmienia `computed` ani zapisanych historycznych TFW.

Oryginalne 814 YAML-i i kod QA są zachowane bajtowo w
[data/history/t02-inputs.zip](../data/history/t02-inputs.zip), pod oryginalnymi
ścieżkami. Każdy wpis jest weryfikowany **oryginalnym** SHA-256 z katalogu T02.
Cały dotychczasowy `data/baseline/2026-10-24`, jego hashe, kopie kodu,
parquety i obrazy pozostają identyczne. Audyt i przeliczenie historii czytają
archiwum i zamrożony generator; nie zależą od bieżących YAML-i ani modelu T05.
Dla czystego checkoutu T02 bez archiwum nadal odczytywane są oryginalne ścieżki.

W przypiętym środowisku można ponowić odbiór bez zapisu YAML-i:

```sh
python pipeline/migrate_north.py --report /tmp/t05-north.json
cmp /tmp/t05-north.json data/migrations/t05-north.json
python pipeline/catalogue_baseline.py verify
python pipeline/catalogue_baseline.py recalculate --output /tmp/recalculated.json
cmp /tmp/recalculated.json data/baseline/2026-10-24/recalculated-v1.3.1.json
./scripts/check
```

`--apply` jest jawną opcją zapisu migracji. Narzędzie przyjmuje tylko
oryginalne bajty lub dokładny już zmigrowany wynik i odrzuca obce edycje;
nie służy do aktualizacji planów po późniejszych decyzjach. Archiwum powstało
jednorazowo przed migracją, z kontrolą wszystkich oryginalnych hashy.

Nowy tryb T04 snapshotuje także katalog T02 i archiwum YAML-i; hashe oraz
status/powód trafiają do manifestu. Kontrola ścieżek, GeoTIFF i atomowa
publikacja pozostają obowiązkowe. QA dodaje cztery kolumny do `summary.csv`;
wersjonowane stare CSV nie są nadpisane. Przebudowa QA i wyjątków to T09,
przełączenie workflow to T10/T11; modele, znak zbieżności i półpiksel to T06.
