# Benchmark Claim Inventory

This file lists the claims the reset benchmark was implicitly asked to support, and whether issue27r found enough semantic evidence.

## full Mirai anonymous_clean115 can serve as within-dataset protocol-reset benchmark

- required evidence: stable feature matrix, labels, split identity, semantic caveats documented
- current evidence: clean115 exists, split hashes exist, previous engineering leakage lite passed
- missing evidence: feature semantics and split deployment meaning remain limited
- risk level: `medium`
- next check: use only as within-dataset protocol reset if semantic risks are bounded

## ID benign represents known normal traffic

- required evidence: benign label purity and row range consistency
- current evidence: label sidecar marks the first 121621 rows as benign
- missing evidence: no source/capture metadata to verify normal subpopulation identity
- risk level: `medium`
- next check: raw/source metadata recovery

## OOD benign represents deploy-time normal drift

- required evidence: valid ID/OOD drift plus timestamp/capture/deployment interpretation
- current evidence: ood_shift_too_artificial_or_row_order_bound
- missing evidence: split is row-order based, no timestamp/capture/session metadata
- risk level: `high`
- next check: raw timestamp/capture reconstruction or second dataset

## low OOD alert constraint has practical meaning

- required evidence: OOD benign is pure and sufficiently shifted, threshold tradeoff exists
- current evidence: low_ood_alert_problem_artifact_risk
- missing evidence: problem validity is weakened if OOD drift is row-order/source artifact
- risk level: `high`
- next check: score-dump threshold curves after semantic split validation

## attack eval represents attack behavior rather than data construction trace

- required evidence: attack/benign separation not dominated by row suffix, source, or scale artifact
- current evidence: attack_benign_artifact_risk
- missing evidence: all attack rows are after benign rows; no capture/source metadata
- risk level: `blocking`
- next check: raw provenance or independently interleaved/capture-disjoint split

## detection collapse under low-OOD-alert constraint is a real evaluation phenomenon

- required evidence: models show attack detection loss under <=1% OOD alarm on semantically valid split
- current evidence: low_ood_alert_problem_artifact_risk
- missing evidence: issue27p rankings may be diagnostic if benchmark semantics are blocked
- risk level: `high`
- next check: rerun curves after semantic gate

## model ranking can be used for method comparison

- required evidence: benchmark semantics supported and high-performing models pass artifact audit
- current evidence: issue27p model ranking exists; issue27q_P0P1 flags DeepSADStyle_Lite as suspicious
- missing evidence: DeepSAD controls and semantic gates are not clean enough for main claim
- risk level: `blocking`
- next check: pause model line until semantic validity is resolved

## second dataset is only needed later for external generalization

- required evidence: within-dataset semantics are good enough for main benchmark
- current evidence: protocol reset plan says second dataset is external stage
- missing evidence: if full Mirai semantics remain blocked, second dataset or raw reconstruction becomes prerequisite
- risk level: `high`
- next check: decide after issue27r
