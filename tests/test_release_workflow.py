"""T10: oba zdarzenia wymagają tej samej bramki przed publikacją."""
import hashlib
import os
import subprocess
import sys
import tempfile
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

    def test_qa_archive_is_readable_by_another_user_without_changing_bytes(self):
        self.assertEqual(os.geteuid(), 0, 'Regresja wymaga przypiętego kontenera')
        steps = self.workflow('release-geotiff.yml')['jobs']['release']['steps']
        permission = next((i for i, step in enumerate(steps)
            if step.get('name') == 'Udostępnij odebraną paczkę do odczytu na runnerze'), None)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.chmod(0o755)
            (root / 'build').mkdir(mode=0o755)
            archive = root / 'build/geotiff-tatry-v1.2.3.zip'
            archive.write_bytes(bytes(range(256)) * 5)
            archive.chmod(0o600)  # mkstemp w kontenerze root, odbiorca hostowy ma inne UID
            before = hashlib.sha256(archive.read_bytes()).hexdigest()

            def reader_identity():
                os.setgroups([])
                os.setgid(65534)
                os.setuid(65534)

            def read_as_publisher():
                return subprocess.run([sys.executable, '-c',
                    'from pathlib import Path; import sys; print(Path(sys.argv[1]).read_bytes().hex())',
                    str(archive)], capture_output=True, text=True, preexec_fn=reader_identity)

            denied = read_as_publisher()
            self.assertNotEqual(denied.returncode, 0)
            self.assertIn('PermissionError', denied.stderr)
            self.assertIsNotNone(permission, 'Brak przekazania prawa odczytu ZIP po QA')
            gate = next(i for i, step in enumerate(steps) if './scripts/build package ' in step.get('run', ''))
            publish = next(i for i, step in enumerate(steps)
                if step.get('uses', '').startswith('softprops/action-gh-release@'))
            self.assertLess(gate, permission)
            self.assertLess(permission, publish)
            self.assertNotIn('if', steps[permission])
            self.assertNotIn('continue-on-error', steps[permission])
            # W teście już jesteśmy root; wykonujemy rzeczywisty chmod z workflow.
            environment = dict(os.environ, RELEASE_TAG='v1.2.3')
            command = 'sudo() { "$@"; }\n' + steps[permission]['run']
            result = subprocess.run(['sh', '-eu', '-c', command],
                cwd=root, env=environment, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            received = read_as_publisher()
            self.assertEqual(received.returncode, 0, received.stderr)
            self.assertEqual(bytes.fromhex(received.stdout), archive.read_bytes())
            self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), before)
            self.assertEqual(archive.stat().st_mode & 0o777, 0o644)

    def test_publisher_never_overwrites_an_existing_release_asset(self):
        steps = self.workflow('release-geotiff.yml')['jobs']['release']['steps']
        publish = next(step for step in steps
            if step.get('uses', '').startswith('softprops/action-gh-release@'))
        self.assertEqual(publish['with'].get('overwrite_files'), 'false')


if __name__ == '__main__':
    unittest.main()
