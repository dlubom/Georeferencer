"""T07: jawna kwalifikacja obserwacji i odtwarzalne agregaty, bez zapisu YAML.

Wejściem jest DataFrame albo sekwencja słowników. Kolejność wszystkich obliczeń
i list dowodowych wynika z submission_id. Jedna obserwacja ma wagę jeden;
liczba odrębnych user_id jest raportowana osobno dla każdego komponentu.
Ważny otwór ma skończone x/y punktu 0. Ważna skala oznacza zapisaną dodatnią,
skończoną wartość pixels_per_meter; nie odtwarzamy jej z odcinka i realScale_m.
Północ dodatkowo wymaga kompletnej, niezerowej strzałki punktów 3/4,
skończonego north_deg i jawnego skipNorth=False.
Nie wnioskujemy o rodzaju północy ani nie nadajemy orientacji geodezyjnej.
"""
import hashlib
import json
import math
import re
from numbers import Real
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CLASSIFICATION = ROOT / 'data/classification/test-submissions-v1.json'


def _identifier(value, name):
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f'{name}: wymagany niepusty stabilny identyfikator')
    return value


def _finite(value):
    return isinstance(value, Real) and not isinstance(value, (bool, np.bool_)) and math.isfinite(value)


def _rows(subs):
    rows = subs.to_dict('records') if isinstance(subs, pd.DataFrame) else list(subs)
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Zgłoszenie musi być słownikiem')
        sid = _identifier(row.get('submission_id'), 'submission_id')
        if sid in seen:
            raise ValueError(f'Powtórzony submission_id: {sid}')
        seen.add(sid)
        _identifier(row.get('user_id'), f'{sid}: user_id')
        _identifier(row.get('cave_id'), f'{sid}: cave_id')
        if row.get('submit_type') not in ('NORMAL', 'SKIP'):
            raise ValueError(f'{sid}: nieobsługiwany submit_type')
    return sorted(rows, key=lambda row: row['submission_id'])


def load_classification(path=DEFAULT_CLASSIFICATION):
    """Wczytaj listę konkretnych ID i sprawdź jej dowód w przypiętym parquet.

    Zwraca mapę submission_id → wpis. Nie klasyfikuje nowych rekordów według
    markera ani assignment_id. Zmieniony snapshot wymaga nowego przeglądu.
    """
    registry = json.loads(Path(path).read_text(encoding='utf-8'))
    if registry.get('schema_version') != 1 or not registry.get('classification_version'):
        raise ValueError('Nieobsługiwana wersja rejestru klasyfikacji')
    source = registry.get('source', {})
    source_path = (ROOT / source.get('path', '')).resolve()
    if not source_path.is_relative_to(ROOT) or not source_path.is_file():
        raise ValueError('Nieprawidłowa ścieżka snapshotu klasyfikacji')
    digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
    if source.get('sha256') != digest:
        raise ValueError('SHA-256 snapshotu klasyfikacji nie odpowiada rejestrowi')
    records = registry.get('exclusions')
    if not isinstance(records, list):
        raise ValueError('Brak listy exclusions w rejestrze klasyfikacji')
    result = {}
    snapshot = pd.read_parquet(source_path)
    if snapshot['submission_id'].duplicated().any():
        raise ValueError('Snapshot klasyfikacji zawiera powtórzony submission_id')
    snapshot = snapshot.set_index('submission_id')
    for entry in records:
        sid = _identifier(entry.get('submission_id'), 'submission_id klasyfikacji')
        _identifier(entry.get('cave_id'), f'{sid}: cave_id klasyfikacji')
        _identifier(entry.get('reason'), f'{sid}: reason klasyfikacji')
        if sid in result:
            raise ValueError(f'Powtórzony submission_id w klasyfikacji: {sid}')
        if entry.get('classification') != 'TEST':
            raise ValueError(f'{sid}: nieobsługiwana klasyfikacja')
        if entry.get('evidence') != {'column': 'Unnamed: 52', 'value': 'TEST'}:
            raise ValueError(f'{sid}: brak jawnego dowodu markera TEST')
        if (sid not in snapshot.index or snapshot.loc[sid, 'cave_id'] != entry['cave_id']
                or snapshot.loc[sid, 'Unnamed: 52'] != 'TEST'):
            raise ValueError(f'{sid}: dowód klasyfikacji nie odpowiada snapshotowi')
        result[sid] = entry
    return dict(sorted(result.items()))


def _points(row):
    try:
        points = json.loads(row.get('points_orig_json', ''))
    except (TypeError, ValueError):
        return []
    return points if isinstance(points, list) else []


