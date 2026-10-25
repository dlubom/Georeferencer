"""T10: cache dopiero po preflight, kopia do pełnego atomowego przebiegu."""
import copy
import importlib.util
import json
import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml
import test_geotiff_output as output_fixture
generator, hashes = output_fixture.generator, output_fixture.hashes


class IncrementalTest(unittest.TestCase):
    setUp = output_fixture.OutputTest.setUp
    cli = output_fixture.OutputTest.cli
    run_ok = output_fixture.OutputTest.run_ok

    def api(self, **kwargs):
        return generator.process_output(generator.find_caves(self.data_dir), self.output,
            self.data_dir, self.coordinates_path, self.registry_path, **kwargs)

    def manifest(self, run):
        return json.loads((run / 'manifest.json').read_text())

    def test_second_run_uses_complete_results_without_translation(self):
        first = self.api()
        before = hashes(first)
        with patch('geotiff_output.translate_geotiff', side_effect=AssertionError('niepotrzebna generacja')):
            second = self.api()
        self.assertNotEqual(first, second)
        self.assertEqual(hashes(first), before)
        self.assertEqual(self.manifest(second)['build']['reused'], ['001131'])
        self.assertEqual(self.manifest(second)['build']['generated'], [])
        for name in ('image.tfw', 'image_georef.tif', 'computed.json'):
            self.assertEqual((first / '001131' / name).read_bytes(), (second / '001131' / name).read_bytes())

    def test_content_change_with_old_mtime_and_force_regenerate(self):
        self.api()
        self.meta_path.write_text(self.meta_path.read_text() + '# zmiana treści\n')
        os.utime(self.meta_path, (1, 1))
        changed = self.api()
        self.assertEqual(self.manifest(changed)['build']['generated'], ['001131'])
        forced = self.api(force=True)
        self.assertEqual(self.manifest(forced)['build']['generated'], ['001131'])

    def test_missing_corrupt_extra_and_old_cache_are_repaired(self):
        for fault in ('missing', 'corrupt', 'extra', 'old', 'duplicate', 'environment'):
            with self.subTest(fault=fault):
                run = self.api()
                if fault == 'missing':
                    (run / '001131/computed.json').unlink()
                elif fault == 'corrupt':
                    (run / '001131/image_georef.tif').write_bytes(b'broken TIFF')
                elif fault == 'extra':
                    (run / '001131/extra').write_text('unexpected')
                else:
                    manifest = self.manifest(run)
                    if fault == 'old':
                        manifest['plans'][0].pop('fingerprint', None)
                    elif fault == 'duplicate':
                        manifest['plans'].append(copy.deepcopy(manifest['plans'][0]))
                    else:
                        manifest['environment'] = {'Python': 'different'}
                    (run / 'manifest.json').write_text(json.dumps(manifest))
                repaired = self.api()
                self.assertEqual(self.manifest(repaired)['build']['generated'], ['001131'])
                self.assertEqual(set(p.name for p in (repaired / '001131').iterdir()),
                                 {'image.tfw', 'image_georef.tif', 'computed.json'})

    def test_cached_result_never_bypasses_validation(self):
        first = self.api()
        self.meta_path.write_text(self.meta_path.read_text().replace('pixels_per_meter: 2.0', 'pixels_per_meter: 0.0'))
        with self.assertRaisesRegex(ValueError, 'scale.pixels_per_meter'):
            self.api()
        self.assertEqual((self.output / 'current').resolve(), first)

    def test_common_code_dependencies_pin_registry_and_environment_invalidate(self):
        self.assertIsNotNone(importlib.util.find_spec('build_identity'), 'Brak tożsamości obliczeń i środowiska T10')
        import build_identity
        first = self.api()
        original = build_identity.implementation
        def changed_implementation():
            return {**original(), 'ci/requirements.lock': 'changed'}
        with patch.object(build_identity, 'implementation', side_effect=changed_implementation):
            changed = self.api()
        self.assertEqual(self.manifest(changed)['build']['generated'], ['001131'])
        real_environment = build_identity.environment
        with patch.object(build_identity, 'environment', side_effect=lambda: {**real_environment(), 'Python': 'changed'}):
            changed = self.api()
        self.assertEqual(self.manifest(changed)['build']['generated'], ['001131'])
        self.registry_path.write_text(self.registry_path.read_text() + '\n')
        changed = self.api()
        self.assertEqual(self.manifest(changed)['build']['generated'], ['001131'])

    def test_incremental_full_catalogue_addition_removal_and_last_plan_removal(self):
        first = self.api()
        second = self.data_dir / '001132'
        shutil.copytree(self.cave_dir, second)
        meta = yaml.safe_load((second / 'meta.yaml').read_text())
        meta['cave']['dir_id'] = '001132'
        from orientation_fixture import attach_orientation
        (second / 'meta.yaml').write_text(yaml.safe_dump(attach_orientation(meta)))
        registry = json.loads(self.registry_path.read_text())
        registry['plans']['001132'] = registry['plans']['001131']
        self.registry_path.write_text(json.dumps(registry))
        added = self.api()
        self.assertEqual({p['dir_id'] for p in self.manifest(added)['plans']}, {'001131', '001132'})
        shutil.rmtree(second)
        removed = self.api()
        self.assertEqual({p.name for p in removed.iterdir()}, {'manifest.json', '001131'})
        self.assertEqual(self.manifest(removed)['build']['reused'], ['001131'])
        shutil.rmtree(self.cave_dir)
        empty = self.api()
        self.assertEqual(self.manifest(empty)['plans'], [])
        self.assertEqual({p.name for p in empty.iterdir()}, {'manifest.json'})

    def test_cache_copy_readback_failure_preserves_previous_current(self):
        first = self.api()
        import geotiff_output
        real = geotiff_output.check_geotiff
        def fail_staging(source, output, transform):
            if '.staging-' in str(output):
                raise ValueError('odbiór kopii')
            return real(source, output, transform)
        with patch.object(geotiff_output, 'check_geotiff', side_effect=fail_staging):
            with self.assertRaisesRegex(ValueError, 'odbiór kopii'):
                self.api()
        self.assertEqual((self.output / 'current').resolve(), first)

    def test_default_and_changed_cli_do_not_write_source_outputs(self):
        import subprocess
        import sys
        before = hashes(self.data_dir)
        result = subprocess.run([sys.executable, generator.__file__, '--changed',
            '--data-dir', str(self.data_dir), '--image-registry', str(self.registry_path)],
            cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, hashes(self.data_dir))

    def test_new_catalogue_directory_during_build_keeps_previous_current(self):
        first = self.api()
        import geotiff_output
        real = geotiff_output.translate_geotiff
        def add_directory(*args):
            real(*args)
            (self.data_dir / 'new-plan').mkdir()
        with patch.object(geotiff_output, 'translate_geotiff', side_effect=add_directory):
            with self.assertRaisesRegex(ValueError, 'katalog'):
                self.api(force=True)
        self.assertEqual((self.output / 'current').resolve(), first)

    def test_malformed_common_cache_metadata_is_repaired(self):
        run = self.api()
        manifest = self.manifest(run)
        manifest['image_registry'] = []
        (run / 'manifest.json').write_text(json.dumps(manifest))
        repaired = self.api()
        self.assertEqual(self.manifest(repaired)['build']['generated'], ['001131'])

    def test_known_git_range_does_not_override_content_cache_on_retry(self):
        for full, plans in ((True, []), (False, ['001131'])):
            with self.subTest(full=full):
                selection = self.root / 'selection.json'
                selection.write_text(json.dumps({'schema_version': 1, 'full': full,
                    'uncertain': False, 'plans': plans, 'reason': 'pełny znany zakres'}))
                self.run_ok('--changed', '--selection-file', str(selection))
                run = self.run_ok('--changed', '--selection-file', str(selection))
                self.assertEqual(self.manifest(run)['build']['generated'], [])
                self.assertEqual(self.manifest(run)['build']['reused'], ['001131'])

    def test_uncertain_git_range_still_forces_full_recalculation(self):
        self.api()
        selection = self.root / 'selection.json'
        selection.write_text(json.dumps({'schema_version': 1, 'full': True,
            'uncertain': True, 'plans': [], 'reason': 'brak bazy'}))
        run = self.run_ok('--changed', '--selection-file', str(selection))
        self.assertEqual(self.manifest(run)['build']['generated'], ['001131'])


if __name__ == '__main__':
    unittest.main()
