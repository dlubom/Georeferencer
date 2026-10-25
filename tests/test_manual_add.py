"""T08: tylko dane syntetyczne; pełne CLI, rzeczywisty GDAL i brak nadpisywania."""
import copy
import contextlib
import io
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pipeline'))
from validation import validate_plan, read_registry
from gps_kataster_coordinates import load_best_measurements
from orientation import record_decision, rotation, validate_orientation

spec = importlib.util.spec_from_file_location('manual_add', ROOT / 'pipeline/05_add_cave.py')
adder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adder)
spec = importlib.util.spec_from_file_location('manual_generator', ROOT / 'pipeline/02_generate_geotiff.py')
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


class ManualAddTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.scraper = self.root / 'scraper'
        self.data = self.root / 'caves'
        self.data.mkdir()
        self.jsonl = self.root / 'pig.jsonl'
        self.cave = {'cave_id': 'test-cave', 'name': 'Jaskinia testowa',
                     'inventory_number': 'T.TEST', 'images': []}
        for image_id in (101, 102):
            name = f'image_{image_id}_zoom_10'
            self.cave['images'].append({'metadata': {'graphics_id': image_id,
                'graphics_type_name': 'plan', 'inventory_number': 'T.TEST',
                'maxWidth': 4, 'maxHeight': 3},
                'image_path': f'caves/test-cave/{name}.jpg'})
            path = self.scraper / 'caves_mono/test-cave' / (name + '.tif')
            path.parent.mkdir(parents=True, exist_ok=True)
            image = Image.new('1', (8, 6))
            image.putpixel((image_id - 101, 1), 255)
            image.save(path)
        self.save_cave()
        self.index = load_best_measurements(ROOT / 'data/coordinate-source/best-measurements-v1.3.1.csv')

    def save_cave(self):
        self.jsonl.write_text(json.dumps(self.cave) + '\n')

    def source(self, image_id=102):
        return self.scraper / f'caves_mono/test-cave/image_{image_id}_zoom_10.tif'

    def argv(self, image_id=102, reference='grid', plan_id='test-plan-2'):
        args = ['--cave', 'test-cave', '--plan-id', plan_id, '--image-id', str(image_id),
                '--scraper-dir', str(self.scraper), '--jsonl', str(self.jsonl),
                '--data-dir', str(self.data), '--image-sha256', hashlib.sha256(self.source(image_id).read_bytes()).hexdigest(),
                '--gps-kataster-object-id', 'KSZ-0033', '--entrance-x', '2.25', '--entrance-y', '3.5',
                '--pixels-per-meter', '2', '--entrance-source', 'Klik w symbol otworu na obrazie mono',
                '--scale-source', 'Odcinek podziałki 10 m na obrazie mono',
                '--north-reference', reference, '--decision-date', '2026-10-25',
                '--decision-reason', 'Próba syntetyczna, dopuszczona orientacja do odbioru']
        if reference == 'unknown':
            args += ['--north-skipped', '--assumed-grid-angle', '17.25',
                     '--grid-angle-convention', 'image_x_ccw_from_grid_east']
        else:
            args += ['--north-angle', '0', '--north-source', 'Legenda syntetycznego planu i pomiar strzałki']
        if reference == 'magnetic':
            args += ['--declination', '-4.5', '--declination-basis', 'Dane syntetyczne epoki planu',
                     '--declination-epoch', '2001', '--declination-sign-convention', 'east_positive']
        return args

    def cli(self, args):
        return subprocess.run([sys.executable, str(ROOT / 'pipeline/05_add_cave.py'), *args],
                              capture_output=True, text=True, timeout=40)

    def add(self, **kwargs):
        result = self.cli(self.argv(**kwargs))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return self.data / kwargs.get('plan_id', 'test-plan-2')

    def reject(self, args, pattern=None):
        before = hashes(self.root)
        result = self.cli(args)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        if pattern:
            self.assertRegex(result.stdout + result.stderr, pattern)
        self.assertEqual(hashes(self.root), before)
        self.assertEqual(sorted(p.name for p in self.data.iterdir()),
                         sorted({str(Path(p).parts[1]) for p in before if p.startswith('caves/')}))

    def test_image_id_selects_second_plan_and_preserves_distinct_ids(self):
        plan = self.add()
        meta, resolved = validate_plan(plan, self.index)
        self.assertEqual(meta['cave']['source_cave_id'], 'test-cave')
        self.assertEqual(meta['cave']['dir_id'], 'test-plan-2')
        self.assertEqual(meta['image']['image_id'], 102)
        self.assertEqual(meta['coordinates']['gps_kataster_object_id'], 'KSZ-0033')
        self.assertEqual((plan / 'image.tif').read_bytes(), self.source().read_bytes())
        self.assertEqual(meta['north']['angle_origin'], 'measured')
        self.assertFalse(meta['north']['all_skipped'])
        self.assertNotIn('historical', meta['orientation'])
        self.assertEqual(meta['orientation']['status'], 'unverified')
        self.assertEqual(resolved['coordinates']['lat'], self.index.by_object_id['KSZ-0033'].lat)
        self.assertTrue(meta['provenance']['entrance']['source'])
        self.assertTrue(meta['provenance']['scale']['source'])
        self.assertEqual(meta['provenance']['coordinates']['sha256'],
                         json.loads((ROOT / 'data/coordinate-source/source.json').read_text())['sha256'])

    def test_two_plans_same_cave_same_dimensions_different_hashes_and_no_overwrite(self):
        first = self.add(image_id=101, plan_id='test-plan-1')
        second = self.add()
        self.assertNotEqual((first / 'image.tif').read_bytes(), (second / 'image.tif').read_bytes())
        for plan in (first, second):
            validate_plan(plan, self.index)
        (first / 'meta.yaml').write_text((first / 'meta.yaml').read_text() + '# ręczna korekta\n')
        self.reject(self.argv(image_id=101, plan_id='test-plan-1'), 'istnieje')
        (second / 'image.tif').write_bytes((first / 'image.tif').read_bytes())
        with self.assertRaisesRegex(ValueError, 'sha256'):
            validate_plan(second, self.index)

    def test_ambiguous_missing_image_and_inconsistent_metadata_are_errors(self):
        args = self.argv()
        i = args.index('--image-id')
        self.reject(args[:i] + args[i+2:], 'wieloznacz|plan')
        self.source().unlink()
        self.reject(args, 'obraz|TIFF|plik')  # pierwszy TIFF nadal istnieje
        self.source().write_bytes(self.source(101).read_bytes())
        for field, value in [('graphics_id', 101), ('inventory_number', 'INNY'), ('maxWidth', 9)]:
            original = copy.deepcopy(self.cave)
            self.cave['images'][1]['metadata'][field] = value
            self.save_cave()
            self.reject(args)
            self.cave = original
        self.cave['images'][1]['image_path'] = 'caves/test-cave/image_101_zoom_10.jpg'
        self.save_cave()
        self.reject(args)

    def test_missing_required_parameters_never_creates_production_plan(self):
        for option in ['--gps-kataster-object-id', '--entrance-x', '--pixels-per-meter',
                       '--north-angle', '--north-reference', '--image-sha256', '--scale-source',
                       '--entrance-source', '--north-source', '--decision-reason', '--decision-date', '--plan-id']:
            with self.subTest(option=option):
                args = self.argv()
                i = args.index(option)
                self.reject(args[:i] + args[i+2:])

    def test_preview_writes_no_files_even_temporary_and_full_preview_validates(self):
        before = hashes(self.root)
        args = adder.parse_args(self.argv() + ['--dry-run'])
        with patch.object(tempfile, 'TemporaryDirectory', side_effect=AssertionError('preview writes')), \
             patch.object(Path, 'mkdir', side_effect=AssertionError('preview mkdir')):
            with contextlib.redirect_stdout(io.StringIO()):
                adder.add_plan(args)
        self.assertEqual(hashes(self.root), before)
        args = self.argv() + ['--dry-run']
        args[args.index('--image-sha256') + 1] = '0' * 64
        self.reject(args, 'SHA|sha')

    def test_unknown_requires_explicit_assumption_and_no_historical_inheritance(self):
        for option in ['--assumed-grid-angle', '--grid-angle-convention']:
            args = self.argv(reference='unknown')
            i = args.index(option)
            self.reject(args[:i] + args[i+2:])
        plan = self.add(reference='unknown')
        meta, resolved = validate_plan(plan, self.index)
        self.assertEqual(meta['north']['reference'], 'unknown')
        self.assertIsNone(meta['north']['angle_deg'])
        self.assertEqual(meta['north']['angle_origin'], 'unknown')
        self.assertEqual(meta['orientation']['mode'], 'assumed_grid')
        self.assertEqual(rotation(resolved), 17.25)
        resolved['coordinates']['lon'] += 1
        resolved['scale']['pixels_per_meter'] *= 2
        resolved['entrance']['x'] += .25
        self.assertEqual(rotation(resolved), 17.25)
        resolved['orientation']['grid_assumption']['rotation_deg'] += 2
        with self.assertRaisesRegex(ValueError, 'decyzj'):
            validate_orientation(resolved)
        resolved = record_decision(resolved, 'Nowe jawne przyjęcie obrotu', '2026-10-25')
        self.assertEqual(rotation(resolved), 19.25)
        resolved['orientation']['historical'] = copy.deepcopy(
            yaml.safe_load((ROOT / 'data/caves/001131/meta.yaml').read_text())['orientation']['historical'])
        with self.assertRaisesRegex(ValueError, 'T02|historical'):
            validate_orientation(resolved)

    def test_unknown_measured_zero_is_distinct_from_skipped(self):
        args = self.argv(reference='unknown')
        args.remove('--north-skipped')
        args += ['--north-angle', '0', '--north-source', 'Dwa punkty pionowej strzałki, rodzaj nieznany']
        result = self.cli(args)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        meta, _ = validate_plan(self.data / 'test-plan-2', self.index)
        self.assertEqual(meta['north']['angle_deg'], 0)
        self.assertEqual(meta['north']['angle_origin'], 'measured')
        self.assertFalse(meta['north']['all_skipped'])
        self.assertEqual(meta['north']['reference'], 'unknown')

    def test_all_orientation_variants_pass_explicit_and_default_output_cli(self):
        for reference in ('unknown', 'grid', 'geographic', 'magnetic'):
            with self.subTest(reference=reference):
                plan = self.add(reference=reference, plan_id='test-' + reference)
                out = self.root / ('output-' + reference)
                args = [sys.executable, str(ROOT / 'pipeline/02_generate_geotiff.py'),
                        '--data-dir', str(self.data), '--cave', plan.name]
                sources = hashes(self.data)
                result = subprocess.run(args + ['--output-dir', str(out)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(hashes(self.data), sources)
                manifest = json.loads((out / 'current/manifest.json').read_text())
                entry = manifest['plans'][0]
                self.assertIn('image-identity.json', entry['inputs'])
                self.assertEqual(entry['orientation']['north_reference'], reference)
                info = json.loads(subprocess.check_output(['gdalinfo', '-json', str(out / 'current' / plan.name / 'image_georef.tif')]))
                gt = info['geoTransform']
                _, meta = validate_plan(plan, self.index)
                world = generator.TRANSFORMER.transform(meta['coordinates']['lon'], meta['coordinates']['lat'])
                for axis, expected in [(0, world[0]), (3, world[1])]:
                    self.assertAlmostEqual(gt[axis] + 2.25*gt[axis+1] + 3.5*gt[axis+2], expected, places=6)
                result = subprocess.run(args, cwd=self.root, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                validate_plan(plan, self.index)
                self.assertEqual(hashes(self.data), sources)

    def test_invalid_values_ids_and_pin_do_not_write(self):
        for option, value in [('--plan-id', '../escape'), ('--plan-id', '_hidden'),
                              ('--plan-id', '001131'), ('--image-id', '999'),
                              ('--gps-kataster-object-id', 'NONEXISTENT'), ('--entrance-x', 'nan'),
                              ('--entrance-y', '6'), ('--pixels-per-meter', '0'), ('--north-angle', 'inf'),
                              ('--decision-date', '2026-99-01')]:
            with self.subTest(option=option, value=value):
                args = self.argv()
                args[args.index(option)+1] = value
                self.reject(args)
        csv = self.root / 'wrong.csv'
        csv.write_text('invalid')
        self.reject(self.argv() + ['--gps-kataster-best-measurements', str(csv)], 'SHA')

    def test_gdal_failure_cleans_staging_and_retry_succeeds(self):
        args = adder.parse_args(self.argv())
        before = hashes(self.root)
        with patch.object(adder, 'accept_generation', side_effect=ValueError('GDAL failure')):
            with self.assertRaisesRegex(ValueError, 'GDAL failure'):
                adder.add_plan(args)
        self.assertEqual(hashes(self.root), before)
        self.assertEqual(list(self.data.iterdir()), [])
        self.add()

    def test_duplicate_cave_record_and_nonplan_id_are_errors(self):
        self.jsonl.write_text(self.jsonl.read_text() * 2)
        self.reject(self.argv(), 'JSONL')
        self.cave['images'][1]['metadata']['graphics_type_name'] = 'przekrój'
        self.save_cave()
        self.reject(self.argv(), 'plan')

    def test_existing_empty_directory_broken_symlink_and_lock_are_preserved(self):
        target = self.data / 'test-plan-2'
        target.mkdir()
        result = self.cli(self.argv())
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(target.is_dir())
        self.assertEqual(list(target.iterdir()), [])
        target.rmdir()
        target.symlink_to(self.root / 'missing')
        self.assertNotEqual(self.cli(self.argv()).returncode, 0)
        self.assertTrue(target.is_symlink())
        target.unlink()
        lock = self.data / '.manual-add.lock'
        lock.write_text('blokada innego wywołania')
        self.reject(self.argv())
        self.assertEqual(lock.read_text(), 'blokada innego wywołania')

    def test_publication_failure_cleans_staging_and_retry_succeeds(self):
        before = hashes(self.root)
        with patch.object(adder, 'publish_directory', side_effect=OSError('publication failure')):
            with self.assertRaisesRegex(OSError, 'publication failure'):
                adder.add_plan(adder.parse_args(self.argv()))
        self.assertEqual(hashes(self.root), before)
        self.assertEqual(list(self.data.iterdir()), [])
        self.add()

    def test_concurrent_empty_target_is_never_replaced(self):
        target = self.data / 'test-plan-2'
        rename = adder.publish_directory
        target_inode = []
        def concurrent(source, destination):
            target.mkdir()
            target_inode.append(target.stat().st_ino)
            return rename(source, destination)
        with patch.object(adder, 'publish_directory', concurrent):
            with self.assertRaises(FileExistsError):
                adder.add_plan(adder.parse_args(self.argv()))
        self.assertEqual(target.stat().st_ino, target_inode[0])
        self.assertEqual(list(target.iterdir()), [])
        self.assertEqual(list(self.data.iterdir()), [target])

    def test_local_registration_conflict_missing_origin_and_provenance_are_errors(self):
        plan = self.add()
        path = plan / 'image-identity.json'
        raw = path.read_bytes()
        local = json.loads(raw)
        registry = read_registry()
        registry['plans'][plan.name] = local['plans'][plan.name]
        with self.assertRaisesRegex(ValueError, 'konflikt'):
            validate_plan(plan, self.index, registry)
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'tożsamości'):
            validate_plan(plan, self.index)
        path.write_bytes(raw)
        original = (plan / 'meta.yaml').read_bytes()
        for field in ('provenance',):
            meta = yaml.safe_load(original)
            meta.pop(field)
            with self.assertRaisesRegex(ValueError, 'provenance'):
                validate_plan(plan, self.index, meta_text=yaml.safe_dump(meta))
        meta = yaml.safe_load(original)
        meta['orientation']['origin']['reason'] = 'podmieniony korzeń'
        with self.assertRaisesRegex(ValueError, 'origin'):
            validate_plan(plan, self.index, meta_text=yaml.safe_dump(meta))

    def test_t02_plan_cannot_replace_history_with_t08_origin(self):
        meta = yaml.safe_load((ROOT / 'data/caves/001131/meta.yaml').read_text())
        meta['orientation']['origin'] = {'kind': 'manual_t08'}
        with self.assertRaises(ValueError):
            validate_orientation(meta)

    def test_t04_uses_local_registration_snapshot_and_guards_changed_identity(self):
        plan = self.add(reference='unknown')
        path = plan / 'image-identity.json'
        original = path.read_bytes()
        prepare = generator.prepare_cave
        def aba(*args, **kwargs):
            path.write_text('invalid identity temporarily B')
            try:
                return prepare(*args, **kwargs)
            finally:
                path.write_bytes(original)
        out = self.root / 'snapshot-result'
        with patch.object(generator, 'prepare_cave', side_effect=aba):
            run = generator.process_output([plan], out, self.data)
        manifest = json.loads((run / 'manifest.json').read_text())
        self.assertEqual(manifest['plans'][0]['inputs']['image-identity.json'],
                         hashlib.sha256(original).hexdigest())
        import geotiff_output
        real_translate = geotiff_output.translate_geotiff
        def change(*args, **kwargs):
            real_translate(*args, **kwargs)
            path.write_bytes(original + b' ')
        current = (out / 'current').resolve()
        with patch.object(geotiff_output, 'translate_geotiff', side_effect=change):
            with self.assertRaisesRegex(ValueError, 'zmieniły'):
                generator.process_output([plan], out, self.data, force=True)
        self.assertEqual((out / 'current').resolve(), current)
        path.write_bytes(original)
        path.unlink()
        external = self.root / 'external-identity.json'
        external.write_bytes(original)
        (run / 'outside-identity').symlink_to(external)
        path.symlink_to(out / 'current' / 'outside-identity')
        with self.assertRaisesRegex(ValueError, 'ścieżce wejścia'):
            generator.process_output([plan], out, self.data)

    def test_t04_snapshot_of_absent_local_identity_rejects_appearance_during_hashing(self):
        plan = self.add()
        path = plan / 'image-identity.json'
        raw = path.read_bytes()
        local = json.loads(raw)
        registry = read_registry()
        registry['plans'][plan.name] = local['plans'][plan.name]
        registry_path = self.root / 'global-registry.json'
        registry_path.write_text(json.dumps(registry))
        path.unlink()
        real_hashes = generator.input_hashes
        def appears(directory):
            path.write_bytes(raw)
            return real_hashes(directory)
        output = self.root / 'absent-snapshot-output'
        with patch.object(generator, 'input_hashes', side_effect=appears):
            with self.assertRaisesRegex(ValueError, 'zmieni'):
                generator.process_output([plan], output, self.data, registry_path=registry_path)
        self.assertFalse((output / 'current').exists())

    def test_t10_cache_tracks_local_identity_content_and_requires_its_presence(self):
        plan = self.add()
        output = self.root / 'local-cache-results'
        first = generator.process_output([plan], output, self.data)
        identity = plan / 'image-identity.json'
        original = identity.read_bytes()
        identity.write_bytes(original + b'\n')
        second = generator.process_output([plan], output, self.data)
        manifest = json.loads((second / 'manifest.json').read_text())
        self.assertEqual(manifest['build']['generated'], [plan.name])
        self.assertNotEqual(json.loads((first / 'manifest.json').read_text())['plans'][0]['fingerprint'],
                            manifest['plans'][0]['fingerprint'])
        identity.unlink()
        with self.assertRaises(ValueError):
            generator.process_output([plan], output, self.data)
        self.assertEqual((output / 'current').resolve(), second)

    def test_jsonl_provenance_hash_describes_the_bytes_actually_selected(self):
        original = self.jsonl.read_bytes()
        load = adder.load_cave_from_jsonl
        def change(*args, **kwargs):
            result = load(*args, **kwargs)
            self.jsonl.write_bytes(original + b' ')
            return result
        args = adder.parse_args(self.argv() + ['--dry-run'])
        with patch.object(adder, 'load_cave_from_jsonl', side_effect=change), contextlib.redirect_stdout(io.StringIO()):
            meta = adder.add_plan(args)
        self.assertEqual(meta['provenance']['registry']['sha256'], hashlib.sha256(original).hexdigest())


if __name__ == '__main__':
    unittest.main()
