"""Kotwica podpisanego otworu północnego Mroźnej, grafika 569."""
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


class MroznaAnchorTest(unittest.TestCase):
    def test_northern_symbol_maps_to_northern_entrance(self):
        generator = generator_module()
        index = load_best_measurements(verify())
        _, resolved = validate_plan(ROOT / 'data/caves/001094', index)
        params = generator.compute_world_file(resolved)
        # Niezależny od YAML odczyt kropki w trójkącie podpisanym
        # OTWÓR PÓŁNOCNY / 0,00; docs/reports/2026-10-26-mrozna-anchor.md.
        x, y = 20695.166666666668, 1733.1666666666667
        actual = (params['A']*(x-.5) + params['B']*(y-.5) + params['C'],
                  params['D']*(x-.5) + params['E']*(y-.5) + params['F'])
        row = index.by_object_id['KSW-0256']
        expected = generator.TRANSFORMER.transform(row.lon, row.lat)
        # Próg dotyczy położenia symbolu względem kotwicy, nie jakości GPS.
        self.assertLess(math.dist(actual, expected), .05)
