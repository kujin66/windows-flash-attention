"""CPU-only checks of the Windows validation supervisor and hardware policy."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def supervisor():
    return load('native_supervisor_test', REPO / 'tools/windows_native.py')


def test_recovery_does_not_inherit_results_from_an_interrupted_retry(tmp_path, supervisor):
    events = tmp_path / 'events.jsonl'
    records = []
    for phase in ('setup', 'call', 'teardown'):
        records.append(dict(event='report', nodeid='case', phase=phase, outcome='passed'))
    records.append(dict(event='report', nodeid='case', phase='setup', outcome='passed'))
    events.write_text('\n'.join(map(json.dumps, records)) + '\n{"torn":')
    outcomes, history = supervisor.case_results(events)
    assert outcomes == {'case': 'incomplete'}
    assert history == []


def test_recovery_keeps_failure_evidence_after_a_successful_retry(tmp_path, supervisor):
    events = tmp_path / 'events.jsonl'
    records = [dict(event='report', nodeid='case', phase='call', outcome='failed', details='illegal access')]
    records += [dict(event='report', nodeid='case', phase=p, outcome='passed') for p in ('setup', 'call', 'teardown')]
    events.write_text('\n'.join(map(json.dumps, records)))
    outcomes, history = supervisor.case_results(events)
    assert outcomes == {'case': 'passed'}
    assert history[0]['details'] == 'illegal access'


def test_source_invalidation_requires_a_fresh_run_and_keeps_failures(tmp_path, supervisor):
    events = tmp_path / 'events.jsonl'
    records = [dict(event='report', nodeid='changed', phase='call', outcome='failed')]
    records += [dict(event='report', nodeid=node, phase=phase, outcome='passed')
                for node in ('changed', 'unchanged') for phase in ('setup', 'call', 'teardown')]
    records.append(dict(event='invalidate', nodeids=['changed'], reason='New reference oracle'))
    events.write_text('\n'.join(map(json.dumps, records)))
    outcomes, history = supervisor.case_results(events)
    assert outcomes == {'unchanged': 'passed'}
    assert len(history) == 1
    records += [dict(event='report', nodeid='changed', phase=p, outcome='passed')
                for p in ('setup', 'call', 'teardown')]
    events.write_text('\n'.join(map(json.dumps, records)))
    outcomes, history = supervisor.case_results(events)
    assert outcomes == {'changed': 'passed', 'unchanged': 'passed'}
    assert len(history) == 1


def test_acceptance_marks_exited_supervisor_and_pending_cases(tmp_path, supervisor, monkeypatch):
    monkeypatch.setattr(supervisor, 'WORK', tmp_path)
    folder = tmp_path / 'run'
    report = folder / 'test_example'
    report.mkdir(parents=True)
    (tmp_path / 'status.json').write_text(json.dumps(dict(state='running', suite='full', folder=str(folder))))
    records = [dict(event='collection', originals=100, representatives=3)]
    records += [dict(event='report', nodeid='case', phase=p, outcome='passed') for p in ('setup', 'call', 'teardown')]
    (report / 'events.jsonl').write_text('\n'.join(map(json.dumps, records)))
    result = supervisor.acceptance_snapshot(False)
    assert result['state'] == 'supervisor_exited'
    assert result['passed'] is False
    assert result['counts'] == {'passed': 1}
    assert result['pending_collected'] == 2


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows launcher process-tree cleanup')
def test_timeout_terminates_the_real_interpreter_child(tmp_path, supervisor):
    import ctypes
    pid_file = tmp_path / 'child.pid'
    child = f'import os,time; from pathlib import Path; Path({str(pid_file)!r}).write_text(str(os.getpid())); time.sleep(60)'
    parent = f'import subprocess,sys,time; subprocess.Popen([sys.executable,"-c",{child!r}]); time.sleep(60)'
    assert supervisor.run([sys.executable, '-c', parent], tmp_path / 'timeout.log', timeout=3) == 124
    assert pid_file.exists(), 'Test must actually start the grandchild before timeout'
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x100000, False, int(pid_file.read_text()))
    if handle:
        try:
            assert kernel.WaitForSingleObject(handle, 0) == 0
        finally:
            kernel.CloseHandle(handle)


@pytest.fixture
def policy(tmp_path, monkeypatch):
    done = tmp_path / 'done.json'
    done.write_text('[]')
    monkeypatch.setenv('FA4_REPORT', str(tmp_path))
    monkeypatch.setenv('FA4_DONE_FILE', str(done))
    module = load('native_policy_test', REPO / 'tools/windows_policy.py')
    yield module
    module.EVENTS.close()


def parameters(**extra):
    return dict(causal=False, local_enum=0, has_learnable_sink=False,
                d=128, deterministic=True, has_qv=False,
                seqlen_q=256, seqlen_k=128, **extra)


def test_deterministic_skip_requires_a_real_backward_branch(policy):
    params = parameters()
    assert policy.matrix_skip('test_flash_attn_varlen_output', params, True, 101376)
    params['local_enum'] = 1
    assert policy.matrix_skip('test_flash_attn_output', params, True, 101376) is None
    params['seqlen_k'] = 256
    assert 'deterministic backward' in policy.matrix_skip('test_flash_attn_output', params, True, 101376)


def test_hardware_policy_does_not_skip_supported_or_unknown_cases(policy):
    params = parameters()
    assert policy.matrix_skip('test_flash_attn_output', params, False, 101376) is None
    params['deterministic'] = False
    assert policy.matrix_skip('test_flash_attn_varlen_output', params, True, 101376) is None
    assert policy.matrix_skip('unrelated_test', params, True, 101376) is None
    assert policy.matrix_skip('test_flash_attn_output', {'causal': False, 'd': 128}, True, 101376) is None


@pytest.mark.skipif(sys.platform != 'win32', reason='Native Windows LockFileEx')
def test_cache_lock_excludes_another_process_and_releases(tmp_path):
    import os
    import subprocess
    backend_path = REPO / 'flash_attn/cute/_filelock.py'
    backend = load('native_lock_backend_test', backend_path)
    lock_path = tmp_path / 'cache.lock'
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
    program = (
        'import importlib.util,os,sys; '
        f'spec=importlib.util.spec_from_file_location("lock_backend",{str(backend_path)!r}); '
        'm=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); '
        f'fd=os.open({str(lock_path)!r},os.O_RDWR); '
        'm.flock(fd,m.LOCK_EX|m.LOCK_NB); os.close(fd)'
    )
    try:
        backend.flock(fd, backend.LOCK_EX | backend.LOCK_NB)
        blocked = subprocess.run([sys.executable, '-c', program], capture_output=True, timeout=15, check=False)
        assert blocked.returncode != 0
        assert b'BlockingIOError' in blocked.stderr
        backend.flock(fd, backend.LOCK_UN)
        free = subprocess.run([sys.executable, '-c', program], capture_output=True, timeout=15, check=False)
        assert free.returncode == 0, free.stderr.decode(errors='replace')
    finally:
        os.close(fd)


def test_unsupported_skip_cannot_hide_an_asynchronous_cuda_fault(policy, monkeypatch):
    fault = RuntimeError('CUDA illegal memory access')

    def synchronize():
        raise fault

    cuda = SimpleNamespace(is_initialized=lambda: True, synchronize=synchronize,
                           is_available=lambda: True, get_device_capability=lambda: (12, 0))
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(cuda=cuda, OutOfMemoryError=MemoryError))

    class Outcome:
        excinfo = (AssertionError, AssertionError('deterministic backward not supported on SM 12.0'), None)

        def force_exception(self, exception):
            self.excinfo = (type(exception), exception, None)

    outcome = Outcome()
    hook = policy.pytest_runtest_call(SimpleNamespace())
    next(hook)
    with pytest.raises(StopIteration):
        hook.send(outcome)
    assert outcome.excinfo[1] is fault
    assert 'deterministic backward not supported on SM 12.0' in '\n'.join(fault.__notes__)


@pytest.mark.parametrize('body_error', [None, RuntimeError('original kernel launch failed')])
def test_cuda_sync_fault_retains_original_body_status(policy, monkeypatch, body_error):
    fault = RuntimeError('CUDA illegal memory access')

    def synchronize():
        raise fault

    cuda = SimpleNamespace(is_initialized=lambda: True, is_available=lambda: True,
                           synchronize=synchronize, get_device_capability=lambda: (12, 0))
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(cuda=cuda, OutOfMemoryError=MemoryError))

    class Outcome:
        excinfo = (type(body_error), body_error, None) if body_error else None

        def force_exception(self, exception):
            self.excinfo = (type(exception), exception, None)

    outcome = Outcome()
    hook = policy.pytest_runtest_call(SimpleNamespace())
    next(hook)
    with pytest.raises(StopIteration):
        hook.send(outcome)
    assert outcome.excinfo[1] is fault
    notes = '\n'.join(fault.__notes__)
    if body_error:
        assert 'Original test-body exception' in notes
        assert 'original kernel launch failed' in notes
        assert 'returned normally' not in notes
    else:
        assert 'Test body returned normally' in notes


def test_cpu_mock_does_not_synchronize_an_initialized_cuda_context(policy, monkeypatch):
    def synchronize():
        pytest.fail('A CPU mock must not enter the CUDA device context')

    cuda = SimpleNamespace(is_initialized=lambda: True, is_available=lambda: False,
                           synchronize=synchronize)
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(cuda=cuda))
    outcome = SimpleNamespace(excinfo=None)
    hook = policy.pytest_runtest_call(SimpleNamespace())
    next(hook)
    with pytest.raises(StopIteration):
        hook.send(outcome)


def test_original_size_policy_retains_oom_failure(policy, monkeypatch):
    monkeypatch.setattr(policy, 'CAP', 0)
    cuda = SimpleNamespace(is_initialized=lambda: False, is_available=lambda: False)
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(cuda=cuda, OutOfMemoryError=MemoryError))
    error = MemoryError('original input cannot fit')
    outcome = SimpleNamespace(excinfo=(MemoryError, error, None))
    hook = policy.pytest_runtest_call(SimpleNamespace(funcargs={'seqlen_q': 8192}))
    next(hook)
    with pytest.raises(StopIteration):
        hook.send(outcome)
    assert outcome.excinfo[1] is error


def test_exhausted_failure_does_not_block_remaining_cases(tmp_path, supervisor):
    events = tmp_path / 'events.jsonl'
    records = [dict(event='report', nodeid='bad', phase='call', outcome='failed')] * 3
    records += [dict(event='report', nodeid='good', phase=p, outcome='passed') for p in ('setup', 'call', 'teardown')]
    events.write_text('\n'.join(map(json.dumps, records)))
    assert set(supervisor.completed_for_resume(events, 3)) == {'bad', 'good'}
    outcomes, history = supervisor.case_results(events)
    assert outcomes == {'bad': 'failed', 'good': 'passed'}
    assert len(history) == 3


def test_full_loop_visits_case_after_exhausted_failure(tmp_path, supervisor, monkeypatch):
    monkeypatch.setattr(supervisor, 'REPO', tmp_path)
    monkeypatch.setattr(supervisor, 'WORK', tmp_path / 'work')
    supervisor.WORK.mkdir()
    tests = tmp_path / 'tests/cute'
    tests.mkdir(parents=True)
    (tests / 'test_one.py').write_text('# synthetic worker')
    monkeypatch.setitem(sys.modules, 'windows_architecture', SimpleNamespace(toolchain=lambda: []))
    attempts = []

    def worker(command, log, **kwargs):
        if 'build' in command:
            dist = Path(command[command.index('--outdir') + 1])
            dist.mkdir(parents=True)
            (dist / 'test.whl').write_bytes(b'synthetic wheel')
        elif 'pytest' in command:
            env = kwargs['env']
            report = Path(env['FA4_REPORT'])
            done = json.loads(Path(env['FA4_DONE_FILE']).read_text())
            node = 'bad' if 'bad' not in done else 'good'
            attempts.append(node)
            mapping = [dict(original=n, representative=n) for n in ('bad', 'good')]
            (report / 'mapping.json').write_text(json.dumps(mapping))
            with (report / 'events.jsonl').open('a') as output:
                for phase in ('setup', 'call', 'teardown'):
                    outcome = 'failed' if node == 'bad' and phase == 'call' else 'passed'
                    output.write(json.dumps(dict(event='report', nodeid=node, phase=phase, outcome=outcome)) + '\n')
            return 1 if node == 'bad' else 0
        return 0

    monkeypatch.setattr(supervisor, 'run', worker)
    monkeypatch.setattr(supervisor.subprocess, 'check_output', lambda *a, **k: 'synthetic-head')
    args = SimpleNamespace(suite='full', sequence_cap=0, max_attempts=3, worker_seconds=10)
    assert supervisor.validate(args) == 1
    assert attempts == ['bad', 'bad', 'bad', 'good']
    state = json.loads((supervisor.WORK / 'status.json').read_text())
    verification = json.loads((Path(state['folder']) / 'test_one/verification.json').read_text())
    assert verification['unresolved'] == {'bad': 'failed'}
    assert verification['counts'] == {'failed': 1, 'passed': 1}


def test_resume_rejects_changed_numerical_sources(tmp_path, supervisor, monkeypatch):
    previous = tmp_path / 'old'
    previous.mkdir()
    import platform
    manifest = dict(git_status='', suite='full', sequence_cap=0, architecture=platform.machine().lower(), head='old-head')
    (previous / 'manifest.json').write_text(json.dumps(manifest))
    monkeypatch.setattr(supervisor.subprocess, 'check_output', lambda *a, **k: 'changed kernel')
    args = SimpleNamespace(suite='full', sequence_cap=0)
    with pytest.raises(RuntimeError, match='numerical sources'):
        supervisor.resume_evidence(previous, tmp_path / 'new', args, 'a' * 64)
    assert not (tmp_path / 'new').exists()


def test_invalidated_failures_receive_a_fresh_retry_budget(tmp_path, supervisor):
    events = tmp_path / 'events.jsonl'
    records = [dict(event='report', nodeid='bad', phase='call', outcome='failed')] * 3
    records.append(dict(event='invalidate', nodeids=['bad']))
    records.append(dict(event='report', nodeid='bad', phase='call', outcome='failed'))
    events.write_text('\n'.join(map(json.dumps, records)))
    assert supervisor.completed_for_resume(events, 3) == []
    assert len(supervisor.case_results(events)[1]) == 4


def test_workspace_temp_ignores_an_unusable_shared_temp_root(tmp_path, supervisor, monkeypatch):
    import os
    import subprocess
    blocked = tmp_path / 'not-a-directory'
    blocked.write_text('A shared temp root must not be required')
    monkeypatch.setenv('PYTEST_DEBUG_TEMPROOT', str(blocked))
    test = tmp_path / 'test_temp_fixture.py'
    test.write_text('def test_temp(tmp_path):\n    (tmp_path / "probe").write_text("ok")\n')
    result = subprocess.run([sys.executable, '-m', 'pytest', str(test), '-q',
                             *supervisor.pytest_workspace_args(tmp_path / 'worker')],
                            capture_output=True, text=True, timeout=30, env=os.environ.copy())
    assert result.returncode == 0, result.stdout + result.stderr
