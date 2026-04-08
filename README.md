# Instrukcja Georeferencji Planów Jaskiń

## O co chodzi w tym projekcie?

Celem projektu jest **georeferencja planów jaskiń** - czyli przypisanie współrzędnych geograficznych do rysunków jaskiń, tak aby można je było wyświetlić na mapach w programach GIS (np. QGIS, ArcGIS).

### Siła w grupie!

Zakładamy, że **każda jaskinia zostanie opracowana minimum 5 razy przez różne osoby**. Dzięki temu uzyskamy statystykę, która pozwoli wykryć błędy i uśrednić wyniki. Im więcej osób weźmie udział, tym dokładniejsze będą końcowe geotiffy!

---

## Wymagania

**Koniecznie użyj tabletu, komputera PC lub laptopa!**

Ekran telefonu jest zbyt mały, aby osiągnąć wymaganą precyzję przy zaznaczaniu punktów. Praca na telefonie nie ma sensu - wyniki będą niedokładne.

---

## Przerwa? Żaden problem!

Jeśli potrzebujesz kawy, odpoczynku, albo po prostu musisz popracować nad czymś innym:

- **Po prostu zamknij stronę** - system zapamięta Twój ostatni przydział
- Gdy wrócisz, **kontynuujesz od miejsca gdzie skończyłeś**
- System **gwarantuje, że nie dostaniesz powtórzonych jaskiń** - o ile pracujesz na tym samym komputerze i w tej samej przeglądarce

> **Uwaga:** Jeśli zmienisz komputer (np. praca vs dom) lub przeglądarkę, system potraktuje Cię jako nową osobę i może przydzielić jaskinie, które już robiłeś.

---

## Instrukcja krok po kroku

### 1. Wejdź na stronę

Otwórz w przeglądarce: **https://dlubom.github.io/Georeferencer/index.html**

**Poczekaj aż statystyki się załadują** - zobaczysz pasek postępu i informację ile jaskiń zostało do opracowania.

---

### 2. Kliknij "Daj mi jaskinię"

Po załadowaniu strony kliknij przycisk **"Daj mi jaskinię"**. System przydzieli Ci losową jaskinię do opracowania.

---

### 3. Wybierz plan jaskini

W praktyce zazwyczaj automatycznie załaduje się pierwszy plan z listy.

> **Uwaga:** Kilka jaskiń nie posiada planu - jeśli trafisz na taką, po prostu ją pomiń i weź kolejną.

---

### 4. Zaznacz otwór jaskini

Otwór jaskini na planie jest zazwyczaj oznaczony **trójkącikiem z kropką w środku**, umieszczonym na przecięciu osi siatki **0,0**.

```
        0,0
         |
         |
0,0 -----△-----
         |
```

**Wskazówki dotyczące precyzji:**
- **Przybliżaj/oddalaj** - użyj kółka myszy
- **Przesuwaj ekran** - trzymaj **Shift** i przeciągaj
- **Cofnij pomyłkę** - możesz anulować błędne kliknięcie

Precyzja jest ważna - postaraj się kliknąć dokładnie w środek symbolu otworu!

---

### 5. Określ skalę

1. **Odczytaj długość skali** z rysunku (np. "10 m", "50 m")
2. **Wpisz tę wartość** w odpowiednie pole
3. **Zaznacz skalę** - kliknij początek i koniec podziałki na rysunku

**Alternatywa gdy brak skali:**
- Możesz użyć **oczek siatki** - kliknij jedno oczko i podaj jego długość
- Dla większej precyzji możesz zaznaczyć **kilka oczek** i wpisać ich sumaryczną długość

---

### 6. Zaznacz linię północy

Określ kierunek północy na planie.

> **Domyślnie ustawione jest 0°** - bo na 99% planów północ jest skierowana pionowo w górę. Jeśli tak jest na Twoim planie, możesz przejść dalej.

Jeśli strzałka północy wskazuje inny kierunek - zaznacz ją na rysunku.

---

### 7. Zaznacz punkty przecięć siatki

Ten krok pozwala wykryć **ewentualne deformacje lub błędy** w planie.

**Jak to zrobić:**
1. Zacznij od **punktu otworu** (przecięcie 0,0) - zazwyczaj już go masz zaznaczonego
2. Zaznaczaj **kolejne punkty przecięć** siatki
3. **Pomijaj** te przecięcia, które są zasłonięte przez rysunek korytarzy jaskini

**Jeśli plan nie ma siatki** - po prostu kliknij przycisk **"Brak siatki"**.

---

### 8. Zweryfikuj i wyślij

1. **Sprawdź** wszystkie zaznaczone punkty - czy wyglądają sensownie?
2. Kliknij **"Wyślij do Google Sheets"**

I to tyle! Twoja praca została zapisana.

---

## Co dalej?

Etap crowdsourcingowy został zakończony: **4048 zgłoszeń** od **89 użytkowników** dla **801 jaskiń** (każda z minimum 5 niezależnymi kliknięciami).

### Pipeline generacji GeoTIFF

Zebrane dane są przetwarzane automatycznym pipeline'em:

1. **Ekstrakcja** — dane ze zgłoszeń agregowane do edytowalnych plików YAML (`data/caves/{dir_id}/meta.yaml`): mediana pikseli otworu, mediana skali, mediana kąta północy
2. **Generacja GeoTIFF** — z YAML wyliczane parametry World File (A-F) i generowany GeoTIFF w układzie EPSG:2180 (PL-1992)
3. **Raporty QA** — automatyczne flagowanie jaskiń z wysokim rozrzutem wyników

### Edycja wyników

Każdy plik `meta.yaml` jest edytowalny — można ręcznie poprawić:
- współrzędne otworu (`coordinates.lat`, `coordinates.lon`)
- pozycję otworu w pikselach (`entrance.x`, `entrance.y`)
- skalę (`scale.pixels_per_meter`)
- kąt północy (`north.angle_deg`)
- deklinację (`declination_deg`)

Po edycji i pushu na `main` — CI automatycznie przelicza World File i generuje nowy GeoTIFF.

### Uruchomienie lokalne

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r pipeline/requirements.txt
brew install gdal  # macOS

# Generacja GeoTIFF dla jednej jaskini
python pipeline/02_generate_geotiff.py --cave 001131

# Generacja dla wszystkich
python pipeline/02_generate_geotiff.py --all

# Raporty QA
python pipeline/03_report.py
```

### Release

Przy utworzeniu tagu `v*` (np. `v1.0`) GitHub Actions automatycznie generuje wszystkie GeoTIFF-y i publikuje je jako paczkę `.tar.gz` w GitHub Releases.

---

## Pytania?

Jeśli masz wątpliwości lub napotkasz problem - skontaktuj się z koordynatorem projektu.

**Dziękujemy za pomoc w georeferencji polskich jaskiń!**
