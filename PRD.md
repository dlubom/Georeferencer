PRD 1.0 — Tatry Cave Plan Georeferencer (crowdsourcing k=5)
1) Cel produktu

Zbudować prosty system crowdsourcingowy (GitHub Pages + Google Sheets), który:

losowo przydziela użytkownikom jaskinie (CaveID) z Tatr,

zbiera k=5 niezależnych wyników georeferencji na każdą jaskinię,

zapisuje maksymalnie dużo danych wejścia/wyjścia do Google Sheets,

umożliwia późniejszą analizę jakości i wybór konsensusu (w Sheets / offline).

2) Kontekst i istniejąca baza

Aplikacja już:

ładuje listę jaskiń z caves_transformed.jsonl z raw.githubusercontent.com 

index

index

filtruje obrazy do typów plan / plan i przekrój (co w praktyce odcina zdjęcia otworów, ale zostawia czasem “plan i przekrój”) 

index

index

pozwala wybrać obraz z listy plan_images i załadować go; domyślnie wybiera indeks 0 (co zwykle jest planem) 

index

po kliknięciach wylicza transformację World File i trzyma ją w state.transform={A,D,B,E,C,F} oraz eksportuje World File i generuje komendę GDAL. 

index

index

index

3) Założenia (z Twojej decyzji)

Jednostka losowania: CaveID (nie image_id).

Użytkownik ma możliwość wybrać właściwy plan spośród obrazów dla tej jaskini (domyślnie zazwyczaj pierwszy).

Logujemy “jak najwięcej”; nie potrzebujemy wariantu “GDAL mono” w logach (mono robione w postprocessingu). 

index

GEOREFERENCER

K na sztywno: k = 5.

Zakres danych: Tatry.

Wynik/źródło prawdy: Google Sheets (bez dodatkowej bazy).

Użytkownicy: koledzy — minimalne bezpieczeństwo, ale nie budujemy pełnego auth.

4) Miary sukcesu

100% jaskiń z Tatr ma ≥5 submissionów.

<5% submissionów oznaczonych jako “SKIPPED / błąd / brak danych”.

Dla większości jaskiń rozrzut między wynikami (metry/rotacja/scale) jest “mały” wg ustalonej miary (metryka do analizy po zebraniu danych).

5) Zakres funkcjonalny (MVP)
5.1 Tryb pracy użytkownika

Wejście na stronę → generuje się user_id (UUID) i zapis do localStorage.

Klik “Daj mi jaskinię” → backend przydziela CaveID.

Aplikacja ładuje metadane tej jaskini (z już wczytanego JSONL) i pokazuje listę obrazów (plan_images).

Użytkownik wybiera właściwy plan (domyślnie 1. pozycja) i klika “Załaduj”.

Użytkownik wykonuje georeferencję (kliknięcia), aplikacja liczy A..F.

Klik “Zapisz do Sheets” → zapis pełnego payloadu, zmiana statusu przydziału na SUBMITTED.

Następny przydział.

Debug: opcjonalnie zostawiamy dotychczasowy manualny wybór jaskini (dla testów), ale w trybie produkcyjnym preferujemy “assignment-first”.

5.2 Przydział (k=5, wyrównujący)

Backend przydziela jaskinię tak, żeby:

użytkownik nie dostał tej samej jaskini ponownie,

preferować jaskinie z mniejszą liczbą oddań (n_submissions), a w ramach remisu losowo,

nie przydzielać jaskiń, które mają już n_submissions >= 5,

obsłużyć “porzucone” przydziały (expiry).

6) Model danych w Google Sheets

Zakładamy 4 zakładki (Sheets tabs).

6.1 CAVES

Źródło listy zadań + liczniki.

Kolumny (minimalne):

cave_id (PK)

name

region

lat, lon

n_submissions (int)

n_open_assignments (int)

last_assigned_at

disabled (bool) + disabled_reason

Uwagi:

Inicjalizowane jednorazowo (import z caves_transformed.jsonl po stronie Apps Script).

Filtr Tatry: region (logika doprecyzowana w implementacji; w MVP np. region contains "Tat" / konkretna lista regionów).

6.2 USERS

Minimalna ewidencja.

Kolumny:

user_id (UUID, PK)

created_at

last_seen_at

display_name (opcjonalnie)

