# Native Windows x64 FA4 validation

Status: the configured matrix completed; overall acceptance remains open.
Two historical GPU anomalies passed subsequent targeted checks and the fresh
full matrix, but their causes are unresolved.
This report does not certify that every FA4 configuration works on Windows.

## Source and CI

Validation source commit: `5c208760a514d14da966d218489198acaa54b3b0`.
Validation fingerprint (package, upstream tests and supervisor Python files):
`be21bf6432c5c9c25cf9f628b80c8485bb7ad736e610908e545282335bfca8ff`.

[Windows CI run 43348191065](https://github.com/kujin66/windows-flash-attention/actions/runs/43348191065)
succeeded at that commit. An independent artifact comparison verified all 63
package Python files in the wheel and source distribution, plus the source
distribution's pyproject.toml, WINDOWS.md and WINDOWS_VALIDATION.md, normalizing
only line endings. The fresh local wheel and installed package also matched
all 63 current Python files. Documentation-only follow-up commits do not change
the validated Python fingerprint; final-head CI must be checked separately.
CI uses the existing PEP 517 package build and checks CPU supervisor tests and
package metadata; it does not execute CUDA kernels.

CI/CD follow-up: Windows x64 build/CPU and local GPU jobs now live directly
in the existing ci.yml. The existing publish-fa4.yml contains direct Windows
CPU/build and mandatory GPU validation of the resolved release tag before
GitHub Release creation or PyPI publication. No separate Windows workflows
remain. The repository had no registered self-hosted runner when checked;
release GPU validation requires runner provisioning, and its GitHub GPU
execution is not yet certified. CI PR runs do not execute on that local GPU;
manual CI can select smoke/full, and configured main pushes use smoke. These workflow
and supervisor changes postdate the full matrix fingerprint above. The full
counts describe that recorded source epoch, not a rerun of the new supervisor.
Production attention and cache Python code is unchanged by this CI follow-up.
The follow-up CPU regression suite passed 40 tests (including isolated CLI
report-directory coverage). Actionlint passed after the CI integration change;
the existing b200 and new fa4-gpu runner labels are declared in actionlint.yaml.

## Windows changes

- `_filelock.py`: native LockFileEx locking; `cache_utils.py`: Windows fallback
  for fcntl and absent RTLD_GLOBAL.
- `flash_bwd.py`: ragged GQA scratch offsets match backward postprocess tile
  alignment on the SM80-derived path used by SM120.
- `interface.py`: reject unsupported or unaligned SM8x/SM120 head dimensions
  before CUDA dispatch.
- Windows workflow, resumable supervisor, explicit hardware/resource policy,
  independent evidence audit and regression tests.

Test contracts also changed transparently: the preallocation test checks both
paths against the independent gradient budget while permitting adjacent dQ
storage values from nondeterministic accumulation; dK/dV remain strict. The
varlen GQA oracle reduces independent KV-head groups in checkpointed FP32,
retaining original numerical tolerances. Explicit SM100 FakeTensor tests supply
their own synthetic SM count. These are not production kernel fixes.

## Completed checks

| Check | Result |
| --- | --- |
| Configured full matrix, 36 files | 66,426 passed; 28,983 skipped |
| Representative coverage | 95,409 representatives mapping 471,182 original IDs |
| Independent evidence audit | Passed; no missing current phase evidence |
| CPU regression suite, including original-body evidence guards | 39 passed |
| Cold smoke | 26 passed; 2 skipped |
| Warm SM120 cache | 10 passed; zero new kernel compiles |
| Warm CUDA graph cache | 6 passed; 2 skipped; zero new kernel compiles |
| Native cold/warm integration | 59 comparisons; 50 AMD64 COFF objects; both passed |

Warm integration prohibited new FA4/QuACK compilation. The standalone CuTe
vector example compiled before that prohibition. Prior failure reports remain
in the prior validation evidence: 21 historical reports, including two anomalies
observed with the same attention Python code. The fresh current-hook full run
has zero failed reports and zero unresolved representatives.
Passing latest outcomes does not erase those failures.

Fresh full evidence is under
`agent_space/windows-native/body-evidence-current/be21bf6432c5c9c2-full`.
Its independent audit covers all 36 files, every representative and complete
current-source phase evidence with no issues. A programmed worker timeout
resumed from 33,513 complete checkpoint cases; incomplete cases were rerun.
Original cached kernels were copied into a separate directory; prior outcomes
were not imported. The prior `17930445e5d3a6a7-full` report and its 21 failed
reports remain intact.

Current smoke evidence is under
`agent_space/windows-native/body-evidence-smoke-1794540478642144500`; current
integration evidence is under
`agent_space/windows-native/body-evidence-integration-639301376629447616`.
The corresponding `followup-smoke.json`, `followup-integration.json` and
`followup-case0-racecheck.json` are in `body-evidence-current`. These scratch
artifacts are local, not included in the package. The IDE's separate
`native-stack/logs/acceptance.json` is not this FA4 validation report.

An initial integration controller stopped when PowerShell treated a compiler
UserWarning on redirected stderr as a terminating error, despite 59 numerical
comparisons completing successfully. Its logs were retained. Recovery used
separate stdout/stderr files and actual child exit codes; both fresh cold/warm
passes completed successfully. Compiler warnings remain visible.

## Open anomalies

Both use BF16 MHA, head dimensions Q/K=192 and V=128, random varlen lengths
and softcap=15:

1. Dense Q/K, effective Q255/K1, noncausal/nonlocal: CUDA illegal memory access
   reported at final synchronization. The historical hook could replace an
   earlier body exception, so that traceback does not prove body assertions
   returned. The hook now preserves the original body status in exception notes.
2. Dense Q/packed KV, effective Q255/K255, local enum 3: forward numerical
   mismatch, max difference 1.65625 against budget 3*0.109375+0.03125.

Each subsequently passed 20 exact cached replays. Device-memory memcheck found
zero device errors for each. API error reporting was disabled because separate
diagnostics reported expected version/procedure lookup errors; this is not a
zero-CUDA-API-error claim. Case 1 completed an unfiltered racecheck replay with
zero hazards. Case 0 completed selected-CuTe-kernel racecheck with zero hazards;
Torch reference kernels still executed but were not instrumented in that
selected check. Cached object names verified the filter prefix for forward,
backward, preprocess and postprocess. Both checks disabled CUDA API reporting.

Finite 0/7 output poisoning completed 10 paired trials per case (40 upstream
calls), with valid-query outputs bit-exact. Legitimately unwritten dense Q
padding was excluded by the original contract. The two exact eight-predecessor
sequences plus their target cases completed 10 repetitions each (180 calls).
Both anomaly configurations also passed complete phase evidence in the fresh
full matrix. These checks reject the tested isolated/coverage/short-sequence
explanations; they do not establish why the historical faults occurred.
No speculative patch or hardware-skip reclassification was applied.
Status of these anomalies: NOT REPRODUCED; mechanism OPEN; not FIXED.

Windows System event records 4829498/4829499/4829500/4829510/4829511 show an
nvlddmkm TDR reset/restart at 01:16:02--04 local time, immediately before the
first CUDA700 report at 01:16:05.860. No matching driver/display/WHEA event was
returned for the second numerical failure at 02:05:42.780 in the queried
01:15--02:06:40 interval. These are retrospective correlations: the TDR trigger
is unknown and could be a software fault. They do not establish a hardware
defect, explain the numerical mismatch, or justify an additional skip.

## Scope and environment

Windows 11 x64; Python 3.12.16; torch 2.14.1+cu130; CuTe DSL/libraries 4.8.1;
TVM FFI 0.1.15.post2; cuda-bindings 13.5.0; QuACK 0.6.5; RTX 5060 Laptop
(SM120, 8151 MiB); driver 610.62; system ptxas 13.5.37.

Architecture/backend exclusions are explicit skips. Resource-heavy attention
matrices were capped at sequence length 256 with partial boundaries preserved:
the ID mapping does not establish correctness at every original large size.
FP8-KV also has an explicit missing sibling-vLLM dependency exclusion. Tests
on SM120 do not validate SM90/SM100-only instructions or other GPU models.
The dedicated FA4 environment borrows native dependencies through a .pth file;
this is not a clean-machine installation certificate.
