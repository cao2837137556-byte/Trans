# Mainline Docs Patch Suggestion

No mainline docs were edited in this run. If desired, append the following short strategy note to `runs/mainline_docs/mainline_experiment_map.md` and `runs/mainline_docs/mainline_handoff.md`.

## 2026-05-15 Strategy Update: Deployment Timeline and Activation Rule

Issue13 organizes the current evidence into a deployment timeline:

1. dA and Transformer remain cold-start/base detectors in ordinary normal-vs-attack settings.
2. Under current low-OOD guarded evaluation, base scalar scores show working-point collapse.
3. Scalar score-level few-shot fusion is insufficient.
4. The current stable deployment-stage adapter is GDA-minimal: original100 representation + fixed OOD-benign guard + few-shot LR.
5. source_rich and Transformer hidden provide representation-level signals, but neither is yet a stable primary source of gain over original100 fixed guard.
6. The next required experiment is issue14 arbitration: base-only, GDA-only, OR, AND, and mode-gated review policy.

This update does not change the manuscript and does not claim full GDA or detector-agnostic adaptation is proven.
