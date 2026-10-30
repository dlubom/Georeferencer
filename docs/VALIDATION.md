# Walidacja wejść T03 i metadane orientacji T05

Produkcja uruchamiana przez `pipeline/02_generate_geotiff.py` sprawdza przed
pierwszym zapisem cały wybrany zestaw planów. Błąd zwraca status 1 oraz plan,
pole i regułę, np. `plan 001131: scale.pixels_per_meter: wymagana skala > 0`.
Błąd wejścia nie zmienia YAML, TFW ani poprzedniego GeoTIFF-u żadnego wybranego
planu. Walidacja nie tworzy plików. T04/T10 zapewnia obowiązkowy
[osobny katalog wyników z kontrolą GeoTIFF i atomową publikacją](GENERATION_OUTPUT.md).
Bez `--output-dir` wyniki trafiają do `build/geotiff`; źródła pozostają bez zmian.
Cache T10 nie pomija tej walidacji.

## Kontrakt v1

[pipeline/meta-schema-v1.json](../pipeline/meta-schema-v1.json) jest wersjonowanym
schematem interpretowanym przez `validation.py`, bez dodatkowej biblioteki.
T05 rozszerza wymagane pola v1 o jawny model [orientacji](ORIENTATION.md).
Migracja 814 YAML-i jest udokumentowana osobnym raportem; brak tych pól jest błędem.
Schemat definiuje typy,
wymagalność i zakresy; wszystkie liczby, także w dodatkowych metadanych,
muszą być skończone. Bool ani tekst liczbowy nie zastępują liczby. Powtórzone
klucze YAML są błędem. Metadane dopuszczają mapy o tekstowych kluczach, listy
i zwykłe skalary; zbiory, daty z tagów YAML i aliasy cykliczne są odrzucane. Wymagane są m.in. dodatnia skala, dodatnie całkowite
wymiary, nazwa/ID obrazu, jawne object_id oraz lat/lon.
`declination_deg` jest historyczną liczbą; udokumentowana deklinacja wymaga
wartości, podstawy, konwencji znaku oraz epoki dla północy magnetycznej.
Nie ma domyślnego modelu orientacji ani zastępczego wzoru.

Kliknięcie UI w układzie narożnika obrazu spełnia `0 <= x < width` i `0 <= y < height`. Kontrola wyklucza
kliknięcia poza obrazem. T06 rozstrzyga [konwencję półpiksela i modele
północy](ORIENTATION.md): układ UI/GDAL ma początek w narożniku, a TFW
w środku pierwszego piksela. T05 zachowuje historyczny kąt dla `unknown`;
ustalone rodzaje korzystają z modeli T06, bez automatycznej weryfikacji
źródłowych metadanych. Zmiany orientacji uzasadniaj w opisie PR.

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
teście. Bez niej stosowany jest rejestr wersjonowany. Bezpieczne dodawanie nowych planów T08 opisano poniżej.

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
odrzucane. YAML nie jest wykonywany jako dowolny szablon.
Wszystkie 814 planów spełniało kontrakt współrzędnych już w T03.
Migracja T05 dodaje tylko metadane północy/deklinacji/orientacji.

Funkcje niskopoziomowe `GpsKatasterIndex`, `validate_plan`, `process_cave`
przyjmują jawny indeks do testów syntetycznych i analiz kandydatów. Same nie
poświadczają pinu; granicą produkcyjną jest CLI. Raport aktualizacji źródła
weryfikuje oba manifesty zgodnie z [COORDINATE_SOURCE.md](COORDINATE_SOURCE.md).

## Historia i kontrola bieżącego kodu

`./scripts/check` sprawdza bieżący walidator i pipeline. Archiwalne dane,
kod i raporty pozostają zapisem dawnych odbiorów; CI ich nie odtwarza ani
nie porównuje z zamrożonymi hashami T02.

## Lokalny wpis tożsamości T08

Nowy plan dodany przez `05_add_cave.py` ma `image-identity.json` w swoim
katalogu. Ma ten sam format v1 i dokładnie jeden wpis `plans[plan_id]`,
Historyczne `orientation_origin` jest opisem pochodzenia, bez blokady edycji. Wpis jest
wersjonowany wraz z obrazem i nie uzupełnia automatycznie wspólnego rejestru.
Konflikt obu rejestrów jest błędem. Pozostałe reguły T03 — wymiary, tryb,
SHA-256 treści i orientacji — obowiązują bez zmian. Rejestru T02/T03 nie
odświeżamy. Nowy plan nie może przejąć historycznej orientacji innego ID.

Schemat dopuszcza null dla `north.angle_deg` wyłącznie dla nowego unknown
w trybie assumed_grid, przy jawnym braku pomiaru. Dodatkowa walidacja T08
wymaga wtedy all_skipped=true, angle_origin=unknown oraz pełnej decyzji
przyjęcia obrotu. Pozostałe kąty wymagają skończonej liczby; zmierzony 0°
pozostaje pomiarem. Nowe plany mają obowiązkowe źródłowe ID jaskini,
pochodzenie obrazu, kliknięcia i skali oraz pin współrzędnych w `provenance`.

Oba tryby generatora automatycznie odczytują lokalny rejestr. T04 używa
snapshotu jego surowych bajtów i zapisuje hash w `plans[].inputs`, obejmuje
plik kontrolą ścieżek/dowiązań oraz zmian podczas generowania. API testowe
przyjmuje `identity_text`; `False` oznacza jawny snapshot braku tego pliku,
`None` pozwala na zwykły odczyt z katalogu. Nie jest to przełącznik pomijający
kontrolę obrazu. [Instrukcja dodawania](../pipeline/MANUAL_ADD.md).

## Bieżąca ocena jakości T09

[QA i wyjątki](QA.md) używa tego samego walidatora przed oceną niepewności.
Błąd techniczny nie może zostać dopuszczony wyjątkiem. Raport opisuje dokładny
bieżący zbiór planów, rozdziela ważne komponenty T07 i plany ręczne T08 oraz
status wejścia od statusu wybranego przebiegu wyników T04.
