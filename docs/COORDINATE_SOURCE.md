# Współrzędne i historyczny punkt odniesienia

Build korzysta z [data/coordinate-source/source.json](../data/coordinate-source/source.json):
release **v1.3.2** repozytorium `dlubom/gps-kataster-obiektow-tatr`, artefakt
`best-measurements.csv`, SHA-256
`6ef2607dacc02933240e820c42a0bab544790a38b5594a730fc4130b105c9ec0`.
Surowe bajty CSV są wersjonowane obok opisu. Hash pobranego pliku potwierdzono
z digestem assetu [release v1.3.2](https://github.com/dlubom/gps-kataster-obiektow-tatr/releases/tag/v1.3.2).
Poprzedni CSV i dokładny opis zachowano jako `best-measurements-v1.3.1.csv`
i `source-v1.3.1.json`. Nowy opis jest też w `source-v1.3.2.json`.
[Raport aktualizacji](reports/coordinate-source-v1.3.2-impact.json) obejmuje cały
katalog; [odbiór i ponowna ocena dziewięciu wyjątków](plans/2026-10-25-gps-v1.3.2-odbior.md)
wyjaśniają zakres zmiany. Żaden pin nie jest deklaracją źródła dawnych TFW.

## Użycie i odtworzenie snapshotu

Z katalogu repozytorium, Python 3.12 (sam helper wymaga tylko biblioteki standardowej):

```sh
python pipeline/coordinate_source.py verify
python pipeline/coordinate_source.py copy --output /tmp/georeferencer-best-measurements.csv
# Niezależne odzyskanie dokładnie tego release z GitHub, kontrola przed zapisem:
python pipeline/coordinate_source.py fetch --output /tmp/georeferencer-downloaded.csv
python pipeline/coordinate_source.py verify --csv /tmp/georeferencer-downloaded.csv
```

`fetch` buduje URL z konkretnego release i nazwy assetu. Nie rozwiązuje `latest`.
`copy` używa wersjonowanego snapshotu bez sieci. Oba polecenia odrzucają
niezgodny hash przed zapisem; błędne pobranie nie zastępuje dotychczasowego pliku.
Usunięcie albo podmiana assetu na GitHub nie niszczy kopii w Git.

Oba workflow używają `scripts/build` i przypiętego środowiska. Generator
sam weryfikuje i snapshotuje pin/CSV przed obliczeniami. Ręczne wydanie używa opisu źródła z wybranego checkoutu
tagu; usunięto parametr pozwalający zastąpić ten opis dowolnym tagiem. Stare tagi
sprzed T02 nadal zawierają stary workflow — T02 nie przepisuje ich historii.
Wybranie takiego tagu w bieżącym ręcznym workflow zakończy się błędem braku
opisu/helpera, zamiast pobraniem zmiennego źródła. Odtwarzanie dawnego wydania
wymaga jego własnego kodu i ustalenia ówczesnych źródeł.
T10 przełącza środowisko wydania, zapis wyników i pełne QA; T11 niezależnie
sprawdzi bramki i odtwarzalność.

Od T03 produkcyjny generator sam sprawdza pin T02. Jawny argument
`--gps-kataster-best-measurements` musi odpowiadać hashowi z `source.json`;
bez argumentu używa zapisanego snapshotu. Dowolne katalogi syntetyczne są
obsługiwane wyłącznie przez niskopoziomowe API testów, nie przez produkcyjne CLI.
Helper nadal pozwala jawnie odtworzyć i zweryfikować bajty:

```sh
python pipeline/coordinate_source.py copy --output /tmp/georeferencer-best-measurements.csv
python pipeline/02_generate_geotiff.py --cave 001131 \
  --gps-kataster-best-measurements /tmp/georeferencer-best-measurements.csv \
  --gps-kataster-strict
```

Generator zawsze używa [osobnego katalogu T04/T10](GENERATION_OUTPUT.md),
z manifestem i kontrolą wyniku. Domyślnie jest to `build/geotiff`;
`--output-dir /tmp/georeferencer-results` wskazuje inne miejsce. **Nie jest poleceniem
odbioru T02.** Odbiór T02 używa odczytu i raportów opisanych niżej.

## Jawna aktualizacja źródła

1. W osobnym PR zachowaj nowy surowy CSV pod nazwą zawierającą release oraz nowy
   opis JSON. Wskaż konkretny release, asset i digest potwierdzony u wydawcy.
   Zachowaj poprzedni snapshot i opis (np. `source-v1.3.1.json`); nie nadpisuj CSV.
2. Zweryfikuj kandydata i przygotuj raport względem dotychczasowego opisu:

   ```sh
   python pipeline/coordinate_source.py --manifest data/coordinate-source/candidate.json verify
   python pipeline/coordinate_source.py impact \
     --candidate data/coordinate-source/candidate.json \
     --output /tmp/coordinate-impact.json
   ```

3. Dołącz raport do PR. `affected_plans` obejmuje wszystkie bieżące powiązania
   zmienionych obiektów; `changes` zawiera wszystkie różnice pól, pełne rekordy
   przed/po, identyfikatory pomiarów oraz dodane/usunięte obiekty, również bez
   powiązanego planu. Powtórzone `object_id` blokuje raport, zamiast gubić rekord.
4. `geometry` porównuje obie wersje CSV przy tym samym bieżącym generatorze
   i YAML-ach. Osobno pokazuje przesunięcie w otworze, obrót i skalę TFW.
   Parametry wejściowe skali i północy pozostają identyczne. Od T05 nieustalona
   północ zachowuje kąt historycznego TFW niezależnie od zmiany pozycji;
   nie jest przeliczana ukryta zbieżność. Ustalony rodzaj korzysta z modelu T06; geographic/magnetic uwzględnia
   zbieżność dla bieżącej pozycji. Położenie w raporcie bieżącego modelu
   używa narożnikowej konwencji kliknięć T06; audyt historii zachowuje własną
   dawną interpretację.
   Brak obiektu w nowym CSV jest jawnym błędem
   per-plan w raporcie geometrii, wymagającym rozstrzygnięcia przed zmianą pinu.
5. Po review podmień `source.json`, uruchom `./scripts/check` i opisz listę planów,
   pomiarów oraz wpływ. Historyczny katalog bazowy pozostaje bez zmian. Jeżeli
   zmiana celowo zmienia wejścia katalogu lub generator, dostosuj test porównania
   bieżących wejść z historią do jawnego raportu różnic; nie przepisuj historii,
   aby wyzerować różnice.

## Punkt odniesienia 2026-10-24

[data/baseline/2026-10-24/catalogue.json](../data/baseline/2026-10-24/catalogue.json)
zachowuje stan `fad70f09992671a0da5a364dfea4a2c538f80e3d`: **814 planów**,
801 z crowdsourcingu i 13 ręcznych. Sprawdzono, że wejścia tego stanu były
niezmienione na bazie T02, `52c031533aa7f76c54e8eb9c9d50aa60af4b6cd1`
(scalony T01 / PR #17).

Dla każdego planu zapisano nazwę i identyfikatory, SHA-256 `meta.yaml`, wszystkich
obecnych źródłowych TIFF/JPG, istniejącego `image.tfw`, pełny tekst TFW i sześć
parametrów w kolejności A,D,B,E,C,F. Są też jawne powiązania z `object_id` i pełnym
rekordem pomiaru z przypiętego CSV. To powiązanie identyfikuje wejście nowego buildu;
nie dowodzi, że ten pomiar posłużył do dawnego TFW. Hashe parquetów, raportów QA
i starego kodu zabezpieczają kontekst reprodukcji review. Pliki wejściowe można
odzyskać z wymienionego commitu Git; manifest nie kopiuje obrazów.

**T05 pobiera orientację historyczną z `plans[].historical_tfw`**, a nie z
`computed` ani ponownego obliczenia wzoru. Historia nie jest potwierdzeniem
poprawności geodezyjnej.

[recalculated-v1.3.1.json](../data/baseline/2026-10-24/recalculated-v1.3.1.json)
to osobna klasa: przeliczenie starego generatora na przypiętym CSV, w środowisku
T01. Wszystkie 814 planów można przeliczyć; **28 TFW różni się bajtowo** od
historycznych. Raport wymienia te plany i oddzielnie podaje zmiany położenia,
obrotu oraz skali. Nie ustala przyczyny każdej dawnej różnicy; nie można nazwać
ich zbiorczo aktualizacją współrzędnych ani naprawą rotacji. Parametry nie zostały
zapisane do `data/caves`.

## Odtworzenie kontroli i raportów

```sh
./scripts/check
docker build --platform linux/amd64 --iidfile /tmp/georeferencer-audit-image ci
audit_dir=$(mktemp -d)
docker run --rm --platform linux/amd64 --network none \
  --mount "type=bind,source=$PWD,target=/workspace,readonly" \
  --mount "type=bind,source=$audit_dir,target=/audit" \
  "$(cat /tmp/georeferencer-audit-image)" \
  python pipeline/catalogue_baseline.py verify
docker run --rm --platform linux/amd64 --network none \
  --mount "type=bind,source=$PWD,target=/workspace,readonly" \
  --mount "type=bind,source=$audit_dir,target=/audit" \
  "$(cat /tmp/georeferencer-audit-image)" \
  python -c 'from pathlib import Path; import json,sys; sys.path.insert(0,"pipeline"); import catalogue_baseline as b; Path("/audit/recalculated.json").write_text(json.dumps(b.recalculation(b.ROOT,json.loads(b.BASELINE.read_text()),b.ROOT/"data/coordinate-source/source-v1.3.1.json"),ensure_ascii=False,indent=2)+"\n")'
cmp "$audit_dir/recalculated.json" data/baseline/2026-10-24/recalculated-v1.3.1.json
```

Testy odczytują rzeczywisty punkt odniesienia, sprawdzają komplet i hashe oraz
odtwarzają raport. Rozbieżność historycznych wejść lub zamrożonego kodu blokuje audyt starego
generatora. Od T03 dwie zmienione implementacje są zachowane bajtowo w
`data/baseline/2026-10-24/legacy/` i kontrolowane oryginalnymi hashami T02;
`recalculate` używa tych kopii, a raport wpływu aktualizacji — bieżącego kodu.
Nie podstawiaj nowego generatora pod historyczne przeliczenie. Pełną dawną
sesję można też odtworzyć z checkoutu T02 i jego środowiska. `capture` służy do
tworzenia **nowego**, osobno nazwanego punktu odniesienia; wymaga Git na hoście,
pełnego `--reference-commit`, `--output` i niezmienionych śledzonych wejść.
Kontener kontroli nie potrzebuje Git, bo korzysta z zapisanego manifestu.

Ustalenia i cztery przenośne reprodukcje review opisano w
[review/README.md](../data/baseline/2026-10-24/review/README.md).

Bieżący kontrakt danych i obrazu: [VALIDATION.md](VALIDATION.md).

Migracja T05 i niezależny od bieżących YAML-i odczyt archiwum historii:
[ORIENTATION.md](ORIENTATION.md). Oryginalne hashe T02 pozostają bez zmian.
