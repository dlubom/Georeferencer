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
        self.meta_path.write_text(self.meta_path.read_text().replace(
            "  name: Plan syntetyczny", "  name: Plan syntetyczny\n  inventory_number: T.X-01.02"))
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

    def test_failed_manual_readback_preserves_previous_package_and_current(self):
        import release_acceptance
        self.archive.write_bytes(b'previous package')
        current = (self.output / 'current').readlink()
        with patch.object(release_acceptance, 'verify_archive', side_effect=ValueError('controlled manual ZIP fault')):
            with self.assertRaises(ValueError):
                self.pack(mode='manual')
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

    def test_v2_maps_all_artifacts_to_exact_bytes_and_preserves_run_manifest(self):
        before = (self.run / 'manifest.json').read_bytes()
        self.pack()
        with zipfile.ZipFile(self.archive) as archive:
            manifest = json.loads(archive.read('manifest.json'))
            self.assertEqual(manifest['release']['version'], 't11-v2', 'Brak nowego kontraktu ZIP')
            files = manifest['release']['files']
            self.assertEqual(len(files), 3)
            self.assertEqual({f['archive_path'] for f in files},
                {'metadane/001131/computed.json', 'metadane/001131/image.tfw',
                 '001131_T.X-01.02_Plan_syntetyczny.tif'})
            for item in files:
                self.assertEqual(archive.read(item['archive_path']),
                    (self.run / item['plan_id'] / item['output']).read_bytes())
        self.assertEqual((self.run / 'manifest.json').read_bytes(), before)
        self.assertTrue(self.verify()['passed'])

    def test_reader_accepts_legacy_v1_and_rejects_unknown_contract_versions(self):
        self.pack()
        with zipfile.ZipFile(self.archive) as archive:
            manifest = json.loads(archive.read('manifest.json'))
        manifest['release']['version'] = 't11-v1'
        manifest['release'].pop('files', None)
        with zipfile.ZipFile(self.archive, 'w') as archive:
            archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False).encode())
            for plan in manifest['plans']:
                for output in plan['outputs']:
                    archive.write(self.run / plan['dir_id'] / output, plan['dir_id'] + '/' + output)
        self.assertTrue(self.verify()['passed'])
        original = self.archive.read_bytes()
        for version in ('t11-v0', 't11-v3', None):
            self.archive.write_bytes(original)
            def mutate(entries):
                m = json.loads(dict(entries)['manifest.json'])
                m['release']['version'] = version
                return [(n, json.dumps(m).encode() if n == 'manifest.json' else r) for n, r in entries]
            self.rewrite(mutate)
            with self.subTest(version=version), self.assertRaises(ValueError):
                self.verify()
        self.archive.write_bytes(original)
        changed = copy.deepcopy(self.options)
        changed['exceptions']['exceptions'][0]['basis_sha256'] = 'stale'
        import release_acceptance
        with self.assertRaises(ValueError):
            release_acceptance.verify_archive(self.archive, self.data, qa_kwargs=changed)
        self.meta_path.write_text(self.meta_path.read_text() + '# stale source\n')
        with self.assertRaises(ValueError):
            self.verify()

    def test_reader_rederives_names_and_rejects_forged_or_incomplete_mappings(self):
        self.pack()
        original = self.archive.read_bytes()
        for fault in ('name', 'plan_id', 'output', 'hash', 'missing', 'extra', 'duplicate', 'absent'):
            self.archive.write_bytes(original)
            def mutate(entries):
                m = json.loads(dict(entries)['manifest.json'])
                self.assertIn('files', m['release'], 'Brak jawnego mapowania wyników')
                rows = m['release']['files']
                replacement = None
                if fault == 'name':
                    row = next(f for f in rows if f['output'] == 'image_georef.tif')
                    replacement = (row['archive_path'], '001131_T.X-01.02_Inna_nazwa.tif')
                    row['archive_path'] = replacement[1]
                elif fault in ('plan_id', 'output'):
                    rows[0][fault] = 'wrong'
                elif fault == 'hash':
                    rows[0]['sha256'] = '0' * 64
                elif fault == 'missing':
                    rows.pop()
                elif fault == 'extra':
                    rows.append({'plan_id': 'unknown', 'output': 'extra', 'archive_path': 'extra', 'sha256': '0'*64})
                elif fault == 'duplicate':
                    rows.append(copy.deepcopy(rows[0]))
                else:
                    del m['release']['files']
                return [(replacement[1] if replacement and n == replacement[0] else n,
                         json.dumps(m).encode() if n == 'manifest.json' else raw) for n, raw in entries]
            self.rewrite(mutate)
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                self.verify()

    def test_swapped_plan_artifacts_and_forged_hash_mapping_are_rejected(self):
        import yaml
        other = self.data / '001132'
        shutil.copytree(self.cave_dir, other)
        metadata = yaml.safe_load((other / 'meta.yaml').read_text())
        metadata['cave'].update(dir_id='001132', name='Drugi plan')
        metadata['entrance']['x'] = 4.0
        from orientation_fixture import attach_orientation
        metadata = attach_orientation(metadata, hashlib.sha256((other / 'image.tif').read_bytes()).hexdigest())
        (other / 'meta.yaml').write_text(yaml.safe_dump(metadata, allow_unicode=True))
        registry = json.loads(self.registry_path.read_text())
        registry['plans']['001132'] = copy.deepcopy(registry['plans']['001131'])
        self.registry_path.write_text(json.dumps(registry))
        self.run = qa_fixture.generator.process_output([self.cave_dir, other], self.output,
            self.data, self.coordinates_path, self.registry_path)
        report = self.report()
        self.options['exceptions']['exceptions'] = [
            {'plan_id': p['plan_id'], 'rule': p['rule'], 'basis_sha256': p['basis_sha256'],
             'evidence': p['evidence'], 'reason': 'Znana niepewność próby',
             'close_when': 'Po przeglądzie źródła', 'sources': ['synthetic:test_release_acceptance']}
            for p in report['problems'] if p['rule'] == 'orientation.unknown']
        self.pack()
        self.assertTrue(self.verify()['passed'])
        original = self.archive.read_bytes()
        for output in ('image_georef.tif', 'image.tfw', 'computed.json'):
            for forged in (False, True):
                self.archive.write_bytes(original)
                def mutate(entries):
                    m = json.loads(dict(entries)['manifest.json'])
                    self.assertIn('files', m['release'], 'Brak mapowania t11-v2')
                    rows = [f for f in m['release']['files'] if f['output'] == output]
                    left, right = rows
                    payloads = dict(entries)
                    self.assertNotEqual(payloads[left['archive_path']], payloads[right['archive_path']])
                    if forged:
                        left['sha256'], right['sha256'] = right['sha256'], left['sha256']
                        plans = {p['dir_id']: p for p in m['plans']}
                        for row in rows:
                            plans[row['plan_id']]['outputs'][output] = row['sha256']
                        release = m.pop('release')
                        canonical = (json.dumps(m, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode()
                        release['run_manifest_sha256'] = hashlib.sha256(canonical).hexdigest()
                        m['release'] = release
                    return [(n, json.dumps(m).encode() if n == 'manifest.json' else
                        payloads[right['archive_path']] if n == left['archive_path'] else
                        payloads[left['archive_path']] if n == right['archive_path'] else raw)
                        for n, raw in entries]
                self.rewrite(mutate)
                with self.subTest(output=output, forged=forged), self.assertRaises(ValueError):
                    self.verify()

    def test_invalid_deflate_stream_has_a_readable_rejection(self):
        import struct
        self.pack()
        with zipfile.ZipFile(self.archive) as archive:
            member = next(i for i in archive.infolist() if i.filename.endswith('.tif'))
            self.assertEqual(member.compress_type, zipfile.ZIP_DEFLATED)
        raw = bytearray(self.archive.read_bytes())
        name_size, extra_size = struct.unpack_from('<HH', raw, member.header_offset + 26)
        data_offset = member.header_offset + 30 + name_size + extra_size
        raw[data_offset] = 7  # DEFLATE BTYPE=3 jest niedozwolone.
        self.archive.write_bytes(raw)
        try:
            self.verify()
        except Exception as error:
            self.assertIsInstance(error, ValueError, 'Uszkodzenie ZIP musi dać czytelny błąd odbioru')
        else:
            self.fail('Uszkodzony strumień ZIP został przyjęty')

    def test_dos_directory_attribute_blocks_an_otherwise_valid_member(self):
        self.pack()
        with zipfile.ZipFile(self.archive) as archive:
            entries = [(info, archive.read(info)) for info in archive.infolist()]
        with zipfile.ZipFile(self.archive, 'w') as archive:
            for info, raw in entries:
                if info.filename == 'manifest.json':
                    info.create_system = 0
                    info.external_attr = 0x10  # katalog DOS, nawet bez końcowego /
                archive.writestr(info, raw)
        with self.assertRaises(ValueError):
            self.verify()

    def test_all_zipinfo_are_checked_before_deduplicating_names(self):
        self.pack()
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(self.archive, 'a') as archive:
                duplicate = zipfile.ZipInfo('manifest.json')
                duplicate.create_system = 3
                duplicate.external_attr = 0o120777 << 16
                archive.writestr(duplicate, b'target')
        with self.assertRaisesRegex(ValueError, 'katalog/dowiązanie'):
            self.verify()

    def test_zipinfo_unsafe_paths_symlinks_casefold_and_crc_are_rejected(self):
        self.pack()
        original = self.archive.read_bytes()
        for path in ('../escape', '/abs', 'metadane/../escape', 'a\\b', 'C:stream', 'bad\x00suffix', 'bad\nname'):
            self.archive.write_bytes(original)
            with zipfile.ZipFile(self.archive, 'a') as archive:
                archive.writestr(path, b'bad')
            with self.subTest(path=repr(path)), self.assertRaises(ValueError):
                self.verify()
        for mode in (0o120777, 0o040755, 0o020666):
            self.archive.write_bytes(original)
            with zipfile.ZipFile(self.archive, 'a') as archive:
                info=zipfile.ZipInfo('link')
                info.create_system=3
                info.external_attr=mode << 16
                archive.writestr(info,b'manifest.json')
            with self.subTest(mode=oct(mode)), self.assertRaises(ValueError):
                self.verify()
        self.archive.write_bytes(original)
        with zipfile.ZipFile(self.archive, 'a') as archive:
            archive.writestr('MANIFEST.JSON',b'extra')
        with self.assertRaises(ValueError):
            self.verify()
        self.archive.write_bytes(original)
        # Zmiana CRC w katalogu centralnym bez zmiany payloadu/manifestu.
        raw = bytearray(original)
        offset = raw.index(b'PK\x01\x02') + 16
        raw[offset] ^= 1
        self.archive.write_bytes(raw)
        with self.assertRaises(ValueError):
            self.verify()

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