notes (opcjonalnie)

6.3 ASSIGNMENTS

Historia przydziałów (źródło prawdy “czego user już nie może dostać”).

Kolumny:

assignment_id (PK)

user_id

cave_id

assigned_at

expires_at

status enum: ASSIGNED | SUBMITTED | SKIPPED | EXPIRED

attempt_no (kolejny przydział dla usera)

selected_image_id (uzupełniane przy submit)

selected_image_path (uzupełniane przy submit)

6.4 SUBMISSIONS

Najważniejsza tabela — “loguj jak najwięcej”.

Kolumny (rekomendowane):

Identyfikacja:

submission_id (PK)

submitted_at

assignment_id

user_id

cave_id

Wybrany plan:

image_id

image_path_original

image_path_upscaled

image_used_path

image_selected_index

use_original (bool)

image_description

image_author

Wejście użytkownika / konfiguracja:

lat_input, lon_input (z pól, po ewentualnej korekcie)

lat_db, lon_db (z bazy — przydatne do porównań)

realScale_m

declination_deg

skipNorth (bool)

proj4def (string)

Kliknięcia i geometria:

points_canvas_json (lista punktów w canvas)

points_orig_json (punkty przeliczone na oryg. obraz)

Wyniki:

A, D, B, E, C, F (transformacja; dokładnie jak w World File) 

index

worldfile_ext (np. jgw/pgw/tfw; wynik z logiki appki) 

index

worldfile_text (6 linii)

gdal_cmd_standard (to, co pokazuje przycisk GDAL) 

index

pixels_per_meter

north_deg

convergence_deg

total_deg

Debug/telemetria (lekko, ale przydatne):

app_version

client_time_iso

tz (np. Europe/Warsaw)

user_agent

screen_w, screen_h

errors_json (jeśli coś poszło nie tak)

Status/uwagi:

submit_type enum: NORMAL | SKIP

skip_reason (jeśli SKIP)

freeform_comment (opcjonalnie)

7) API (Apps Script Web App)

Jeden endpoint, np. POST /api z polem action.

7.1 action = "ping"

Rejestruje / aktualizuje USERS.last_seen_at.

Request: {action, user_id, display_name?}
Response: {ok:true}

7.2 action = "assign"

Cel: przydzielić CaveID.

Request: { action:"assign", user_id }

Response (MVP):

{
  "ok": true,
  "assignment_id": "A_...",
  "cave_id": "J.Tat....",
  "target_k": 5,
  "n_submissions": 2,
  "expires_at": "2026-01-10T12:00:00Z"
}


Reguły:

wyklucz jaskinie już przypisane/oddane temu userowi (ASSIGNMENTS),

wyklucz n_submissions >= 5,

wybierz z minimalnego n_submissions (lub z n_submissions < 5 z wagą), losowo w obrębie koszyka,

ustaw expires_at (np. 24h).

7.3 action = "submit"

Cel: zapisać wynik.

Request: duży payload z danymi (jak w SUBMISSIONS) + assignment_id.

Side effects:

dopisz wiersz do SUBMISSIONS,

ustaw ASSIGNMENTS.status = SUBMITTED,

inkrementuj CAVES.n_submissions dla cave_id,

zmniejsz CAVES.n_open_assignments.

7.4 action = "skip"

Cel: użytkownik nie może zrobić tej jaskini.

Request: {action:"skip", assignment_id, user_id, cave_id, reason }

Side effects:

ASSIGNMENTS.status=SKIPPED,

(opcjonalnie) nie inkrementować n_submissions,

umożliwić ponowne trafienie tej jaskini do innych.

7.5 action = "progress"

Response (przykład):

{
  "ok": true,
  "total": 1000,
  "target_k": 5,
  "ge_1": 812,
  "ge_2": 700,
  "ge_3": 590,
  "ge_4": 410,
  "ge_5": 120,
  "remaining_lt_5": 880
}

8) Zmiany w UI (index.html)

Minimalne zmiany:

dodać przycisk “Daj mi jaskinię” (wywołuje assign),

po assign: automatycznie ustawić state.selectedCave na tę jaskinię (bez ręcznego wyboru z listy),

pokazać listę obrazów do wyboru (już jest imageSelect), z domyślnym indeksem 0 (już działa) 

index

