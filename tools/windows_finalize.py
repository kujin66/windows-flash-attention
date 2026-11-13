"""Create only a Draft PR after original-size GPU acceptance and exact-head CI."""
import json
import subprocess
import sys
import time

from windows_artifacts import audit as audit_artifacts
from windows_native import REPO, WORK, source_fingerprint, write


def command(*args):
    return subprocess.check_output(list(map(str, args)), cwd=REPO, text=True).strip()


def gh_json(*args):
    return json.loads(command('gh', *args))


def require_full_acceptance(folder):
    result = json.loads((folder / 'independent-audit.json').read_text(encoding='utf-8'))
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    if (not result.get('passed') or result.get('issues')
            or result.get('files_expected') != result.get('files_audited')
            or result.get('files_audited', 0) == 0
            or manifest.get('suite') != 'full' or manifest.get('sequence_cap') != 0
            or manifest.get('architecture') not in ('arm64', 'aarch64')
            or result.get('source_sha256') != source_fingerprint()
            or manifest.get('source_sha256') != source_fingerprint()):
        raise RuntimeError('Draft PR blocked: full current-source original-size ARM64 acceptance is missing')
    return result, manifest


def finalize(folder, repository):
    result, manifest = require_full_acceptance(folder)
    if command('git', 'status', '--porcelain'):
        raise RuntimeError('Draft PR blocked: commit reviewed source changes before finalization')
    branch = command('git', 'branch', '--show-current')
    base = gh_json('api', f'repos/{repository}')['default_branch']
    if not branch or branch == base:
        raise RuntimeError('Draft PR requires a development branch')
    report = REPO / 'flash_attn/cute/WINDOWS_ARM64_VALIDATION.md'
    counts = result['counts']
    lines = ['# Native Windows ARM64 FA4 validation', '',
             f'Numerical source fingerprint: `{result["source_sha256"]}`.',
             f'Numerical validation started from commit `{manifest["head"]}`.',
             'Every original test ID retained its input sizes. Hardware and upstream',
             'exclusions remain skips and are not numerical passes.', '',
             f'Full suite: {result["files_audited"]} files; {result["originals"]:,} original IDs;',
             f'{counts.get("passed", 0):,} passed; {counts.get("skipped", 0):,} skipped.',
             'Independent current-source, phase-coverage, native-image and artifact audit passed.', '',
             '| File | Original IDs | Passed | Skipped | Historical failure reports |',
             '| --- | ---: | ---: | ---: | ---: |']
    for name, value in result['files'].items():
        c = value['counts']
        lines.append(f'| {name} | {value["originals"]} | {c.get("passed", 0)} | {c.get("skipped", 0)} | {value["historical_failed_reports"]} |')
    lines += ['', 'Evidence is retained in the local `agent_space/windows-native` run directory.',
              'Final CI must pass at the PR head and both downloaded architecture artifacts',
              'must match package sources before the loop creates the Draft PR.',
              'The dedicated environment reuses existing native dependencies; this is not',
              'a clean-machine installation certificate. SM121 validation does not certify',
              'SM90/SM100-only kernels or resolve the historical x64 GPU anomalies.']
    report.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    command('git', 'add', str(report))
    command('git', 'commit', '-m', 'Record completed native ARM64 FA4 validation', '--', str(report))
    head = command('git', 'rev-parse', 'HEAD')
    state = dict(state='cpu_checks', head=head, source_sha256=result['source_sha256'], full_report=str(folder))
    write(WORK / 'finalization.json', state)
    with (folder / 'final-cpu.log').open('w', encoding='utf-8') as output:
        subprocess.run([sys.executable, '-m', 'pytest', str(REPO / 'tests/windows'), '-q',
                        '-o', f'cache_dir={WORK / "cpu-cache"}'], cwd=REPO, stdout=output, stderr=subprocess.STDOUT, check=True)
    command('git', 'push', 'origin', f'HEAD:refs/heads/{branch}')
    state['state'] = 'waiting_for_ci'
    write(WORK / 'finalization.json', state)
    deadline = time.monotonic() + 2700
    run = None
    while time.monotonic() < deadline:
        runs = gh_json('run', 'list', '--repo', repository, '--branch', branch, '--commit', head,
                       '--limit', '20', '--json', 'databaseId,name,status,conclusion,headSha,url')
        candidates = [r for r in runs if r['name'] == 'Windows native FA4 build' and r['headSha'] == head]
        if candidates:
            run = candidates[0]
            if run['status'] == 'completed':
                break
        time.sleep(20)
    if not run or run['status'] != 'completed' or run['conclusion'] != 'success':
        raise RuntimeError(f'Draft PR blocked: final-head Windows CI did not succeed: {run}')
    jobs = gh_json('run', 'view', str(run['databaseId']), '--repo', repository, '--json', 'jobs')['jobs']
    for architecture in ('arm64', 'x64'):
        if not any(architecture in j['name'] and j['conclusion'] == 'success' for j in jobs):
            raise RuntimeError(f'Draft PR blocked: {architecture} CI job missing')
    dist = folder / f'ci-{head[:12]}-{run["databaseId"]}'
    if not dist.exists():
        command('gh', 'run', 'download', str(run['databaseId']), '--repo', repository, '--dir', str(dist))
    artifacts = {}
    for architecture in ('arm64', 'x64'):
        audit = audit_artifacts(dist / f'windows-{architecture}-flash-attn-4')
        if not audit['passed']:
            raise RuntimeError(f'Draft PR blocked: CI/source mismatch: {audit}')
        artifacts[architecture] = audit
    require_full_acceptance(folder)
    if command('git', 'rev-parse', 'HEAD') != head or command('git', 'status', '--porcelain'):
        raise RuntimeError('Draft PR blocked: source changed during final CI')
    body = folder / 'draft-pr-body.md'
    body.write_text(
        'Native Windows ARM64 FA4 now builds from the existing PEP 517 package and validates every original FA4 test ID with native PE/COFF evidence. The resumable loop preserves failed cases, checks full phase coverage and compares both final CI artifacts with source.\n\n'
        f'Validation: {result["originals"]:,} original IDs across {result["files_audited"]} files; {counts.get("passed", 0):,} passed, {counts.get("skipped", 0):,} explicit skips. Independent full audit passed. Final CPU regressions passed.\n\n'
        f'Numerical fingerprint: `{result["source_sha256"]}`. Final source commit: `{head}`. [Final x64/ARM64 CI]({run["url"]}) passed; downloaded wheel/sdist package sources match the checkout on both architectures.\n\n'
        'See `flash_attn/cute/WINDOWS_ARM64_VALIDATION.md` for per-file results and historical failure counts. Existing x64 anomalies remain documented. Draft only: review is required before any merge.\n', encoding='utf-8')
    existing = gh_json('pr', 'list', '--repo', repository, '--head', branch, '--state', 'open',
                       '--json', 'number,isDraft,url')
    if existing:
        if len(existing) != 1 or not existing[0]['isDraft']:
            raise RuntimeError('Existing PR is not an unambiguous Draft; manual review required')
        command('gh', 'pr', 'edit', str(existing[0]['number']), '--repo', repository, '--body-file', str(body))
        url = existing[0]['url']
    else:
        url = command('gh', 'pr', 'create', '--repo', repository, '--draft', '--base', base, '--head', branch,
                      '--title', 'Add native Windows ARM64 FA4 support and full validation loop', '--body-file', str(body))
    pr = gh_json('pr', 'view', url, '--repo', repository, '--json', 'isDraft,headRefOid,url,state')
    if not pr['isDraft'] or pr['headRefOid'] != head or pr['state'] != 'OPEN':
        raise RuntimeError(f'Unexpected final Draft PR state: {pr}')
    state.update(state='draft_created', pr=pr, ci=run, artifacts=artifacts)
    write(WORK / 'finalization.json', state)
    print(f'Draft PR created: {pr["url"]}', flush=True)
