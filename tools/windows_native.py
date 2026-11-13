"""Build the existing FA4 pyproject, install its wheel, resume real tests."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import threading
import time

REPO = Path(__file__).resolve().parents[1]
WORK = REPO / 'agent_space' / 'windows-native'


def case_results(events):
    phases = {}
    failures = []
    if events.exists():
        for line in events.read_text(encoding='utf-8').splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue  # Recover complete records preceding a torn final write.
            if event.get('event') == 'invalidate':
                for node in event['nodeids']:
                    phases.pop(node, None)
                continue  # Source changes expire outcomes, never historical failures.
            if event.get('event') != 'report':
                continue
            node, phase = event['nodeid'], event['phase']
            if phase == 'setup':
                phases[node] = {}  # A new attempt must not inherit old call/teardown.
            phases.setdefault(node, {})[phase] = event['outcome']
            if event['outcome'] == 'failed':
                failures.append(event)
    outcomes = {}
    for node, value in phases.items():
        if 'failed' in value.values():
            outcomes[node] = 'failed'
        elif value.get('teardown') != 'passed':
            outcomes[node] = 'incomplete'
        elif 'skipped' in value.values():
            outcomes[node] = 'skipped'
        elif value.get('call') == 'passed':
            outcomes[node] = 'passed'
        else:
            outcomes[node] = 'incomplete'
    return outcomes, failures


def completed_for_resume(events, max_attempts):
    outcomes, history = case_results(events)
    failures = Counter(entry['nodeid'] for entry in history)
    # Exhausted failures remain failures in verification; excluding them lets
    # every other original test run instead of repeatedly aborting one file.
    return [node for node, outcome in outcomes.items()
            if outcome in ('passed', 'skipped')
            or (outcome == 'failed' and failures[node] >= max_attempts)]


def write(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temporary.replace(path)


def acceptance_snapshot(alive):
    status = json.loads((WORK / 'status.json').read_text(encoding='utf-8'))
    folder = Path(status['folder'])
    counts = Counter()
    inventories = {}
    historical_failures = 0
    for events in folder.glob('test_*/events.jsonl'):
        outcomes, history = case_results(events)
        counts.update(outcomes.values())
        historical_failures += len(history)
        for line in events.read_text(encoding='utf-8').splitlines():
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if entry.get('event') == 'collection':
                inventories[events.parent.name] = {key: entry[key] for key in ('originals', 'representatives')}
    representatives = sum(value['representatives'] for value in inventories.values())
    resolved = counts['passed'] + counts['skipped']
    return dict(state=status['state'] if alive or status['state'] in ('completed', 'needs_fix', 'build_failed', 'supervisor_error') else 'supervisor_exited',
                supervisor_alive=alive, supervisor_pid=os.getpid(),
                passed=status['state'] == 'completed' and not counts['failed'] and not counts['incomplete'],
                suite=status['suite'], counts=dict(counts), historical_failed_reports=historical_failures,
                pending_collected=max(0, representatives - resolved), inventories=inventories,
                test_files_total=len(list((REPO / 'tests/cute').glob('test_*.py'))) if status['suite'] == 'full' else 4,
                test_files_reported=len(status.get('files', {})), source_report=str(folder),
                updated_unix=time.time(),
                scope='See manifest.sequence_cap and mapping.json for input sizes; hardware skips are not passes')


def monitor_acceptance(stop):
    while not stop.is_set():
        try:
            write(WORK / 'acceptance.json', acceptance_snapshot(True))
        except (OSError, ValueError, KeyError):
            pass  # Status and event writers may be replacing a checkpoint.
        stop.wait(30)


def run(command, log, **kwargs):
    timeout = kwargs.pop('timeout', None)
    with log.open('w', encoding='utf-8') as output:
        worker = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT, **kwargs)
        try:
            return worker.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            # A Windows venv launcher has a real interpreter child. Kill the
            # whole tree before starting another CUDA worker.
            subprocess.run(['taskkill', '/PID', str(worker.pid), '/T', '/F'],
                           stdout=output, stderr=subprocess.STDOUT, check=False)
            worker.wait()
            output.write('\nWorker timeout; durable case reports will be recovered.\n')
            return 124


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', choices=('smoke', 'full'), default='full')
    parser.add_argument('--max-attempts', type=int, default=3)
    parser.add_argument('--worker-seconds', type=int, default=1800)
    parser.add_argument('--sequence-cap', type=int, default=0,
                        help='Optional reduced matrix; 0 preserves every original input size')
    args = parser.parse_args()
    if sys.platform != 'win32' or platform.machine().lower() not in ('amd64', 'x86_64', 'arm64', 'aarch64'):
        parser.error('Native Windows x64 or ARM64 Python required')
    if args.sequence_cap != 0 and args.sequence_cap < 128:
        parser.error('--sequence-cap must be 0 or at least 128')
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
        stop = threading.Event()
        monitor = threading.Thread(target=monitor_acceptance, args=(stop,), daemon=True)
        monitor.start()
        try:
            return validate(args)
        except BaseException as error:
            if (WORK / 'status.json').exists():
                state = json.loads((WORK / 'status.json').read_text())
                state.update(state='supervisor_error', error=repr(error))
                write(WORK / 'status.json', state)
            raise
        finally:
            stop.set()
            monitor.join()
            if (WORK / 'status.json').exists():
                write(WORK / 'acceptance.json', acceptance_snapshot(False))


def validate(args):
    from windows_architecture import toolchain
    tools = toolchain()
    digest = hashlib.sha256()
    for base in ('flash_attn/cute', 'tests/cute', 'tools'):
        for path in sorted((REPO / base).glob('*.py')):
            digest.update(str(path.relative_to(REPO)).encode())
            digest.update(path.read_bytes())
    architecture = platform.machine().lower()
    folder = WORK / (digest.hexdigest()[:16] + '-' + architecture + '-' + args.suite
                     + f'-cap{args.sequence_cap}')
    folder.mkdir(exist_ok=True)
    write(WORK / 'status.json', dict(state='building', suite=args.suite, folder=str(folder)))
    dist = folder / 'builds' / str(time.time_ns())
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
          python=sys.version, platform=platform.platform(), suite=args.suite,
          architecture=architecture, sequence_cap=args.sequence_cap,
          tools=tools,
          git_status=subprocess.check_output(['git', 'status', '--short'], cwd=REPO, text=True)))
    env = os.environ.copy()
    env.update(PYTHONPATH=str(REPO / 'tools'), PYTHONUNBUFFERED='1',
               FLASH_ATTENTION_FAKE_TENSOR='0', FA4_SEQUENCE_CAP=str(args.sequence_cap),
               FLASH_ATTENTION_CUTE_DSL_CACHE_ENABLED='1',
               FLASH_ATTENTION_CUTE_DSL_CACHE_DIR=str(WORK / (architecture + '-kernel-cache')))
    probe = 'import sys; from pathlib import Path; import flash_attn.cute as m; print(m.__file__); assert Path(m.__file__).is_relative_to(Path(sys.prefix))'
    if run([sys.executable, '-c', probe], folder / 'import.log', cwd=folder, env=env):
        raise SystemExit('Installed FA4 wheel import failed; inspect import.log')
    if run([sys.executable, REPO / 'tools/windows_artifacts.py', '--dist', str(dist),
            '--installed', str(Path(sys.prefix) / 'Lib/site-packages/flash_attn/cute')],
           folder / 'source-audit.log', cwd=folder, env=env):
        raise SystemExit('Wheel/sdist/installed sources differ')
    paths = sorted((REPO / 'tests/cute').glob('test_*.py'))
    if args.suite == 'smoke':
        names = ('test_windows_filelock.py', 'test_windows_sm120.py', 'test_cuda_graph.py', 'test_cache_utils.py')
        paths = [REPO / 'tests/cute' / name for name in names]
    summary = {}
    for path in paths:
        report = folder / path.stem
        report.mkdir(exist_ok=True)
        env['FA4_REPORT'] = str(report)
        attempt = 0
        previous_completed = -1
        while attempt < args.max_attempts:
            write(WORK / 'status.json', dict(state='running', suite=args.suite, current=path.name,
                  folder=str(folder), files=summary))
            events = report / 'events.jsonl'
            done = completed_for_resume(events, args.max_attempts)
            if len(done) > previous_completed:
                attempt = 0
            previous_completed = len(done)
            attempt += 1
            write(report / 'done.json', done)
            env['FA4_DONE_FILE'] = str(report / 'done.json')
            code = run([sys.executable, '-m', 'pytest', str(path), '-p', 'windows_policy',
                        '-q', '--tb=short', '--maxfail=1', f'--junitxml={report / (str(time.time_ns()) + ".xml")}'],
                       report / f'attempt-{time.time_ns()}.log', cwd=folder, env=env,
                       timeout=args.worker_seconds)
            summary[path.name] = dict(exitcode=code, previously_completed=len(done), report=str(report))
            write(WORK / 'status.json', dict(state='running', suite=args.suite, current=path.name,
                  folder=str(folder), files=summary))
            print(path.name, 'attempt', attempt, 'exit', code, flush=True)
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
        outcomes, history = case_results(report / 'events.jsonl')
        mapping = json.loads((report / 'mapping.json').read_text()) if (report / 'mapping.json').exists() else []
        collection_skips = []
        if (report / 'events.jsonl').exists():
            for line in (report / 'events.jsonl').read_text().splitlines():
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if entry.get('event') == 'collection_report' and entry['outcome'] == 'skipped':
                    collection_skips.append(entry)
        expected = {entry['representative'] for entry in mapping}
        unresolved = {node: outcomes.get(node, 'missing') for node in expected
                      if outcomes.get(node) not in ('passed', 'skipped')}
        write(report / 'verification.json', dict(originals=len(mapping), representatives=len(expected),
              counts={kind: list(outcomes.values()).count(kind) for kind in set(outcomes.values())},
              unresolved=unresolved, historical_failed_reports=history, collection_skips=collection_skips))
        summary[path.name].update(originals=len(mapping), representatives=len(expected), unresolved=len(unresolved))
        if code not in (0, 5) or unresolved or (not mapping and not collection_skips):
            summary[path.name]['needs_fix'] = True
    failed = [p for p, r in summary.items() if r.get('needs_fix')]
    write(WORK / 'status.json', dict(state='needs_fix' if failed else 'completed',
          suite=args.suite, folder=str(folder), failed_files=failed, files=summary,
          scope=('Original input sizes' if not args.sequence_cap else 'Resource-reduced counterparts')
                + '; hardware skips are not passes'))
    if args.suite == 'full':
        audit_code = run([sys.executable, REPO / 'tests/windows/evidence_audit.py', str(folder)],
                         folder / 'independent-audit.log', cwd=folder, env=env)
        if audit_code:
            state = json.loads((WORK / 'status.json').read_text())
            state.update(state='needs_fix', independent_audit_exitcode=audit_code)
            write(WORK / 'status.json', state)
            return 1
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
