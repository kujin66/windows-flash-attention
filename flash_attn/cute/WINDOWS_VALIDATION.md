# Windows x64 and ARM64 validation evidence

PR #2 consolidates [x64 PR #1](https://github.com/kujin66/windows-flash-attention/pull/1)
and [ARM64 PR #2](https://github.com/kujin66/windows-flash-attention/pull/2).
The records below describe their original source epochs, not a new execution
of the combined branch. Existing reports, historical failures and original
Actions artifacts retain their identities.

## Original CI executions

| Check | Windows x64 | Windows ARM64 |
| --- | --- | --- |
| Run | [43410275747](https://github.com/kujin66/windows-flash-attention/actions/runs/43410275747) | [43560615359](https://github.com/kujin66/windows-flash-attention/actions/runs/43560615359) |
| Source | `fb4d9d460b192d6338bf656d2f2161b3981a6258` | `773e11f432234211f4657020db9a4bb5c894f8d4` |
| Completed (UTC+08:00) | 2026-11-13 18:40:03 | 2026-11-14 13:19:29 |
| Build/CPU | Passed; 40 CPU tests | Passed; 56 CPU tests on each hosted architecture |
| Native GPU | Passed; RTX 5060 Laptop, SM120 | Passed; RTX Spark N1X, SM121 |
| Cold smoke | 26 passed; 2 skipped | 26 passed; 2 skipped |
| Warm SM12x cache | 10 passed; zero new kernel compiles | 10 passed; zero new kernel compiles |
| Warm CUDA graphs | 6 passed; 2 skipped; zero new kernel compiles | 6 passed; 2 skipped; zero new kernel compiles |
| Uploaded evidence audit (recorded) | JUnit, mappings and complete phases matched | All 28 IDs and setup/call/teardown phases matched |
| Package comparison (recorded) | 63 Python files matched source; metadata/docs checked | 63 Python files matched source; metadata checked |

Both runs completed successfully. ARM64's run also executed x64 build/CPU;
it did not execute x64 GPU tests. Linux/B200 jobs were skipped in these manual
runs. Recorded audit outcomes above come from the original PR records; saving
their identities is not a new independent audit of downloaded artifacts.
ARM64 also recorded 912 loaded-image checks across worker processes.

### Environments

- **x64:** Windows 11; Python 3.12.16; torch 2.14.1+cu130; CuTe DSL 4.8.1;
  RTX 5060 Laptop (8151 MiB); driver 610.62. CI smoke source fingerprint:
  `ac4a517c3d9425b02079ae90496119464a0a44ca25b5e4dd69c961aaa10711a9`.
- **ARM64:** native Windows ARM64; Python 3.13.17;
  torch 2.14.0a0+git20b0f57; CuTe DSL 4.9.0.dev0; RTX Spark N1X (SM121).
  Native Python/toolchain and loaded-image evidence are in the GPU artifact.

### Original artifact identities

| Run | Artifact | ID | Archive SHA256 |
| --- | --- | --- | --- |
| 43410275747 | windows-x64-flash-attn-4 | 14029745781 | `cd1ba3e6aba90b1cc840ba5c71c2a768655c49d085abfbfacc740d0c4168b9cb` |
| 43410275747 | windows-x64-gpu-smoke-1 | 14028838776 | `4e312e5bb8c4e5f5d937f501518d464f584a026b8c0c9ae9a306370274c0cd17` |
| 43560615359 | windows-arm64-flash-attn-4 | 14100340634 | `252d2754ac13f02dad9c0bec862f7a459012e13a35519623c79450bb9c1f2379` |
| 43560615359 | windows-x64-flash-attn-4 | 14100290941 | `72d62fa018978c0ce1d3997ece3499439de854596748fe6cf620be8e8bf54bf6` |
| 43560615359 | windows-arm64-gpu-smoke-1 | 14099453965 | `ef86212bfce2b69d9bb5f5e47659ebda13bd5dea88798d5255a225c8517f1271` |

Archive digests are GitHub's original artifact metadata. The x64 hosted
package file SHA256 values recorded independently in PR #1 are:

- Wheel: `7bd3d39f62fad30370fada1d59d311fd5c116d005e93552c350668ae705c9e17`.
- Sdist: `201e2a51b117faae280ec9c560f5086b059440bda877c425e735a3d64eb30fbb`.

GPU artifacts contain JSON/JSONL, JUnit XML and logs, including build/import
evidence. The original runs remain the artifact download locations; these
archives are not duplicated in the source tree. Normal Actions retention
applies. Local full-run evidence paths are retained in the detailed reports
and refer to the original validation machines, not a fresh clone.

## Recorded full matrices

| Check | x64 | ARM64 |
| --- | --- | --- |
| Detailed report | [x64 record](#windows-x64-full-validation) | [ARM64 record](#windows-arm64-full-validation) |
| Numerical source commit | `5c208760a514d14da966d218489198acaa54b3b0` | `a56ccb3f6b8b05df6b67e02e2ccac5a6367656a7` |
| Source fingerprint | `be21bf6432c5c9c25cf9f628b80c8485bb7ad736e610908e545282335bfca8ff` | `4b55b61ed0032a67555c96be0ecf42bf4d1e09ad2792e6fcefae87ddd5aa1eb2` |
| Files / original IDs | 36 / 471,182 | 36 / 471,182 |
| Execution scope | 95,409 representatives; sequence cap256 | 471,182 original-size IDs |
| Final outcomes | 66,426 passed; 28,983 skipped | 118,538 passed; 352,644 skipped |
| Final failures / pending | 0 / 0 | 0 / 0 |
| Independent audit | Passed | Passed |

x64 additionally recorded 59 comparisons and 50 AMD64 COFF objects in each
successful native cold/warm integration pass. Its earlier evidence retains
21 historical failure reports, including two GPU anomalies. Both anomalies
passed 20 exact cached replays, device-only memcheck and the fresh full matrix;
scoped racechecks, finite-poison trials and predecessor sequences also passed.
Their status remains **NOT REPRODUCED; mechanism OPEN; not FIXED**.

ARM64 retains 18 historical PermissionError phase reports from six file-lock
tests during shared pytest temporary-directory setup. Per-attempt workspace
directories resolved the setup issue; all six unchanged tests passed on retest.
The per-file result table and source fingerprint remain in its original report.

## Review scope

- x64 reduced representatives do not establish correctness for every original
  large input. ARM64 retains original sizes. Hardware/resource/dependency
  exclusions remain explicit skips, never numerical passes.
- SM120/SM121 evidence does not validate SM90/SM100-only instructions or other
  GPU models. Root FA2/FA3 Windows native extensions are outside this work.
- Review inherited test-contract changes: nondeterministic preallocated dQ
  adjacent-value handling (independent budgets, strict dK/dV, NaN poisoning);
  checkpointed FP32 varlen GQA reductions with unchanged tolerances/input sizes;
  synthetic SM counts for explicit SM100 FakeTensor tests.
- Dedicated environments reuse native dependencies through explicit `.pth`
  paths; this is not clean-machine installation certification.
- Original ephemeral GPU runners were unregistered after validation. Future
  GPU jobs and mandatory release gates require matching online runners.
  Release workflows were not executed.
- The appended detailed records are historical snapshots. Their references to then
  pending workflow checks are superseded by the original CI records above;
  they do not imply that the combined branch has passed CI.

## Windows x64 full validation

Historical record from [the original report](https://github.com/kujin66/windows-flash-attention/blob/fb4d9d460b192d6338bf656d2f2161b3981a6258/flash_attn/cute/WINDOWS_VALIDATION.md). Only heading levels are adjusted.

Status: the configured matrix completed; overall acceptance remains open.
Two historical GPU anomalies passed subsequent targeted checks and the fresh
full matrix, but their causes are unresolved.
This report does not certify that every FA4 configuration works on Windows.

### Source and CI

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

### Windows changes

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

### Completed checks

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

### Open anomalies

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

### Scope and environment

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


## Windows ARM64 full validation

Historical record from [the original report](https://github.com/kujin66/windows-flash-attention/blob/773e11f432234211f4657020db9a4bb5c894f8d4/flash_attn/cute/WINDOWS_ARM64_VALIDATION.md). Only heading levels are adjusted.

Numerical source fingerprint: `4b55b61ed0032a67555c96be0ecf42bf4d1e09ad2792e6fcefae87ddd5aa1eb2`.
Numerical validation started from commit `a56ccb3f6b8b05df6b67e02e2ccac5a6367656a7`.
Every original test ID retained its input sizes. Hardware and upstream
exclusions remain skips and are not numerical passes.

Full suite: 36 files; 471,182 original IDs;
118,538 passed; 352,644 skipped.
Independent current-source, phase-coverage, native-image and artifact audit passed.

| File | Original IDs | Passed | Skipped | Historical failure reports |
| --- | ---: | ---: | ---: | ---: |
| test_block_sparsity.py | 4923 | 4883 | 40 | 0 |
| test_bwd_config.py | 34 | 34 | 0 | 0 |
| test_cache_utils.py | 4 | 4 | 0 | 0 |
| test_clc_fuzz.py | 196 | 0 | 196 | 0 |
| test_cuda_graph.py | 8 | 6 | 2 | 0 |
| test_cute_dsl_utils.py | 5 | 5 | 0 | 0 |
| test_flash_attn.py | 416069 | 95100 | 320969 | 0 |
| test_flash_attn_bwd_pack_gqa.py | 601 | 0 | 601 | 0 |
| test_flash_attn_bwd_tile_n.py | 116 | 0 | 116 | 0 |
| test_flash_attn_combine.py | 2397 | 2397 | 0 | 0 |
| test_flash_attn_decode_sm100.py | 95 | 0 | 95 | 0 |
| test_flash_attn_dynamic_causal.py | 66 | 0 | 66 | 0 |
| test_flash_attn_fast.py | 248 | 193 | 55 | 0 |
| test_flash_attn_fp8_kv_cache.py | 0 | 0 | 0 | 0 |
| test_flash_attn_fp8_output.py | 49 | 1 | 48 | 0 |
| test_flash_attn_hd256_bwd.py | 96 | 0 | 96 | 0 |
| test_flash_attn_hd256_features.py | 48 | 0 | 48 | 0 |
| test_flash_attn_mla.py | 2261 | 0 | 2261 | 0 |
| test_flash_attn_mla_sparse_decode.py | 94 | 0 | 94 | 0 |
| test_flash_attn_mla_sparse_flat_kv.py | 16 | 0 | 16 | 0 |
| test_flash_attn_race_condition.py | 2496 | 0 | 2496 | 0 |
| test_flash_attn_varlen.py | 5838 | 2592 | 3246 | 0 |
| test_fwd_autotune.py | 15 | 13 | 2 | 0 |
| test_fwd_config.py | 173 | 173 | 0 | 0 |
| test_fwd_work_coords.py | 24 | 24 | 0 | 0 |
| test_hd256_varlen_scheduler.py | 153 | 0 | 153 | 0 |
| test_mask_mod.py | 1585 | 155 | 1430 | 0 |
| test_mask_mod_varlen.py | 909 | 273 | 636 | 0 |
| test_mla_fwd_config.py | 63 | 63 | 0 | 0 |
| test_score_mod.py | 2624 | 1524 | 1100 | 0 |
| test_score_mod_varlen.py | 29832 | 10956 | 18876 | 0 |
| test_swapab_config.py | 113 | 113 | 0 | 0 |
| test_tmem_barrier.py | 2 | 0 | 2 | 0 |
| test_utils.py | 13 | 13 | 0 | 0 |
| test_windows_filelock.py | 6 | 6 | 0 | 18 |
| test_windows_sm120.py | 10 | 10 | 0 | 0 |

Evidence is retained in the local `agent_space/windows-native` run directory.
Final CI must pass at the PR head and both downloaded architecture artifacts
must match package sources before the loop creates the Draft PR.
The dedicated environment reuses existing native dependencies; this is not
a clean-machine installation certificate. SM121 validation does not certify
SM90/SM100-only kernels or resolve the historical x64 GPU anomalies.
