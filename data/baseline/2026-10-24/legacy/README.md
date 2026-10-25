# Zamrożone źródła do audytu T02

Dwa pliki Python są wiernymi kopiami źródeł z commitu T02
`3a7e00651c298444e6ed8d7a012c9c82658f8e4b` (identycznymi ze stanem `fad70f0`).
Nie są nową implementacją ani odzyskanym kodem. T03 zachowuje je, ponieważ
zmienia bieżący generator i loader, a historyczne przeliczenie musi nadal
używać dawnych funkcji. Nie należy importować ich w produkcyjnym buildzie.

`catalogue_baseline.verify_inputs` porównuje te kopie z **oryginalnymi** hashami
`pipeline/02_generate_geotiff.py` i `pipeline/gps_kataster_coordinates.py`
w `../catalogue.json`. Manifest i oryginalne nazwy ścieżek pozostają bez zmian.
`recalculation` ładuje obie stare implementacje w izolacji od cache modułów
bieżącego programu. Pozostałe historyczne dane i źródła są sprawdzane w ich
oryginalnych lokalizacjach.

Dawny kod celowo zachowuje znane błędy. Używa się go wyłącznie do odtworzenia
`recalculated-v1.3.1.json`; walidację obecnej implementacji sprawdzają osobne
testy T03. Zgodność historii nie jest potwierdzeniem poprawności geodezyjnej.
