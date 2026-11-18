"""Independent final audit of every mapped representative and phase record."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time

REPO = Path(__file__).resolve().parents[2]


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def audit(folder):
    issues = []
    details = {}
    totals = Counter()
    manifest = load(folder / 'manifest.json')
    fingerprint = hashlib.sha256()
    for base in ('flash_attn/cute', 'tests/cute', 'tools'):
        for path in sorted((REPO / base).glob('*.py')):
            fingerprint.update(str(path.relative_to(REPO)).encode())
            fingerprint.update(path.read_bytes())
    if manifest['suite'] != 'full' or fingerprint.hexdigest() != manifest['source_sha256']:
        issues.append('Manifest does not describe full validation of current source')
    architecture = manifest.get('architecture')
    if architecture:
        artifact_report = Path(manifest['wheel']).parent / 'source-audit.json'
        if not artifact_report.exists():
            issues.append('Missing wheel/sdist/installed source audit')
        else:
            artifacts = load(artifact_report)
            if not artifacts.get('passed'):
                issues.append('Distribution source audit failed')
            for name in ('wheel', 'sdist'):
                path = Path(artifacts[name])
                if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != artifacts[name + '_sha256']:
                    issues.append(f'{name} changed after source audit')
    for test in sorted((REPO / 'tests/cute').glob('test_*.py')):
        report = folder / test.stem
        required = [report / name for name in ('mapping.json', 'events.jsonl', 'verification.json')]
        missing = [str(path) for path in required if not path.exists()]
        if missing:
            issues.append(dict(file=test.name, missing=missing))
            continue
        mapping = load(required[0])
        originals = {row['original'] for row in mapping}
        expected = {row['representative'] for row in mapping}
        file_issues = []
        if len(originals) != len(mapping) or not expected <= originals:
            file_issues.append('Mapping contains duplicate original IDs or invalid representatives')
        if architecture and manifest.get('sequence_cap') == 0:
            if any(row['original'] != row['representative'] or row['original_params'] != row['effective_params'] for row in mapping):
                file_issues.append('Original-size run substituted or grouped test cases')
        phases = {}
        collection_skips = []
        historical_failures = 0
        invalid_records = 0
        latest_collection = None
        latest_finish = None
        invalidations = []
        native_images = None
        with required[1].open(encoding='utf-8') as stream:
            for line in stream:
                try:
                    entry = json.loads(line)
                except ValueError:
                    invalid_records += 1
                    continue
                kind = entry.get('event')
                if kind == 'invalidate':
                    expired = set(entry['nodeids'])
                    target = entry.get('source_sha256', '')
                    valid_digest = isinstance(target, str) and len(target) == 64 and all(c in '0123456789abcdef' for c in target)
                    if not expired <= expected or not entry.get('reason') or not valid_digest:
                        file_issues.append('Invalid source-epoch invalidation record')
                    for node in expired:
                        phases.pop(node, None)
                    invalidations.append(dict(cases=len(expired), reason=entry.get('reason'),
                                              source_sha256=target,
                                              previous_source_sha256=entry.get('previous_source_sha256')))
                elif kind == 'report':
                    node, phase = entry['nodeid'], entry['phase']
                    if phase == 'setup':
                        phases[node] = {}
                    phases.setdefault(node, {})[phase] = entry['outcome']
                    historical_failures += entry['outcome'] == 'failed'
                elif kind == 'collection':
                    latest_collection = entry
                elif kind == 'collection_report' and entry['outcome'] == 'skipped':
                    collection_skips.append(entry['details'])
                elif kind == 'sessionfinish':
                    latest_finish = entry['exitstatus']
                elif kind == 'native_images':
                    native_images = entry['images']
                elif kind == 'native_architecture_failure':
                    file_issues.append(dict(native_architecture_failure=entry['error']))
        if invalidations and invalidations[-1]['source_sha256'] != manifest['source_sha256']:
            file_issues.append('Latest invalidation does not describe the current source epoch')
        outcomes = Counter()
        unresolved = {}
        for node in expected:
            value = phases.get(node, {})
            if value == dict(setup='passed', call='passed', teardown='passed'):
                outcomes['passed'] += 1
            elif value.get('teardown') == 'passed' and (
                (value.get('setup') == 'skipped' and 'call' not in value) or
                (value.get('setup') == 'passed' and value.get('call') == 'skipped')
            ):
                outcomes['skipped'] += 1
            else:
                unresolved[node] = value
        if unresolved:
            file_issues.append(dict(incomplete_or_failed_phases=unresolved))
        if set(phases) - expected:
            file_issues.append(dict(outside_current_representatives=sorted(set(phases) - expected)))
        if invalid_records:
            file_issues.append(dict(invalid_jsonl_records=invalid_records))
        if latest_finish not in (0, 5):
            file_issues.append(dict(final_session_exitstatus=latest_finish))
        if architecture:
            allowed = {'0xaa64', '0xa641', '0xa64e'} if architecture in ('arm64', 'aarch64') else {'0x8664'}
            if not native_images or any(image['machine'] not in allowed for image in native_images):
                file_issues.append('Missing or non-native loaded-image evidence')
        if latest_collection is None or any(
            latest_collection.get(key) != value
            for key, value in (('originals', len(mapping)), ('representatives', len(expected)))
        ):
            file_issues.append('Collection inventory does not match mapping')
        if not mapping and not collection_skips:
            file_issues.append('Empty inventory without an explicit collection skip')
        verification = load(required[2])
        if verification.get('unresolved') or verification.get('originals') != len(mapping) or verification.get('representatives') != len(expected):
            file_issues.append('Supervisor verification is incomplete or disagrees with mapping')
        if file_issues:
            issues.append(dict(file=test.name, issues=file_issues))
        details[test.name] = dict(originals=len(mapping), representatives=len(expected),
                                  counts=dict(outcomes), historical_failed_reports=historical_failures,
                                  collection_skips=collection_skips, invalidations=invalidations)
        totals.update(outcomes)
    return dict(passed=not issues, source_sha256=fingerprint.hexdigest(),
                files_expected=len(list((REPO / 'tests/cute').glob('test_*.py'))),
                files_audited=len(details), counts=dict(totals),
                originals=sum(value['originals'] for value in details.values()),
                representatives=sum(value['representatives'] for value in details.values()),
                files=details, issues=issues, checked_unix=time.time(),
                sequence_cap=manifest.get('sequence_cap'), architecture=architecture,
                scope='Input sizes follow sequence_cap and mappings; collection, hardware and dependency skips are not passes')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    args = parser.parse_args()
    result = audit(args.folder.resolve())
    output = args.folder / 'independent-audit.json'
    output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in result.items() if key != 'files'}, indent=2))
    raise SystemExit(0 if result['passed'] else 1)
