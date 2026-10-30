# Agregacja crowdsourcingu T07

`pipeline/crowdsourcing.py` jest warstwą analizy bez zapisu katalogu.
Jednorazowa migracja T07 jest zakończona; jej narzędzie usunięto.
`01_extract_yaml.py` pozostaje narzędziem historycznej ekstrakcji; **nie uruchamiaj pełnej ekstrakcji ani `--force` w celu korekty
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

## Ręczne edycje i historia

Bieżące korekty wprowadzaj w małych PR-ach, porównując agregat ze źródłem
oraz istniejącymi ręcznymi poprawkami. Różnica z agregatem nie dowodzi błędu
ręcznej korekty; nie zastępuj automatycznie aktualnych parametrów.

[Raport T07](reports/t07-aggregation-impact.json) zachowuje wynik zakończonej
migracji: zmiany 12 YAML-i, liczniki obserwacji i zachowane ręczne korekty.
Nie jest odtwarzany przez bieżące CI. Dawne narzędzia są dostępne w historii Git.
