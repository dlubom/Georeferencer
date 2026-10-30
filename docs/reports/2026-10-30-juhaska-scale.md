# Jaskinia Juhaska — korekta skali (2026-10-30)

Plan `001212`, `T.D-14.01`, grafika CBDG 694 „plan i przekrój”, wg K. Kowalskiego
(1953, uzupełnione). Źródło: [PIG, karta 1212](https://jaskiniepolski.pgi.gov.pl/Details/Information/1212),
odczyt 2026-10-30. Karta przypisuje dokumentację K. Kowalskiemu (10.08.1951),
podaje długość 23 m i opis komory szerokości 5 m. Są to dane pomocnicze,
a nie odcinki kalibracyjne; długość jaskini nie jest jej zasięgiem poziomym.

## Pomiar i rozstrzygnięcie konfliktu

Pomiar na niezmienionym `data/caves/001212/image.tif`, 3674 × 3004,
SHA-256 `7edb9544268754e15d001f7663929c7e83783cbf6642b5103063e01f39db5e61`.
Oryginalny JPG ma 1837 × 1502; wszystkie poniższe piksele dotyczą TIFF-a 2×.

W dwóch osobnych pasach x=[180,350) oraz [850,1250) znaleziono poziome linie
opisane 0,0 / −10,0 / −20,0. Wiersze czarnych pikseli pokrywających ponad 90%
szerokości pasa to odpowiednio 602–605, 1580–1583 i 2559–2562.
Ich środki dają:

| Odcinek siatki | Długość w pikselach | Skala |
| --- | ---: | ---: |
| 0 → −10 | 978 | 97,8 px/m |
| −10 → −20 | 979 | 97,9 px/m |
| 0 → −20 | 1957 | **97,85 px/m** |

Podziałka „0 — 1 m” przy strzałce N ma około 196 px, czyli wartość sprzeczną
z opisanymi liniami siatki o czynnik około 2. Konflikt jest już w oryginalnym
JPG; nie wynika ze zmiany rozdzielczości. Dwa surowe zgłoszenia mierzyły
odcinek siatki 20 m (97,8673 i 98,0217 px/m), a trzy podziałkę 1 m
(196,4144, 194,9050 i 196,8724 px/m). Mediana 194,9 wybrała drugą grupę.

Do georeferencji przyjęto **siatkę**, z dwóch zgodnych interwałów.
Opis rozmiaru komory dodatkowo wspiera większy plan. Nie ustalono genezy
błędnej etykiety podziałki ani dokładności terenowego pomiaru; rastra nie
retuszowano. Decyzja dotyczy wyłącznie skali tego planu, bez zmiany agregatora.

## Wpływ i odbiór

- `scale.pixels_per_meter`: 194,9 → 97,85; wymiary liniowe rosną 1,991824 razy.
- Interwały 10 m miały w generowanym układzie 5,018 i 5,023 m;
  po korekcie mają 9,99489 i 10,00511 m (tolerancja odczytu 3 px ≈ 0,03 m).
- Punkt otworu (551,1; 603,52) pozostaje w pozycji `STR-0011` z przypiętego
  CSV v1.3.2. Historyczny obrót T02 i status `unknown/unverified` pozostają.
- Surowe zgłoszenia, `quality`, historyczne `computed`, TFW, archiwum T02
  i hashe odniesienia nie są przepisywane. Nowy wynik powstaje w buildzie.
- Test `tests/test_juhaska_scale.py` wykrywa poprzednią skalę i kontroluje
  obie odległości w wygenerowanej transformacji oraz niezależną projekcję otworu.
- Trzy dotychczasowe wyjątki QA tego planu nadal opisują te same niepewności:
  konflikt surowych skal, słabe wsparcie północy i nieustalony rodzaj północy.
  Po przeglądzie zachowano ich dowody; powiązanie z nowym YAML-em zmieniono
  wyłącznie dla `001212`. Korekta nie nadaje orientacji statusu zweryfikowanej.
