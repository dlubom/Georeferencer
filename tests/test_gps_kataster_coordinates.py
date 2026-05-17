import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))

from gps_kataster_coordinates import (  # noqa: E402
    BestMeasurementRow,
    GpsKatasterAmbiguousMatchError,
    GpsKatasterIndex,
    apply_coordinate_template,
    render_meta_template,
)


def row(
    object_id,
    *,
    name_local="Jaskinia Testowa",
    pig_id="123",
    nr_inwent="T.X-01.01",
    lat=49.0,
    lon=19.0,
):
    return BestMeasurementRow(
        object_id=object_id,
        category="jaskinia_otwor",
        name_local=name_local,
        cave_id="C-0001",
        measurement_id="m-001",
        lat=lat,
        lon=lon,
        x_1992="",
        y_1992="",
        source="TPN",
        source_ref="TPN:{abc}",
        nr_inwent=nr_inwent,
        pig_id=pig_id,
        tpn_globalid="{abc}",
        verification_status="nieweryfikowany",
    )


def meta(*, dir_id="000123", nr_inwent="T.X-01.01", name="Jaskinia Testowa", lat=49.0, lon=19.0):
    return {
        "cave": {
            "dir_id": dir_id,
            "inventory_number": nr_inwent,
            "name": name,
        },
        "coordinates": {
            "lat": lat,
            "lon": lon,
        },
    }


class GpsKatasterCoordinatesTest(unittest.TestCase):
    def test_resolves_unique_pig_and_inventory_match(self):
        index = GpsKatasterIndex([row("OBJ-1", lat=49.1, lon=19.1)])

        resolution = index.resolve_meta(meta())

        self.assertEqual(resolution.row.object_id, "OBJ-1")
        self.assertEqual(resolution.matched_by, "pig_id+nr_inwent")

    def test_explicit_object_id_wins(self):
        index = GpsKatasterIndex([
            row("OBJ-1", lat=49.1, lon=19.1),
            row("OBJ-2", lat=49.2, lon=19.2),
        ])
        data = meta()
        data["coordinates"]["gps_kataster_object_id"] = "OBJ-2"

        resolution = index.resolve_meta(data)

        self.assertEqual(resolution.row.object_id, "OBJ-2")
        self.assertEqual(resolution.matched_by, "object_id")

    def test_ambiguous_match_uses_nearest_previous_coordinates_when_clear(self):
        index = GpsKatasterIndex([
            row("OBJ-NEAR", lat=49.00001, lon=19.00001),
            row("OBJ-FAR", lat=49.01, lon=19.01),
        ])

        resolution = index.resolve_meta(meta(lat=49.0, lon=19.0))

        self.assertEqual(resolution.row.object_id, "OBJ-NEAR")
        self.assertEqual(resolution.matched_by, "pig_id+nr_inwent+nearest_previous_coordinates")
        self.assertGreater(resolution.match_distance_m, 0)

    def test_ambiguous_match_without_safe_disambiguation_raises(self):
        index = GpsKatasterIndex([
            row("OBJ-1", lat=49.00001, lon=19.00001),
            row("OBJ-2", lat=49.00002, lon=19.00002),
        ])

        with self.assertRaises(GpsKatasterAmbiguousMatchError):
            index.resolve_meta(meta(lat=49.0, lon=19.0))

    def test_apply_coordinate_template_records_opening_id(self):
        index = GpsKatasterIndex([row("OBJ-1", lat=49.123456789, lon=19.987654321)])
        data = meta()
        resolution = index.resolve_meta(data)

        apply_coordinate_template(data, resolution)

        self.assertEqual(data["coordinates"]["gps_kataster_object_id"], "OBJ-1")
        self.assertEqual(
            data["coordinates"]["lat"],
            "{{ gps_kataster.objects[gps_kataster_object_id].lat }}",
        )
        self.assertEqual(
            data["coordinates"]["lon"],
            "{{ gps_kataster.objects[gps_kataster_object_id].lon }}",
        )

    def test_render_meta_template_uses_opening_id(self):
        index = GpsKatasterIndex([row("OBJ-1", lat=49.123456789, lon=19.987654321)])
        raw_text = """
coordinates:
  gps_kataster_object_id: OBJ-1
  lat: "{{ gps_kataster.objects[gps_kataster_object_id].lat }}"
  lon: "{{ gps_kataster.objects[gps_kataster_object_id].lon }}"
"""

        rendered = render_meta_template(raw_text, index)

        self.assertIn("lat: \"49.123456789\"", rendered)
        self.assertIn("lon: \"19.987654321\"", rendered)


if __name__ == "__main__":
    unittest.main()
