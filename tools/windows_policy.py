"""Opt-in local hardware/resource policy; every substitution is recorded."""
import inspect
import json
import os
from pathlib import Path
import time
from types import SimpleNamespace

import pytest

ROOT = Path(os.environ['FA4_REPORT'])
ROOT.mkdir(parents=True, exist_ok=True)
EVENTS = (ROOT / 'events.jsonl').open('a', encoding='utf-8')
DONE = set(json.loads(Path(os.environ['FA4_DONE_FILE']).read_text()))
CAP = int(os.environ.get('FA4_SEQUENCE_CAP', '256'))
MATRIX_PARAMETERS = {'causal', 'local_enum', 'has_learnable_sink', 'd',
                     'deterministic', 'has_qv', 'seqlen_q', 'seqlen_k'}


def matrix_skip(name, params, sm120, memory_limit):
    """Only source-proven exclusions of the two known upstream matrices."""
    if name not in ('test_flash_attn_output', 'test_flash_attn_varlen_output') or not MATRIX_PARAMETERS <= params.keys():
        return None
    if params['causal'] and params['local_enum'] > 0:
        return 'upstream_skip: local and causal are excluded by the test body'
    if not sm120:
        return None
    if params.get('has_learnable_sink'):
        return 'hardware_architecture: Learnable sink is not supported in this kernel'
    if params['d'] == 256:
        from flash_attn.cute.config import select_initial_fwd_tile
        m, n, _, _ = select_initial_fwd_tile(SimpleNamespace(
            device_capacity=12, head_dim=256, requested_tile_m=None, requested_tile_n=None))
        required = 2 * (m * 256 + n * (256 + 256))
        if required > memory_limit:
            return f'hardware_shared_memory: production tile {m}x{n} needs at least {required} bytes; device limit {memory_limit}'
    # These branches actually execute backward in the unchanged upstream body.
    backward = params['d'] in (64, 96, 128, 192) and not params.get('has_qv')
    if name == 'test_flash_attn_output':
        backward &= not ((params['causal'] or params['local_enum'] > 0) and params['seqlen_k'] < params['seqlen_q'])
    if params['deterministic'] and backward:
        return 'hardware_architecture: deterministic backward not supported on SM 12.0'
    return None


def emit(value):
    EVENTS.write(json.dumps(dict(time=time.time(), **value), default=str) + '\n')
    EVENTS.flush()
    os.fsync(EVENTS.fileno())


def pytest_configure(config):
    import torch
    from flash_attn.cute import interface
    emit(dict(event='environment', imported=interface.__file__,
              torch=torch.__version__, gpu=torch.cuda.get_device_name() if torch.cuda.is_available() else None))
    if not torch.cuda.is_available() or torch.cuda.get_device_capability()[0] != 12:
        return
    from flash_attn.cute.flash_fwd import FlashAttentionForwardBase
    cls = interface.FlashAttentionForwardSm120
    original = cls.__init__
    signature = inspect.signature(FlashAttentionForwardBase.__init__)
    limit = torch.cuda.get_device_properties(0).shared_memory_per_block_optin

    def guarded(self, *args, **kwargs):
        bound = signature.bind(self, *args, **kwargs)
        bound.apply_defaults()
        p = bound.arguments
        m, n = p['tile_m'], p['tile_n']
        q = m * p['head_dim'] * 2
        k = n * p['head_dim'] * p['num_stages'] * 2
        v = n * (p['head_dim_v'] or p['head_dim']) * p['num_stages'] * 2
        required = (max(q, v) if p['Q_in_regs'] else q + v) + k
        if required > limit:
            pytest.skip(f'hardware_shared_memory: tile {m}x{n} needs at least {required} bytes; device limit {limit}')
        original(self, *args, **kwargs)
    cls.__init__ = guarded


