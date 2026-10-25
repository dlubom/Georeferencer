"""T06: wzorzec kierunku z dwóch rzutowanych punktów, rzeczywisty GDAL."""
import copy
import json
import math
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml
from pyproj import Transformer

from test_orientation import ROOT, generator, resolved
from orientation import inputs_hash, record_decision
import test_gdal_smoke as fixture

# Symetryczna sieczna południka: 0.0001° (~11 m) w każdą stronę.
# Błąd drugiego rzędu O(h²) oraz odejmowania współrzędnych ~500 km.
# 2e-8 dla wektora jednostkowego = 2 µm na kontrolnym odcinku 100 m.
DIRECTION_TOL = 2e-8
PROJECT = Transformer.from_crs(4326, 2180, always_xy=True)


def meridian_north(lon, lat):
    south = PROJECT.transform(lon, lat - 0.0001)
    north = PROJECT.transform(lon, lat + 0.0001)
    dx, dy = north[0] - south[0], north[1] - south[1]
    length = math.hypot(dx, dy)
    return dx / length, dy / length


def establish(meta, reference, angle=0.0, declination=0.0):
    meta = copy.deepcopy(meta)
    meta['north'].update(reference=reference, angle_deg=angle, angle_origin='measured',
                         evidence='Syntetyczny wzorzec testowy; nie ustala północy rzeczywistego planu.')
    meta['declination_deg'] = declination
    meta['declination'] = {'status': 'documented', 'sign_convention': 'east_positive',
                           'basis': 'Jawna wartość syntetycznego wzorca: wschód dodatni, zachód ujemny.',
                           'epoch': '2000.0 (epoka syntetyczna)'}
    accepted = meta['orientation']['decisions']
    if accepted and accepted[-1]['after_sha256'] == inputs_hash(meta):
        return meta
    return record_decision(meta, 'Próba modelu, bez potwierdzenia źródłowych metadanych.', '2026-10-25')


def arrow_vector(params, angle, ppm):
    dx, dy = math.sin(math.radians(angle)) * ppm, -math.cos(math.radians(angle)) * ppm
    return params['A'] * dx + params['B'] * dy, params['D'] * dx + params['E'] * dy


def raster_point(gt, x, y):
    return gt[0] + gt[1] * x + gt[2] * y, gt[3] + gt[4] * x + gt[5] * y


def tfw_tolerance(x, y):
    # C,F zaokrąglone do 1e-6 m; A,B,D,E do 1e-10 m/px.
    # Indeksy środków w TFW to x-.5, y-.5 dla punktu z UI/GDAL.
    # 2e-9 m: odczyt GDAL i działania double na współrzędnych PL-1992.
    return 0.5e-6 + (abs(x - .5) + abs(y - .5)) * 0.5e-10 + 2e-9


