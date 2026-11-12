# Native Windows x64

FA4 uses its existing CuTeDSL package build, not the FA2 CUDA-extension build:

~~~powershell
python -m pip install build twine
python -m build flash_attn/cute
python -m twine check flash_attn/cute/dist/*
~~~

The Windows CI workflow is .github/workflows/windows-fa4.yml. It builds wheel
and sdist with the same pyproject/backend as publish-fa4.yml, checks metadata,
and uploads both artifacts. Hosted CI has no NVIDIA GPU; its build result
does not certify GPU kernels. CuTeDSL compiles those kernels at runtime.

Install compatible native Windows CUDA PyTorch, CuTeDSL, QuACK, TVM FFI and
the package dependencies before running numerical tests. Initialize the x64
Visual Studio toolchain using tools/windows-loop.ps1:

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/windows-loop.ps1 -Python ./agent_space/venv/Scripts/python.exe -Suite smoke
powershell -NoProfile -ExecutionPolicy Bypass -File tools/windows-loop.ps1 -Python ./agent_space/venv/Scripts/python.exe -Suite full
~~~

The interpreter must be a dedicated environment: the loop installs a regular
FA4 wheel into it. The local agent_space/venv reuses dependencies from the
existing native-stack environment through explicit .pth entries; this is not
a clean-machine dependency-installation test. Imports of FA4 itself must
resolve inside that interpreter's prefix, not to the old editable checkout.

The smoke suite checks native LockFileEx shared/exclusive locking, FP16/BF16
dense and ragged attention and gradients, upstream CUDA graph replays and
persistent-cache behavior. Separate warm processes prohibit new kernel
compilation for the numerical files.

The full suite visits every tests/cute/test_*.py file. The two large attention
matrices use sequence-length counterparts capped at 256 on this 8 GB device,
retaining partial tile boundaries and every other parameter. mapping.json
records every original ID, original parameters and representative counterpart.
It does not establish correctness for the original larger input sizes.
Actual OOM gets a smaller sequence counterpart where the test exposes those
arguments. Architecture skips require exact upstream SM120 feature rejections;
shared-memory skips require the selected constructor's byte demand to exceed
the measured device limit. Numerical and unclassified CUDA errors stay failures.

The resumable loop saves source identity, wheel SHA256, logs, JUnit XML and
fsynced per-phase JSONL evidence in agent_space/windows-native. A source/test/
policy change creates a new report directory. status.json reports completion
or needs_fix; a software failure exits nonzero after bounded retries. The loop
does not invent kernel fixes or relabel software failures as hardware limits.
Re-run after fixing the reported error. Skips are reported separately from passes.

The SM80-derived backward path used on SM120 now aligns ragged GQA dK/dV
scratch offsets to the same tile boundaries as its postprocess. The unchanged
upstream varlen graph tests reproduce the former numerical error and validate
the correction without adjusting reference computations or tolerances.