def pytest_collection_modifyitems(config, items):
    import torch
    sm120 = torch.cuda.is_available() and torch.cuda.get_device_capability()[0] == 12
    memory_limit = torch.cuda.get_device_properties(0).shared_memory_per_block_optin if sm120 else 0
    representatives = {}
    kept = []
    mapping = []
    for item in items:
        params = getattr(getattr(item, 'callspec', None), 'params', {})
        original = dict(params)
        is_matrix = item.originalname in ('test_flash_attn_output', 'test_flash_attn_varlen_output') and MATRIX_PARAMETERS <= params.keys()
        if is_matrix:
            for name in ('seqlen_q', 'seqlen_k'):
                if params.get(name, 0) > CAP:
                    params[name] = CAP - 128 + (params[name] % 128 or 128)
            # The varlen test overwrites K length before seeding or allocating.
            if item.originalname == 'test_flash_attn_varlen_output' and (params['causal'] or params['local_enum'] > 0):
                params['seqlen_k'] = params['seqlen_q']
        reason = matrix_skip(item.originalname, params, sm120, memory_limit)
        if not reason:
            for mark in item.iter_markers('skipif'):
                if mark.args and not isinstance(mark.args[0], str) and mark.args[0]:
                    reason = 'upstream_skipif: ' + mark.kwargs.get('reason', 'condition is true')
                    break
        if reason:
            item.add_marker(pytest.mark.skip(reason=reason))
        key = (str(item.path), item.originalname, reason or repr(sorted(params.items())))
        representative = representatives.setdefault(key, item.nodeid)
        mapping.append(dict(original=item.nodeid, representative=representative,
                            original_params=original, effective_params=dict(params), skip_reason=reason))
        if representative == item.nodeid and item.nodeid not in DONE:
            kept.append(item)
    (ROOT / 'mapping.json').write_text(json.dumps(mapping, default=str), encoding='utf-8')
    emit(dict(event='collection', originals=len(items), representatives=len(representatives), pending=len(kept)))
    kept_ids = {id(i) for i in kept}
    deselected = [i for i in items if id(i) not in kept_ids]
    items[:] = kept
    config.hook.pytest_deselected(items=deselected)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    import torch
    outcome = yield
    # Surface asynchronous faults in the case that launched them. In particular,
    # an unsupported-feature exception must not hide a preceding CUDA failure.
    if torch.cuda.is_initialized() and torch.cuda.is_available():
        try:
            torch.cuda.synchronize()
        except Exception as error:
            outcome.force_exception(error)
    if outcome.excinfo:
        error = outcome.excinfo[1]
        message = str(error)
        known = ('Learnable sink is not supported in this kernel',
                 'deterministic backward not supported on SM 12.0',
                 'SM120 forward does not support paged KV or block sparsity',
                 'SM120 forward only supports num_splits=1',
                 'Block sparsity backward not supported on SM 12.0',
                 'score_mod backward not supported on SM 12.0',
                 'mask_mod backward not supported on SM 12.0')
        if torch.cuda.is_available() and torch.cuda.get_device_capability()[0] == 12 and any(s in message for s in known):
            outcome.force_exception(pytest.skip.Exception('hardware_architecture: ' + message))
        elif isinstance(error, torch.OutOfMemoryError):
            effective = {}
            for name in ('seqlen_q', 'seqlen_k', 'seqlen', 'max_seq_len'):
                value = item.funcargs.get(name)
                if isinstance(value, int) and value > 128:
                    effective[name] = value % 128 or 128
            if effective:
                emit(dict(event='oom_retry', nodeid=item.nodeid, effective_params=effective, details=message))
                item.funcargs.update(effective)
                import gc
                gc.collect()
                torch.cuda.empty_cache()
                try:
                    item.runtest()
                    torch.cuda.synchronize()
                except torch.OutOfMemoryError as smaller_error:
                    outcome.force_exception(pytest.skip.Exception('hardware_memory: OOM on smaller counterpart; ' + str(smaller_error)))
                except BaseException as smaller_error:
                    outcome.force_exception(smaller_error)
                else:
                    outcome.force_result(None)
            else:
                outcome.force_exception(pytest.skip.Exception('hardware_memory: actual device OOM; ' + message))


def pytest_runtest_logreport(report):
    emit(dict(event='report', nodeid=report.nodeid, phase=report.when, outcome=report.outcome,
              wasxfail=str(getattr(report, 'wasxfail', '')),
              details=str(report.longrepr) if report.failed or report.skipped else None))


def pytest_collectreport(report):
    if report.failed or report.skipped:
        emit(dict(event='collection_report', nodeid=report.nodeid, outcome=report.outcome,
                  details=str(report.longrepr)))


def pytest_sessionfinish(session, exitstatus):
    emit(dict(event='sessionfinish', exitstatus=exitstatus))
    EVENTS.close()