class GeometryTest(unittest.TestCase):
    def assert_vector(self, actual, expected, tolerance=DIRECTION_TOL):
        for a, b in zip(actual, expected):
            self.assertLessEqual(abs(a - b), tolerance, (actual, expected))

    def test_geographic_arrow_matches_projected_meridian_on_both_sides_and_centre(self):
        for lon in (17.0, 19.0, 21.0):
            for angle in (0.0, 32.75, -119.5):
                with self.subTest(lon=lon, angle=angle):
                    meta = establish(resolved(), 'geographic', angle, declination=8.0)
                    meta['coordinates'].update(lon=lon, lat=49.25)
                    params = generator.compute_world_file(meta)
                    expected = meridian_north(lon, 49.25)
                    self.assert_vector(arrow_vector(params, angle, meta['scale']['pixels_per_meter']), expected)
                    if lon == 19:
                        self.assertLess(abs(expected[0]), DIRECTION_TOL)
                    else:
                        # Wschód od λ0: północ geograficzna biegnie ku zachodowi siatki.
                        self.assertLess(expected[0] * (lon - 19), 0)

    def test_grid_arrow_has_no_convergence_or_declination_correction(self):
        for lon in (17.0, 21.0):
            meta = establish(resolved(), 'grid', 37.0, declination=-8.0)
            meta['coordinates']['lon'] = lon
            params = generator.compute_world_file(meta)
            self.assert_vector(arrow_vector(params, 37.0, meta['scale']['pixels_per_meter']), (0, 1), 1e-12)
            self.assertAlmostEqual(params['total_rotation_deg'], 37.0, places=12)

    def test_magnetic_arrow_uses_documented_east_positive_declination(self):
        for delta in (-6.5, 0.0, 5.25):
            for lon in (17.0, 21.0):
                with self.subTest(delta=delta, lon=lon):
                    meta = establish(resolved(), 'magnetic', -28.25, delta)
                    meta['coordinates'].update(lon=lon, lat=49.25)
                    params = generator.compute_world_file(meta)
                    nx, ny = meridian_north(lon, 49.25)
                    # Obrót wzorca północy ku wschodowi o dodatnią deklinację.
                    d = math.radians(delta)
                    expected = (nx * math.cos(d) + ny * math.sin(d),
                                ny * math.cos(d) - nx * math.sin(d))
                    self.assert_vector(arrow_vector(params, -28.25, meta['scale']['pixels_per_meter']), expected)
                    self.assertEqual(meta['orientation']['status'], 'unverified')

    def test_click_uses_raster_corner_coordinates_not_pixel_centre_indices(self):
        for reference in ('unknown', 'grid', 'geographic', 'magnetic'):
            meta = resolved() if reference == 'unknown' else establish(resolved(), reference, 31.25, -5.0)
            with self.subTest(reference=reference):
                params = generator.compute_world_file(meta)
                x, y = meta['entrance']['x'], meta['entrance']['y']
                actual = (params['C'] + params['A'] * (x-.5) + params['B'] * (y-.5),
                          params['F'] + params['D'] * (x-.5) + params['E'] * (y-.5))
                expected = PROJECT.transform(meta['coordinates']['lon'], meta['coordinates']['lat'])
                self.assert_vector(actual, expected, 1e-9)

    def test_current_coordinate_impact_uses_corner_click_for_changed_rotation(self):
        import catalogue_baseline
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cave = root / 'data/caves/001'
            cave.mkdir(parents=True)
            (cave / 'meta.yaml').write_text('entrance: {x: 10, y: 20}\n')
            # Oba TFW zakotwiczają GDAL (10,20) w (100,200), ze zmianą kierunku.
            old = {'parameters': dict(A=1, B=0, D=0, E=-1, C=90.5, F=219.5)}
            new = {'parameters': dict(A=0, B=1, D=1, E=0, C=80.5, F=190.5)}
            delta = catalogue_baseline.geometry_delta(root, {'dir_id': '001'}, old, new)
            self.assertEqual(delta['entrance_distance_m'], 0)


