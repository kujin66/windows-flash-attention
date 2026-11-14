# Native Windows x64 FA4 validation

Status: the configured matrix completed; overall acceptance remains open.
Two current-source GPU anomalies passed retries but their causes are unresolved.
This report does not certify that every FA4 configuration works on Windows.

## Source and CI

Numerical validation source commit: `4ae8c12dd9a2cfa21a4c329b1a52ad1615b21766`.
Validation fingerprint (package, upstream tests and supervisor Python files):
`17930445e5d3a6a7763b6aedf92face8a9ba8b3149f753cd6b2c639e5929919e`.

[Windows CI run 43250925140](https://github.com/kujin66/windows-flash-attention/actions/runs/43250925140)
succeeded at that commit. An independent artifact comparison verified all 63
package Python files in the wheel and source distribution, plus the source
distribution's pyproject.toml and WINDOWS.md, normalizing only line endings.
CI uses the existing PEP 517 package build and checks CPU supervisor tests and
package metadata; it does not execute CUDA kernels.

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
in the evidence: 21 historical reports, including two current-source anomalies.
Passing latest outcomes does not erase those failures.

Local evidence is under `agent_space/windows-native/17930445e5d3a6a7-full`
(`final-acceptance.json`, `independent-audit.json`). `overall.json` links the
archived original full-run binaries, smoke report and integration reports.
These scratch artifacts are local, not included in the package. The current
top-level acceptance snapshot belongs to the completed smoke stage.
The new exception-note reporting change alters the supervisor fingerprint;
the completed matrix above describes the stated numerical-validation commit.
A fresh cached matrix with the updated evidence hook remains pending.

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
zero-CUDA-API-error claim. Racecheck and output-coverage investigation remain
pending. No speculative patch or hardware-skip reclassification was applied.
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
