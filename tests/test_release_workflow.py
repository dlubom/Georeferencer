"""T10: oba zdarzenia wymagają tej samej bramki przed publikacją."""
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


class ReleaseWorkflowTest(unittest.TestCase):
    def workflow(self, name):
        return yaml.load((ROOT / '.github/workflows' / name).read_text(), Loader=yaml.BaseLoader)

    def test_tag_and_manual_share_a_required_qa_package_gate_before_publication(self):
        workflow = self.workflow('release-geotiff.yml')
        self.assertEqual(set(workflow['on']), {'push', 'workflow_dispatch'})
        steps = workflow['jobs']['release']['steps']
        gate = next(i for i, s in enumerate(steps) if './scripts/build package ' in s.get('run', ''))
        publish = next(i for i, s in enumerate(steps) if s.get('uses', '').startswith('softprops/action-gh-release@'))
        self.assertLess(gate, publish)
        self.assertNotIn('if', steps[gate])
        self.assertNotIn('continue-on-error', steps[gate])
        self.assertIn('--run-dir /build/geotiff/current', steps[gate]['run'])
        self.assertIn('manual', steps[gate]['env']['RELEASE_MODE'])
        self.assertIn('tag', steps[gate]['env']['RELEASE_MODE'])
        self.assertEqual(steps[publish]['with']['fail_on_unmatched_files'], 'true')
        self.assertTrue(steps[publish]['with']['files'].endswith('.zip'))
        self.assertFalse(any('data/caves/*' in s.get('run', '') for s in steps))

    def test_generation_has_full_history_read_permissions_and_no_bot_push(self):
        workflow = self.workflow('generate-geotiff.yml')
        self.assertEqual(set(workflow['on']), {'push', 'pull_request', 'workflow_dispatch'})
        self.assertNotIn('paths', workflow['on']['push'])
        self.assertEqual(workflow['permissions'], {'contents': 'read'})
        job = workflow['jobs']['generate']
        self.assertNotIn('if', job)
        self.assertNotIn('permissions', job)
        checkout = next(s for s in job['steps'] if s.get('uses', '').startswith('actions/checkout@'))
        self.assertEqual(checkout['with']['fetch-depth'], '0')
        commands = '\n'.join(s.get('run', '') for s in job['steps'])
        for unsafe in ('git push', 'git commit', 'apt-get', 'pip install', 'HEAD~1'):
            self.assertNotIn(unsafe, commands)
        self.assertIn('./scripts/build generate --changed', commands)
        self.assertIn('--require-results', commands)


if __name__ == '__main__':
    unittest.main()
