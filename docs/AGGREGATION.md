# Agregacja crowdsourcingu T07

`pipeline/crowdsourcing.py` jest warstwą analizy bez zapisu katalogu.
`pipeline/migrate_crowdsourcing.py` odtwarza i stosuje konkretną, selektywną
migrację T07. `01_extract_yaml.py` pozostaje narzędziem historycznej ekstrakcji
i dowodem T02; **nie uruchamiaj pełnej ekstrakcji ani `--force` w celu korekty
istniejącego katalogu**. Nowy agregator nie wytwarza współrzędnych ani TFW.

## Kwalifikacja i liczniki

[Rejestr TEST](../data/classification/test-submissions-v1.json) wskazuje siedem
stabilnych `submission_id`, uzasadnienie, dowód markera w konkretnym parquet
i SHA-256 źródła. Wykluczenie wynika wyłącznie z listy ID; sam brak przydziału
ani marker nowego rekordu nie tworzą reguły wykluczania. Surowe źródła pozostają
niezmienione. Zmiana snapshotu wymaga ponownego przeglądu klasyfikacji.

Agregator liczy obserwacje i odrębne `user_id` niezależnie. To identyfikatory
użytkowników, nie potwierdzona liczba osób. Każda obserwacja ma wagę jeden;
powtórne zgłoszenia jednego użytkownika nie zwiększają liczby niezależnych ID.

| Komponent | Ważna obserwacja | Wynik |
| --- | --- | --- |
| otwór | skończone x/y pierwszego punktu | mediana geometryczna Weiszfelda: do 100 iteracji, próg 1e-7 px |
| skala przed IQR | zapisane skończone `pixels_per_meter > 0` | lista wartości i ID; nie rekonstruujemy ppm z odcinka i realScale_m |
| skala po IQR | wartość w [Q1−1.5 IQR, Q3+1.5 IQR], od 4 obserwacji | mediana, CV, osobny licznik użytkowników i lista odrzuconych ID |
| północ | logiczne `skipNorth=false`, skończony kąt oraz dwa kompletne, skończone, różne punkty 3/4 strzałki | mediana kołowa na jednoznacznym łuku krótszym niż 180° |

Strzałka pionowa jest ważnym pomiarem **0°**. Brak strzałki, identyczne punkty,
NaN/Inf albo niekompletne punkty nie są pomiarem zera. Brak ważnych pomiarów
daje `angle_deg: null`, `angle_origin: unknown`. Jeśli kąty nie mieszczą się
w otwartym półokręgu, wynik również jest null, z `ambiguous: true`; agregator
nie wybiera arbitralnego kierunku. Wynik numeryczny należy do [-180°,180°).
Rodzaj północy nie jest wnioskowany z pomiaru strzałki.

Przed obliczeniami rekordy są sortowane po `submission_id`; powtórzone ID,
brak ID użytkownika i mieszane tożsamości obrazów są błędami. Listy dowodowe
mają tę samą kolejność, niezależną od kolejności wejścia. `aggregate_catalogue`
zachowuje każdą grupę, również całkowicie wykluczoną i poniżej progu. Pole
`eligible` oznacza próg odrębnych użytkowników zachowanych zgłoszeń NORMAL;
nie zastępuje liczników ważnych pomiarów poszczególnych komponentów.

Snapshot: 4048 zgłoszeń, 7 TEST, 4041 pozostałych, 827 grup. Historyczny katalog
obejmuje 801 grup (4006 nietestowych obserwacji): 800 ma 5 użytkowników,
001337 ma 6. Pozostałe 26 grup nie staje się nowymi planami w T07.
Ważnych pomiarów północy jest 1717. Rozkład liczby ich niezależnych użytkowników
to 0:7, 1:197, 2:311, 3:249, 4:34, 5:3; pięć zgłoszeń całej grupy nie oznacza
pięciu ważnych strzałek. Walidacja obrazu i położenia kliknięcia pozostaje T03.

## Migracja i ręczne edycje

Baza T07 jest odtwarzana z oryginalnych bajtów T02 i dokładnej migracji T05,
sprawdzanej zapisanymi hashami raportu T05. T06 nie zmienił YAML-i.
T07 porównuje każdy komponent ze starym agregatem. Odmienna wartość pozostaje
nienaruszona; trafia do `preserved_edits`, z dowodem ręcznej korekty albo
`requires_decision`. Różnica sama w sobie nie dowodzi błędu.

