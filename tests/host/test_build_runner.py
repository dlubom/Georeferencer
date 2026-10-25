"""Publiczny wrapper: argumenty i mounty Dockera bez zależności hosta."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class RunnerTest(unittest.TestCase):
    def test_report_defaults_to_writable_output_and_source_stays_readonly(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'scripts').mkdir()
            shutil.copy2(ROOT / 'scripts/build', root / 'scripts/build')
            commands = root / 'commands.jsonl'
            fake = root / 'bin/docker'
            fake.parent.mkdir()
            fake.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
with Path(os.environ['T10_COMMANDS']).open('a') as stream:
    stream.write(json.dumps(sys.argv[1:]) + '\\n')
if sys.argv[1] == 'build':
    Path(sys.argv[sys.argv.index('--iidfile')+1]).write_text('fake-image')
''')
            fake.chmod(0o755)
            env = {**os.environ, 'PATH': str(fake.parent) + os.pathsep + os.environ['PATH'],
                   'T10_COMMANDS': str(commands)}
            result = subprocess.run([str(root / 'scripts/build'), 'report'], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            run = json.loads(commands.read_text().splitlines()[-1])
            self.assertIn('type=bind,source=' + str(root) + ',target=/workspace,readonly', run)
            self.assertIn('type=bind,source=' + str(root / 'build') + ',target=/build', run)
            self.assertIn('--read-only', run)
            self.assertEqual(run[-4:], ['python', 'pipeline/03_report.py', '--reports-dir', '/build/qa'])


if __name__ == '__main__':
    unittest.main()
