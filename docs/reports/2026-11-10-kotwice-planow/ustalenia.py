"""Compile the visually reviewed findings against the exact PR base and GPS pin."""
import csv
import json
import math
from pathlib import Path
import sys

from PIL import Image, ImageDraw
from pyproj import Transformer

root = Path(__file__).resolve().parent
repo = Path(sys.argv[1])
rev = 'dc8bbe0697791c49bfe3ee04b8e75c5b86b5d83f'
pin = json.loads((repo / 'data/coordinate-source/source.json').read_text())
plans = {r['plan']: r for r in csv.DictReader((root/'przeglad-814-planow.csv').open(encoding='utf-8-sig'))}
gps = {r['object_id']: r for r in csv.DictReader((repo / 'data/coordinate-source' / pin['snapshot']).open())}
transform = Transformer.from_crs(4326, 2180, always_xy=True)
def pos(obj):
    r = gps[obj]
    return transform.transform(float(r['lon']), float(r['lat']))

records = [
    ('zły otwór systemu', '001364', '001363', 'Cztery z pięciu kliknięć przy 0,0 na części podpisanej Jaskinia Ziobrowa. Piąte wskazuje odrębny otwór pod Niżnią Zbójnicką Turnią w lewym dolnym rogu. Piksel entrance.x/y jest na Ziobrowej, a GPS KSW-0177 wskazuje drugi otwór. Kataster odrzucił KSW-0177 jako punkt stały sieci z powodu rozbieżności.'),
    ('zły otwór systemu', '001020', '001019', 'Legenda: (1) Dziura Wyżnia, (2) Lisia Jama. Kotwica na (1) przy 0,0. Ten sam rysunek w dwóch rozdzielczościach.'),
    ('zły otwór systemu', '001582', '001581', 'Kotwica na 0,0 przy podpisie Jędrusiowa Dziura. Jaskinia przy Jędrusiowej Dziurze jest osobno podpisana po prawej.'),
    ('zły otwór systemu', '001604', '001603', 'Legenda przypisuje (1) Zośce i (2) Zagonnej Studni. Kotwica przy trójkącie otworu (1).'),
    ('zły otwór na wspólnej planszy', '001301', '001285', 'Kotwica 0,0 na dolnym, dłuższym obiekcie z kominem 12 m, opisanym przez PIG jako Suchy Biwak. Schron przy Suchym Biwaku ma odrębny krótki korytarz z dwoma otworami.'),
    ('zły otwór na wspólnej planszy', '001711', '001710', 'Kotwica przy 0,0. Przekrój na tej samej planszy oznacza ten otwór jako T.F-10.07 — Studnia Kuturniańska. T.F-10.08 leży niżej i jest oddzielny.'),
    ('zły otwór na wspólnej planszy', '001614', '001563', 'Kotwica przy 0,0 na rysunku Średniego Leja; Komórka przy Średnim Leju jest osobno podpisana po prawej.'),
    ('zły otwór na wspólnej planszy', '011292', '011291', 'Kotwica na 0,0 przy otworze NW (1) Kozich Okien. PIG opisuje przejście przez Kozie Okna do odrębnego otworu nyży.'),
    ('zły otwór na wspólnej planszy', '001175', '001174', 'Kotwica 0,0 na rysunku Żwirowej Dziury Wyżniej; Niżnia i Schron są osobno opisane na tej samej planszy.'),
    ('zły otwór na wspólnej planszy', '001211', '001248', 'Kotwica 0,0 przy podpisie Schron Partyzantów II 1431,7 m. Otwory Tunelu pod Siwarową Dziurą są na innym fragmencie.'),
    ('zły otwór na wspólnej planszy', '001179', '001174', 'Kotwica 0,0 na rysunku Żwirowej Dziury Wyżniej; Schron ma odrębny otwór na wspólnej planszy.'),
    ('zły otwór na wspólnej planszy', '001260', '001246', 'Kotwica 0,0 na rysunku Nyży z Kozicami; Szczelina jest narysowana osobno w prawym dolnym fragmencie.'),
    ('zły otwór na wspólnej planszy', '001210', '001248', 'Kotwica 0,0 przy podpisie Schron Partyzantów II 1431,7 m. Schron Partyzantów (I) znajduje się na innym fragmencie.'),
    ('konflikt źródeł GPS', '001477', '', 'Pięć kliknięć przy dolnym otworze nr 1. MTW-0032 łączy m-001 PIG (dolny, 1476,5 m) i m-002 TPN (oznaczony górny, 1525,08 m; używany w wydaniu). Różnica XY 36,05 m; potrzebne rozdzielenie lub wyjaśnienie w GPS Kataster.'),
    ('błędna grafika', '004372', '004371', 'Plansza 12233 to wyłącznie Upłazkowa Koleba, bez rysunku Szczeliny. JPEG i TIFF identyczne z 004371. Potrzebna właściwa grafika albo decyzja o wycofaniu planu.'),
    ('nierozstrzygnięte', '004266', '001038', 'To samo miejsce na wspólnym rysunku, ale klik jest przy granicy dwóch części bez rozstrzygającego oznaczenia. Współrzędne Best oddalone o 1,33 m.'),
    ('nierozstrzygnięte', '001568', '', 'TPN opisuje punkt jako dolny, lecz historyczny plan pokazuje jeden otwór. Różnica PIG/TPN to 45,15 m XY i 20,53 m wysokości; potrzebny opis z Jaskinie 100 (2020).'),
    ('nierozstrzygnięte', '001274', '', 'Kotwica na podpisanym dolnym otworze. Wysokość TPN bliższa górnemu, ale wektor PIG→TPN odbiega od wektora między otworami na planie. Brak nazwy otworu w rekordzie TPN.'),
    ('nierozstrzygnięte', '001232', '', 'Kotwica przy głównym dolnym otworze. Wysokość TPN bliższa innym otworom, ale kierunek różnicy XY PIG/TPN nie pasuje do innych otworów na planie.'),
    ('nierozstrzygnięte', '001103', '', 'Kotwica na dolnym otworze. Wysokość TPN bliższa południowemu, ale różnica położenia PIG/TPN w osi N–S jest znacznie mniejsza niż odstęp między otworami na planie.'),
]
Image.MAX_IMAGE_PIXELS = None
rows = []
for status, key, peer, note in records:
    m = plans[key]
    g = plans[peer] if peer else {}
    obj = m['gps_id']
    actual = g.get('gps_id','') if status.startswith('zły otwór') else ''
    delta = f'{math.dist(pos(obj),pos(actual)):.2f}' if actual else ''
    p = repo/'data/caves'/key/'image.tif'
    evidence = root/'dowody'/f'{key}.png'
    with Image.open(p) as im:
        w,h = im.size
        im = im.convert('RGB')
        im.thumbnail((1800,1400), Image.Resampling.LANCZOS)
    x = float(m['entrance_x'])*im.width/w
    y = float(m['entrance_y'])*im.height/h
    draw = ImageDraw.Draw(im)
    draw.ellipse((x-14,y-14,x+14,y+14),outline=(201,0,0),width=4)
    im.save(evidence)
    rows.append(dict(status=status, plan=key, nazwa=m['name'], grafika=m['image_id'],
        kotwica_x_px=m['entrance_x'], kotwica_y_px=m['entrance_y'], gps_obecny=obj,
        gps_odpowiadajacy_kliknietemu_otworowi=actual, roznica_gps_2d_m=delta,
        plan_porownawczy=peer, wniosek=note,
        PIG=m['pig_url'], PIG_plan_porownawczy=g.get('pig_url',''),
        YAML=f'https://github.com/dlubom/Georeferencer/blob/{rev}/data/caves/{key}/meta.yaml',
        rysunek=f'https://github.com/dlubom/Georeferencer/blob/{rev}/data/caves/{key}/image.tif',
        GPS=f'https://github.com/dlubom/gps-kataster-obiektow-tatr/blob/{pin["release"]}/data/objects/{obj.split("-")[0]}/{obj}.yml',
        dowod_png=str(evidence.relative_to(root))))
with (root/'ustalenia.csv').open('w', newline='', encoding='utf-8-sig') as f:
    wr=csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
    wr.writeheader()
    wr.writerows(rows)
assert sum(r['status'].startswith('zły otwór') for r in rows)==13
assert len({r['plan'] for r in rows})==len(rows)
for r in rows:
    print(r['status'],r['plan'],r['gps_obecny'],r['gps_odpowiadajacy_kliknietemu_otworowi'],r['roznica_gps_2d_m'])
