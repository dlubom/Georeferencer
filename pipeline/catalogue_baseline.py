"""Porównanie geometrii przy aktualizacji przypiętych współrzędnych."""
import importlib.util
import math

import yaml

from coordinate_source import sha256, verify

TFW_ORDER = ("A", "D", "B", "E", "C", "F")


def calculate(root, plans, manifest):
    from gps_kataster_coordinates import load_best_measurements
    from validation import validate_plan
    spec = importlib.util.spec_from_file_location('impact_generator', root / 'pipeline/02_generate_geotiff.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    index = load_best_measurements(verify(manifest))
    results = {}
    for plan in plans:
        try:
            _, meta = validate_plan(root / 'data/caves' / plan['dir_id'], index)
            parameters = module.compute_world_file(meta)
            text = "\n".join(f"{parameters[k]:.{10 if k in 'ADBE' else 6}f}" for k in TFW_ORDER) + "\n"
            results[plan['dir_id']] = {'tfw_text': text, 'parameters': dict(zip(TFW_ORDER, map(float, text.splitlines())))}
        except (ValueError, KeyError) as exc:
            results[plan['dir_id']] = {'error': str(exc)}
    return results


def coordinate_impact(root, plans, before_manifest, after_manifest):
    before = calculate(root, plans, before_manifest)
    after = calculate(root, plans, after_manifest)
    return {"interpretation": "Przeliczenie tym samym generatorem; zmiana współrzędnych, bez naprawy rotacji.",
            "generator_sha256": sha256(root / "pipeline/02_generate_geotiff.py"),
            "plans": [{"dir_id": p["dir_id"], "before": before[p["dir_id"]], "after": after[p["dir_id"]],
                       "delta": geometry_delta(root, p, before[p["dir_id"]], after[p["dir_id"]]),
                       "scale_input_changed": False, "north_input_changed": False}
                      for p in plans if before[p["dir_id"]] != after[p["dir_id"]]]}


def geometry_delta(root, plan, before, after):
    if "error" in before or "error" in after:
        return None
    a, b = before["parameters"], after["parameters"]
    path = f"data/caves/{plan['dir_id']}/meta.yaml"
    meta = yaml.safe_load((root / path).read_bytes())
    x, y = meta["entrance"]["x"], meta["entrance"]["y"]
    # Kliknięcia od narożnika obrazu, TFW od środka pierwszego piksela.
    x, y = x - 0.5, y - 0.5
    dx = (b["A"] - a["A"]) * x + (b["B"] - a["B"]) * y + b["C"] - a["C"]
    dy = (b["D"] - a["D"]) * x + (b["E"] - a["E"]) * y + b["F"] - a["F"]
    angle = math.degrees(math.atan2(b["D"], b["A"]) - math.atan2(a["D"], a["A"]))
    return {"entrance_dx_m": dx, "entrance_dy_m": dy, "entrance_distance_m": math.hypot(dx, dy),
            "rotation_deg": (angle + 180) % 360 - 180,
            "scale_m_per_pixel": math.hypot(b["A"], b["D"]) - math.hypot(a["A"], a["D"])}
