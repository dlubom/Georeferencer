"""T10: prawdziwy zakres Git; utrata pewności wymaga pełnego builda."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'pipeline'))


class ChangesTest(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('build_changes'), 'Brak selekcji całego zakresu T10')
        from build_changes import select_changes
        self.select = select_changes
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.invalid')
        self.put('data/caves/a/meta.yaml')
        self.put('data/caves/a/image.tif')
        self.put('data/caves/b/meta.yaml')
        self.base = self.commit()

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], text=True).strip()

    def put(self, name, value='source'):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)

    def commit(self):
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture')
        return self.git('rev-parse', 'HEAD')

    def test_push_covers_multiple_commits_and_documentation_tail(self):
        self.put('data/caves/a/image.tif', 'new image')
        self.put('data/caves/new/image-identity.json')
        (self.repo / 'data/caves/b/meta.yaml').unlink()
        self.commit()
        self.put('README.md', 'docs only last commit')
        head = self.commit()
        result = self.select(self.repo, self.base, head, 'push')
        self.assertFalse(result['full'])
        self.assertFalse(result['uncertain'])
        self.assertEqual(result['plans'], ['a', 'b', 'new'])
        self.assertIn('data/caves/b/meta.yaml', result['paths'])

    def test_pr_uses_merge_base_and_covers_both_sides_of_rename(self):
        self.git('checkout', '-qb', 'feature')
        self.git('mv', 'data/caves/a', 'data/caves/renamed')
        head = self.commit()
        self.git('checkout', '-q', '-')
        self.put('data/caves/b/meta.yaml', 'unrelated base change')
        base = self.commit()
        result = self.select(self.repo, base, head, 'pull_request')
        self.assertFalse(result['full'])
        self.assertEqual(result['plans'], ['a', 'renamed'])

    def test_unknown_missing_zero_shallow_and_unrelated_push_force_full(self):
        for base, head, event in ((None, 'HEAD', 'push'), ('0'*40, 'HEAD', 'push'),
                                  ('missing', 'HEAD', 'push'), (self.base, 'HEAD', 'unknown'),
                                  (123, 'HEAD', 'push'), (self.base, [], 'push')):
            with self.subTest(base=base, event=event):
                selection = self.select(self.repo, base, head, event)
                self.assertTrue(selection['full'])
                self.assertTrue(selection['uncertain'])
        gitdir = self.repo / '.git'
        (gitdir / 'shallow').write_text(self.base + '\n')
        self.assertTrue(self.select(self.repo, self.base, 'HEAD', 'push')['full'])
        (gitdir / 'shallow').unlink()
        self.put('README.md')
        child = self.commit()
        self.assertTrue(self.select(self.repo, child, self.base, 'push')['full'])

    def test_global_inputs_force_all_and_local_registry_add_remove_select_plan(self):
        for name in ('pipeline/validation.py', 'ci/requirements.lock',
                     'data/coordinate-source/source.json', 'data/validation/images-v1.json',
                     'data/history/t02-inputs.zip', '.github/workflows/generate-geotiff.yml'):
            self.put(name)
            head = self.commit()
            self.assertTrue(self.select(self.repo, self.base, head, 'push')['full'], name)
            self.base = head
        self.put('data/caves/a/image-identity.json')
        head = self.commit()
        self.assertEqual(self.select(self.repo, self.base, head, 'push')['plans'], ['a'])
        (self.repo / 'data/caves/a/image-identity.json').unlink()
        removed = self.commit()
        self.assertEqual(self.select(self.repo, head, removed, 'push')['plans'], ['a'])

    def test_unknown_input_is_uncertain_but_gitignore_is_only_metadata(self):
        self.put('.gitignore')
        head = self.commit()
        self.assertFalse(self.select(self.repo, self.base, head, 'push')['uncertain'])
        self.base = head
        self.put('new-runtime-config.json')
        head = self.commit()
        result = self.select(self.repo, self.base, head, 'push')
        self.assertTrue(result['full'])
        self.assertTrue(result['uncertain'])


if __name__ == '__main__':
    unittest.main()
