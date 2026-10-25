"""T10: konserwatywny zakres Git, niezależny od aktualności cache.

Moduł biblioteki standardowej działa także na hoście przed kontenerem.
Niepewna historia wymusza pełne przeliczenie; niczego nie wybiera po mtime.
"""
import argparse
import json
import subprocess
from pathlib import Path


def select_changes(repo, base, head, event):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.PIPE)

    fallback = {'schema_version': 1, 'full': True, 'uncertain': True, 'plans': [], 'paths': [],
                'base': base, 'head': head, 'event': event, 'reason': 'niepewny zakres historii'}
    try:
        if (event not in ('push', 'pull_request') or not isinstance(base, str)
                or not isinstance(head, str) or not base or not head or set(base) == {'0'}):
            return fallback
        if git('rev-parse', '--is-shallow-repository').strip() != b'false':
            return fallback
        base_sha = git('rev-parse', '--verify', base + '^{commit}').decode().strip()
        head_sha = git('rev-parse', '--verify', head + '^{commit}').decode().strip()
        if event == 'pull_request':
            base_sha = git('merge-base', base_sha, head_sha).decode().strip()
        else:
            git('merge-base', '--is-ancestor', base_sha, head_sha)
        # Bez detekcji rename otrzymujemy jawne usunięcie + dodanie obu ścieżek.
        paths = sorted(p.decode('utf-8') for p in git('diff', '--name-only', '-z', '--no-renames',
                                                     base_sha, head_sha, '--').split(b'\0') if p)
        plans, full, uncertain = set(), False, False
        for name in paths:
            parts = Path(name).parts
            if len(parts) >= 4 and parts[:2] == ('data', 'caves') and not parts[2].startswith(('_', '.')):
                plans.add(parts[2])
            elif name.startswith(('pipeline/', 'ci/', 'scripts/', '.github/', 'data/', 'parquet/')):
                full = True
            elif not (name.startswith('docs/') or name.lower().endswith('.md') or name == '.gitignore'):
                full, uncertain = True, True  # nieznanej zależności nie poświadcza fingerprint
        return {**fallback, 'full': full, 'uncertain': uncertain, 'plans': sorted(plans), 'paths': paths,
                'base': base_sha, 'head': head_sha,
                'reason': 'nieznane wejście' if uncertain else ('wejścia wspólne' if full else 'pełny zakres Git')}
    except (OSError, subprocess.CalledProcessError, UnicodeError):
        return fallback


def main():
    parser = argparse.ArgumentParser(description='Zakres zmian T10 (bez zależności Pythona)')
    parser.add_argument('--repo', type=Path, default=Path('.'))
    parser.add_argument('--event', default='local')
    parser.add_argument('--event-file', type=Path)
    parser.add_argument('--base')
    parser.add_argument('--head', default='HEAD')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    base, head = args.base, args.head
    if args.event_file:
        try:
            payload = json.loads(args.event_file.read_text())
            if args.event == 'push':
                base, head = payload['before'], payload['after']
            elif args.event == 'pull_request':
                base, head = payload['pull_request']['base']['sha'], payload['pull_request']['head']['sha']
        except (OSError, ValueError, KeyError, TypeError):
            base = None
    result = select_changes(args.repo, base, head, args.event)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
