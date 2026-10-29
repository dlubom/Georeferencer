"""Kontrakt przypiętego wejścia: integralność, odtwarzanie i wpływ zmiany."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import io
import csv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import coordinate_source as source


class CoordinateSourceTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.csv = self.root / "best-measurements.csv"
        self.csv.write_bytes(b"object_id,measurement_id,lat,lon\nO1,M1,49,19\n")
        self.manifest = self.root / "source.json"
        self.pin = {
            "schema_version": 1, "repository": "dlubom/gps-kataster-obiektow-tatr",
            "release": "v1.3.1", "asset": "best-measurements.csv",
            "sha256": hashlib.sha256(self.csv.read_bytes()).hexdigest(),
            "snapshot": "best-measurements.csv",
        }
        self.manifest.write_text(json.dumps(self.pin))

    def cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "pipeline/coordinate_source.py"),
                               "--manifest", str(self.manifest), *args],
                              capture_output=True, text=True)

    def test_verify_rejects_changed_bytes_before_reading_coordinates(self):
        self.assertEqual(self.cli("verify").returncode, 0)
        self.csv.write_bytes(self.csv.read_bytes() + b"\n")
        result = self.cli("verify")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SHA-256", result.stderr)

    def test_fetch_checks_hash_before_replacing_existing_output(self):
        output = self.root / "download.csv"
        output.write_bytes(b"previous verified download")
        with patch.object(source, "urlopen", return_value=io.BytesIO(b"wrong")):
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                source.fetch(self.manifest, output)
        self.assertEqual(output.read_bytes(), b"previous verified download")
        with patch.object(source, "urlopen", return_value=io.BytesIO(self.csv.read_bytes())):
            source.fetch(self.manifest, output)
        self.assertEqual(output.read_bytes(), self.csv.read_bytes())

    def test_latest_is_not_a_valid_pin(self):
        self.pin["release"] = "latest"
        self.manifest.write_text(json.dumps(self.pin))
        self.assertNotEqual(self.cli("verify").returncode, 0)

    def test_impact_lists_all_linked_plans_and_measurement_changes(self):
        before = {"O1": {"object_id": "O1", "measurement_id": "M1", "lat": "49", "lon": "19"}}
        after = {"O1": {"object_id": "O1", "measurement_id": "M2", "lat": "49.1", "lon": "19"}}
        plans = [{"dir_id": "001", "object_id": "O1"},
                 {"dir_id": "002", "object_id": "O1"}]
        report = source.compare(before, after, plans)
        self.assertEqual(report["affected_plans"], ["001", "002"])
        self.assertEqual(report["changes"][0]["fields"], {
            "measurement_id": {"before": "M1", "after": "M2"},
            "lat": {"before": "49", "after": "49.1"}})
        self.assertEqual(report["changes"][0]["plans"], ["001", "002"])
        self.assertTrue(report["changes"][0]["position_changed"])

    def test_impact_includes_removed_added_and_metadata_only_objects(self):
        report = source.compare({"O1": {"source": "a"}, "O2": {"lat": "49"}},
                                {"O1": {"source": "b"}, "O3": {"lat": "49"}},
                                [{"dir_id": "001", "object_id": "O2"}])
        self.assertEqual([c["object_id"] for c in report["changes"]], ["O1", "O2", "O3"])
        self.assertFalse(report["changes"][0]["position_changed"])
        self.assertEqual(report["affected_plans"], ["001"])

    def test_duplicate_object_is_not_silently_lost_in_impact(self):
        self.csv.write_text("object_id,lat,lon\nO1,49,19\nO1,50,20\n")
        with self.assertRaisesRegex(ValueError, "O1"):
            source.read_rows(self.csv)

    def test_impact_cli_verifies_both_sources_and_reports_position_separately(self):
        pin = source.read_manifest(source.DEFAULT_MANIFEST)
        rows = source.read_rows(source.verify())
        document = json.loads((ROOT / "data/baseline/2026-10-24/catalogue.json").read_text())
        object_id = document["plans"][0]["object_id"]
        expected_plans = sorted(p["dir_id"] for p in document["plans"] if p["object_id"] == object_id)
        rows[object_id]["lat"] = str(float(rows[object_id]["lat"]) + .001)
        rows[object_id]["measurement_id"] = "new-measurement"
        candidate = self.root / "candidate.csv"
        with candidate.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=next(iter(rows.values())).keys())
            writer.writeheader()
            writer.writerows(rows.values())
        pin["snapshot"] = candidate.name
        pin["sha256"] = source.sha256(candidate)
        manifest = self.root / "candidate.json"
        manifest.write_text(json.dumps(pin))
        output = self.root / "impact.json"
        command = [sys.executable, str(ROOT / "pipeline/coordinate_source.py"), "impact",
                   "--candidate", str(manifest), "--output", str(output)]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(output.read_text())
        self.assertEqual(report["affected_plans"], expected_plans)
        self.assertEqual([p["dir_id"] for p in report["geometry"]["plans"]], expected_plans)
        self.assertGreater(report["geometry"]["plans"][0]["delta"]["entrance_distance_m"], 100)
        self.assertFalse(report["geometry"]["plans"][0]["scale_input_changed"])
        candidate.write_text("corrupted")
        output.unlink()
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SHA-256", result.stderr)
        self.assertFalse(output.exists())

    def test_impact_includes_new_manual_plan_without_a_historical_sidecar(self):
        plan_id = '001459-pza-2024'
        self.assertFalse((ROOT / 'data/caves' / plan_id / 'image.tfw').exists())
        pin = source.read_manifest(source.DEFAULT_MANIFEST)
        rows = source.read_rows(source.verify())
        rows['MTZ-0017']['lat'] = str(float(rows['MTZ-0017']['lat']) + .001)
        candidate = self.root / 'manual-candidate.csv'
        with candidate.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=next(iter(rows.values())).keys())
            writer.writeheader()
            writer.writerows(rows.values())
        pin.update(snapshot=candidate.name, sha256=source.sha256(candidate))
        manifest = self.root / 'manual-candidate.json'
        manifest.write_text(json.dumps(pin))
        output = self.root / 'manual-impact.json'
        result = subprocess.run([sys.executable, str(ROOT / 'pipeline/coordinate_source.py'),
            'impact', '--candidate', str(manifest), '--output', str(output)],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(output.read_text())
        self.assertEqual(report['affected_plans'], ['001459', plan_id])
        self.assertEqual([p['dir_id'] for p in report['geometry']['plans']], ['001459', plan_id])
        for plan in report['geometry']['plans']:
            self.assertNotIn('error', plan['before'])
            self.assertNotIn('error', plan['after'])
            self.assertGreater(plan['delta']['entrance_distance_m'], 100)

    def test_workflows_use_pinned_build_entrypoint_without_latest_override(self):
        import yaml
        for name in ("release-geotiff.yml", "generate-geotiff.yml"):
            workflow = yaml.safe_load((ROOT / ".github/workflows" / name).read_text())
            job = next(iter(workflow["jobs"].values()))
            step = next(s for s in job["steps"] if './scripts/build generate ' in s.get('run', ''))
            self.assertNotIn("latest", step["run"])
            self.assertNotIn("gps_kataster_tag", json.dumps(workflow))
            self.assertNotIn('gps-kataster-best-measurements', step['run'])
            # Generator sam weryfikuje snapshot. Próby CLI odrzucenia innych
            # bajtów pozostają w test_validation i test_geotiff_output.