class RasterGeometryTest(unittest.TestCase):
    def setUp(self):
        fixture.GdalSmokeTest.setUp(self)
        self.root = self.data_dir
        self.sources = self.root / 'sources'
        self.sources.mkdir()
        self.cave_dir = self.cave_dir.rename(self.sources / '001131')
        self.meta_path = self.cave_dir / 'meta.yaml'
        self.output = self.root / 'results'

    def generate(self, output=True):
        cmd = [sys.executable, str(fixture.GENERATOR), '--data-dir', str(self.sources),
               '--cave', '001131', '--image-registry', str(self.registry_path)]
        if output:
            cmd += ['--output-dir', str(self.output)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        target = self.output / 'current/001131' if output else self.cave_dir
        info = json.loads(subprocess.check_output(['gdalinfo', '-json', str(target / 'image_georef.tif')], text=True))
        return target, info['geoTransform']

    def test_real_geotiff_click_second_point_and_half_pixel_in_both_cli(self):
        for reference in ('unknown', 'grid', 'geographic', 'magnetic'):
            for output in (True, False):
                with self.subTest(reference=reference, output=output):
                    # Przywróć ten sam syntetyczny plan, aby decyzje nie zależały od kolejności.
                    meta = yaml.safe_load(self.meta_path.read_text())
                    meta['entrance'].update(x=2.125, y=3.75)
                    if reference != 'unknown':
                        meta = establish(meta, reference, 32.75, -6.5)
                    self.meta_path.write_text(yaml.safe_dump(meta))
                    target, gt = self.generate(output)
                    x, y = meta['entrance']['x'], meta['entrance']['y']
                    row = resolved()['coordinates']
                    expected = PROJECT.transform(row['lon'], row['lat'])
                    for a, b in zip(raster_point(gt, x, y), expected):
                        self.assertLessEqual(abs(a-b), tfw_tolerance(x, y))
                    a, d, b, e, c, f = map(float, (target / 'image.tfw').read_text().splitlines())
                    # TFW (0,0) to środek piksela; GDAL (.5,.5) ten sam środek.
                    for actual, expected_centre in zip(raster_point(gt, .5, .5), (c, f)):
                        self.assertLessEqual(abs(actual-expected_centre), 2e-9)
                    self.assertGreater(math.dist(raster_point(gt, x+.5, y+.5), expected), 0.3)
                    if reference == 'unknown':
                        # Osobny wzorzec zgodności historycznej; nie potwierdzenie kierunku.
                        from orientation import default_context
                        p = default_context()['plans']['001131']['historical_tfw']['parameters']
                        length = math.hypot(p['A'], p['D'])
                        direction = (p['B']/length, p['E']/length)
                        qx, qy = x, y + 1.25
                    else:
                        radians = math.radians(meta['north']['angle_deg'])
                        qx, qy = x+1.25*math.sin(radians), y-1.25*math.cos(radians)
                        if reference == 'grid':
                            direction = (0, 1)
                        else:
                            nx, ny = meridian_north(row['lon'], row['lat'])
                            delta = math.radians(-6.5 if reference == 'magnetic' else 0)
                            direction = (nx*math.cos(delta)+ny*math.sin(delta),
                                         ny*math.cos(delta)-nx*math.sin(delta))
                    expected_q = tuple(v + .625*u for v, u in zip(expected, direction))
                    for actual, exp in zip(raster_point(gt, qx, qy), expected_q):
                        self.assertLessEqual(abs(actual-exp), tfw_tolerance(qx, qy) + .625*DIRECTION_TOL)
                    if output:
                        computed = json.loads((target / 'computed.json').read_text())
                        self.assertEqual(computed['orientation']['status'], 'unverified')
                        self.assertIn('pixel', computed['geometry'])
                        if reference == 'magnetic':
                            self.assertEqual(computed['orientation']['declination'], meta['declination'])
                            self.assertEqual(computed['orientation']['north'], meta['north'])

    def test_real_catalogue_image_preserves_unknown_angle_and_maps_two_points(self):
        # Rzeczywisty plan i TIFF, kopiowane tylko do /tmp, bez edycji źródeł.
        source = ROOT / 'data/caves/001131'
        for name in ('meta.yaml', 'image.tif'):
            shutil.copyfile(source / name, self.cave_dir / name)
        self.registry_path = ROOT / 'data/validation/images-v1.json'
        meta = resolved()
        target, gt = self.generate()
        x, y = meta['entrance']['x'], meta['entrance']['y']
        expected = PROJECT.transform(meta['coordinates']['lon'], meta['coordinates']['lat'])
        from orientation import default_context
        p = default_context()['plans']['001131']['historical_tfw']['parameters']
        direction = (p['A']/math.hypot(p['A'], p['D']), p['D']/math.hypot(p['A'], p['D']))
        for px, py, distance in ((x, y, 0), (x+100, y, 100/meta['scale']['pixels_per_meter'])):
            for actual, exp in zip(raster_point(gt, px, py),
                                   (v+distance*u for v, u in zip(expected, direction))):
                self.assertLessEqual(abs(actual-exp), tfw_tolerance(px, py))
        manifest = json.loads((target.parent / 'manifest.json').read_text())
        self.assertEqual(manifest['plans'][0]['orientation']['status'], 'unverified')
        self.assertEqual(manifest['plans'][0]['acceptance']['size'], [902, 1950])
