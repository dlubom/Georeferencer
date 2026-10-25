"""T11: odbiór realnych paczek, bez zaufania do ich deklaracji QA."""
import copy
import hashlib
import json
import unittest
import warnings
import zipfile
from unittest.mock import patch

from test_qa import _QaFixture
import test_qa as qa_fixture
import shutil
import subprocess
import os
from pathlib import Path


class AcceptanceTest(_QaFixture):
    def setUp(self):
        super().setUp()
        import package_release
        self.package = package_release.package_run
        self.output = self.data.parent / (self.data.name + '-results')
        self.addCleanup(lambda: shutil.rmtree(self.output, ignore_errors=True))
        self.run = qa_fixture.generator.process_output([self.cave_dir], self.output, self.data,
                                                       self.coordinates_path, self.registry_path)
        self.archive = self.output / 'package.zip'
        self.reports = self.output / 'qa'
        self.options = {'registry_path': self.registry_path, 'aggregates': {}, 'observations': [],
                        'exceptions': {'schema_version': 1, 'exceptions': [self.exception(self.report(), 'orientation.unknown')]}}

    def pack(self, **kwargs):
        return self.package(self.data, self.output / 'current', self.archive, self.reports,
                            qa_kwargs=self.options, **kwargs)

    def verify(self):
        import release_acceptance
        return release_acceptance.verify_archive(self.archive, self.data, qa_kwargs=self.options)

    def rewrite(self, mutate):
        with zipfile.ZipFile(self.archive) as archive:
            entries = [(i.filename, archive.read(i)) for i in archive.infolist()]
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(self.archive, 'w') as archive:
                for name, raw in mutate(entries):
                    archive.writestr(name, raw)

    def test_release_manifest_carries_exact_enforced_exceptions_and_run_binding(self):
        self.pack(mode='manual')
        with zipfile.ZipFile(self.archive) as archive:
            manifest = json.loads(archive.read('manifest.json'))
        self.assertIn('release', manifest, 'Brak jawnych dowodów QA w manifeście wydania')
        release = manifest['release']
        self.assertEqual(release['qa']['accepted_exceptions'], self.options['exceptions']['exceptions'])
        self.assertEqual(release['run_manifest_sha256'], hashlib.sha256((self.run / 'manifest.json').read_bytes()).hexdigest())
        self.assertEqual(release['run_id'], manifest['run_id'])
        self.assertTrue(self.verify()['passed'])

    def test_archive_reader_rejects_missing_extra_duplicate_and_corrupt_members(self):
        self.assertIsNotNone(__import__('importlib').util.find_spec('release_acceptance'), 'Brak niezależnego odbioru ZIP')
        for fault in ('missing', 'extra', 'duplicate', 'corrupt'):
            with self.subTest(fault=fault):
                self.pack()
                def mutate(entries):
                    if fault == 'missing':
                        return entries[:-1]
                    if fault == 'extra':
                        return entries + [('extra.tif', b'extra')]
                    if fault == 'duplicate':
                        return entries + [entries[-1]]
                    return [(n, b'broken' if n.endswith('.tif') else r) for n, r in entries]
                self.rewrite(mutate)
                with self.assertRaises(ValueError):
                    self.verify()

    def test_manifest_cannot_authorize_a_new_or_stale_exception(self):
        self.assertIsNotNone(__import__('importlib').util.find_spec('release_acceptance'), 'Brak niezależnego odbioru ZIP')
        self.pack()
        for fault in ('stale', 'new'):
            with self.subTest(fault=fault):
                changed = copy.deepcopy(self.options)
                if fault == 'stale':
                    changed['exceptions']['exceptions'][0]['basis_sha256'] = 'stale'
                else:
                    changed['exceptions']['exceptions'] = []
                import release_acceptance
                with self.assertRaises(ValueError):
                    release_acceptance.verify_archive(self.archive, self.data, qa_kwargs=changed)

    def test_failed_archive_readback_preserves_previous_package_and_current(self):
        self.assertIsNotNone(__import__('importlib').util.find_spec('release_acceptance'), 'Brak niezależnego odbioru ZIP')
        import release_acceptance
        self.archive.write_bytes(b'previous package')
        current = (self.output / 'current').readlink()
        with patch.object(release_acceptance, 'verify_archive', side_effect=ValueError('controlled ZIP fault')):
            with self.assertRaises(ValueError):
                self.pack()
        self.assertEqual(self.archive.read_bytes(), b'previous package')
        self.assertEqual((self.output / 'current').readlink(), current)

    def test_actual_geotiff_rejects_forged_hashes_for_geometry_crs_compression_and_pixels(self):
        manifest_path = self.run / 'manifest.json'
        tif = self.run / '001131/image_georef.tif'
        original, raw = manifest_path.read_bytes(), tif.read_bytes()
        for mode in ('tag', 'manual'):
            for fault in ('geometry', 'crs', 'compression', 'pixels'):
                with self.subTest(mode=mode, fault=fault):
                    source = self.run.parent / 'fault-source.tif'
                    source.write_bytes(raw)
                    if fault == 'pixels':
                        from PIL import Image
                        with Image.open(self.cave_dir / 'image.tif') as image:
                            image.putpixel((0, 0), 255 - image.getpixel((0, 0)))
                            image.save(source)
                    from geotiff_output import tfw_geotransform
                    transform = tfw_geotransform(self.run / '001131/image.tfw')
                    if fault == 'geometry':
                        transform[0] += 1
                    subprocess.run(['gdal_translate', '-q', '-of', 'GTiff', '-a_srs',
                        'EPSG:4326' if fault == 'crs' else 'EPSG:2180',
                        '-a_gt', *map(str, transform), '-co',
                        'COMPRESS=LZW' if fault == 'compression' else 'COMPRESS=CCITTFAX4',
                        str(source), str(tif)], check=True, capture_output=True)
                    manifest = json.loads(original)
                    manifest['plans'][0]['outputs']['image_georef.tif'] = hashlib.sha256(tif.read_bytes()).hexdigest()
                    manifest_path.write_text(json.dumps(manifest))
                    self.archive.write_bytes(b'previous package')
                    current = (self.output / 'current').readlink()
                    with self.assertRaises(ValueError):
                        self.pack(mode=mode)
                    self.assertEqual(self.archive.read_bytes(), b'previous package')
                    self.assertEqual((self.output / 'current').readlink(), current)
                    tif.write_bytes(raw)
                    manifest_path.write_bytes(original)

    def test_two_independent_runs_compare_decoded_results_and_detect_stale_output(self):
        import release_acceptance
        second = self.output.parent / (self.output.name + '-second')
        self.addCleanup(lambda: shutil.rmtree(second, ignore_errors=True))
        other = qa_fixture.generator.process_output([self.cave_dir], second, self.data,
                                                    self.coordinates_path, self.registry_path)
        result = release_acceptance.compare_runs(self.run, other, self.data, qa_kwargs=self.options)
        self.assertEqual(result['plans'], 1)
        self.assertEqual([b['reused'] for b in result['builds']], [0, 0])
        (other / '001131/image.tfw').write_text('0\n' * 6)
        with self.assertRaises(ValueError):
            release_acceptance.compare_runs(self.run, other, self.data, qa_kwargs=self.options)

    def test_production_package_requires_current_checkout_clean_as_well_as_build(self):
        with patch.dict(os.environ, {'GEOREFERENCER_COMMIT': 'a' * 40, 'GEOREFERENCER_DIRTY': 'false'}):
            self.run = qa_fixture.generator.process_output([self.cave_dir], self.output, self.data,
                                                          self.coordinates_path, self.registry_path)
        for mode in ('tag', 'manual'):
            with self.subTest(mode=mode), patch.dict(os.environ,
                    {'GEOREFERENCER_COMMIT': 'b' * 40, 'GEOREFERENCER_DIRTY': 'true'}):
                with self.assertRaises(ValueError):
                    self.pack(mode=mode, require_clean_code=True)
        with patch.dict(os.environ, {'GEOREFERENCER_COMMIT': 'b' * 40, 'GEOREFERENCER_DIRTY': 'false'}):
            # Nowy commit dokumentacji nie zmienia aktualności treści wyników.
            self.pack(require_clean_code=True)
            with zipfile.ZipFile(self.archive) as archive:
                self.assertEqual(json.loads(archive.read('manifest.json'))['release']['code'],
                                 {'commit': 'b' * 40, 'dirty': 'false'})

    def test_empty_zip_plan_id_cannot_write_outside_private_directory(self):
        self.pack()
        def mutate(entries):
            manifest = json.loads(dict(entries)['manifest.json'])
            release = manifest.pop('release')
            manifest['plans'][0]['dir_id'] = ''
            canonical = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode()
            release['run_manifest_sha256'] = hashlib.sha256(canonical).hexdigest()
            manifest['release'] = release
            return [(n.replace('001131/', '/'), r) if n != 'manifest.json' else
                    (n, json.dumps(manifest).encode()) for n, r in entries]
        self.rewrite(mutate)
        original_write = Path.write_bytes
        def guarded_write(path, raw):
            self.assertNotEqual(path.parent, Path('/'), 'ZIP próbuje zapisu poza katalogiem prywatnym')
            return original_write(path, raw)
        with patch.object(Path, 'write_bytes', guarded_write), self.assertRaises(ValueError):
            self.verify()


if __name__ == '__main__':
    unittest.main()
