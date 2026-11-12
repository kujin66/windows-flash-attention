"""Build the existing FA4 pyproject, install its wheel, resume real tests."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[1]
WORK = REPO / 'agent_space' / 'windows-native'


def write(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temporary.replace(path)


def run(command, log, **kwargs):
    with log.open('w', encoding='utf-8') as output:
        try:
            return subprocess.run(command, stdout=output, stderr=subprocess.STDOUT, **kwargs).returncode
        except subprocess.TimeoutExpired:
            output.write('\nWorker timeout; durable case reports will be recovered.\n')
            return 124


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', choices=('smoke', 'full'), default='full')
    parser.add_argument('--max-attempts', type=int, default=3)
    parser.add_argument('--worker-seconds', type=int, default=1800)
    args = parser.parse_args()
    if sys.platform != 'win32' or platform.machine().lower() not in ('amd64', 'x86_64'):
        parser.error('This entry point validates native Windows x64 only')
    if args.max_attempts < 1:
        parser.error('--max-attempts must be positive')
    WORK.mkdir(parents=True, exist_ok=True)
    import msvcrt
    with (WORK / 'loop.lock').open('a+b') as lock:
        if not lock.tell():
            lock.write(b'0')
            lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        return validate(args)


def validate(args):
    digest = hashlib.sha256()
    for base in ('flash_attn/cute', 'tests/cute', 'tools'):
        for path in sorted((REPO / base).glob('*.py')):
            digest.update(str(path.relative_to(REPO)).encode())
            digest.update(path.read_bytes())
    folder = WORK / (digest.hexdigest()[:16] + '-' + args.suite)
    folder.mkdir(exist_ok=True)
    write(WORK / 'status.json', dict(state='building', suite=args.suite, folder=str(folder)))
    dist = folder / 'dist'
    code = run([sys.executable, '-m', 'build', '--no-isolation', '--outdir', str(dist)],
               folder / 'build.log', cwd=REPO / 'flash_attn/cute')
    if code:
        write(WORK / 'status.json', dict(state='build_failed', suite=args.suite, folder=str(folder)))
        raise SystemExit(f'Build failed: {folder}')
    wheels = list(dist.glob('*.whl'))
    assert len(wheels) == 1, wheels
    if run([sys.executable, '-m', 'twine', 'check', *map(str, dist.iterdir())], folder / 'metadata.log'):
        raise SystemExit('Distribution metadata failed validation')
    if run([sys.executable, '-m', 'pip', 'install', '--no-deps', '--ignore-installed', str(wheels[0])],
           folder / 'install.log'):
        raise SystemExit('Wheel installation failed')
    write(folder / 'manifest.json', dict(source_sha256=digest.hexdigest(),
          head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
          wheel=str(wheels[0]), wheel_sha256=hashlib.sha256(wheels[0].read_bytes()).hexdigest(),
          python=sys.version, platform=platform.platform(), suite=args.suite))
    env = os.environ.copy()
    env.update(PYTHONPATH=str(REPO / 'tools'), PYTHONUNBUFFERED='1',
               FLASH_ATTENTION_CUTE_DSL_CACHE_ENABLED='1',
               FLASH_ATTENTION_CUTE_DSL_CACHE_DIR=str(WORK / 'kernel-cache'))
    probe = 'import sys; from pathlib import Path; import flash_attn.cute as m; print(m.__file__); assert Path(m.__file__).is_relative_to(Path(sys.prefix))'
    if run([sys.executable, '-c', probe], folder / 'import.log', cwd=folder, env=env):
        raise SystemExit('Installed FA4 wheel import failed; inspect import.log')
    paths = sorted((REPO / 'tests/cute').glob('test_*.py'))
    if args.suite == 'smoke':
        names = ('test_windows_filelock.py', 'test_windows_sm120.py', 'test_cuda_graph.py', 'test_cache_utils.py')
        paths = [REPO / 'tests/cute' / name for name in names]
    summary = {}
    for path in paths:
        report = folder / path.stem
        report.mkdir(exist_ok=True)
        env['FA4_REPORT'] = str(report)
        for attempt in range(args.max_attempts):
            write(WORK / 'status.json', dict(state='running', suite=args.suite, current=path.name,
                  folder=str(folder), files=summary))
            phases = {}
            events = report / 'events.jsonl'
            if events.exists():
                for line in events.read_text(encoding='utf-8').splitlines():
                    try:
                        e = json.loads(line)
                    except ValueError:
                        continue
                    if e['event'] == 'report':
                        phases.setdefault(e['nodeid'], {})[e['phase']] = e['outcome']
            done = [node for node, p in phases.items() if p.get('teardown') == 'passed' and
                    (p.get('call') == 'passed' or 'skipped' in p.values()) and 'failed' not in p.values()]
            write(report / 'done.json', done)
            env['FA4_DONE_FILE'] = str(report / 'done.json')
            code = run([sys.executable, '-m', 'pytest', str(path), '-p', 'windows_policy',
                        '-q', '--tb=short', '--maxfail=1', f'--junitxml={report / (str(attempt) + ".xml")}'],
                       report / f'attempt-{time.time_ns()}.log', cwd=folder, env=env,
                       timeout=args.worker_seconds)
            summary[path.name] = dict(exitcode=code, previously_completed=len(done), report=str(report))
            write(WORK / 'status.json', dict(state='running', suite=args.suite, current=path.name,
                  folder=str(folder), files=summary))
            print(path.name, 'attempt', attempt + 1, 'exit', code, flush=True)
            if code in (0, 5):
                break
        if code == 0 and args.suite == 'smoke' and path.name in ('test_windows_sm120.py', 'test_cuda_graph.py'):
            write(report / 'done.json', [])
            env['FLASH_ATTENTION_TEST_EXPECT_CACHED'] = '1'
            code = run([sys.executable, '-m', 'pytest', str(path), '-p', 'windows_policy',
                        '-q', '--tb=short', f'--junitxml={report / "warm.xml"}'],
                       report / 'warm.log', cwd=folder, env=env, timeout=args.worker_seconds)
            env.pop('FLASH_ATTENTION_TEST_EXPECT_CACHED')
            summary[path.name]['warm_exitcode'] = code
        if code not in (0, 5):
            summary[path.name]['needs_fix'] = True
    failed = [p for p, r in summary.items() if r.get('needs_fix')]
    write(WORK / 'status.json', dict(state='needs_fix' if failed else 'completed',
          suite=args.suite, folder=str(folder), failed_files=failed, files=summary,
          scope='Resource-reduced counterparts plus unchanged remaining tests; skips are not passes'))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
