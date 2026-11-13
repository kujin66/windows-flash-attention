# GitHub Workflow Tagging Flow

This repository uses separate tag lanes so FA2 and FA4 publishing do not collide.

## Release lanes

| Tag pattern | Workflow | Package target | Version source |
| --- | --- | --- | --- |
| `v*` | `.github/workflows/publish.yml` | Root package (`vllm-flash-attn`, FA2/FA3 extensions) | Root package version metadata |
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

To stop weekly betas: GitHub repo â†’ Actions â†’ "Publish flash-attn-4 to PyPI" â†’ `Â·Â·Â·` menu â†’ **Disable workflow**. Re-enable when ready to resume, or switch to manual tag pushes only by removing the `schedule` trigger. Users can still push a `fa4-v*.beta*` tag directly when they need to cut a beta outside the schedule.

## Guardrails

Windows x64 build and CPU tests run directly in ci.yml for pull requests, main/ci-fix pushes and manual dispatch. They use x64 Python 3.12, the existing PEP 517 FA4 package build, metadata checks and windows-x64-flash-attn-4 artifacts. The existing Linux/B200 jobs retain their original push-only behavior.

The Windows GPU job also lives directly in ci.yml. Manual dispatch supports run_windows_gpu and gpu_suite (smoke/full); main/ci-fix pushes run GPU smoke when FA4_GPU_PYTHON is configured. Pull requests never execute on the local GPU runner.

Register the local runner with self-hosted, Windows, X64, fa4-gpu labels and set repository variable FA4_GPU_PYTHON to a dedicated venv Python. It needs FA4 CUDA dependencies, build, twine, pytest, setuptools and setuptools-scm; the host needs NVIDIA drivers, CUDA and MSVC x64 tools. The job installs its built wheel into this venv. Runs are serialized across CI and release jobs, use isolated reports/caches, and upload evidence even on failure. Smoke checks cold/warm cache; full requires independent auditing. Hardware skips and resource reductions remain explicit.

The existing publish-fa4.yml directly validates Windows build/CPU and GPU smoke against the resolved release tag. Both validations are mandatory before GitHub Release or PyPI publication. Without a registered runner and configured venv, GPU validation cannot complete and publication stays blocked. The existing Linux build still supplies publishing distributions. No separate Windows workflow is used.

Local execution without Actions remains available through tools/windows-loop.ps1 with -Python, -Suite and -WorkDir.

- Do not use `v*` tags for FA4 releases.
- Do not use `fa4-v*` tags for FA2 releases.
- Keep `flash_attn/cute/pyproject.toml` tag parsing in sync with the FA4 tag prefix.
- The workflow filename (`publish-fa4.yml`) is part of the PyPI trusted publishing OIDC identity â€” do not rename without updating PyPI.
