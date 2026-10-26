"""Prezentacja ZIP jest odrębna od niezmiennego przebiegu generatora."""
import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


class ReleaseLayoutTest(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('release_layout'),
                             'Brak mapowania czytelnych nazw t11-v2')
        import release_layout
        self.layout = release_layout
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.data = Path(temporary.name)
        self.manifest = {'plans': []}
        self.add_plan('001094', 'T.D-08.07', 'Jaskinia Mroźna')

    def add_plan(self, plan_id, inventory, name):
        directory = self.data / plan_id
        directory.mkdir(exist_ok=True)
        raw = json.dumps({'cave': {'inventory_number': inventory, 'name': name}}, ensure_ascii=False).encode()
        (directory / 'meta.yaml').write_bytes(raw)  # JSON jest także YAML
        plan = {'dir_id': plan_id, 'inputs': {'meta.yaml': hashlib.sha256(raw).hexdigest()},
                'outputs': {'image_georef.tif': '1' * 64, 'image.tfw': '2' * 64, 'computed.json': '3' * 64}}
        self.manifest['plans'].append(plan)
        return plan

    def files(self, version='t11-v2'):
        return self.layout.files_for_release(self.manifest, self.data, version=version)

    def test_exact_historical_mrozna_name_and_complete_three_output_mapping(self):
        self.assertEqual(self.files(), [
            {'plan_id': '001094', 'output': 'computed.json', 'archive_path': 'metadane/001094/computed.json', 'sha256': '3' * 64},
            {'plan_id': '001094', 'output': 'image.tfw', 'archive_path': 'metadane/001094/image.tfw', 'sha256': '2' * 64},
            {'plan_id': '001094', 'output': 'image_georef.tif', 'archive_path': '001094_T.D-08.07_Jaskinia_Mroźna.tif', 'sha256': '1' * 64}])

    def test_historical_normalization_preserves_polish_case_and_repeated_underscores(self):
        self.manifest['plans'] = []
        self.add_plan('001094', 'T.D / "08"', "Jaskinia 'Żółta' / Łąka")
        self.assertEqual(self.files()[-1]['archive_path'], '001094_T.D___08_Jaskinia_Żółta___Łąka.tif')

    def test_missing_empty_nontext_or_unsafe_name_and_inventory_block(self):
        for field in ('name', 'inventory_number'):
            for value in (None, '', '   ', 12, "''", 'abc\\def', 'abc:stream', 'abc\nxyz', 'abc\x00xyz', 'abc\u202exyz'):
                with self.subTest(field=field, value=repr(value)):
                    meta = {'cave': {'name': 'Jaskinia Mroźna', 'inventory_number': 'T.D-08.07'}}
                    meta['cave'][field] = value
                    raw = json.dumps(meta).encode()
                    (self.data / '001094/meta.yaml').write_bytes(raw)
                    self.manifest['plans'][0]['inputs']['meta.yaml'] = hashlib.sha256(raw).hexdigest()
                    with self.assertRaisesRegex(ValueError, '001094.*' + field):
                        self.files()

    def test_invalid_or_casefold_colliding_plan_ids_block_without_suffix(self):
        for invalid in ('', '.', '..', '../escape', '/abs', 'a/b', 'a\\b', 'C:foo'):
            with self.subTest(plan_id=invalid):
                manifest = copy.deepcopy(self.manifest)
                manifest['plans'][0]['dir_id'] = invalid
                with self.assertRaises(ValueError):
                    self.layout.files_for_release(manifest, self.data)
        self.manifest['plans'].append(copy.deepcopy(self.manifest['plans'][0]))
        with self.assertRaisesRegex(ValueError, 'kolizja|powtórz'):
            self.files()
        self.manifest['plans'].pop()
        self.add_plan('Plan', 'T.1', 'Grota')
        self.add_plan('plan', 'T.1', 'Grota')
        with self.assertRaisesRegex(ValueError, 'kolizja'):
            self.files()

    def test_unicode_normalization_collision_blocks_without_changing_names(self):
        self.add_plan('Ż', 'T.1', 'Grota')
        self.add_plan('Z\u0307', 'T.1', 'Grota')
        with self.assertRaisesRegex(ValueError, 'kolizja'):
            self.files()

    def test_metadata_hash_is_checked_and_manifest_run_stays_unchanged(self):
        original = copy.deepcopy(self.manifest)
        self.files()
        self.assertEqual(self.manifest, original)
        (self.data / '001094/meta.yaml').write_text('cave: {name: Inna, inventory_number: X}')
        with self.assertRaisesRegex(ValueError, '001094.*meta.yaml'):
            self.files()

    def test_legacy_layout_has_three_original_paths_and_unknown_versions_block(self):
        self.assertEqual([f['archive_path'] for f in self.files('t11-v1')],
                         ['001094/computed.json', '001094/image.tfw', '001094/image_georef.tif'])
        for version in ('t11-v0', 't11-v3', None):
            with self.subTest(version=version), self.assertRaises(ValueError):
                self.files(version)

    def test_every_output_digest_and_exact_output_inventory_are_required(self):
        for outputs in ({}, {'image.tfw': 'a'*64}, {**self.manifest['plans'][0]['outputs'], 'extra.tif': 'a'*64},
                        {**self.manifest['plans'][0]['outputs'], 'image.tfw': 'bad'}):
            with self.subTest(outputs=outputs), self.assertRaises(ValueError):
                changed=copy.deepcopy(self.manifest)
                changed['plans'][0]['outputs']=outputs
                self.layout.files_for_release(changed,self.data)


if __name__ == '__main__':
    unittest.main()
