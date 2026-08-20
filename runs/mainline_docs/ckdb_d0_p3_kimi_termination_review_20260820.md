# CKDB D0-P3 termination — Kimi confirmation review

Date: 2026-08-20
Reviewer: Kimi
Target: Codex result commit `cc8ef09`
(`ckdb_d0_p3_p0_b_result_20260820.md` + resolution JSON)

## Verdict: TERMINATION CONFIRMED — CKDB external-corpus route is formally and correctly closed

## What I verified

1. **Contract identity**: the resolution JSON carries contract SHA
   `de864fdb...e5a1` — the exact FROZEN text I verified at `010711e`.
2. **The failure is the frozen R1 branch, not discretion**: publisher
   inventory exposes exactly one root object `Modbus Dataset.zip`
   (`SINGLE_WHOLE_DATASET_ZIP`, `benign_subtree_visible=false`,
   `attack_exclusion_before_transfer=false`) → `P0-B` uncloseable → the
   frozen consequence fires verbatim: CIC=0, industrial max = PNNL 2 + 0 =
   2 < 3, `NO_IDENTIFIABLE_THREE_INDUSTRIAL_DOMAINS_CIC_IDENTITY_UNRESOLVED`,
   `route_terminated=true`, no replacement/third-corpus search.
3. **Boundaries held**: 0 body downloads, 0 download clicks, 0 credentials
   or transient URLs recorded, FINAL untouched. The user's form action was
   used only to view the inventory, exactly as authorized.
4. **No remediation owed**: the D: storage question is moot for this route;
   no cleanup or download may be started under D0-P3.

## On record

This termination is the pre-registration system *working*: a bad download
was prevented by a rule frozen before the evidence was seen. CKDB's closure
retracts nothing from CKDA D1 (97.37% global / 96.68% unseen-source attack
recall stands as local-contingency evidence pending the HPC replay), and it
leaves the cross-device benign/OOD problem exactly where D1 placed it.

CKDB is sealed. Any successor route needs its own name and preregistration.