[Rejestr ręcznych kątów](../data/classification/manual-north-v1.json) wskazuje
sześć korekt z commitu `320b14089357d544ba2a1bb35679aea6b12bdb10` i ich ponowne
nałożenie w `2d2ec311134e2d47ee580ead8143d76d460aaf99`. Wszystkie pozostają,
także **50° Mroźnej** wobec nowego agregatu 50.002°. Nie znaleziono innych
niewyjaśnionych rozbieżności badanych komponentów w tym snapshotcie.

Migrator zmienia cztery plany TEST i osiem dodatkowych YAML-i z ważnymi
pomiarami po usunięciu niekompletnych zapisów północy. Dwa pozostałe plany
niekompletnej północy (001050, 004068) pozostają bajtowo niezmienione:
ich stary numeryczny kąt ma nadal pochodzenie `unknown`, a agregat jest null.
W raporcie ujęto wszystkie 14 przypadków, w tym brak zmiany.

Zmiany `north` mają jawne decyzje z powodem, hashem treści obrazu i łańcuchem
hashy wejść. `reference: unknown`, `status: unverified` i historyczne odniesienie
pozostają. Kąt wyniku pochodzi tylko z historycznego TFW T02, a współrzędne,
kliknięcie i skala pozostają aktywne. Migracja nie modyfikuje `computed`, TFW,
powiązań otworów ani 13 ręcznych planów. Zmiany jakości dotyczą tylko czterech
planów TEST; przebudowa raportów QA pozostaje T09.

## Odtworzenie i zapis

W przypiętym środowisku [wspólnej kontroli](../ci/README.md), bez zapisu
katalogu. Po aktualizacji runtime do v1.3.2 odtworzenie historycznego T07
wymaga zachowanego CSV i opisu v1.3.1. Poniższa rekonstrukcja wejścia
zachowuje w raporcie oryginalną nazwę `source.json` oraz liczy rzeczywisty
hash jego zachowanych bajtów; nie podmienia aktywnego pinu ani nie zmienia
oczekiwanego raportu. Tak samo działa test historyczny w `./scripts/check`.

```sh
PYTHONPATH=pipeline python - <<'PY'
import json
from pathlib import Path
from unittest.mock import patch
import migrate_crowdsourcing as migration
from coordinate_source import DEFAULT_MANIFEST, ROOT, sha256, verify

pin = ROOT / 'data/coordinate-source/source-v1.3.1.json'
def historical_hash(path):
    return sha256(pin if Path(path) == DEFAULT_MANIFEST else path)

with patch.object(migration, 'verify', lambda: verify(pin)), \
        patch.object(migration, 'sha256', historical_hash):
    report, _ = migration.migration()
Path('/tmp/t07-impact.json').write_text(
    json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
PY
cmp /tmp/t07-impact.json docs/reports/t07-aggregation-impact.json
./scripts/check
```

Bez `--apply` nie zapisuje YAML-i. Zapis przyjmuje wyłącznie dokładną bazę T07
albo dokładny wynik T07. Późniejsze edycje, także komentarze, blokują migrację
przed pierwszym zapisem. Nie jest to narzędzie do cofania późniejszych korekt.
Zapis przechodzi walidację T03 i nie uruchamia pełnej ekstrakcji.

[Raport JSON](reports/t07-aggregation-impact.json) zawiera pełne pola przed/po,
dokładne różnice, agregat i jego liczniki, historię ręcznych odstępstw oraz
osobne efekty geometryczne. Położenie opisuje w stałym dawnym kliknięciu,
w każdym wybranym otworze i w narożniku obrazu. Zmiana skali powoduje, że
przesunięcie zależy od punktu obrazu. Nie jest to terenowa ocena dokładności.
Raport nie poświadcza odczytu 814 TIFF-ów. [Odbiór T07](plans/2026-10-25-t07-odbior.md)
opisuje testy i rzeczywisty wynik. Historyczne raporty T02/T05/T06 i hashe
nie są odświeżane; ich testy korzystają z historycznych wejść.
