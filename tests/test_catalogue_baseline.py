"""Historyczny TFW musi pochodzić z pliku, także gdy różni się od computed."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import catalogue_baseline as baseline


class CatalogueBaselineTest(unittest.TestCase):
    def test_capture_preserves_existing_tfw_bytes_without_regeneration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cave = root / "data/caves/001"
            cave.mkdir(parents=True)
            (cave / "meta.yaml").write_text("cave:\n  name: Test\ncoordinates:\n  gps_kataster_object_id: O1\ncomputed:\n  A: 999\n")
            (cave / "image.tif").write_bytes(b"source image bytes")
            tfw = "1.0000000000\n0\n0\n-1\n500.123456\n600.123456\n"
            (cave / "image.tfw").write_text(tfw)
            item = baseline.capture_plans(root, {"O1": {"measurement_id": "M1"}})[0]
            self.assertEqual(item["historical_tfw"]["text"], tfw)
            self.assertEqual(item["historical_tfw"]["parameters"]["A"], 1)
            self.assertEqual(item["measurement"]["measurement_id"], "M1")
            self.assertIn("data/caves/001/image.tif", item["sha256"])
            self.assertEqual((cave / "image.tfw").read_text(), tfw)
            self.assertIn("999", (cave / "meta.yaml").read_text())

    def test_frozen_baseline_has_complete_historical_results_and_valid_hashes(self):
        document = json.loads((ROOT / "data/baseline/2026-10-24/catalogue.json").read_text())
        self.assertEqual(len(document["plans"]), 814)
        self.assertEqual(len({p["dir_id"] for p in document["plans"]}), 814)
        for plan in document["plans"]:
            with self.subTest(plan=plan["dir_id"]):
                self.assertEqual(set(plan["historical_tfw"]["parameters"]), set("ADBECF"))
                self.assertTrue(plan["object_id"])
                self.assertTrue(plan["measurement"]["measurement_id"])
        self.assertEqual(baseline.verify_inputs(ROOT, document), [])

    def test_t08_frozen_adder_is_checked_with_original_hash_and_never_current_code(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = 'pipeline/05_add_cave.py'
            current = root / path
            frozen = root / 'data/history/05_add_cave-t02.py'
            current.parent.mkdir(parents=True)
            frozen.parent.mkdir(parents=True)
            (root / 'data/caves').mkdir(parents=True)
            current.write_bytes(b'current implementation')
            frozen.write_bytes(b'historical implementation')
            document = {'reference_commit': baseline.FROZEN_REFERENCE, 'plans': [],
                        'other_inputs_sha256': {path: hashlib.sha256(frozen.read_bytes()).hexdigest()}}
            self.assertEqual(baseline.verify_inputs(root, document), [])
            current.write_bytes(b'historical implementation')
            frozen.write_bytes(b'corruption')
            self.assertEqual(baseline.verify_inputs(root, document), [path])

    def test_geometry_delta_measures_translation_at_the_entrance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cave = root / "data/caves/001"
            cave.mkdir(parents=True)
            (cave / "meta.yaml").write_text("entrance:\n  x: 10\n  y: 20\n")
            old = {"parameters": dict(A=1, B=0, D=0, E=-1, C=100, F=200)}
            new = {"parameters": dict(A=1, B=0, D=0, E=-1, C=103, F=204)}
            delta = baseline.geometry_delta(root, {"dir_id": "001"}, old, new)
            self.assertEqual(delta, {"entrance_dx_m": 3, "entrance_dy_m": 4,
                                     "entrance_distance_m": 5, "rotation_deg": 0,
                                     "scale_m_per_pixel": 0})

    def test_saved_recalculation_is_reproducible_and_cannot_replace_history(self):
        document = json.loads(baseline.BASELINE.read_text())
        saved = json.loads((baseline.BASELINE.parent / "recalculated-v1.3.1.json").read_text())
        recalculated = baseline.recalculation(ROOT, document, baseline.DEFAULT_MANIFEST)
        self.assertEqual(recalculated, saved)
        self.assertTrue(saved["different_from_historical"])
        self.assertFalse(any("error" in p for p in saved["plans"].values()))
        self.assertEqual(baseline.verify_inputs(ROOT, document), [])

    def test_new_baseline_checks_its_own_code_instead_of_t02_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / 'pipeline/02_generate_geotiff.py'
            path.parent.mkdir()
            path.write_text('new generation code')
            (root / 'data/caves').mkdir(parents=True)
            document = {'reference_commit': 'future-reference', 'plans': [],
                        'other_inputs_sha256': {'pipeline/02_generate_geotiff.py': baseline.sha256(path)}}
            self.assertEqual(baseline.verify_inputs(root, document), [])
            path.write_text('changed since new baseline')
            self.assertEqual(baseline.verify_inputs(root, document), ['pipeline/02_generate_geotiff.py'])

    def test_frozen_code_corruption_is_not_hidden_by_current_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            current = root / 'pipeline/02_generate_geotiff.py'
            frozen = root / 'data/baseline/2026-10-24/legacy/02_generate_geotiff.py'
            current.parent.mkdir()
            frozen.parent.mkdir(parents=True)
            (root / 'data/caves').mkdir(parents=True)
            current.write_text('historical bytes')
            frozen.write_text('corrupted archive')
            document = {'reference_commit': 'fad70f09992671a0da5a364dfea4a2c538f80e3d', 'plans': [],
                        'other_inputs_sha256': {'pipeline/02_generate_geotiff.py': baseline.sha256(current)}}
            self.assertEqual(baseline.verify_inputs(root, document), ['pipeline/02_generate_geotiff.py'])

    def test_original_metadata_audit_is_independent_of_current_yaml(self):
        import hashlib
        import zipfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            name = 'data/caves/001/meta.yaml'
            current = root / name
            current.parent.mkdir(parents=True)
            current.write_bytes(b'new migrated metadata')
            archive = root / 'data/history/t02-inputs.zip'
            archive.parent.mkdir(parents=True)
            original = b'original metadata bytes\n'
            document = {'reference_commit': baseline.FROZEN_REFERENCE,
                        'plans': [{'dir_id': '001', 'sha256': {name: hashlib.sha256(original).hexdigest()}}]}
            with zipfile.ZipFile(archive, 'w') as target:
                target.writestr(name, original)
            self.assertEqual(baseline.verify_inputs(root, document), [])
            current.unlink()
            self.assertEqual(baseline.verify_inputs(root, document), [])
            with zipfile.ZipFile(archive, 'w') as target:
                target.writestr(name, b'changed archive')
            self.assertEqual(baseline.verify_inputs(root, document), [name])


class QaHistoryTest(unittest.TestCase):
    def test_t09_qa_reports_keep_original_t02_hashes_in_separate_files(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'data/caves/_reports').mkdir(parents=True)
            (root/'data/history/t02-reports').mkdir(parents=True)
            names=('summary.csv','flagged.csv','missing.csv')
            hashes={}
            for name in names:
                path='data/caves/_reports/'+name
                (root/path).write_text('new QA')
                frozen=root/'data/history/t02-reports'/name
                frozen.write_text('original '+name)
                hashes[path]=hashlib.sha256(frozen.read_bytes()).hexdigest()
            doc={'reference_commit':baseline.FROZEN_REFERENCE,'plans':[],'other_inputs_sha256':hashes}
            self.assertEqual(baseline.verify_inputs(root,doc),[])
            (root/'data/history/t02-reports/summary.csv').write_text('corrupt')
            self.assertEqual(baseline.verify_inputs(root,doc),['data/caves/_reports/summary.csv'])
