# Singleton repair execution card — 2026-10-27

## Proposed single submission

Runtime identity → repaired ORIGINAL104 replay → frozen new reference encoding → dense source CAL. The stages are `runtime`, `encode`, `source_cal` only. No training, new target evaluation or automatic retry. Submission has not occurred.

Original seal SHA256: `ddb94bb9836c9ace0b2a704e875d969c1d3c40c94198212ac795a9d0731db120`.

Budget file SHA256: `8a9216bb0aa64c3e2be0f097796c245475d76aa0dc50e226bedcb681838e9944`.

The final overlay seal and archive SHA are recorded in the external package acceptance receipt, avoiding a circular self-hash in the sealed package.

| Dataset | Logical rows | Physical positions | Extra copies | Singleton batches |
| --- | ---: | ---: | ---: | ---: |
| ORIGINAL104 | 104 | 224 | 120 | 8 |
| CIC_DEV legal references | 5,237 | 5,402 | 165 | 11 |
| SOURCE_REFS legal references | 4,624 | 4,879 | 255 | 17 |
| UNSW_DEV legal references | 11,799 | 12,009 | 210 | 14 |
| Total | 21,764 | 22,514 | 750 | 50 |

There are 1,501 original logical batches. Newly encoded distinct reference UIDs remain 21,660. SOURCE_REFS merges its 4,624 new rows with the frozen original 104 to form exactly 4,728 distinct rows. The 750 compute copies are discarded.

## Resource limits and timing

Slurm amd, one node, one worker, 4 CPU, 16 GiB, at most 12 hours, CPU only, fixed four-thread Torch/BLAS, `--no-requeue`. Process-tree RSS limit is 8 GiB; free-space floor 12 GiB. Encoding output limit 4 GiB, source-CAL output limit 128 MiB. Runtime/encoding/CAL stage limits remain 480/36,000/7,200 seconds, each also capped by remaining total time. SIGTERM unwinds the original supervisor and cleans stage process groups. Any identity, data, numerical or resource failure stops and preserves evidence; 0 retries.

Earlier Windows shape-weighted planning estimated encoding 4–6 hours and CAL approximately 79 minutes; combined 5–8 hours is a planning range, not a measured HPC ETA. The repair adds 750 physical positions (about 3.45% of 21,764), with potentially uneven shape costs. The 36-second small diagnostic does not provide a full-production speed estimate. The 12-hour total cap is unchanged.

## Gates and expected deliverables

1. Verify all original and overlay file bytes, new scoped permission, environment script and exact CPU/runtime dependency identity.
2. Pass the portable inert test suite on the actual compute node before real execution.
3. Independently replay all 104 historical vectors with zero byte mismatches. Any mismatch stops before new reference encoding; no tolerance is relaxed.
4. Encode the exact frozen reference positions; validate actual token shapes/UID queues, 22,514 physical positions, unique bank UIDs, and clone equality.
5. Run unchanged source CAL. Retain original B2 protection/decision parity checks and epsilon-zero byte compatibility, then the registered epsilon=0.1 percentage-point source-CAL budget.
6. Retain launch/stage exit status, ORIGINAL104_PARITY, per-batch ledger, BATCH_REPAIR_RECEIPT, bank receipts, source-CAL RESULT and protection artifacts. COMPLETE requires the inner chain COMPLETE receipt.

This run can deliver completed encoding and source-CAL results. Target A/B FPR and recall require the later authorized matrix and are not promised by this prefix.

## Deployment and progress

Remote original: `/public/home/jiangxinwei.zr/work/paper04/runs/dense_reference_matrix_v1_20261027`.

Remote overlay: `/public/home/jiangxinwei.zr/work/paper04/runs/dense_reference_batch_repair_v1_20261027`.

Remote output: `/public/home/jiangxinwei.zr/work/paper04/runs/dense_reference_batch_repair_v1_20261027_runtime/job_JOBID/science`.

Create the external runtime root before sbatch so Slurm can open its log. The launcher exclusively creates `job_JOBID`, exports the explicit frozen test root and never writes into sealed inputs. Execute no more than one new submission after authorization.

Keep the existing local progress address `http://127.0.0.1:18770/`. A hidden ordinary sync should show queue/running/stopped/complete, current stage and actual counters, with prior 179523/179536 failures and 179591 diagnostic retained. No AI polling, terminal popups or auto-resubmission. An offline cache must preserve terminal status and distinguish communication loss from experiment failure.

## Authorization boundary

The latest permission covered only the completed 136-position source8 diagnostic. This repair turn authorizes engineering preparation and local inert validation. A new cloud execution request must identify this sealed overlay, the 22,514 physical positions, the three-stage scope and the 12-hour cap. The template remains `user_authorized=false` until that permission is given.
