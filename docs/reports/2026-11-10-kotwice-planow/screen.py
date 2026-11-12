"""Read-only inventory for Georeferencer PR #40 base dc8bbe0."""
import collections
import csv
import hashlib
import itertools
import json
import math
from pathlib import Path
import re
import sys

from PIL import Image, ImageDraw
import pyarrow.parquet as pq
import yaml

repo = Path(sys.argv[1])
pig_path = Path(sys.argv[2])
out = Path(__file__).resolve().parent
Image.MAX_IMAGE_PIXELS = None
pin = json.loads((repo / 'data/coordinate-source/source.json').read_text())
gps_csv = repo / 'data/coordinate-source' / pin['snapshot']
assert hashlib.sha256(gps_csv.read_bytes()).hexdigest() == pin['sha256']
gps = {r['object_id']: r for r in csv.DictReader(gps_csv.open())}
by_cave = collections.defaultdict(list)
by_pig = collections.defaultdict(list)
for key, row in gps.items():
    if row['category'] == 'jaskinia_otwor':
        by_cave[row['cave_id']].append(key)
        if row['pig_id']:
            by_pig[int(row['pig_id'])].append(key)
pig = {int(r['cave_id']): r for line in pig_path.open() if (r := json.loads(line))}
norm_inv = lambda text: re.sub(r'\s+', '', text).upper()
by_inv = collections.defaultdict(list)
for key, row in pig.items():
    by_inv[norm_inv(row['inventory_number'])].append(key)
links = collections.defaultdict(set)
for key, row in pig.items():
    for ref in re.findall(r'T\s*\.\s*[A-Z]\s*-\s*\d+\s*\.\s*\d+', row.get('other_entrances') or '', re.I):
        for other in by_inv[norm_inv(ref)]:
            if other != key:
                links[key].add(other)
                links[other].add(key)

def component(key):
    seen = {key}
    pending = [key]
    while pending:
        for other in links[pending.pop()] - seen:
            seen.add(other)
            pending.append(other)
    return seen

def position(obj):
    r = gps[obj]
    return float(r['y_1992']), float(r['x_1992'])  # E,N

def save_csv(name, rows):
    with (out / name).open('w', newline='', encoding='utf-8-sig') as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        wr.writeheader()
        wr.writerows(rows)

by_dims = collections.defaultdict(list)
all_plans = {}
rows = []
for f in sorted((repo / 'data/caves').glob('*/meta.yaml')):
    m = yaml.safe_load(f.read_text())
    plan = f.parent.name
    key = int(plan) if plan.isdecimal() and int(plan) in pig else next(iter(by_inv[norm_inv(m['cave']['inventory_number'])]), None)
    obj = m['coordinates']['gps_kataster_object_id']
    row = gps[obj]
    pr = pig.get(key, {})
    group = component(key) if key else set()
    current_cave = set(by_cave[row['cave_id']])
    alternatives = (current_cave | {x for g in group for x in by_pig[g]}) - {obj}
    image_id = m['image']['image_id']
    dims = (m['image']['width'], m['image']['height'])
    all_plans[plan] = (f, m, key)
    by_dims[dims].append(plan)
    rows.append(dict(plan=plan, name=m['cave']['name'], image_id=image_id,
        pig_id=key, pig_url=f'https://jaskiniepolski.pgi.gov.pl/Details/Information/{key}' if key else '',
        gps_id=obj, gps_cave_id=row['cave_id'], gps_name=row['name_local'], gps_pig_id=row['pig_id'],
        entrance_x=m['entrance']['x'], entrance_y=m['entrance']['y'], ppm=m['scale']['pixels_per_meter'],
        pig_other_entrances=pr.get('other_entrances') or '',
        linked_pig_ids=' '.join(f'{g:06}' for g in sorted(group - {key})),
        gps_other_same_cave=' '.join(sorted(current_cave - {obj})),
        gps_alternatives_with_distance_m=' | '.join(
            f'{o} ({math.dist(position(obj), position(o)):.2f} m) {gps[o]["name_local"]}' for o in sorted(alternatives))))
