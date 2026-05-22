# Purge / Embargo Plan

## Candidates Requiring Purge Or Embargo

- `earlier-to-later`: requires purge/embargo because train bins `2,3,4` and eval bins `6,7,8` are temporally ordered but raw boundary gaps are unknown.
- `future-window holdout`: requires purge/embargo if constructed from raw time or packet order.
- `adjacent-bin holdout with embargo`: requires both purge and embargo; adjacent-window contamination is the central risk.
- `rolling-origin validation`: requires pre-registered gaps around each origin.
- `larger attack eval window`: requires purge if it pools adjacent windows; not clean in current assets.

## Basis

Current artifacts recover bin-level ordering and support/threshold provenance, but they do not recover raw timestamp, packet order, flow/session/capture boundaries, or window_start/window_end. Therefore any numeric embargo gap would be speculative if set now.

## Recommended Gap

- If only bin metadata is available: use a conservative one-bin coarse embargo and report the resulting sample-size loss before running formal validation.
- If raw timestamps are recovered later: define the gap from capture/session adjacency before any final eval is touched.

## Feasibility

With currently persisted bins, a one-bin embargo may leave no unused clean late-window proof because bins `5/6/7/8` have already been consumed by issue23/25c locked evidence. That makes issue26c formal validation blocked until either raw unused windows are recovered or the protocol explicitly changes to a metadata follow-up / second-environment feasibility step.
