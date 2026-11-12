# Audyt kotwic planów jaskiń wielootworowych

Punkt zaznaczony na wspólnej planszy może należeć do innego otworu niż ten zapisany w karcie planu. Na 814 planach z wersji v0.7.5 znaleziono 13 takich rozbieżności poza Lodową Małołącką, której dotyczy [PR #40](https://github.com/dlubom/Georeferencer/pull/40). Raport służy do uzgodnienia korekt poszczególnych planów.

## Połączone systemy

Różnica to odległość w EPSG:2180 pomiędzy dwoma punktami Best z przypiętej wersji GPS. O tyle przesunie się raster przy zachowaniu zaznaczonego piksela, skali i obrotu. Ostatnia kolumna wskazuje rekord systemu w GPS Kataster v2.0.2.

| Plan | Otwór wskazany na rysunku | Obecne ID → ID wskazanego otworu | Różnica | System GPS |
| --- | --- | --- | ---: | --- |
| [001364 – Pod Niżnią Zbójnicką Turnią](dowody/001364.png) | Ziobrowa, punkt 0,0 | KSW-0177 → KSW-0075 | 69,32 m | C-1052 |
| [001020 – Lisia Jama](dowody/001020.png) | Dziura Wyżnia, otwór 1 | DZI-0002 → DZI-0005 | 44,88 m | C-1050 |
| [001582 – Przy Jędrusiowej Dziurze](dowody/001582.png) | Jędrusiowa Dziura, punkt 0,0 | MLZ-0002 → MLZ-0039 | 41,76 m | C-1056 |
| [001604 – Zagonna Studnia](dowody/001604.png) | Zośka, otwór 1 | MLZ-0055 → MLZ-0057 | 9,25 m | C-1055 |

W planie `001364` cztery osoby wskazały punkt Ziobrowej, a jedna otwór pod Niżnią Zbójnicką Turnią. Piksel zapisany w `entrance.x/y` odpowiada pierwszej grupie, a przypisany identyfikator GPS `KSW-0177` wskazuje drugi otwór. Punkt GPS `KSW-0177` i stacja tego samego otworu `Ziobrowa:5.24` obliczona z poligonu JKTZ v1.4.16 różnią się o 47,55 m w poziomie. JKTZ pozostawił GPS jako punkt porównawczy i oblicza położenie stacji z sieci. Położenie drugiego otworu wymaga osobnego rozstrzygnięcia. [OTWORY.SRV](https://github.com/dlubom/Jaskiniowy-Kataster-Tatr-Zachodnich/blob/v1.4.16/Poligony/OTWORY.SRV#L471-L484) · [GPS Kataster v2.0.2 Best](https://github.com/dlubom/gps-kataster-obiektow-tatr/releases/download/v2.0.2/best-measurements.csv)

## Wspólne plansze sąsiednich obiektów

| Plan | Otwór wskazany na rysunku | Obecne ID → ID wskazanego otworu | Różnica |
| --- | --- | --- | ---: |
| [001301 – Schron przy Suchym Biwaku](dowody/001301.png) | Suchy Biwak | LEJ-0019 → LEJ-0018 | 26,23 m |
| [001711 – Schron przy Studni Kuturniańskiej](dowody/001711.png) | Studnia Kuturniańska, trójkąt w rzucie przy 0,0 i na przekroju przy T.F-10.07 | KSW-0112 → KSW-0170 | 17,01 m |
| [001614 – Komórka przy Średnim Leju](dowody/001614.png) | Średni Lej | MLZ-0075 → MLZ-0079 | 12,46 m |
| [011292 – Nyża przy Kozich Oknach](dowody/011292.png) | Kozie Okna, otwór NW | MLW-0002 → MLW-0032 | 7,12 m |
| [001175 – Żwirowa Dziura Niżnia](dowody/001175.png) | Żwirowa Dziura Wyżnia | KSW-0048 → KSW-0166 | 7,06 m |
| [001211 – Tunel pod Siwarową Dziurą](dowody/001211.png) | Schron Partyzantów II | MLZ-0051 → MLZ-0016 | 3,92 m |
| [001179 – Schron pomiędzy Żwirowymi Dziurami](dowody/001179.png) | Żwirowa Dziura Wyżnia | KSW-0034 → KSW-0166 | 3,60 m |
| [001260 – Szczelina przy Nyży z Kozicami](dowody/001260.png) | Nyża z Kozicami | MLZ-0056 → MLZ-0020 | 3,31 m |
| [001210 – Schron Partyzantów](dowody/001210.png) | Schron Partyzantów II | MLZ-0035 → MLZ-0016 | 3,11 m |

Powyższe ID odpowiadają obecnym pikselom kotwic. Przy pracy nad konkretnym planem można zachować ten punkt i wskazać jego obiekt GPS albo odczytać piksel własnego otworu obiektu z tej samej planszy, jeśli otwór można jednoznacznie wskazać w rzucie. Dwie poprawnie osadzone kopie wspólnej planszy mogą się pokrywać. Osobna decyzja dotyczy tego, które kopie mają trafić do eksportu.

## Rejestr GPS i przypadki do rozstrzygnięcia

- **Lodowa Małołącka.** PIG zachowuje dwie karty z osobnymi numerami inwentarzowymi. Otwór górny ma ID `MLW-0024` i kartę `C-0588` (PIG 1627). Dolny, historycznie Dziura pod Lodową Małołącką II, ma `MLW-0011` i kartę `C-0332` (PIG 1629). W v2.0.2 karta dolna wskazuje `C-0588` przez `system_cave_id`. PIG i TPN są zgodne co do położenia poziomego otworów. Wysokości przypisane dolnemu otworowi różnią się o 12,30 m. Cztery pary z pierwszej tabeli zachowują karty źródłowe i mają wspólne rekordy systemów. [Karta dolnego otworu](https://github.com/dlubom/gps-kataster-obiektow-tatr/blob/v2.0.2/data/caves/C-0332.yml) · [Specyfikacja rejestru](https://github.com/dlubom/gps-kataster-obiektow-tatr/blob/v2.0.2/specyfikacja_gps_kataster_obiektow_tatr_v_2.md#L137-L167)
- **Jaskinia pod Dachem (001477).** Na planszy 2950 pięć kliknięć wskazuje dolny otwór 1. Jeden obiekt `MTW-0032` w karcie `C-0404` zawiera pomiar PIG `m-001` dla dolnego otworu (1476,5 m n.p.m.) oraz punkt TPN `m-002`, oznaczony w źródle jako „górny” (1525,08 m n.p.m.). Georeferencer v0.7.5 korzysta z `m-002`. Punkty dzieli 36,05 m w poziomie, a oba pomiary nadal należą do jednego obiektu w v2.0.2. W GPS trzeba rozdzielić pomiary między obiekty w tej samej karcie jaskini i sprawdzić dotychczasowe odwołania przed decyzją, który otwór zachowa `MTW-0032`. [Dowód z planu](dowody/001477.png) · [PIG 1477](https://jaskiniepolski.pgi.gov.pl/Details/Information/1477) · [MTW-0032 w GPS v2.0.2](https://github.com/dlubom/gps-kataster-obiektow-tatr/blob/v2.0.2/data/objects/MTW/MTW-0032.yml) · [Źródło TPN, OBJECTID 836](https://github.com/dlubom/gps-kataster-obiektow-tatr/blob/v2.0.2/data/sources/tpn/snapshots/pbi-101-live-20261019/page-500.json)
- **Upłazkowa Szczelina (004372).** Grafika 12233 przedstawia wyłącznie Upłazkową Kolebę i jest identyczna z plikami źródłowymi jej planu `004371`. Potrzebna jest grafika Szczeliny albo decyzja o wycofaniu planu. [Dowód z planu](dowody/004372.png)
- **Pięć nierozstrzygniętych planów.** Schronisko w Międzyścianach „nad II” (004266), Komora Gwiaździsta (001568), Magurska (001274), Tunel Małołącki (001232) i Naciekowa (001103). Tabela ustaleń podaje powód, dla którego obecne źródła nie rozstrzygają tożsamości punktu. [Ustalenia CSV](ustalenia.csv)

## Zakres i odtworzenie

Źródłem georeferencji jest rewizja [dc8bbe0](https://github.com/dlubom/Georeferencer/commit/dc8bbe0697791c49bfe3ee04b8e75c5b86b5d83f) i jej [pin GPS v1.3.3](../../../data/coordinate-source/source.json). Ustalenia o strukturze rejestru dotyczą osobno [GPS Kataster v2.0.2](https://github.com/dlubom/gps-kataster-obiektow-tatr/tree/v2.0.2). Zrzut PIG pochodzi z [Jaskiniowego Katastru](https://github.com/dlubom/Jaskiniowy-Kataster-Tatr-Zachodnich/blob/dabf88627040d75d3e0e5237ca34dfc76f8ab0b8/doc/jaskinie_polski_pig_dump.jsonl), SHA-256 `e8fd04a43e9520480198048a58b89e67c6ea4ce2f23d749a8c5c81c2d86ed1b0`.

1. [Przegląd 814 planów](przeglad-814-planow.csv) łączy kotwicę z rekordem PIG i obiektem GPS. 145 planów ma wpis o innych otworach w PIG. Po dodaniu powiązań po numerze inwentarzowym i alternatyw z GPS sygnał dotyczy 148 planów, a w 22 można wskazać konkretne alternatywne ID.
2. Porównanie dekodowanych pikseli znalazło [12 par identycznych rastrów](identyczne-rastry.csv). Porównanie miniatur po normalizacji znalazło [18 par podobnych plansz](podobne-plansze.csv) przy progu 0,95, w tym identyczne rastry. W 17 parach bliskie sobie piksele kotwic miały przypisane różne ID GPS.
3. Rozstrzygnięcia opierają się na podpisach, symbolach i opisach źródłowych. Na PNG czerwony okrąg wskazuje piksel zapisany w YAML. Przesiew może pominąć plany o innym kadrowaniu oraz przypadki, gdzie brak podpisu lub drugiego punktu GPS.

Skrypty raportu zapisują wyłącznie pliki w swoim katalogu. Przy odtwarzaniu najlepiej uruchomić kopię katalogu raportu. Wymagają PyYAML, Pillow, PyArrow, NumPy i pyproj oraz ścieżek do wskazanego checkoutu i zrzutu PIG.

```sh
python screen.py /ścieżka/do/Georeferencer /ścieżka/do/jaskinie_polski_pig_dump.jsonl
python podobne.py /ścieżka/do/Georeferencer
python ustalenia.py /ścieżka/do/Georeferencer
```
