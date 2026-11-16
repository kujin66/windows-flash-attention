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
| Detailed report | [WINDOWS_VALIDATION.md](WINDOWS_VALIDATION.md) | [WINDOWS_ARM64_VALIDATION.md](WINDOWS_ARM64_VALIDATION.md) |
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
- The detailed reports are historical snapshots. Their references to then
  pending workflow checks are superseded by the original CI records above;
  they do not imply that the combined branch has passed CI.
