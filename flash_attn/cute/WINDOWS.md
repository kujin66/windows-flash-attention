# Native Windows x64 and ARM64

FA4 uses its existing CuTeDSL package build, not the FA2 CUDA-extension build:

~~~powershell
python -m pip install build twine
python -m build flash_attn/cute
python -m twine check flash_attn/cute/dist/*
~~~

The existing .github/workflows/ci.yml runs native x64 and ARM64 hosted
build/CPU jobs. Both build wheel
and sdist with the same pyproject/backend as publish-fa4.yml, checks metadata,
and upload both artifacts. The source audit compares every package Python file
in wheel and sdist against the checkout, plus sdist metadata and this document.
CPU tests also exercise cross-process LockFileEx,
launcher-tree timeout cleanup, checkpoint recovery and hardware-policy guards.
Hosted CPU jobs have no NVIDIA GPU. A separate native Windows ARM64 GPU job
inside ci.yml runs on self-hosted Windows/ARM64/fa4-gpu runners for enabled
manual dispatches and configured main/ci-fix pushes. PR events never use the
local GPU. publish-fa4.yml requires ARM64 build/CPU and GPU smoke against the
release tag before publication. See .github/workflows/README.md for runner
variables, triggers and artifact handling. CuTeDSL compiles kernels at runtime.

Install compatible native Windows CUDA PyTorch, CuTeDSL, QuACK, TVM FFI and
the package dependencies before running numerical tests. Initialize the native
Visual Studio toolchain using tools/windows-loop.ps1:

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/windows-loop.ps1 -Python ./agent_space/venv/Scripts/python.exe -Suite smoke
powershell -NoProfile -ExecutionPolicy Bypass -File tools/windows-loop.ps1 -Python ./agent_space/venv/Scripts/python.exe -Suite full
~~~

The entry point selects an ARM64 host/target toolchain for ARM64 Python. For a
custom Visual Studio installation, pass `-VcVarsBat PATH_TO_NATIVE_VCVARS_BAT`.
It verifies the PE architecture and SHA256 of Python, cl, link, nvcc and ptxas,
and records loaded native images at the end of each worker. Pass `-WorkDir`
to isolate reports, checkpoints and caches (Actions uses the runner temp
directory plus the run ID/attempt). ARM64EC/ARM64X
Windows system libraries are recorded separately from native ARM64 extensions.
SM120 and SM121 both run the Windows numerical smoke tests.

For a persistent loop that creates a Draft PR only after full acceptance and
matching final x64/ARM64 CI artifacts:

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/windows-loop.ps1 -Python ./agent_space/arm64-venv/Scripts/python.exe -Suite full -Watch -DraftPR -VcVarsBat PATH_TO_NATIVE_VCVARS_BAT
~~~

The loop retries interrupted workers, preserves exhausted failures, and watches
for source changes when fixes are needed. `-ResumeFrom OLD_REPORT_DIRECTORY`
can continue after orchestration-only changes: a clean recorded commit and
unchanged package sources, upstream tests, policy and audit implementations are
required. Source comparison and epoch history are saved; changed numerical
sources always need a fresh run. Before finalization, commit all source changes
and authenticate `gh` in the account running the loop. The optional finalizer
records the completed matrix, pushes the development branch, dispatches the
existing CI workflow, requires both
final-head CI jobs, independently audits downloaded artifacts, and creates only
a Draft PR. It contains no merge step.

The interpreter must be a dedicated environment: the loop installs a regular
FA4 wheel into it. The local agent_space/venv reuses dependencies from the
existing native-stack environment through explicit .pth entries; this is not
a clean-machine dependency-installation test. Imports of FA4 itself must
resolve inside that interpreter's prefix, not to the old editable checkout.

The smoke suite checks native LockFileEx shared/exclusive locking, FP16/BF16
dense and ragged attention and gradients, upstream CUDA graph replays and
persistent-cache behavior. Separate warm processes prohibit new kernel
compilation for the numerical files.

The full suite visits every tests/cute/test_*.py file. By default each original
test ID executes with its original parameters (`-SequenceCap 0`), fake-tensor
mode is disabled, and OOM remains a failure. No IDs are grouped in this mode.
For an explicitly reduced run, `-SequenceCap 256` enables sequence-length
counterparts for the two large attention matrices,
retaining partial tile boundaries and every other parameter. mapping.json
records every original ID, original parameters and representative counterpart.
The matching matrix functions in the race-condition module use the same policy;
the fast module has a different parameter schema and retains its own inputs.
Source-proven unsupported matrix configurations and true upstream skipif marks
are grouped by their exact exclusion reason, with every original ID retained.
The varlen matrix's internal K-length override is normalized before grouping.
It does not establish correctness for the original larger input sizes.
In reduced mode, actual OOM gets a smaller sequence counterpart where the test exposes those
arguments. Architecture skips require exact upstream SM120 feature rejections;
shared-memory skips require the selected constructor's byte demand to exceed
the measured device limit. Numerical and unclassified CUDA errors stay failures.

The resumable loop saves source identity, wheel SHA256, logs, JUnit XML and
fsynced per-phase JSONL evidence in agent_space/windows-native. A source/test/
policy change creates a new report directory. status.json reports completion
or needs_fix; a software failure exits nonzero after bounded retries. The loop
refreshes acceptance.json every 30 seconds with current outcomes, collected
pending cases, historical failure counts and supervisor liveness. Pending counts
exclude files not collected yet; the reported file total identifies that gap.
Normal and exceptional exits write a final snapshot with supervisor_alive=false.
Intentional CPU mocks are excluded from post-case CUDA synchronization; real
CUDA cases still synchronize before unsupported-feature errors can become skips.
If synchronization fails, exception notes retain an earlier test-body exception
or explicitly record that the body returned normally.
The loop resumes after timeouts while completed-case counts keep increasing. Timeout
cleanup terminates the entire Windows launcher/interpreter process tree.
Each representative needs complete phase evidence; collection skips and all
historical failed reports are retained in verification.json. Re-running a case
resets its phase state so an interrupted retry cannot inherit an older pass.
Skips are reported separately from passes. Fix reported software errors and rerun.

Exhausted failing cases retain failure evidence while remaining cases continue.
They never become passes. The full loop automatically runs the independent audit
before acceptance. It can also be run separately with
`python tests/windows/evidence_audit.py PATH_TO_FULL_REPORT`. The independent
audit checks every current test file, representative mapping, complete phase
evidence, source fingerprint, native loaded images and final session status.
For original-size runs it also rejects parameter substitutions or grouped IDs. It writes
`independent-audit.json` and exits nonzero for missing or inconsistent evidence.
Explicit module-level collection skips remain visible and contribute zero
numerical passes. Its incomplete-evidence guards are covered by Windows CI.

When a test contract changes, explicit source-epoch invalidation records require
fresh phase evidence for the affected cases while retaining every historical
report. Unchanged cases can resume after source comparison and provenance checks.

The preallocated-output test permits adjacent storage values for nondeterministic
dQ accumulation and checks both allocation paths against the dense suite's
independent reference budget. It also checks NaN-poisoned output coverage and
retains the original strict dK/dV comparison. The varlen oracle accumulates GQA
head reductions in FP32, with unchanged numerical tolerances. Independent head
groups are checkpointed so all original sequence, batch and head sizes remain
covered at bounded reference-memory cost. Explicit-architecture fake tests supply
their own target SM count instead of depending on matching local hardware.

SM8x/SM120 validate the supported aligned head-dimension range before dispatch.
Invalid dimensions raise a host-side assertion before any attention kernel can
poison the CUDA context. CPU tests cover both dimensions and architecture paths;
the native GPU suite retains the upstream invalid-input regression cases.

The SM80-derived backward path used on SM120 now aligns ragged GQA dK/dV
scratch offsets to the same tile boundaries as its postprocess. The unchanged
upstream varlen graph tests reproduce the former numerical error and validate
the correction without adjusting reference computations or tolerances.
