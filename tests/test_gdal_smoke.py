"""Mała próba pełnego CLI z rzeczywistym GDAL i danymi syntetycznymi."""

import csv
import hashlib
import json
import math
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from pyproj import CRS

import yaml


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "pipeline" / "02_generate_geotiff.py"


class GdalSmokeTest(unittest.TestCase):
    def setUp(self):
        for executable in ("gdal_translate", "gdalinfo"):
            self.assertIsNotNone(
                shutil.which(executable),
                f"Brak {executable}; uruchom kontrolę w referencyjnym środowisku CI.",
            )
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.data_dir = Path(temporary_directory.name)
        self.cave_dir = self.data_dir / "001131"
        self.cave_dir.mkdir()
        self.image_path = self.cave_dir / "image.tif"
        # Niesymetryczny wzór ujawnia odwrócenie, obrót albo utratę pikseli.
        with Image.new("1", (8, 6)) as image:
            for pixel in ((0, 0), (1, 0), (7, 1), (2, 3), (5, 4), (6, 5)):
                image.putpixel(pixel, 255)
            image.save(self.image_path)

        self.meta_path = self.cave_dir / "meta.yaml"
        self.meta_path.write_text(
            """cave:
  dir_id: '001131'
  name: Plan syntetyczny
image:
  filename: image_1_zoom_10.tif
  image_id: 1
  width: 8
  height: 6
coordinates:
  gps_kataster_object_id: KSZ-0033
  lat: "{{ gps_kataster.objects[gps_kataster_object_id].lat }}"
  lon: "{{ gps_kataster.objects[gps_kataster_object_id].lon }}"
entrance:
  x: 2.0
  y: 3.0
scale:
  pixels_per_meter: 2.0
north:
  angle_deg: 0.0
declination_deg: 0.0
""",
            encoding="utf-8",
        )
        sys.path.insert(0, str(ROOT / 'pipeline'))
        from orientation_fixture import attach_orientation
        self.meta_path.write_text(yaml.safe_dump(attach_orientation(yaml.safe_load(self.meta_path.read_text()),
            hashlib.sha256(self.image_path.read_bytes()).hexdigest()),
                                                  allow_unicode=True, sort_keys=False))
        from coordinate_source import verify
        self.coordinates_path = verify()
        self.registry_path = self.data_dir / "images.json"
        self.registry_path.write_text(json.dumps({"schema_version": 1, "plans": {
            "001131": {"filename": "image_1_zoom_10.tif", "image_id": 1,
                          "width": 8, "height": 6,
                          "sha256": hashlib.sha256(self.image_path.read_bytes()).hexdigest()}}}))
        output_temporary = tempfile.TemporaryDirectory()
        self.addCleanup(output_temporary.cleanup)
        self.output = Path(output_temporary.name)

    def run_generator(self):
        return subprocess.run(
            [
                sys.executable, str(GENERATOR),
                "--data-dir", str(self.data_dir),
                "--cave", self.cave_dir.name,
                "--gps-kataster-best-measurements", str(self.coordinates_path),
                "--gps-kataster-strict",
                "--image-registry", str(self.registry_path),
                "--output-dir", str(self.output),
            ],
            cwd=self.data_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_cli_generates_readable_geotiff_with_crs_and_unchanged_pixels(self):
        result = self.run_generator()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        output_path = self.output / 'current' / self.cave_dir.name / 'image_georef.tif'
        info_result = subprocess.run(
            ["gdalinfo", "-json", str(output_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(
            info_result.returncode, 0, info_result.stdout + info_result.stderr
        )
        info = json.loads(info_result.stdout)
        self.assertEqual(info["driverShortName"], "GTiff")
        self.assertEqual(info["size"], [8, 6])
        self.assertEqual(len(info["bands"]), 1)
        crs = CRS.from_wkt(info["coordinateSystem"]["wkt"]).to_json_dict()
        self.assertEqual(crs["id"], {"authority": "EPSG", "code": 2180})
        self.assertEqual(info["metadata"]["IMAGE_STRUCTURE"]["COMPRESSION"], "CCITTFAX4")
        transform = info["geoTransform"]
        self.assertEqual(len(transform), 6)
        self.assertTrue(all(math.isfinite(value) for value in transform))
        self.assertNotEqual(transform[1] * transform[5] - transform[2] * transform[4], 0)
        # To próba zapisu/odczytu GDAL, nie orzeczenie o konwencji otworu,
        # zbieżności południków ani korekcie półpiksela (osobne zadanie T06).
        tfw = [float(line) for line in (output_path.parent / "image.tfw").read_text().splitlines()]
        self.assertEqual(len(tfw), 6)
        self.assertTrue(all(math.isfinite(value) for value in tfw))
        with Image.open(self.image_path) as source, Image.open(output_path) as output:
            self.assertEqual(output.size, source.size)
            self.assertEqual(output.convert("L").tobytes(), source.convert("L").tobytes())

    def test_cli_returns_failure_for_mismatched_image_dimensions(self):
        self.meta_path.write_text(
            self.meta_path.read_text(encoding="utf-8").replace("width: 8", "width: 9"),
            encoding="utf-8",
        )

        result = self.run_generator()

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("image.width", result.stdout + result.stderr)
        self.assertFalse((self.cave_dir / "image_georef.tif").exists())


if __name__ == "__main__":
    unittest.main()
