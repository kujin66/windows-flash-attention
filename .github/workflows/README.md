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

Windows validation runs directly in `ci.yml` and `publish-fa4.yml`. Hosted
Windows x64/Python 3.12 and ARM64/Python 3.13 jobs build wheel/sdist, run CPU
regressions, check metadata and compare packaged sources with the checkout.
Linux/B200 jobs retain their existing main/ci-fix push behavior.

| Native GPU | Runner labels | Dedicated venv variable | Manual CI input |
| --- | --- | --- | --- |
| x64 | `self-hosted, Windows, X64, fa4-gpu` | `FA4_GPU_PYTHON` | `run_windows_gpu` |
| ARM64 | `self-hosted, Windows, ARM64, fa4-gpu` | `FA4_ARM64_GPU_PYTHON` | `run_windows_arm64_gpu` |

Each venv needs native CUDA dependencies, build, twine, pytest and setuptools-scm;
the host needs NVIDIA drivers, CUDA and the matching native MSVC toolchain.
`FA4_ARM64_GPU_VCVARS` optionally selects an ARM64 vcvars batch file.
`arm64_runner_label` optionally selects an isolated one-job ARM64 runner
registered without default labels; leaving it empty uses the labels above.

Manual CI can enable either or both GPUs and select `gpu_suite` (`smoke`/`full`).
Configured main/ci-fix pushes use smoke; PR events never use local GPU runners.
GPU checkouts are pinned to the triggering commit. Smoke checks cold/warm
caches and CUDA graphs. Full preserves x64 cap256 representatives and ARM64
original input sizes, with independent phase/source/native-image auditing;
reduced mappings do not certify original large inputs. The x64 job retains
its six-hour budget and ARM64 full its 24-hour budget; unfinished runs fail
acceptance. Reports, pytest temporary directories and caches are isolated by
architecture/run/attempt. CI and release serialize each architecture using
the same concurrency group and upload JSON/JSONL/JUnit/log evidence on failure.

Both GitHub Release and PyPI publication require x64 **and** ARM64 build/CPU
and GPU smoke gates against the resolved release tag. Missing/offline runners
block publication. The existing Linux distribution remains the publishing
input. Local execution uses `tools/windows-loop.ps1 -Python ... -Suite ...
-WorkDir ...`; pass `-SequenceCap 256` to reproduce the reduced x64 matrix.
Recorded results and original artifact identities are indexed in
[`WINDOWS_CI_VALIDATION.md`](../../flash_attn/cute/WINDOWS_CI_VALIDATION.md).

- Do not use `v*` tags for FA4 releases.
- Do not use `fa4-v*` tags for FA2 releases.
- Keep `flash_attn/cute/pyproject.toml` tag parsing in sync with the FA4 tag prefix.
- The workflow filename (`publish-fa4.yml`) is part of the PyPI trusted publishing OIDC identity — do not rename without updating PyPI.
