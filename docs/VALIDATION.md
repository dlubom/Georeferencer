# Walidacja wejść T03

Produkcja uruchamiana przez `pipeline/02_generate_geotiff.py` sprawdza przed
pierwszym zapisem cały wybrany zestaw planów. Błąd zwraca status 1 oraz plan,
pole i regułę, np. `plan 001131: scale.pixels_per_meter: wymagana skala > 0`.
Błąd wejścia nie zmienia YAML, TFW ani poprzedniego GeoTIFF-u żadnego wybranego
planu. Walidacja nie tworzy plików. T04 dodaje opcjonalny
[osobny katalog wyników z kontrolą GeoTIFF i atomową publikacją](GENERATION_OUTPUT.md).
Dotychczasowy zapis bez `--output-dir` pozostaje przejściowo obsługiwany do T10.

## Kontrakt v1

[pipeline/meta-schema-v1.json](../pipeline/meta-schema-v1.json) jest wersjonowanym
schematem interpretowanym przez `validation.py`, bez dodatkowej biblioteki.
Istniejące YAML-e korzystają z v1 bez dopisywania pól. Schemat definiuje typy,
wymagalność i zakresy; wszystkie liczby, także w dodatkowych metadanych,
muszą być skończone. Bool ani tekst liczbowy nie zastępują liczby. Powtórzone
klucze YAML są błędem. Metadane dopuszczają mapy o tekstowych kluczach, listy
i zwykłe skalary; zbiory, daty z tagów YAML i aliasy cykliczne są odrzucane. Wymagane są m.in. dodatnia skala, dodatnie całkowite
wymiary, nazwa/ID obrazu, jawne object_id oraz lat/lon. `declination_deg`
pozostaje opcjonalne z dotychczasowym domyślnym zerem.

Kliknięcie spełnia `0 <= x < width` i `0 <= y < height`. Kontrola wyklucza
kliknięcia poza obrazem; nie rozstrzyga konwencji georeferencji środka piksela,
orientacji ani półpiksela (T05/T06). Wzór World File pozostał bez zmian.

Obraz `image.tif` musi być dostępnym, czytelnym, jednostronicowym TIFF-em
w trybie Pillow `1`, zgodnym z CCITTFAX4. Wymiary muszą odpowiadać YAML-owi.
[data/validation/images-v1.json](../data/validation/images-v1.json) wiąże katalog
planu z `filename`, `image_id`, wymiarami i SHA-256 **surowych bajtów TIFF**.
Zapobiega też podmianie obrazu przy niezmienionych wymiarach. Pierwszy rejestr
zawiera 814 obrazów, których bajty porównano z historią T02. Nie modyfikuje tej
historii i nie zastępuje wymogu nowych kliknięć po zmianie obrazu.

Nowy lub celowo zmieniony obraz wymaga osobnego wpisu/aktualizacji rejestru
w PR, z listą planów, identyfikacją źródła, hashem, wymiarami i uzasadnieniem
zgodności kliknięć. Nie wolno automatycznie odświeżać hashy po błędzie kontroli.
Opcja `--image-registry` pozwala wskazać jawny rejestr w roboczej kopii albo
teście. Bez niej stosowany jest rejestr wersjonowany. Usprawnienie ręcznego
dodawania planów pozostaje T08.

## Jedno źródło współrzędnych

CLI zawsze weryfikuje SHA-256 względem przypiętego
[data/coordinate-source/source.json](../data/coordinate-source/source.json).
Bez argumentu CSV czyta zapisany snapshot. Jawny
`--gps-kataster-best-measurements` musi wskazywać identyczne bajty CSV;
dowolny CSV/GeoJSON jest odrzucany. `--gps-kataster-strict` jest zachowany dla
zgodności istniejących poleceń, pełna walidacja jest zawsze obowiązkowa.

Loader CSV/GeoJSON sprawdza cały katalog przed filtrowaniem kategorii:
unikalne, tekstowe object_id, kategorię, skończone lat/lon w zakresach
[-90,90]/[-180,180], oraz obecne liczby x/y, wysokości i dokładności.
Katalog może zawierać inne kategorie, lecz plan może wskazać wyłącznie
`jaskinia_otwor` albo `sztolnia`. Duplikat między kategoriami też jest błędem.
Zmiana kolejności rekordów nie wybiera innego rekordu ani nie ukrywa błędu.

Wymagane jest dokładnie `coordinates.gps_kataster_object_id`. Resolver po PIG
lub numerze inwentarzowym pozostaje narzędziem migracji, nie źródłem buildu.
Lat/lon mogą mieć wyłącznie kanoniczne szablony:

```yaml
lat: '{{ gps_kataster.objects[gps_kataster_object_id].lat }}'
lon: '{{ gps_kataster.objects[gps_kataster_object_id].lon }}'
```

Dozwolona jest też skończona liczba zgodna dokładnie z rekordem katalogu.
Zawsze używana jest liczba z rekordu object_id. Sprzeczne liczby, stare
zagnieżdżone powiązania, szablon innego obiektu i inne wyrażenia Jinja są
odrzucane. YAML nie jest wykonywany jako dowolny szablon. Wszystkie 814
bieżących planów już spełnia kontrakt; nie wykonano migracji danych.

Funkcje niskopoziomowe `GpsKatasterIndex`, `validate_plan`, `process_cave`
przyjmują jawny indeks do testów syntetycznych i analiz kandydatów. Same nie
poświadczają pinu; granicą produkcyjną jest CLI. Raport aktualizacji źródła
weryfikuje oba manifesty zgodnie z [COORDINATE_SOURCE.md](COORDINATE_SOURCE.md).

## Historia i kontrola bieżącego kodu

`./scripts/check` oddzielnie sprawdza integralność historycznych danych T02
oraz obecny walidator na 814 planach i przypadkach syntetycznych. Zamrożone
moduły są opisane w [legacy/README.md](../data/baseline/2026-10-24/legacy/README.md).
Ani historyczne hashe, ani zapisane TFW nie zostały przepisane. Odbiór T03
nie nadaje historii statusu poprawności geodezyjnej.
