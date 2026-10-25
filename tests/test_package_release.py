"""Ta sama bramka T09 dla tagu i ręcznego wydania; bez publikacji."""
import copy
import importlib.util
import json
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import test_qa as qa_fixture


class PackageTest(qa_fixture._QaFixture):
    def setUp(self):
        super().setUp()
        self.assertIsNotNone(importlib.util.find_spec('package_release'), 'Brak wspólnej bramki publikacji T10')
        import package_release
        self.package = package_release.package_run
        self.output = self.data.parent / (self.data.name + '-results')
        self.addCleanup(lambda: __import__('shutil').rmtree(self.output, ignore_errors=True))
        self.run = qa_fixture.generator.process_output([self.cave_dir], self.output, self.data,
                                                       self.coordinates_path, self.registry_path)
        self.archive = self.output / 'package.zip'
        self.reports = self.output / 'qa'
        self.options = {'registry_path': self.registry_path, 'aggregates': {}, 'observations': [],
                        'exceptions': {'schema_version': 1, 'exceptions': [self.exception(self.report(), 'orientation.unknown')]}}

    def pack(self, **kwargs):
        return self.package(self.data, self.output / 'current', self.archive, self.reports,
                            qa_kwargs=self.options, **kwargs)

    def test_complete_package_has_exact_manifest_inventory_and_external_qa(self):
        self.pack()
        with zipfile.ZipFile(self.archive) as package:
            self.assertEqual(set(package.namelist()), {'manifest.json', '001131/image.tfw',
                '001131/image_georef.tif', '001131/computed.json'})
            self.assertEqual(len(package.namelist()), 4)
        report = json.loads((self.reports / 'qa.json').read_text())
        self.assertTrue(report['passed'])
        self.assertEqual(report['plans'][0]['output_status'], 'current')
        self.assertEqual({p.name for p in self.run.iterdir()}, {'manifest.json', '001131'})

    def test_missing_extra_duplicate_stale_corrupt_and_bad_manifest_block_both_modes(self):
        manifest_path = self.run / 'manifest.json'
        original = manifest_path.read_bytes()
        tif = self.run / '001131/image_georef.tif'
        original_tif = tif.read_bytes()
        for mode in ('tag', 'manual'):
            for fault in ('missing', 'extra', 'duplicate', 'stale', 'corrupt', 'manifest', 'duplicate_key'):
                with self.subTest(mode=mode, fault=fault):
                    if fault == 'missing':
                        tif.unlink()
                    elif fault == 'extra':
                        (self.run / 'extra.tif').write_bytes(original_tif)
                    elif fault == 'corrupt':
                        tif.write_bytes(b'broken')
                    elif fault == 'manifest':
                        manifest_path.write_text('[]')
                    elif fault == 'duplicate_key':
                        manifest_path.write_text(original.decode().replace('"schema_version": 1', '"schema_version": 1, "schema_version": 1'))
                    else:
                        manifest = json.loads(original)
                        if fault == 'duplicate':
                            manifest['plans'].append(copy.deepcopy(manifest['plans'][0]))
                        else:
                            manifest['environment']['Python'] = 'stale'
                        manifest_path.write_text(json.dumps(manifest))
                    self.archive.write_bytes(b'previous correct package')
                    with self.assertRaises(ValueError):
                        self.pack(mode=mode)
                    self.assertEqual(self.archive.read_bytes(), b'previous correct package')
                    manifest_path.write_bytes(original)
                    tif.write_bytes(original_tif)
                    (self.run / 'extra.tif').unlink(missing_ok=True)

    def test_qa_new_problem_stale_exception_and_technical_exception_block(self):
        original = copy.deepcopy(self.options['exceptions'])
        for mode in ('tag', 'manual'):
            for fault in ('stale', 'new', 'technical'):
                with self.subTest(mode=mode, fault=fault):
                    self.options['exceptions'] = copy.deepcopy(original)
                    if fault == 'stale':
                        self.options['exceptions']['exceptions'][0]['basis_sha256'] = 'old basis'
                    elif fault == 'new':
                        self.options['exceptions']['exceptions'] = []
                    else:
                        self.options['exceptions']['exceptions'][0]['rule'] = 'result.corrupt'
                    with self.assertRaises(ValueError):
                        self.pack(mode=mode)
                    self.assertFalse(self.archive.exists())

    def test_current_is_resolved_once_and_reports_must_stay_outside_run(self):
        import package_release
        original = package_release.create_report
        def move_current(*args, **kwargs):
            self.assertEqual(kwargs['run_dir'], self.run)
            (self.output / 'current').unlink()
            (self.output / 'current').symlink_to('missing-run')
            return original(*args, **kwargs)
        with patch.object(package_release, 'create_report', side_effect=move_current):
            self.pack()
        self.assertTrue(self.archive.is_file())
        with self.assertRaises(ValueError):
            self.package(self.data, self.run, self.archive, self.run / 'qa', qa_kwargs=self.options)

    def test_package_and_reports_cannot_overwrite_common_input_registry(self):
        registry = self.output / 'protected-inputs/registry.json'
        registry.parent.mkdir()
        original = self.registry_path.read_bytes()
        registry.write_bytes(original)
        self.options['registry_path'] = registry
        with self.assertRaises(ValueError):
            self.package(self.data, self.run, registry, self.reports, qa_kwargs=self.options)
        self.assertEqual(registry.read_bytes(), original)
        with self.assertRaises(ValueError):
            self.package(self.data, self.run, self.archive, registry.parent, qa_kwargs=self.options)
        self.assertFalse((registry.parent / 'qa.json').exists())


if __name__ == '__main__':
    unittest.main()
