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

FA4 Windows CI builds on a native x64 (`windows-latest`) runner with x64
Python 3.12. It runs CPU-only Windows regressions, uses the existing PEP 517
package build, checks metadata, and uploads `windows-x64-flash-attn-4`.
This hosted job certifies packaging and CPU behavior, not CUDA execution.

Local Windows CUDA tests are available in `windows-fa4-gpu.yml` through manual
dispatch with `smoke` or `full`. Register the local runner with labels
`self-hosted`, `Windows`, `X64`, `fa4-gpu`, and set repository variable
`FA4_GPU_PYTHON` to a dedicated runner venv Python. That environment needs
the FA4 CUDA dependencies, build, twine, pytest, setuptools and setuptools-scm;
the host needs NVIDIA drivers, CUDA and MSVC x64 tools. The job installs its
built wheel into this venv.

GPU runs are serialized, use separate caches and reports per invocation, and
upload logs and numerical evidence on success or failure. Smoke includes
cold/warm cache tests; full also requires independent evidence auditing.
Hardware skips and resource-reduced cases remain explicit. This manual job
does not run automatically for pull requests or gate releases.

The same entry point can run locally without a registered runner:

```powershell
./tools/windows-loop.ps1 -Python ./agent_space/venv/Scripts/python.exe -Suite smoke -WorkDir ./agent_space/windows-local-gpu-smoke
```

FA4 release runs reuse this workflow against the resolved release tag. Windows
x64 validation must pass before GitHub Release creation or PyPI publication.
The existing Linux build supplies the single universal wheel and sdist used
for publishing; Windows artifacts remain separate validation outputs.

- Do not use `v*` tags for FA4 releases.
- Do not use `fa4-v*` tags for FA2 releases.
- Keep `flash_attn/cute/pyproject.toml` tag parsing in sync with the FA4 tag prefix.
- The workflow filename (`publish-fa4.yml`) is part of the PyPI trusted publishing OIDC identity — do not rename without updating PyPI.
