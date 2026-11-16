# Native Windows x64 and ARM64

FA4 uses its existing CuTeDSL PEP 517 package build. Kernels compile at runtime;
this does not build the root FA2/FA3 CUDA extensions.

~~~powershell
python -m pip install build twine
python -m build flash_attn/cute
python -m twine check flash_attn/cute/dist/*
~~~

## CI and release validation

The existing ci.yml builds/tests x64 with Python 3.12 and ARM64 with native
Python 3.13. Both hosted jobs build wheel/sdist, check metadata and compare
packaged sources with the checkout. Hosted jobs have no NVIDIA GPU.

| Native GPU | Runner labels | Dedicated venv variable | Manual CI input |
| --- | --- | --- | --- |
| x64 | self-hosted, Windows, X64, fa4-gpu | FA4_GPU_PYTHON | run_windows_gpu |
| ARM64 | self-hosted, Windows, ARM64, fa4-gpu | FA4_ARM64_GPU_PYTHON | run_windows_arm64_gpu |

Each dedicated venv needs native CUDA PyTorch, CuTeDSL, QuACK, TVM FFI and the
package dependencies, plus build, twine, pytest and setuptools-scm. The host
needs NVIDIA drivers, CUDA and the matching native MSVC toolchain.
FA4_ARM64_GPU_VCVARS optionally selects an ARM64 vcvars batch file.
arm64_runner_label optionally selects an isolated one-job runner registered
without default labels; leaving it empty uses the standard labels above.

Manual CI enables either or both GPUs and chooses gpu_suite (smoke/full).
Configured main/ci-fix pushes use smoke; PR events never use local GPU runners.
GPU checkouts are pinned to the triggering commit. Linux/B200 jobs retain
their existing main/ci-fix push behavior.

publish-fa4.yml requires both architectures' build/CPU and GPU smoke gates
against the resolved release tag before GitHub Release/PyPI publication.
Missing/offline GPU runners block publication. The existing Linux distribution
remains the publishing input. CI/release serialize each architecture using the
same concurrency group and upload JSON/JSONL/JUnit/log evidence even on failure.
Reports, pytest temporary directories and caches are isolated by run/attempt.

## Local validation

~~~powershell
./tools/windows-loop.ps1 -Python ./agent_space/venv/Scripts/python.exe -Suite smoke -WorkDir ./agent_space/smoke
./tools/windows-loop.ps1 -Python ./agent_space/venv/Scripts/python.exe -Suite full -WorkDir ./agent_space/full
# Reproduce the resource-reduced x64 CI matrix:
./tools/windows-loop.ps1 -Python ./agent_space/venv/Scripts/python.exe -Suite full -SequenceCap 256 -WorkDir ./agent_space/x64-reduced
~~~

The entry point selects the native host/target toolchain for the interpreter.
Pass -VcVarsBat PATH for a custom Visual Studio installation. PE architecture
and SHA256 checks cover Python, cl, link, nvcc and ptxas; each worker records
loaded native images. Native ARM64 extensions must not be emulated x64 images;
ARM64EC/ARM64X Windows system libraries are recorded separately.

The loop builds and installs a regular FA4 wheel into the dedicated venv and
verifies that package imports resolve inside its prefix. It validates wheel,
sdist and installed Python sources against the checkout.

Smoke checks shared/exclusive LockFileEx locking, FP16/BF16 dense and ragged
attention/gradients, CUDA graphs and persistent caches on SM120/SM121. Warm
processes prohibit new kernel compilation for the numerical files.

Full visits every tests/cute/test_*.py file. The default SequenceCap 0 retains
each original input size and ID; OOM remains a failure. Explicit SequenceCap
256 uses reduced representatives for the supported large matrices, preserving
partial tile boundaries and other parameters. mapping.json retains original
IDs/parameters and their effective counterparts. Reduced results do not certify
the original large sizes. Unsupported architecture/resource/dependency cases
are explicit skips; numerical and unclassified CUDA errors remain failures.

The supervisor resumes durable checkpoints and retries interrupted workers;
exhausted failures remain recorded while other cases continue. Timeout cleanup
terminates the Windows launcher/interpreter tree. Each case requires complete
setup/call/teardown evidence, with CUDA synchronization before hardware skips.
Original test-body exceptions and historical failures remain in the reports.
acceptance.json records current outcomes, pending cases and supervisor liveness.
Source/test/policy changes create a new report directory.

ResumeFrom OLD_REPORT can continue an orchestration-only source epoch after
verifying a clean recorded commit, matching architecture/suite/input sizes and
unchanged numerical sources, upstream tests, policy and audit implementations.
Source comparison and epoch history are saved; changed numerical sources need
a fresh run. The tools only build, validate and report; they do not manage Git
commits, pushes or pull requests.

Full acceptance requires independent phase/mapping/source/native-image auditing:

~~~powershell
python tests/windows/evidence_audit.py PATH_TO_FULL_REPORT
~~~

The audit writes independent-audit.json and fails on missing or inconsistent
evidence. [WINDOWS_CI_VALIDATION.md](WINDOWS_CI_VALIDATION.md) indexes both
architectures' original results, source epochs, artifacts, test-contract changes
and historical anomalies. Dependency reuse is not clean-machine installation
certification; SM120/SM121 results do not validate SM90/SM100-only kernels.
