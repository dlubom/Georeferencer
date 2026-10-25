"""Odczyt historycznych TFW i audyt bez zapisu do katalogu planów."""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import platform
import subprocess
from pathlib import Path

import yaml

from coordinate_source import DEFAULT_MANIFEST, ROOT, read_manifest, read_rows, sha256, verify

BASELINE = ROOT / "data/baseline/2026-10-24/catalogue.json"
TFW_ORDER = ("A", "D", "B", "E", "C", "F")


def capture_plans(root, rows):
    plans = []
    for path in sorted((root / "data/caves").glob("*/meta.yaml")):
        meta = yaml.safe_load(path.read_text(encoding="utf-8"))
        directory = path.parent
        files = [path, directory / "image.tfw"] + sorted(
            p for p in directory.iterdir()
            if p.suffix.lower() in {".tif", ".jpg", ".jpeg", ".png"}
            and p.name != "image_georef.tif")
        text = (directory / "image.tfw").read_bytes().decode("utf-8")
        values = [float(v) for v in text.splitlines()]
        if len(values) != 6:
            raise ValueError(f"Niepoprawny historyczny TFW: {directory}")
        object_id = meta["coordinates"]["gps_kataster_object_id"]
        plans.append({"dir_id": directory.name, "cave": meta["cave"],
                      "object_id": object_id,
                      "measurement": rows.get(object_id),
                      "sha256": {str(p.relative_to(root)): sha256(p) for p in files},
                      "historical_tfw": {"text": text, "parameters": dict(zip(TFW_ORDER, values))}})
    return plans


def verify_inputs(root, document):
    mismatches = []
    expected = {p["dir_id"] for p in document["plans"]}
    actual = {p.parent.name for p in (root / "data/caves").glob("*/meta.yaml")}
    if actual != expected:
        mismatches.append("Zmieniony zestaw planów")
    hashes = dict(document.get("other_inputs_sha256", {}))
    for plan in document["plans"]:
        hashes.update(plan["sha256"])
    for path, expected_hash in hashes.items():
        full_path = root / path
        if not full_path.is_file() or sha256(full_path) != expected_hash:
            mismatches.append(path)
    return mismatches


def generator(root):
    spec = importlib.util.spec_from_file_location("baseline_generator", root / "pipeline/02_generate_geotiff.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def calculate(root, plans, manifest):
    from gps_kataster_coordinates import load_best_measurements, render_meta_template
    index = load_best_measurements(verify(manifest))
    module = generator(root)
    results = {}
    for plan in plans:
        raw = (root / "data/caves" / plan["dir_id"] / "meta.yaml").read_text(encoding="utf-8")
        try:
            meta = yaml.safe_load(render_meta_template(raw, index))
            module.validate_gps_kataster_object_id(meta, index)
            parameters = module.compute_world_file(meta)
            # Ten sam format liczbowy co write_tfw, bez uruchamiania mutującego process_cave.
            text = "\n".join(f"{parameters[k]:.{10 if k in 'ADBE' else 6}f}" for k in TFW_ORDER) + "\n"
            results[plan["dir_id"]] = {"tfw_text": text, "parameters": {k: float(v) for k, v in zip(TFW_ORDER, text.splitlines())}}
        except (ValueError, KeyError) as exc:
            results[plan["dir_id"]] = {"error": str(exc)}
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
    meta = yaml.safe_load((root / "data/caves" / plan["dir_id"] / "meta.yaml").read_text())
    x, y = meta["entrance"]["x"], meta["entrance"]["y"]
    dx = (b["A"] - a["A"]) * x + (b["B"] - a["B"]) * y + b["C"] - a["C"]
    dy = (b["D"] - a["D"]) * x + (b["E"] - a["E"]) * y + b["F"] - a["F"]
    angle = math.degrees(math.atan2(b["D"], b["A"]) - math.atan2(a["D"], a["A"]))
    return {"entrance_dx_m": dx, "entrance_dy_m": dy, "entrance_distance_m": math.hypot(dx, dy),
            "rotation_deg": (angle + 180) % 360 - 180,
            "scale_m_per_pixel": math.hypot(b["A"], b["D"]) - math.hypot(a["A"], a["D"])}


def recalculation(root, document, manifest):
    mismatches = verify_inputs(root, document)
    if mismatches:
        raise ValueError(f"Przeliczenie wymaga niezmienionych wejść i generatora bazowego: {mismatches}")
    calculated = calculate(root, document["plans"], manifest)
    differences = []
    for plan in document["plans"]:
        result = calculated[plan["dir_id"]]
        historical = plan["historical_tfw"]
        result["equals_historical_bytes"] = result.get("tfw_text") == historical["text"]
        result["delta_from_historical"] = geometry_delta(root, plan, historical, result)
        if not result["equals_historical_bytes"]:
            differences.append(plan["dir_id"])
    import pyproj
    return {"kind": "legacy_generator_with_pinned_csv_recalculation",
            "environment": {"Python": platform.python_version(), "pyproj": pyproj.__version__, "PROJ": pyproj.proj_version_str},
            "historical_reference": document["reference_commit"],
            "coordinate_source": read_manifest(manifest),
            "interpretation": "To przeliczenie starszym wzorem, nie historyczny TFW ani naprawa rotacji. Pochodzenie CSV historycznych TFW nie jest potwierdzone.",
            "different_from_historical": differences, "plans": calculated}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["capture", "verify", "recalculate"])
    parser.add_argument("--baseline", type=Path, default=BASELINE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--reference-commit", help="Pełny commit źródeł historycznych; tylko capture")
    args = parser.parse_args()
    if args.command == "capture":
        if not args.reference_commit or not args.output:
            parser.error("capture wymaga --reference-commit i --output")
        reference = subprocess.check_output(["git", "rev-parse", args.reference_commit], cwd=ROOT, text=True).strip()
        guarded = ["data/caves", "parquet", "pipeline/01_extract_yaml.py", "pipeline/02_generate_geotiff.py",
                   "pipeline/03_report.py", "pipeline/05_add_cave.py", "pipeline/gps_kataster_coordinates.py"]
        subprocess.run(["git", "diff", "--exit-code", reference, "--", *guarded], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
        files = sorted((ROOT / "parquet").glob("*.parquet")) + sorted((ROOT / "data/caves/_reports").glob("*.csv"))
        files += [ROOT / p for p in guarded[2:]]
        document = {"schema_version": 1, "kind": "existing_historical_files",
                    "reference_commit": reference, "coordinate_source": read_manifest(DEFAULT_MANIFEST),
                    "measurement_provenance": "Powiązania i pomiary odczytane z przypiętego CSV; nie dowodzą źródła historycznego TFW.",
                    "other_inputs_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in files},
                    "plans": capture_plans(ROOT, read_rows(verify(DEFAULT_MANIFEST)))}
        args.output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return
    document = json.loads(args.baseline.read_text(encoding="utf-8"))
    if args.command == "verify":
        problems = verify_inputs(ROOT, document)
        if problems:
            parser.exit(1, f"Różnice względem punktu odniesienia: {problems}\n")
        print(f"OK: {len(document['plans'])} historycznych planów")
    else:
        if not args.output:
            parser.error("recalculate wymaga --output poza data/caves")
        if args.output.resolve().is_relative_to((ROOT / "data/caves").resolve()):
            parser.error("Nie wolno zapisywać audytu w data/caves")
        args.output.write_text(json.dumps(recalculation(ROOT, document, DEFAULT_MANIFEST), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
