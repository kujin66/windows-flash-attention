# GitHub Workflow Tagging Flow

This repository uses separate tag lanes so FA2 and FA4 publishing do not collide.

## Release lanes

| Tag pattern | Workflow | Package target | Version source |
| --- | --- | --- | --- |
| `v*` | `.github/workflows/publish.yml` | Root package (`flash-attn`) | Root package version metadata |
| `fa4-v*` | `.github/workflows/publish-fa4.yml` | `flash_attn/cute` package (`flash-attn-4`) | `setuptools-scm` with `fa4-v*` tags |

## How to publish

### FA2 / root package lane

1. Create a tag matching `v*` (example: `v2.9.0`).
2. Push that tag.
3. `publish.yml` creates a release, builds wheel matrix artifacts, and publishes to PyPI.

### FA4 / CUTE package lane

**Manual release**: create and push a tag matching `fa4-v*` (example: `fa4-v4.0.0`).

**Weekly beta**: `publish-fa4.yml` also runs every Wednesday at 08:00 UTC via cron. The scheduled or manual run creates and pushes the next `fa4-v*.beta*` tag, then continues in the same workflow run to build and publish that beta. Manual dispatch is restricted to the repository default branch so it cannot tag a feature branch commit. The pushed tag matches the `fa4-v*` trigger, but GitHub suppresses workflow runs for events created by `GITHUB_TOKEN`, so no recursive run is triggered.

| Week | Tag created | PyPI version |
| --- | --- | --- |
| 1 | `fa4-v4.0.0.beta5` | `4.0.0b5` |
| 2 | `fa4-v4.0.0.beta6` | `4.0.0b6` |

To stop weekly betas: GitHub repo → Actions → "Publish flash-attn-4 to PyPI" → `···` menu → **Disable workflow**. Re-enable when ready to resume, or switch to manual tag pushes only by removing the `schedule` trigger. Users can still push a `fa4-v*.beta*` tag directly when they need to cut a beta outside the schedule.

## Guardrails

Windows validation is part of the existing `ci.yml` and `publish-fa4.yml`; no
standalone Windows workflow is used. Hosted x64/Python 3.12 and
ARM64/Python 3.13 jobs build the FA4 wheel/sdist, run CPU regressions, and compare
packaged Python sources and metadata with the checkout. Linux/B200 jobs retain
their original main/ci-fix push behavior.

For native ARM64 CUDA validation, register a runner with
`self-hosted, Windows, ARM64, fa4-gpu` labels and configure
`FA4_ARM64_GPU_PYTHON` to a dedicated native ARM64 venv containing the CUDA
dependencies, build, twine, pytest and setuptools-scm.
`FA4_ARM64_GPU_VCVARS` optionally names a native ARM64 vcvars batch file for
custom Visual Studio installations. The existing x64 `FA4_GPU_PYTHON` variable
is separate. The GPU job verifies ARM64 Python/PE toolchain and a real CUDA GPU,
builds/installs its own source wheel, and records native loaded images.

Manual CI dispatch enables `run_windows_arm64_gpu` and chooses `gpu_suite`
(`smoke` or `full`). Configured main/ci-fix pushes run GPU smoke. PR events
never execute on the local runner. Smoke checks cold/warm caches and CUDA
graphs. An optional `arm64_runner_label` selects a unique label for an
ephemeral one-job runner registered without default labels; other queued
repository jobs cannot match it. Leaving it empty uses the standard labels.
Full retains every original test ID/input size and requires independent
phase/source/native-image auditing. Full has a 24-hour self-hosted job budget;
an unfinished run fails acceptance. Reports, pytest temporary directories and
kernel caches are isolated by run ID/attempt. CI and release GPU jobs share a
concurrency group; failed jobs still upload JSON/JSONL/JUnit/log evidence.

FA4 publication now requires ARM64 CPU/build validation and native GPU smoke
against the resolved release tag. Both GitHub Release and PyPI publication
depend on these gates; a missing/offline ARM64 runner blocks publication. The
original Linux distribution remains the publishing input. Local execution uses
`tools/windows-loop.ps1 -Python ... -Suite smoke -WorkDir ...`.

- Do not use `v*` tags for FA4 releases.
- Do not use `fa4-v*` tags for FA2 releases.
- Keep `flash_attn/cute/pyproject.toml` tag parsing in sync with the FA4 tag prefix.
- The workflow filename (`publish-fa4.yml`) is part of the PyPI trusted publishing OIDC identity — do not rename without updating PyPI.