def _point(points, index):
    if index >= len(points):
        return None
    point = points[index]
    if not isinstance(point, dict) or not all(_finite(point.get(k)) for k in ('x', 'y')):
        return None
    return float(point['x']), float(point['y'])


def _geometric_median(points):
    """Metoda Weiszfelda T02 (100 iteracji, 1e-7), ze stabilną kolejnością."""
    pts = np.array(points, dtype=float)
    value = np.median(pts, axis=0)
    for _ in range(100):
        distances = np.linalg.norm(pts - value, axis=1)
        weights = 1.0 / np.where(distances == 0, 1e-10, distances)
        updated = (pts * weights[:, None]).sum(axis=0) / weights.sum()
        if np.linalg.norm(updated - value) < 1e-7:
            break
        value = updated
    return [float(v) for v in value]


def _circular_median(values):
    """Mediana po rozwinięciu jednoznacznego łuku krótszego niż 180°.

    Kanoniczny wynik należy do [-180, 180). Dla danych nieobejmowanych
    otwartym półokręgiem nie wybieramy arbitralnego kierunku: null/ambiguous.
    W tym jednoznacznym zakresie mediana zwykła rozwiniętych kątów (średnia
    dwóch środkowych dla parzystej próby) jest też medianą odległości kołowej.
    """
    if not values:
        return None, False
    angles = sorted(float(value) % 360.0 for value in values)
    gaps = [angles[i + 1] - angles[i] for i in range(len(angles) - 1)]
    gaps.append(angles[0] + 360.0 - angles[-1])
    largest = max(range(len(gaps)), key=lambda i: gaps[i])
    if 360.0 - gaps[largest] >= 180.0 - 1e-10:
        return None, True
    start = angles[(largest + 1) % len(angles)]
    unwrapped = [a if a >= start else a + 360.0 for a in angles]
    angle = (float(np.median(unwrapped)) + 180.0) % 360.0 - 180.0
    return angle, False


def _counts(rows, **extra):
    return {'observations': len(rows), 'users': len({row['user_id'] for row in rows}),
            'submission_ids': [row['submission_id'] for row in rows], **extra}


def _rounded(value, digits):
    return None if value is None else round(float(value), digits)


