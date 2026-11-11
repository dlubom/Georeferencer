# Lodowa w Ciemniaku (001701) — georeferencja ryciny 2

## Źródło i pomiary rastra

Rycina 2 ze s. 408 artykułu Barabacha i in. (2023) pokazuje plan z pomiarów
z 2021 r. i zasięg lodu z 11 września 2021 r. Autorzy rysunku z 2022 r. to
Jan Barabach, Michał Filipiak i Adam Łada. Pochodzenie, sumy SHA-256 oraz
współrzędne pomiarów zapisano obok planu. [Dane źródłowe](../../data/caves/001701/source.json) ·
[Rycina 2](https://rcin.org.pl/Content/240185/WA51_276513_r2023-t96-no4_G-Polonica-Barabach.pdf#page=4) ·
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

Z PDF-u wyodrębniono osadzony JPEG w natywnej rozdzielczości 1286 × 1071 px.
Wersja do GeoTIFF-u ma te same wymiary i używa konwersji 1-bit Floyd–Steinberg.
Kropki oddają niebieskie pola lodu. GeoTIFF zawiera atrybucję, DOI, licencję
i opis przekształcenia. Dotychczasową grafikę 1217, obie wersje JPG, TFW
i YAML zachowano bajtowo w [archiwum](../../data/archive/caves/001701).

| Parametr | Wynik |
| --- | --- |
| Siatka co 10 m | 10,34036 px/m w osi poziomej i 10,34126 px/m w pionowej |
| Skala użyta w generatorze | 10,3408 px/m (0,09670 m/px) |
| Kotwica | Środek symbolu Koziej Koleby przy przecięciu siatki 0/0, piksel (68,6; 675,2) |
| Współrzędne kotwicy EPSG:2180 | E 564 952,38 m, N 152 212,64 m (KSW-0173, m-002, pin GPS Kataster v1.3.3) |
| Oś strzałki `Ng` | 0° od pionu obrazu, oszacowane na odcinku 62 px |
| Obrót osi x względem wschodu siatki | +0,67598° przeciwnie do ruchu wskazówek zegara |

Środki linii oszacowano z jasności pikseli na górnym i prawym marginesie,
a skalę i przecięcie 0/0 wyznaczono dopasowaniem prostych. Maksymalne
odchylenia środków od dopasowania wynoszą 0,14 px w poziomie i 0,52 px
w pionie. Odczyt transformacji GeoTIFF-u daje rozpiętości 100,009 m i
69,986 m dla odcinków opisanych na siatce jako 100 m i 70 m.

Roboczo odczytano `Ng` jako północ geograficzną. Przyjęty obrót to
zbieżność południków EPSG:2180 w punkcie kotwicy. Kierunek strzałki w
GeoTIFF-ie sprawdzono przez rzut dwóch punktów tego samego południka.
Znaczenie skrótu wymaga potwierdzenia u autorów. Status orientacji to
`unknown/unverified`.

## Odczyt GeoTIFF-u i porównanie z poligonem

Wynik generatora odczytano w GDAL i wyrenderowano w QGIS 4.0.1. Kontrola
potwierdziła EPSG:2180, jeden kanał 1-bit, CCITTFAX4, zgodność wszystkich
pikseli z wejściowym TIFF-em i numeryczny błąd kotwicy poniżej 1 µm.
Kod publikacji mapy JKTZ wyrenderował z tego GeoTIFF-u podgląd
512 × 428 px oraz 13 kafli WebP. [Rewizja kodu mapy](https://github.com/dlubom/jktz-mapa/commit/59feb7ae958958ef3aeebdbe09a786b09c68666c)

Z modelu KATASTER z rewizji `30dbedf` odczytano w Survex 1.4.24 współrzędne 71 nazwanych
stacji i 67 odcinków poligonu głównego oraz bocznych ciągów, z pominięciem
domiarów. Przekształcono współrzędne z EPSG:32634 do EPSG:2180 bez
dopasowania poligonu do obrysu. W danych stacja `gc0` wypada 0,005 m
od kotwicy `KSW-0173`, w granicach zapisu współrzędnych Survex do 1 cm.
[JKTZ PR #162](https://github.com/dlubom/Jaskiniowy-Kataster-Tatr-Zachodnich/pull/162)

Ciąg `gc17–gc24` ma 20,01 m długości w rzucie poziomym i przebiega
wzdłuż rysunku Ssaka. `gc24` wypada około 0,88 m od wskazanego na rastrze
końca obrysu (piksel 1082,5; 944,5). Rycina i poligon pochodzą z tej
samej kampanii. Identyfikacja stacji i dowiązanie Partii górnych
pozostają do potwierdzenia w źródłach pomiarowych.
