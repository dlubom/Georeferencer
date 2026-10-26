"""T04: rzeczywisty GDAL, osobne wyniki, atomowa publikacja i odbiór."""
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml
from PIL import Image

import test_gdal_smoke as fixture

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pipeline'))
spec = importlib.util.spec_from_file_location('t04_generator', fixture.GENERATOR)
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


def hashes(directory):
    return {str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directory.rglob('*')) if p.is_file()}


class OutputTest(unittest.TestCase):
    def setUp(self):
        fixture.GdalSmokeTest.setUp(self)
        self.root = self.data_dir
        self.data_dir = self.root / 'sources'
        self.data_dir.mkdir()
        self.cave_dir = self.cave_dir.rename(self.data_dir / '001131')
        self.image_path = self.cave_dir / 'image.tif'
        self.meta_path = self.cave_dir / 'meta.yaml'
        self.output = self.root / 'results'
        # Konflikt ma być ignorowany, a nie naprawiony w źródłach.
        (self.cave_dir / 'image.tfw').write_text('99\n0\n0\n-99\n123\n456\n')
        (self.cave_dir / 'image_original.jpg').write_bytes(b'archiwalny obraz')

    def cli(self, *extra, output=True):
        args = [sys.executable, str(fixture.GENERATOR), '--data-dir', str(self.data_dir),
                '--image-registry', str(self.registry_path)]
        if output:
            args += ['--output-dir', str(self.output)]
        return subprocess.run(args + list(extra), cwd=self.root, capture_output=True, text=True, timeout=60)

    def run_ok(self, *extra):
        result = self.cli(*(extra or ('--all',)))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return (self.output / 'current').resolve(strict=True)

    def api(self, force=True):
        return generator.process_output(generator.find_caves(self.data_dir), self.output, self.data_dir,
                                        self.coordinates_path, self.registry_path, force=force)

    def test_separate_output_preserves_sources_and_binds_manifest(self):
        before = hashes(self.data_dir)
        run = self.run_ok('--cave', '001131')
        self.assertEqual(before, hashes(self.data_dir))
        self.assertEqual(sorted(p.name for p in (run / '001131').iterdir()),
                         ['computed.json', 'image.tfw', 'image_georef.tif'])
        manifest = json.loads((run / 'manifest.json').read_text())
        self.assertEqual(manifest['status'], 'complete')
        plan = manifest['plans'][0]
        self.assertEqual(plan['dir_id'], '001131')
        self.assertEqual(plan['inputs']['meta.yaml'], before['001131/meta.yaml'])
        self.assertEqual(plan['inputs']['image.tif'], before['001131/image.tif'])
        self.assertEqual(plan['measurement']['object_id'], 'KSZ-0033')
        self.assertTrue(plan['measurement']['measurement_id'])
        from coordinate_source import DEFAULT_MANIFEST, read_manifest
        self.assertEqual(manifest['coordinate_source']['release'], read_manifest(DEFAULT_MANIFEST)['release'])
        self.assertEqual(manifest['coordinate_source']['sha256'],
                         hashlib.sha256(self.coordinates_path.read_bytes()).hexdigest())
        self.assertTrue(manifest['implementation'])
        self.assertEqual(plan['orientation']['status'], 'unverified')
        self.assertTrue(plan['orientation']['uncertainty_reason'])
        self.assertEqual(plan['orientation']['north_reference'], 'unknown')
        self.assertEqual(manifest['orientation_sources']['catalogue.json'],
                         hashlib.sha256((ROOT / 'data/baseline/2026-10-24/catalogue.json').read_bytes()).hexdigest())
        self.assertEqual(manifest['image_registry']['sha256'],
                         hashlib.sha256(self.registry_path.read_bytes()).hexdigest())
        for name, digest in plan['outputs'].items():
            self.assertEqual(digest, hashlib.sha256((run / '001131' / name).read_bytes()).hexdigest())

    def test_matches_current_t03_on_same_inputs_despite_conflicting_sidecar(self):
        self.assert_matches_t03()

    def test_t03_parity_for_nonzero_angles_scales_and_declination(self):
        for number, (angle, ppm, declination) in enumerate(((37.25, 3.1234567, 5.0),
                                                          (-125.75, 0.18, -4.5))):
            with self.subTest(angle=angle, ppm=ppm):
                meta = yaml.safe_load(self.meta_path.read_text())
                meta['north']['angle_deg'] = angle
                meta['scale']['pixels_per_meter'] = ppm
                meta['declination_deg'] = declination
                from orientation import record_decision
                meta = record_decision(meta, 'Jawna zmiana danych orientacji próby T04.', '2026-10-25')
                self.meta_path.write_text(yaml.safe_dump(meta))
                self.assert_matches_t03('legacy-' + str(number))

    def assert_matches_t03(self, legacy_name='legacy'):
        run = self.run_ok()
        new = run / '001131'
        # Oddzielna kopia i zamrożony generator T06. Produkcyjny CLI T10
        # nie udostępnia już zapisu do źródeł; hashe historii są niezmienione.
        legacy = self.root / legacy_name
        shutil.copytree(self.data_dir, legacy)
        old = legacy / '001131'
        from geometry_impact import load_generator
        from gps_kataster_coordinates import load_best_measurements
        frozen = ROOT / 'data/history/t06-code/02_generate_geotiff.py'
        digest = json.loads((ROOT / 'docs/reports/t06-geometry-impact.json').read_text())['after_implementation_sha256']['02_generate_geotiff.py']
        reference = load_generator(frozen, digest)
        meta, params = reference.prepare_cave(old, load_best_measurements(self.coordinates_path),
                                              json.loads(self.registry_path.read_text()))
        ok, message = reference.process_prepared(old, meta, params)
        self.assertTrue(ok, message)
        self.assertEqual((new / 'image.tfw').read_bytes(), (old / 'image.tfw').read_bytes())
        self.assertNotEqual((new / 'image.tfw').read_bytes(), (self.cave_dir / 'image.tfw').read_bytes())
        self.assertEqual(json.loads((new / 'computed.json').read_text()),
                         yaml.safe_load((old / 'meta.yaml').read_text())['computed'])
        for name in ('geoTransform', 'size', 'coordinateSystem'):
            self.assertEqual(self.info(new / 'image_georef.tif')[name],
                             self.info(old / 'image_georef.tif')[name])
        with Image.open(new / 'image_georef.tif') as a, Image.open(old / 'image_georef.tif') as b:
            self.assertEqual(a.tobytes(), b.tobytes())

    def info(self, path):
        return json.loads(subprocess.check_output(['gdalinfo', '-json', str(path)], text=True))

    def test_repeated_run_preserves_tfw_geometry_pixels_and_previous_complete_set(self):
        first = self.run_ok()
        before = hashes(first)
        second = self.run_ok()
        self.assertNotEqual(first, second)
        self.assertEqual(before, hashes(first))
        self.assertEqual((first / '001131/image.tfw').read_bytes(),
                         (second / '001131/image.tfw').read_bytes())
        self.assertEqual(self.info(first / '001131/image_georef.tif')['geoTransform'],
                         self.info(second / '001131/image_georef.tif')['geoTransform'])
        with Image.open(first / '001131/image_georef.tif') as a, Image.open(second / '001131/image_georef.tif') as b:
            self.assertEqual(a.tobytes(), b.tobytes())

    def test_t03_validation_and_pin_fail_before_output_writes(self):
        self.meta_path.write_text(self.meta_path.read_text().replace('width: 8', 'width: 9'))
        before = hashes(self.data_dir)
        result = self.cli('--all')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('image.width', result.stderr)
        self.assertFalse(self.output.exists())
        self.assertEqual(before, hashes(self.data_dir))
        fake = self.root / 'fake.csv'
        fake.write_bytes(self.coordinates_path.read_bytes() + b'\n')
        result = self.cli('--all', '--gps-kataster-best-measurements', str(fake))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('SHA-256', result.stderr)
        self.assertFalse(self.output.exists())

    def test_output_cannot_overlap_sources_even_through_symlink(self):
        for destination in (self.data_dir, self.cave_dir / 'result', self.root / 'alias'):
            if destination.name == 'alias':
                destination.symlink_to(self.cave_dir, target_is_directory=True)
            self.output = destination
            before = hashes(self.data_dir)
            result = self.cli('--all')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('wynik', result.stderr)
            self.assertEqual(before, hashes(self.data_dir))

    def test_changed_mode_builds_complete_manifest_in_t10(self):
        result = self.cli('--changed')
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((self.output / 'current/manifest.json').read_text())
        self.assertEqual([p['dir_id'] for p in manifest['plans']], ['001131'])

    def test_rejects_input_symlink_chain_through_current_to_external_file(self):
        for external_current in (True, False):
            with self.subTest(external_current=external_current):
                self.output = self.root / ('results-' + str(external_current))
                archive = self.root / ('archive-' + str(external_current)) / '001131'
                archive.mkdir(parents=True)
                shutil.copy2(self.meta_path, archive / 'meta.yaml')
                old = self.output / 'runs/old/001131'
                old.mkdir(parents=True)
                (old / 'meta.yaml').symlink_to(archive / 'meta.yaml')
                previous = archive.parent if external_current else old.parent
                (self.output / 'current').symlink_to(previous, target_is_directory=True)
                original = self.meta_path.read_bytes()
                self.meta_path.unlink()
                self.meta_path.symlink_to(self.output / 'current/001131/meta.yaml')
                try:
                    result = self.cli('--all')
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertEqual((self.output / 'current').resolve(), previous)
                    self.assertEqual(self.meta_path.read_bytes(), original)
                finally:
                    self.meta_path.unlink()
                    self.meta_path.write_bytes(original)

    def test_rejects_input_file_symlink_into_output_before_pointer_changes(self):
        old = self.output / 'runs/old/001131'
        old.mkdir(parents=True)
        shutil.copy2(self.meta_path, old / 'meta.yaml')
        (self.output / 'current').symlink_to('runs/old', target_is_directory=True)
        self.meta_path.unlink()
        self.meta_path.symlink_to(self.output / 'current/001131/meta.yaml')
        before = hashes(self.data_dir)
        result = self.cli('--all')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.output / 'current').resolve(), old.parent)
        self.assertTrue(self.meta_path.is_file())
        self.assertEqual(hashes(self.data_dir), before)

    def test_absent_optional_input_symlink_through_future_current_never_publishes(self):
        for name in ('image-identity.json', 'image_future.jpg', 'future-plan'):
            with self.subTest(name=name):
                self.output = self.root / ('results-' + name)
                link = (self.data_dir if name == 'future-plan' else self.cave_dir) / name
                target = self.output / 'current/001131'
                link.symlink_to(target if name == 'future-plan' else target / 'computed.json')
                self.assertFalse(link.exists())
                try:
                    with self.assertRaisesRegex(ValueError, 'ścieżce wejścia'):
                        self.api()
                    self.assertFalse((self.output / 'current').exists())
                    self.assertFalse(link.exists())
                    self.assertTrue(link.is_symlink())
                finally:
                    link.unlink()

    def test_gdal_failure_and_false_success_never_publish_or_replace_complete_run(self):
        first = self.run_ok()
        complete = hashes(first)
        sources = hashes(self.data_dir)
        import geotiff_output
        for exit_code in (7, 0):
            with self.subTest(exit_code=exit_code):
                real_run = subprocess.run

                def broken(cmd, **kwargs):
                    if cmd[0] == 'gdal_translate':
                        Path(cmd[-1]).write_bytes(b'partial TIFF')
                        return subprocess.CompletedProcess(cmd, exit_code, '', 'awaria GDAL')
                    return real_run(cmd, **kwargs)

                with patch.object(geotiff_output.subprocess, 'run', side_effect=broken):
                    with self.assertRaises((ValueError, OSError)):
                        self.api()
                self.assertEqual((self.output / 'current').resolve(), first)
                self.assertEqual(hashes(first), complete)
                self.assertEqual(hashes(self.data_dir), sources)
                self.assertFalse(list(self.output.glob('.staging-*')))
        # Także pierwsza nieudana próba nie tworzy current.
        self.output = self.root / 'new-output'
        with patch.object(geotiff_output.subprocess, 'run', side_effect=broken):
            with self.assertRaises((ValueError, OSError)):
                self.api()
        self.assertFalse((self.output / 'current').exists())

    def test_readback_rejects_wrong_crs_transform_dimensions_and_pixels(self):
        first = self.run_ok()
        import geotiff_output
        original = first / '001131/image_georef.tif'
        expected = self.info(original)['geoTransform']
        for options, diagnostic in [(['-a_srs', 'EPSG:4326'], 'CRS'),
                                    (['-a_gt', '0', '1', '0', '0', '0', '-1'], 'transform'),
                                    (['-a_gt', '5', '1', '2', '6', '2', '4'], 'transform'),
                                    (['-outsize', '4', '3', '-a_gt', *map(str, expected)], 'wymiar')]:
            with self.subTest(options=options):
                bad = self.root / 'bad.tif'
                subprocess.run(['gdal_translate', '-co', 'COMPRESS=CCITTFAX4', *options, str(original), str(bad)],
                               check=True, capture_output=True)
                with self.assertRaisesRegex(ValueError, diagnostic):
                    geotiff_output.check_geotiff(self.image_path, bad, expected)
        other = self.root / 'other.tif'
        Image.new('1', (8, 6), 255).save(other)
        with self.assertRaisesRegex(ValueError, 'piksel'):
            geotiff_output.check_geotiff(other, original, expected)

    def test_readback_error_and_late_plan_failure_keep_whole_previous_batch(self):
        first = self.run_ok()
        before = hashes(first)
        sources = hashes(self.data_dir)
        import geotiff_output
        real_check = geotiff_output.check_geotiff

        def fail_read(*args):
            real_check(*args)
            raise ValueError('kontrolny odczyt zawiódł')

        with patch.object(geotiff_output, 'check_geotiff', side_effect=fail_read):
            with self.assertRaisesRegex(ValueError, 'odczyt'):
                self.api()
        self.assertEqual(hashes(self.data_dir), sources)
        second = self.data_dir / '001132'
        shutil.copytree(self.cave_dir, second)
        meta = (second / 'meta.yaml').read_text().replace("dir_id: '001131'", "dir_id: '001132'")
        from orientation_fixture import attach_orientation
        (second / 'meta.yaml').write_text(yaml.safe_dump(attach_orientation(yaml.safe_load(meta))))
        registry = json.loads(self.registry_path.read_text())
        registry['plans']['001132'] = registry['plans']['001131']
        self.registry_path.write_text(json.dumps(registry))
        sources = hashes(self.data_dir)

        def fail_late(source, output, expected):
            result = real_check(source, output, expected)
            if source.parent.name == '001132':
                raise ValueError('późniejszy plan')
            return result

        with patch.object(geotiff_output, 'check_geotiff', side_effect=fail_late):
            with self.assertRaisesRegex(ValueError, 'późniejszy'):
                self.api()
        self.assertEqual((self.output / 'current').resolve(), first)
        self.assertEqual(hashes(first), before)
        self.assertEqual(hashes(self.data_dir), sources)
        self.assertFalse(list(self.output.glob('.staging-*')))

    def test_csv_cannot_change_between_pin_verification_and_snapshot(self):
        # Stabilna reprodukcja zmiany pliku między verify() i jego użyciem.
        csv = self.root / 'coordinates.csv'
        csv.write_bytes(self.coordinates_path.read_bytes())
        self.coordinates_path = csv
        real_verify = generator.verify

        def change_after_verify(*args, **kwargs):
            result = real_verify(*args, **kwargs)
            csv.write_bytes(csv.read_bytes().replace(b'49.', b'48.'))
            return result

        with patch.object(generator, 'verify', side_effect=change_after_verify):
            with self.assertRaisesRegex(ValueError, 'SHA-256|zmieni'):
                self.api()
        self.assertFalse((self.output / 'current').exists())

    def test_yaml_hash_and_calculation_use_same_snapshot_during_aba_edit(self):
        original = self.meta_path.read_text()
        real_prepare = generator.prepare_cave

        def edit_during_prepare(*args, **kwargs):
            self.meta_path.write_text(original.replace('angle_deg: 0.0', 'angle_deg: 15.0'))
            try:
                return real_prepare(*args, **kwargs)
            finally:
                self.meta_path.write_text(original)

        with patch.object(generator, 'prepare_cave', side_effect=edit_during_prepare):
            result = self.api()
        manifest = json.loads((result / 'manifest.json').read_text())
        self.assertLess(abs(manifest['plans'][0]['parameters']['total_rotation_deg']), 1)
        self.assertEqual(manifest['plans'][0]['inputs']['meta.yaml'],
                         hashlib.sha256(original.encode()).hexdigest())

    def test_source_change_during_generation_prevents_publication(self):
        first = self.run_ok()
        import geotiff_output
        real_check = geotiff_output.check_geotiff

        def change_source(*args):
            result = real_check(*args)
            self.meta_path.write_text(self.meta_path.read_text() + '# zmiana użytkownika\n')
            return result

        with patch.object(geotiff_output, 'check_geotiff', side_effect=change_source):
            with self.assertRaisesRegex(ValueError, 'zmieniły'):
                self.api()
        self.assertEqual((self.output / 'current').resolve(), first)

    def test_readback_rejects_nonfinite_transform_and_malformed_metadata(self):
        first = self.run_ok()
        import geotiff_output
        original = first / '001131/image_georef.tif'
        info = self.info(original)
        expected = info['geoTransform'][:]
        for payload in ('{bad json', '{}', json.dumps({**info, 'geoTransform': [float('nan')] * 6})):
            with self.subTest(payload=payload[:40]):
                response = subprocess.CompletedProcess([], 0, payload, '')
                with patch.object(geotiff_output.subprocess, 'run', return_value=response):
                    with self.assertRaises(ValueError):
                        geotiff_output.check_geotiff(self.image_path, original, expected)

    def test_orientation_archive_uses_hashed_snapshot_during_aba_edit(self):
        archive = self.root / 'history.zip'
        original = generator.orientation.ARCHIVE.read_bytes()
        archive.write_bytes(original)
        real_load = generator.orientation.load_context

        def aba(*args, **kwargs):
            archive.write_bytes(b'changed archive during load')
            try:
                return real_load(*args, **kwargs)
            finally:
                archive.write_bytes(original)

        with patch.object(generator.orientation, 'ARCHIVE', archive), patch.object(generator.orientation, 'load_context', side_effect=aba):
            run = self.api()
        manifest = json.loads((run / 'manifest.json').read_text())
        self.assertEqual(manifest['orientation_sources']['history.zip'], hashlib.sha256(original).hexdigest())
        self.assertEqual(manifest['plans'][0]['orientation']['status'], 'unverified')

    def test_incomplete_reference_aborts_preflight_and_keeps_current(self):
        from orientation import record_decision
        first = self.run_ok()
        before = hashes(first)
        meta = yaml.safe_load(self.meta_path.read_text())
        meta['north'].update(reference='geographic', evidence='Jawne źródło z legendy planu')
        meta = record_decision(meta, 'Ustalono rodzaj w próbie preflight.', '2026-10-25')
        del meta['north']['evidence']
        self.meta_path.write_text(yaml.safe_dump(meta))
        sources = hashes(self.data_dir)
        for output in (True, False):
            with self.subTest(output=output):
                result = self.cli('--all', output=output)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('north.evidence', result.stderr)
                self.assertEqual((self.output / 'current').resolve(), first)
                self.assertEqual(before, hashes(first))
                self.assertEqual(sources, hashes(self.data_dir))
        self.assertFalse(list(self.output.glob('.staging-*')))

    def test_default_output_preserves_source_precision_and_orientation_decision(self):
        from orientation import inputs_hash, record_decision
        meta = yaml.safe_load(self.meta_path.read_text())
        meta['north']['angle_deg'] = 0.123456789012345
        meta['declination_deg'] = -0.123456789012345
        meta = record_decision(meta, 'Precyzyjna jawna korekta opisu; zachowujemy TFW.', '2026-10-25')
        self.meta_path.write_text(yaml.safe_dump(meta))
        accepted = inputs_hash(meta)
        first = self.cli('--all', output=False)
        self.assertEqual(first.returncode, 0, first.stderr)
        saved = yaml.safe_load(self.meta_path.read_text())
        self.assertEqual(saved['north']['angle_deg'], 0.123456789012345)
        self.assertEqual(saved['declination_deg'], -0.123456789012345)
        self.assertEqual(inputs_hash(saved), accepted)
        second = self.cli('--all', output=False)
        self.assertEqual(second.returncode, 0, second.stderr)

    def test_publication_failure_preserves_previous_pointer(self):
        first = self.run_ok()
        before = hashes(first)
        import geotiff_output
        real_replace = os.replace

        def fail_pointer(src, dst):
            if Path(dst).name == 'current':
                raise OSError('awaria publikacji')
            return real_replace(src, dst)

        with patch.object(geotiff_output.os, 'replace', side_effect=fail_pointer):
            with self.assertRaisesRegex(OSError, 'publikacji'):
                self.api()
        self.assertEqual((self.output / 'current').resolve(), first)
        self.assertEqual(hashes(first), before)
        self.assertFalse(list(self.output.glob('.staging-*')))


if __name__ == '__main__':
    unittest.main()
