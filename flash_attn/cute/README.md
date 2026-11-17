# FlashAttention-4 (CuTeDSL)

FlashAttention-4 is a CuTeDSL-based implementation of FlashAttention for Hopper and Blackwell GPUs.

## Installation

```sh
pip install flash-attn-4
```

If you're on CUDA 13, install with the `cu13` extra for best performance:

```sh
pip install "flash-attn-4[cu13]"
```

## Usage

```python
from flash_attn.cute import flash_attn_func, flash_attn_varlen_func

out = flash_attn_func(q, k, v, causal=True)
```

## Native Windows x64 and ARM64

Use native x64 Python 3.12 or ARM64 Python 3.13 matching the target platform.
From the repository root, build FA4 through its existing PEP 517 package:

~~~powershell
python -m venv venv
./venv/Scripts/python.exe -c "import platform; print(platform.machine())"
./venv/Scripts/python.exe -m pip install build twine
./venv/Scripts/python.exe -m build flash_attn/cute --outdir flash_attn/cute/dist
./venv/Scripts/python.exe -m twine check flash_attn/cute/dist/*
~~~

This builds the FA4 wheel and sdist without importing CUDA dependencies. The
root setup.py builds the separate FA2/FA3 native extensions; it is not the FA4
build entry point. FA4 compiles its GPU kernels at runtime.

Running FA4 requires compatible native Windows CUDA PyTorch, CuTeDSL, QuACK,
TVM FFI and the other dependencies declared in pyproject.toml, plus NVIDIA
drivers, CUDA and the matching native MSVC toolchain. Install those dependencies
in the dedicated venv first, then install the built wheel:

~~~powershell
./venv/Scripts/python.exe -m pip install --no-deps (Get-ChildItem flash_attn/cute/dist/*.whl).FullName
./venv/Scripts/python.exe -I -c "import torch; assert torch.cuda.is_available(); import flash_attn.cute"
~~~

The recorded GPU environments reused native dependencies; they do not certify
clean-machine availability or installation of every Windows dependency.

### Native validation and CI

The validation runner uses the same package build and upstream pytest suites.
It also requires build, twine, pytest and the pyproject build dependencies:

~~~powershell
./venv/Scripts/python.exe -m pip install build twine pytest "setuptools>=75" "setuptools-scm>=8"
./tools/windows-loop.ps1 -Python ./venv/Scripts/python.exe -Suite smoke -WorkDir ./build/windows-smoke
./tools/windows-loop.ps1 -Python ./venv/Scripts/python.exe -Suite full -WorkDir ./build/windows-full
~~~

The PowerShell entry point selects the native MSVC host/target toolchain.
Pass -VcVarsBat PATH for a custom Visual Studio installation. Native PE
toolchain/loaded-image checks reject architecture mismatches. The runner reuses
tools/ci/assert_dsl_floor.py for dependency minimums and the existing pytest
compile instrumentation for warm-cache checks.

Full validation retains original input sizes by default; -SequenceCap 256
explicitly selects the reduced x64 matrix used in CI. Checkpoints, original-ID
mappings, complete phase reports and historical failures remain recorded.
-ResumeFrom OLD_REPORT requires matching architecture/suite/input sizes and
verified unchanged numerical sources/tests/policy. Full acceptance requires
the independent audit in tests/windows/evidence_audit.py. The tools do not
commit, push or manage pull requests.

Existing ci.yml builds/tests both architectures and supports native GPU jobs:

| GPU | Runner labels | Dedicated venv variable | Manual CI input |
| --- | --- | --- | --- |
| x64 | self-hosted, Windows, X64, fa4-gpu | FA4_GPU_PYTHON | run_windows_gpu |
| ARM64 | self-hosted, Windows, ARM64, fa4-gpu | FA4_ARM64_GPU_PYTHON | run_windows_arm64_gpu |

FA4_ARM64_GPU_VCVARS optionally selects an ARM64 vcvars batch file;
arm64_runner_label optionally selects an isolated one-job runner registered
without default labels. Manual dispatch selects gpu_suite (smoke/full).
Configured main/ci-fix pushes use smoke; PR events never use local GPU runners.
CI/release serialize each architecture and isolate reports/caches per run.
publish-fa4.yml requires both build/CPU and GPU smoke gates against the release
tag before publication; matching online runners are required. The existing
Linux build supplies publishing distributions. Linux/B200 behavior is retained.

[Windows validation records](WINDOWS_VALIDATION.md) preserve both architectures'
source epochs, original results, artifact identities, exclusions and historical
anomalies. SM120/SM121 results do not validate SM90/SM100-only kernels.

## Development

```sh
git clone https://github.com/Dao-AILab/flash-attention.git
cd flash-attention
pip install -e "flash_attn/cute[dev]"       # CUDA 12.x
pip install -e "flash_attn/cute[dev,cu13]"  # CUDA 13.x (e.g. B200)
pytest tests/cute/
```
