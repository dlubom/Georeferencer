import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PIPELINE_DIR = ROOT / "pipeline"
sys.path.insert(0, str(PIPELINE_DIR))

spec = importlib.util.spec_from_file_location(
    "generate_geotiff",
    PIPELINE_DIR / "02_generate_geotiff.py",
)
generate_geotiff = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(generate_geotiff)

from gps_kataster_coordinates import (  # noqa: E402
    BestMeasurementRow,
    GpsKatasterCoordinateError,
    GpsKatasterIndex,
)


def row(object_id="OBJ-1", *, category="jaskinia_otwor"):
    return BestMeasurementRow(
        object_id=object_id,
        category=category,
        name_local="Jaskinia Testowa",
        cave_id="C-0001",
        measurement_id="m-001",
        lat=49.0,
        lon=19.0,
        x_1992="",
        y_1992="",
        source="TPN",
        source_ref="TPN:{abc}",
        nr_inwent="T.X-01.01",
        pig_id="123",
        tpn_globalid="{abc}",
        verification_status="nieweryfikowany",
    )


class GenerateGeotiffStrictTest(unittest.TestCase):
    def test_accepts_known_object_id(self):
        for category in ("jaskinia_otwor", "sztolnia"):
            with self.subTest(category=category):
                index = GpsKatasterIndex([row("OBJ-1", category=category)])
                meta = {"coordinates": {"gps_kataster_object_id": "OBJ-1"}}

                generate_geotiff.validate_gps_kataster_object_id(meta, index)

    def test_rejects_other_categories(self):
        for category in ("ponor", "wywierzysko", "unknown"):
            with self.subTest(category=category):
                index = GpsKatasterIndex([row("OBJ-1", category=category)])
                meta = {"coordinates": {"gps_kataster_object_id": "OBJ-1"}}

                with self.assertRaises(GpsKatasterCoordinateError):
                    generate_geotiff.validate_gps_kataster_object_id(meta, index)

    def test_rejects_unknown_object_id(self):
        index = GpsKatasterIndex([row("OBJ-1")])
        meta = {"coordinates": {"gps_kataster_object_id": "UNKNOWN"}}

        with self.assertRaises(GpsKatasterCoordinateError):
            generate_geotiff.validate_gps_kataster_object_id(meta, index)

    def test_rejects_missing_object_id(self):
        index = GpsKatasterIndex([row("OBJ-1")])
        meta = {"coordinates": {"lat": 49.0, "lon": 19.0}}

        with self.assertRaises(GpsKatasterCoordinateError):
            generate_geotiff.validate_gps_kataster_object_id(meta, index)

    def test_requires_index(self):
        meta = {"coordinates": {"gps_kataster_object_id": "OBJ-1"}}

        with self.assertRaises(GpsKatasterCoordinateError):
            generate_geotiff.validate_gps_kataster_object_id(meta, None)


if __name__ == "__main__":
    unittest.main()