dodać przycisk “Zapisz do Sheets” (submit),

opcjonalnie panel postępu (progress) u góry.

9) Cache w przeglądarce (localStorage)

Wymagane klucze:

user_id (trwały)

current_assignment (assignment_id + cave_id + expires_at)

seen_assignments (opcjonalnie; tylko UX)

Ważne: źródłem prawdy jest Sheets/Apps Script — localStorage tylko upraszcza UX po odświeżeniu.

10) Współbieżność i spójność

Apps Script powinien używać LockService.getScriptLock() w assign i submit, żeby równoczesne requesty nie psuły liczników i nie przydzielały tej samej jaskini “wbrew regułom”.

11) Kryteria akceptacji (MVP)

[A1] Użytkownik otrzymuje CaveID, którego wcześniej nie miał (sprawdzone po ASSIGNMENTS).

[A2] System nie przydziela jaskiń z n_submissions >= 5.

[A3] Użytkownik może zmienić obraz planu w obrębie jaskini przed “submit”.

[A4] “Submit” zapisuje do SUBMISSIONS co najmniej: cave_id, user_id, assignment_id, image_used_path, A..F, worldfile_text, gdal_cmd_standard, punkty. 

index

index

[A5] “Progress” pokazuje aktualne pokrycie (≥1..≥5) i zmienia się po submit.

[A6] “Skip” nie zlicza submissionu, ale blokuje ponowne dostanie tej jaskini przez tego samego usera (status SKIPPED w ASSIGNMENTS).

12) Plan wdrożenia (praktyczny)

Apps Script: utworzyć arkusz, zakładki, endpoint, import CAVES (jednorazowo).

Front: dodać assign/submit/progress/skip + UI.

Test z 2–3 osobami (czy działa przydział i logowanie).

Wysyłka do 50 osób.

13) Deployment & Links

**Status implementacji:** ✅ Gotowe do wdrożenia

**Pliki:**
- `index.html` - Produkcja (crowdsourcing, tylko Tatry)
- `debug.html` - Testy (ręczny wybór, wszystkie regiony)
- `Code.gs` - Backend API (Google Apps Script)
- `ImportCaves.gs` - Import danych (Google Apps Script)
- `DEPLOYMENT.md` - Instrukcje wdrożenia krok po kroku

**Deployment URLs:**

**Google Apps Script API Endpoint:**
```
https://script.google.com/macros/s/AKfycbyDf8y7ivssMws4cUfNTC8IHxKmE_QY4xGqMZXT5lyNc4VeKfGmqR3-souNHsClWTEzNw/exec
```

**Frontend (GitHub Pages):**
```
Produkcja:   https://dlubom.github.io/Georeferencer/index.html
Debug:       https://dlubom.github.io/Georeferencer/debug.html
```

**Google Sheets (dane):**
```
https://docs.google.com/spreadsheets/d/YOUR_SPREADSHEET_ID_HERE/edit
```

**Uwagi:**
1. Zaktualizować linki w `GEOREFERENCER.md` (linie 7, 12, 42) z rzeczywistą nazwą użytkownika GitHub po wdrożeniu na GitHub Pages.

2. Szczegółowe instrukcje wdrożenia znajdują się w `DEPLOYMENT.md` (500+ linii instrukcji krok po kroku).

**Następne kroki:**
1. ✅ Wdrożyć backend według `DEPLOYMENT.md` (Steps 1-5)
2. ✅ Zaktualizować `API_ENDPOINT` w `index.html`
3. Wdrożyć frontend na GitHub Pages
4. Przetestować workflow (Steps 7-8 w DEPLOYMENT.md)
5. Zebrać dane od 50 kontrybutorów

**Metryki do monitorowania:**
- Liczba użytkowników (`USERS` sheet)
- Liczba jaskiń z ≥k submissions (`progress` API)
- Procent SKIPPED submissions
- Czas średni na submission (delta `assigned_at` → `submitted_at`)
- Rozrzut wyników (A-F parameters) między różnymi userami dla tej samej jaskini (analiza post-hoc)

**Dokumentacja:**
- `GEOREFERENCER.md` - Instrukcje dla użytkowników i kontrybutorów
- `DEPLOYMENT.md` - Instrukcje wdrożenia dla administratora
- `PRD.md` (ten dokument) - Specyfikacja produktu