save_csv('przeglad-814-planow.csv', rows)
print('Plans', len(rows), 'mapped PIG',sum(bool(r['pig_id']) for r in rows))
print('PIG other_entrances',sum(bool(r['pig_other_entrances']) for r in rows))
print('Linked PIG',sum(bool(r['linked_pig_ids']) for r in rows))
print('GPS same cave alternatives',sum(bool(r['gps_other_same_cave']) for r in rows))
print('Union PIG / GPS',sum(bool(r['pig_other_entrances'] or r['linked_pig_ids'] or r['gps_other_same_cave']) for r in rows))
print('Concrete other GPS',sum(bool(r['gps_alternatives_with_distance_m']) for r in rows))
print('same dims groups',sum(len(v)>1 for v in by_dims.values()))

duplicates = []
rby = {r['plan']:r for r in rows}
for dims, plans in by_dims.items():
    if len(plans) < 2: continue
    def digest(p):
        f, m, _ = all_plans[p]
        with Image.open(f.parent / 'image.tif') as im:
            assert im.size == dims
            return hashlib.sha256(im.convert('L').tobytes()).hexdigest()
    digests = {p:digest(p) for p in plans}
    for a,b in itertools.combinations(plans, 2):
        if digests[a] != digests[b]: continue
        ra,rb = rby[a],rby[b]
        dist_click = math.dist((ra['entrance_x'],ra['entrance_y']),(rb['entrance_x'],rb['entrance_y']))
        dup=dict(plan_a=a, name_a=ra['name'], image_id_a=ra['image_id'], gps_a=ra['gps_id'],
                 plan_b=b, name_b=rb['name'], image_id_b=rb['image_id'], gps_b=rb['gps_id'],
                 click_distance_px=round(dist_click,2),
                 gps_distance_m=round(math.dist(position(ra['gps_id']),position(rb['gps_id'])),2),
                 width=dims[0],height=dims[1],decoded_pixel_sha256=digests[a])
        duplicates.append(dup)
        print('DUP', *list(dup.values())[:10])
if duplicates: save_csv('identyczne-rastry.csv', duplicates)

sub = pq.read_table(repo / 'parquet/SUBMISSIONS.parquet',
                   columns=['cave_id','image_id','submission_id','points_orig_json','submit_type']).to_pylist()
test = json.loads((repo/'data/classification/test-submissions-v1.json').read_text())
excluded = {x['submission_id'] for x in test['exclusions']}
def crop(p, radius):
    f,m,key = all_plans[p]
    x,y = m['entrance']['x'],m['entrance']['y']
    iw,ih = m['image']['width'],m['image']['height']
    box = (max(0, int(x-radius)),max(0, int(y-radius)),min(iw,int(x+radius)),min(ih,int(y+radius)))
    with Image.open(f.parent/'image.tif') as im:
        c = im.crop(box).convert('RGB')
    d = ImageDraw.Draw(c)
    hits = []
    for s in sub:
        if norm_inv(s['cave_id']) != norm_inv(m['cave']['inventory_number']) or str(s['image_id']) != str(m['image']['image_id']) or s['submission_id'] in excluded:
            continue
        v = json.loads(s['points_orig_json'] or '[]')
        if not v: continue
        xx,yy = v[0]['x']-box[0],v[0]['y']-box[1]
        hits.append((v[0]['x'],v[0]['y']))
        d.ellipse((xx-5,yy-5,xx+5,yy+5),outline='blue',width=2)
    xx,yy=x-box[0],y-box[1]
    d.line((xx-14,yy,xx+14,yy), fill='red',width=2)
    d.line((xx,yy-14,xx,yy+14), fill='red',width=2)
    c.save(out / f'{p}-klik-{radius}.png')
    print('CLICK',p,len(hits),hits)
for p in sys.argv[3:]:
    crop(p,500)
