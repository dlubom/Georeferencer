"""Skala Juhaskiej z opisanych linii siatki, niezależnie od błędnej podziałki."""
import importlib.util
import math
from pathlib import Path
import sys
import unittest

from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pipeline'))
from coordinate_source import verify
from gps_kataster_coordinates import load_best_measurements
from validation import validate_plan

spec = importlib.util.spec_from_file_location('juhaska_generator', ROOT / 'pipeline/02_generate_geotiff.py')
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


class JuhaskaScaleTest(unittest.TestCase):
    def test_projected_grid_intervals_are_ten_metres_and_entrance_stays_anchored(self):
        _, resolved = validate_plan(ROOT / 'data/caves/001212', load_best_measurements(verify()))
        params = generator.compute_world_file(resolved)

        def world(x, y):
            return (params['C'] + params['A'] * (x - .5) + params['B'] * (y - .5),
                    params['F'] + params['D'] * (x - .5) + params['E'] * (y - .5))

        # Środki kreski 0, -10 i -20 na TIFF-ie 3674x3004; pomiar opisany w raporcie.
        points = [world(1000, y) for y in (603.5, 1581.5, 2560.5)]
        for start, end in zip(points, points[1:]):
            self.assertAlmostEqual(math.dist(start, end), 10, delta=.03)
        coords = resolved['coordinates']
        expected = Transformer.from_crs(4326, 2180, always_xy=True).transform(coords['lon'], coords['lat'])
        entrance = resolved['entrance']
        self.assertLess(math.dist(world(entrance['x'], entrance['y']), expected), 1e-7)


if __name__ == '__main__':
    unittest.main()
