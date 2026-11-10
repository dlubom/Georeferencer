"""Podpisany otwór dolny Lodowej Małołąckiej, grafika PIG 1123."""
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pipeline'))

from coordinate_source import verify
from gps_kataster_coordinates import load_best_measurements
from qa import generator_module
from validation import validate_plan


class LodowaAnchorTest(unittest.TestCase):
    def test_lower_symbol_maps_to_lower_entrance(self):
        generator = generator_module()
        index = load_best_measurements(verify())
        _, resolved = validate_plan(ROOT / 'data/caves/001627', index)
        p = generator.compute_world_file(resolved)
        # Odczyt znaku „OTWÓR DOLNY” przy zerze siatki grafiki 1123.
        x, y = 436.14, 2324.0
        actual = (p['A'] * (x - .5) + p['B'] * (y - .5) + p['C'],
                  p['D'] * (x - .5) + p['E'] * (y - .5) + p['F'])
        lower = index.by_object_id['MLW-0011']
        expected = generator.TRANSFORMER.transform(lower.lon, lower.lat)
        self.assertLess(math.dist(actual, expected), .05)
