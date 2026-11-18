"""Incomplete or interrupted phase evidence must not certify a full run."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    'phases,count,collection_skip,expected',
    [
        (('setup', 'call', 'teardown'), 1, False, True),
        (('call', 'teardown'), 1, False, False),
        (('setup', 'call', 'teardown', 'setup'), 1, False, False),
        (('setup', 'call', 'teardown'), 2, False, False),
        ((), 0, False, False),
        ((), 0, True, True),
    ],
    ids=['complete', 'missing-setup', 'interrupted-retry', 'missing-case',
         'silent-empty-file', 'explicit-collection-skip'],
)
def test_full_evidence_gate(tmp_path, monkeypatch, phases, count, collection_skip, expected):
    spec = importlib.util.spec_from_file_location('audit_fixture', Path(__file__).with_name('evidence_audit.py'))
    auditor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(auditor)
    monkeypatch.setattr(auditor, 'REPO', tmp_path)
    source = tmp_path / 'tests/cute/test_one.py'
    source.parent.mkdir(parents=True)
    source.write_text('# synthetic evidence fixture only', encoding='utf-8')
    fingerprint = hashlib.sha256(str(source.relative_to(tmp_path)).encode() + source.read_bytes()).hexdigest()
    report = tmp_path / 'report'
    file_report = report / 'test_one'
    file_report.mkdir(parents=True)
    (report / 'manifest.json').write_text(json.dumps(dict(suite='full', source_sha256=fingerprint)))
    mapping = [dict(original=f'case{i}', representative=f'case{i}') for i in range(count)]
    (file_report / 'mapping.json').write_text(json.dumps(mapping))
    records = [dict(event='collection', originals=count, representatives=count)]
    records += [dict(event='report', nodeid='case0', phase=phase, outcome='passed') for phase in phases]
    if collection_skip:
        records.append(dict(event='collection_report', outcome='skipped', details='explicit dependency skip'))
    records.append(dict(event='sessionfinish', exitstatus=0 if count else 5))
    (file_report / 'events.jsonl').write_text('\n'.join(map(json.dumps, records)))
    (file_report / 'verification.json').write_text(json.dumps(dict(originals=count, representatives=count, unresolved={})))
    result = auditor.audit(report)
    assert result['passed'] is expected
    assert result['files_expected'] == result['files_audited'] == 1
    assert result['representatives'] == count
    if not count:
        assert result['counts'] == {}, 'A collection skip must never produce a numerical pass'
    elif phases == ('setup', 'call', 'teardown'):
        assert result['counts'] == {'passed': 1}


def test_invalidation_preserves_history_and_requires_current_phase_evidence(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('audit_epoch', Path(__file__).with_name('evidence_audit.py'))
    auditor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(auditor)
    monkeypatch.setattr(auditor, 'REPO', tmp_path)
    source = tmp_path / 'tests/cute/test_one.py'
    source.parent.mkdir(parents=True)
    source.write_text('# source epoch fixture', encoding='utf-8')
    fingerprint = hashlib.sha256(str(source.relative_to(tmp_path)).encode() + source.read_bytes()).hexdigest()
    report = tmp_path / 'report'
    case = report / 'test_one'
    case.mkdir(parents=True)
    (report / 'manifest.json').write_text(json.dumps(dict(suite='full', source_sha256=fingerprint)))
    (case / 'mapping.json').write_text(json.dumps([dict(original='case0', representative='case0')]))
    (case / 'verification.json').write_text(json.dumps(dict(originals=1, representatives=1, unresolved={})))
    records = [dict(event='collection', originals=1, representatives=1),
               dict(event='report', nodeid='case0', phase='call', outcome='failed')]
    records += [dict(event='report', nodeid='case0', phase=p, outcome='passed') for p in ('setup', 'call', 'teardown')]
    records.append(dict(event='invalidate', nodeids=['case0'], reason='Historical epoch',
                        source_sha256='a' * 64, previous_source_sha256='previous'))
    records += [dict(event='report', nodeid='case0', phase=p, outcome='passed') for p in ('setup', 'call', 'teardown')]
    records += [dict(event='sessionfinish', exitstatus=0),
                dict(event='invalidate', nodeids=['case0'], reason='Changed oracle',
                     source_sha256=fingerprint, previous_source_sha256='previous')]
    (case / 'events.jsonl').write_text('\n'.join(map(json.dumps, records)))
    result = auditor.audit(report)
    assert result['passed'] is False
    assert result['files']['test_one.py']['historical_failed_reports'] == 1
    records += [dict(event='report', nodeid='case0', phase=p, outcome='passed') for p in ('setup', 'call', 'teardown')]
    records.append(dict(event='sessionfinish', exitstatus=0))
    (case / 'events.jsonl').write_text('\n'.join(map(json.dumps, records)))
    result = auditor.audit(report)
    assert result['passed'] is True
    assert result['counts'] == {'passed': 1}
    assert result['files']['test_one.py']['historical_failed_reports'] == 1
    assert len(result['files']['test_one.py']['invalidations']) == 2
