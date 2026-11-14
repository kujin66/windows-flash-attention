# Native Windows ARM64 FA4 validation

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
