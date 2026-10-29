# Piwnica Miętusia — dodatkowy plan z publikacji PZA

Plan `001459-pza-2024` pochodzi ze strony 17
[Polish Caving 2017–2025](https://pza.org.pl/wp-content/uploads/2025/07/POLISH-CAVING-2017-2025.pdf#page=17).
Rysunek: **Zestawienie: P. Graczyk, 2024**. Wzmianka artykułu o 2940 m
nie potwierdza objęcia tej długości rysunkiem podpisanym 2024.

Wycięto górny rzut poziomy bez dolnego przekroju W–E. Wektorowy PDF
wyrenderowano w 1100 dpi do TIFF-a 1-bit/CCITTFAX4, 7630 × 5020.
Hash PDF-u, kadr, pomiary i pochodzenie JPG-ów są w
[`source.json`](../../data/caves/001459-pza-2024/source.json).
ID `20250017` należy do `local:pza-polish-caving`, nie do PIG/CBDG.

## Pomiary i orientacja

Kliki dotyczą nowego obrazu mono: początek w narożniku, środek piksela (.5,.5).

| Parametr | Pomiar |
| --- | --- |
| Otwór | (6194,5; 275,5), środek trójkąta przy siatce 0/0 i opisie 1396,0 m |
| Skala | (1582,5; 353,5) → (2351,5; 353,5): 769 px / 20 m = 38,45 px/m |
| Kontrola skali | Siatka x=3119,5 → 6194,5: 3075 px / 80 m = 38,4375 px/m |
| Północ | Oś N (2455,5; 430,5) → (2455,5; 260,5): zmierzone 0° |

![Punkty ręcznej georeferencji](assets/piwnica-pza-manual-points.png)

Kotwica: przypięty gps-kataster **v1.3.2**, obiekt **MTZ-0017**, pomiar **m-002**.
Rodzaj północy nie jest opisany: `unknown/unverified`. Jawnie przyjęto N jako
geograficzną i obrót **+0,679677158507°** w EPSG:2180 (`assumed_grid`).
Wyjątek QA `orientation.unknown` wymaga potwierdzenia autora, jawnej decyzji
i ponownego odbioru. Nie przyjęto poprawki magnetycznej.

## Odtworzenie rastra

Sprawdź hash PDF-u z `source.json`, następnie wykonaj:

```sh
pdftoppm -f 17 -l 17 -r 1100 -x 855 -y 733 -W 7630 -H 5020 \
  -png -singlefile POLISH-CAVING-2017-2025.pdf /tmp/piwnica-plan
```

```python
from PIL import Image
im = Image.open('/tmp/piwnica-plan.png').convert('RGB')
im.convert('L').point(lambda p: 255 if p >= 200 else 0, mode='1').save(
    '/tmp/piwnica-image.tif', compression='group4', dpi=(1100, 1100))
```

Zmiana rastra wymaga nowych kliknięć i decyzji orientacji.

## Odbiór i wpływ

T03/T04: zgodne piksele, wymiary, EPSG:2180 i kompresja. Niezależny odczyt
GeoTIFF-a daje 19,999999973 m podziałki i błąd kotwicy 0,000000403 m
(kontrola numeryczna, nie dokładność terenowa). Test wykrywa zmianę skali +10%.
Plan odebrano w stagingu funkcjami T03/T04 i opublikowano bez zastępowania celu.
Stary `001459` pozostał bajtowo bez zmian; katalog rośnie z 814 do 815 planów.
Poprawka `coordinate_source.py impact` usuwa wymóg historycznego TFW nowego T08;
test regresji obejmuje oba plany Piwnicy. Historia i hashe pozostają bez zmian.
Wyniki `./scripts/check`, wersje środowiska i CI: [PR #34](https://github.com/dlubom/Georeferencer/pull/34).
