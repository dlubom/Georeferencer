"""Triage related plans at different resolutions; matches require visual review."""
import csv
import math
from pathlib import Path
import sys

import numpy as np
from PIL import Image

repo = Path(sys.argv[1])
out = Path(__file__).resolve().parent
plans = list(csv.DictReader((out/'przeglad-814-planow.csv').open(encoding='utf-8-sig')))
Image.MAX_IMAGE_PIXELS = None
thumbs, clicks = [], []
for r in plans:
    with Image.open(repo / 'data/caves' / r['plan'] / 'image.tif') as im:
        w, h = im.size
        t = im.convert('L').resize((60, 60), resample=Image.Resampling.BOX)
    a = np.maximum(0, 254 - np.asarray(t, dtype=np.float32))[2:-2, 2:-2].ravel()
    thumbs.append(a / np.linalg.norm(a))
    clicks.append((float(r['entrance_x'])/w, float(r['entrance_y'])/h))
m = np.stack(thumbs)
i, j = np.triu_indices(len(plans), 1)
sim = np.einsum('ik,jk->ij', m, m)[i, j]
assert np.isfinite(sim).all()
order = np.argsort(sim)[::-1]
with (out/'podobne-plansze.csv').open('w', newline='', encoding='utf-8-sig') as f:
    wr = csv.writer(f, lineterminator="\n")
    wr.writerow(('plan_a', 'plan_b', 'podobienstwo', 'roznica_znormalizowanych_klikniec', 'gps_a', 'gps_b'))
    for k in order:
        if sim[k] < 0.95:
            print('Highest score outside threshold:', round(float(sim[k]), 4))
            break
        a,b = i[k],j[k]
        wr.writerow((plans[a]['plan'], plans[b]['plan'], round(float(sim[k]), 5),
                     round(math.dist(clicks[a], clicks[b]), 6), plans[a]['gps_id'], plans[b]['gps_id']))
print('Pairs >= 0.95:', int(np.count_nonzero(sim >= 0.95)))
