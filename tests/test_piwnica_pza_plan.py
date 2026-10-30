"""Odbiór ręcznych pomiarów nowego planu PZA, niezależnie od zapisu TFW."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import unittest

from PIL import Image
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pipeline'))
from coordinate_source import verify
from gps_kataster_coordinates import load_best_measurements
from validation import validate_plan

spec = importlib.util.spec_from_file_location('piwnica_generator', ROOT / 'pipeline/02_generate_geotiff.py')
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)
PLAN = ROOT / 'data/caves/001459-pza-2024'


class PiwnicaPzaPlanTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.meta, cls.resolved = validate_plan(PLAN, load_best_measurements(verify()))
        cls.source = json.loads((PLAN / 'source.json').read_text())

    def test_export_selects_only_current_piwnica_plan(self):
        selected = {path.name for path in generator.find_caves(ROOT / 'data/caves')}
        self.assertIn(PLAN.name, selected)
        self.assertNotIn('001459', selected)

    def test_external_publication_identity_and_two_raster_sizes(self):
        self.assertEqual(self.meta['cave']['source_cave_id'], '001459')
        self.assertEqual(self.meta['coordinates']['gps_kataster_object_id'], 'MTZ-0017')
        self.assertEqual(self.meta['image']['id_namespace'], 'local:pza-polish-caving')
        self.assertEqual(self.source['document']['page'], 17)
        self.assertEqual(self.meta['provenance']['registry']['sha256'],
                         hashlib.sha256((PLAN / 'source.json').read_bytes()).hexdigest())
        with Image.open(PLAN / 'image.tif') as mono, Image.open(PLAN / 'image_original.jpg') as small, Image.open(PLAN / 'image_upscaled.jpg') as large:
            self.assertEqual(mono.mode, '1')
            self.assertEqual(mono.info['compression'], 'group4')
            self.assertEqual(mono.size, (7630, 5020))
            self.assertEqual(large.size, mono.size)
            self.assertEqual(small.size, (3815, 2510))

    def test_printed_ruler_and_independently_projected_entrance(self):
        params = generator.compute_world_file(self.resolved)
        def world(point):
            x, y = point
            return (params['C'] + params['A'] * (x - .5) + params['B'] * (y - .5),
                    params['F'] + params['D'] * (x - .5) + params['E'] * (y - .5))
        measurements = self.source['measurements']
        scale = measurements['scale']
        self.assertAlmostEqual(math.dist(world(scale['start']), world(scale['end'])), scale['meters'], places=8)
        # Druga, niezależna linia siatki obejmuje 80 m; tolerancja pomiaru 3 px.
        self.assertLess(abs(math.dist(world((3119.5, 1000)), world((6194.5, 1000))) - 80), 3 / 38.45)
        entrance = measurements['entrance']
        coords = self.resolved['coordinates']
        expected = Transformer.from_crs(4326, 2180, always_xy=True).transform(coords['lon'], coords['lat'])
        self.assertLess(math.dist(world((entrance['x'], entrance['y'])), expected), 1e-7)

    def test_measured_north_does_not_claim_a_verified_reference(self):
        north = self.source['measurements']['north']
        x0, y0 = north['shaft_start']
        x1, y1 = north['shaft_end']
        self.assertAlmostEqual(math.degrees(math.atan2(x1 - x0, y0 - y1)), self.meta['north']['angle_deg'])
        self.assertEqual(self.meta['north']['angle_origin'], 'measured')
        self.assertEqual(self.meta['north']['reference'], 'unknown')
        self.assertEqual(self.meta['orientation']['status'], 'unverified')
        self.assertEqual(self.meta['orientation']['mode'], 'assumed_grid')
        self.assertNotIn('historical', self.meta['orientation'])
        exceptions = json.loads((ROOT / 'data/qa/exceptions-v1.json').read_text())['exceptions']
        self.assertEqual([e['rule'] for e in exceptions if e['plan_id'] == PLAN.name], ['orientation.unknown'])


if __name__ == '__main__':
    unittest.main()