def _aggregate(cave_id, rows, classification):
    if not rows:
        raise ValueError(f'{cave_id}: brak grupy źródłowej')
    if any(row['cave_id'] != cave_id for row in rows):
        raise ValueError(f'{cave_id}: grupa zawiera inny cave_id')
    identities = set()
    for row in rows:
        image_id = row.get('image_id')
        if not _finite(image_id) or int(image_id) != image_id or image_id <= 0:
            raise ValueError(f"{row['submission_id']}: nieprawidłowy image_id")
        path = _identifier(row.get('image_used_path'), 'image_used_path')
        identities.add((int(image_id), path))
    if len(identities) != 1:
        raise ValueError(f'{cave_id}: mieszane tożsamości obrazów (image_id/image_used_path)')
    image_id, path = next(iter(identities))
    match = re.search(r'/(\d{6})/', path)
    if match is None:
        raise ValueError(f'{cave_id}: brak dir_id w image_used_path')

    retained, exclusions = [], {}
    for row in rows:
        sid = row['submission_id']
        if sid in classification:
            entry = classification[sid]
            if entry.get('cave_id') != cave_id or entry.get('classification') != 'TEST':
                raise ValueError(f'{sid}: klasyfikacja nie odpowiada zgłoszeniu')
            exclusions[sid] = _identifier(entry.get('reason'), f'{sid}: reason klasyfikacji')
        elif row['submit_type'] != 'NORMAL':
            exclusions[sid] = f"submit_type={row['submit_type']}: brak zgłoszenia pomiarowego"
        else:
            retained.append(row)

    entrance_rows, entrance_points, scale_rows, north_rows, north_values = [], [], [], [], []
    invalid = {'entrance': [], 'scale': [], 'north': []}
    skipped = []
    for row in retained:
        sid, points = row['submission_id'], _points(row)
        entrance = _point(points, 0)
        if entrance is None:
            invalid['entrance'].append(sid)
        else:
            entrance_rows.append(row)
            entrance_points.append(entrance)
        ppm = row.get('pixels_per_meter')
        if _finite(ppm) and ppm > 0:
            scale_rows.append(row)
        else:
            invalid['scale'].append(sid)
        flag = row.get('skipNorth')
        start, end = _point(points, 3), _point(points, 4)
        if isinstance(flag, (bool, np.bool_)) and bool(flag):
            skipped.append(sid)
        elif (isinstance(flag, (bool, np.bool_)) and not flag and start is not None
              and end is not None and start != end and _finite(row.get('north_deg'))):
            north_rows.append(row)
            north_values.append(float(row['north_deg']))
        else:
            invalid['north'].append(sid)

    entrance_x, entrance_y, entrance_std = None, None, None
    if entrance_points:
        entrance_x, entrance_y = _geometric_median(entrance_points)
        xs, ys = zip(*entrance_points)
        entrance_std = float(np.sqrt(np.std(xs) ** 2 + np.std(ys) ** 2))
    ppm_values = [float(row['pixels_per_meter']) for row in scale_rows]
    filtered = scale_rows
    if len(ppm_values) >= 4:
        q1, q3 = np.percentile(ppm_values, [25, 75])
        lower, upper = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
        filtered = [row for row in scale_rows if lower <= row['pixels_per_meter'] <= upper]
    filtered_values = [float(row['pixels_per_meter']) for row in filtered]
    ppm = float(np.median(filtered_values)) if filtered_values else None
    cv = float(np.std(filtered_values) / np.mean(filtered_values)) if filtered_values else None
    filtered_ids = {row['submission_id'] for row in filtered}
    rejected = [row['submission_id'] for row in scale_rows if row['submission_id'] not in filtered_ids]
    angle, ambiguous = _circular_median(north_values)
    # Zaokrąglenie 179.9999 nie może stworzyć niekanonicznego +180°.
    rounded_angle = _rounded(angle, 3)
    if rounded_angle == 180.0:
        rounded_angle = -180.0
    quality_flag = None
    if cv is not None and cv > .1:
        quality_flag = 'high_ppm_cv'
    elif entrance_std is not None and entrance_std > 10.:
        quality_flag = 'high_entrance_std'

    return {
        'cave_id': cave_id, 'dir_id': match.group(1), 'image_id': image_id,
        'image_filename': Path(path).name, 'source_count': len(rows), 'count': len(retained),
        'users': len({row['user_id'] for row in retained}),
        'included_submission_ids': [row['submission_id'] for row in retained],
        'excluded_submission_ids': list(exclusions), 'exclusions': exclusions,
        'components': {
            'entrance': _counts(entrance_rows, invalid_submission_ids=invalid['entrance']),
            'scale_before_iqr': _counts(scale_rows, invalid_submission_ids=invalid['scale']),
            'scale_after_iqr': _counts(filtered, rejected_submission_ids=rejected),
            'north': _counts(north_rows, invalid_submission_ids=invalid['north'],
                             skipped_submission_ids=skipped),
        },
        'entrance': {'x': _rounded(entrance_x, 2), 'y': _rounded(entrance_y, 2)},
        'scale': {'pixels_per_meter': _rounded(ppm, 2)},
        'north': {'angle_deg': rounded_angle, 'all_skipped': bool(retained) and len(skipped) == len(retained),
                  'angle_origin': 'measured' if angle is not None else 'unknown', 'ambiguous': ambiguous},
        'quality': {'ppm_cv': _rounded(cv, 3), 'ppm_values': [_rounded(v, 2) for v in ppm_values],
                    'entrance_std_px': _rounded(entrance_std, 2), 'outliers_removed': len(rejected),
                    'flag': quality_flag},
        'raw': {'entrance_std_px': entrance_std, 'ppm_cv': cv, 'north_angle_deg': angle},
    }


def aggregate_cave(cave_id, subs, classification=None):
    """Agreguj jedną grupę; classification={} daje jawne przeliczenie kontrolne."""
    registry = load_classification() if classification is None else classification
    return _aggregate(_identifier(cave_id, 'cave_id'), _rows(subs), registry)


def aggregate_catalogue(subs, min_users=5, classification=None):
    """Zachowaj wszystkie grupy, także całkowicie wykluczone i poniżej progu.

    eligible odnosi się do odrębnych użytkowników zachowanych zgłoszeń NORMAL.
    Nie zastępuje liczników użytkowników ważnych pomiarów każdego komponentu.
    """
    if isinstance(min_users, bool) or not isinstance(min_users, int) or min_users < 1:
        raise ValueError('min_users musi być dodatnią liczbą całkowitą')
    registry = load_classification() if classification is None else classification
    groups = {}
    for row in _rows(subs):
        groups.setdefault(row['cave_id'], []).append(row)
    result = {}
    for cave_id, rows in sorted(groups.items()):
        aggregate = _aggregate(cave_id, rows, registry)
        aggregate.update(min_users=min_users, eligible=aggregate['users'] >= min_users)
        result[cave_id] = aggregate
    return result
