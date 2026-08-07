"""CKBY: DROCC feature snapshot dump (read-only reuse of the frozen CKBW assembly).

This script re-executes the *assembly half* of the frozen CKBW formal program
(issue27ckbw_tail_margin_dual_control_v1.run_formal) unchanged — same inputs,
same asserts, same UnifiedFeatureStore — and stops before any preprocessing,
training, or scoring.  It exports the raw 51-D causal features (pre-quantile)
for the union of:

* the GLOBAL fit_records (18,398 rows: 14,013 benign + 4,385 attack), and
* every uid appearing in the frozen ckbw_record_predictions.csv.gz
  (all five held_value slices).

Contract: ckbw_tail_margin_dual_control_preregistered_20260803.md (data roles)
+ ckby_drocc_record_capacity_baseline_preregistered_20260807.md (FROZEN)
+ ckby_preregistered_erratum_1_feature_snapshot_contract_20260807.md.

No PCAP decode, no frontend change, no model training, no threshold choice.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

OOD = Path(__file__).resolve().parent
if str(OOD) not in sys.path:
    sys.path.insert(0, str(OOD))

import issue27ckbw_tail_margin_dual_control_v1 as ckbw  # noqa: E402

ckbu = ckbw.ckbu
ckbo = ckbw.ckbo
ckbq = ckbw.ckbq
raw51 = ckbw.raw51

ISSUE = "issue27ckby_drocc_feature_dump_v1_2026-08-07"
SEED = 27
FIT_ROWS = 18_398
FIT_BENIGN_ROWS = 14_013
FIT_ATTACK_ROWS = 4_385
SELECT_BENIGN_ROWS = 7_000
SELECT_ATTACK_ROWS = 69


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument(
        "--held-values",
        default=",".join(str(value) for value in ckbw.EXPECTED_PROTOCOLS[1:]),
    )
    # Same runtime-asset contract as the CKBW formal CLI (no defaults).
    parser.add_argument("--t0-root", type=Path, required=True)
    parser.add_argument("--report-t0-extension", type=Path, required=True)
    parser.add_argument("--c1-plan", type=Path, required=True)
    parser.add_argument("--c1-targets", type=Path, required=True)
    parser.add_argument("--c1-cache", type=Path, required=True)
    parser.add_argument("--c1-report-extension", type=Path, required=True)
    parser.add_argument("--gotham-manifest", type=Path, required=True)
    parser.add_argument("--gotham-cache", type=Path, required=True)
    parser.add_argument("--auxiliary-manifest", type=Path, required=True)
    parser.add_argument("--auxiliary-plan", type=Path, required=True)
    parser.add_argument("--auxiliary-cache", type=Path, required=True)
    parser.add_argument("--ton-cache", type=Path, required=True)
    parser.add_argument("--raw51-mask", required=True)
    parser.add_argument("--raw51-mask-sha256", required=True)
    parser.add_argument("--train-cap", type=int, default=4000)
    parser.add_argument("--eval-cap", type=int, default=3000)
    # Frozen CKBW record table (from the completed 157624 run root) used only
    # for the snapshot coverage assertion.
    parser.add_argument("--record-predictions", type=Path, required=True)
    parser.add_argument(
        "--snapshot-name", default="ckby_drocc_feature_snapshot_seed27.npz"
    )
    return parser.parse_args()


def main() -> None:
    started = time.time()
    args = parse_args()
    if int(args.seed) != SEED:
        raise RuntimeError("CKBY dump is preregistered for seed 27 only")
    closure = ckbu.validate_frozen_formal_dependency_closure()
    print(json.dumps(closure, indent=2, sort_keys=True), flush=True)
    np.random.seed(SEED)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    # --- Assembly: mirrors ckbw.run_formal lines 1719-1789 exactly. ---
    (
        x_by_role,
        report_frames,
        input_audit,
        t0,
        t0_audit,
        extension_audit,
        c1_extension_audit,
    ) = ckbq.prepare_inputs(args, out)
    print("CKBY_DUMP_STAGE prepare_inputs ok", flush=True)
    model_frames, permanent = ckbo.permanently_mask_frames(report_frames)
    model_frames, frozen_scope = ckbo.restrict_model_scope_to_frozen_targets(
        model_frames, Path(args.c1_targets), t0
    )
    requested = [value.strip() for value in str(args.held_values).split(",") if value.strip()]
    dev_holds = ckbo.legal_development_holds(report_frames, requested)
    protocols = ckbo.formal_protocol_values(requested, dev_holds)
    if protocols != ckbw.EXPECTED_PROTOCOLS:
        raise RuntimeError(f"CKBY protocol boundary drift: {protocols}")
    mask = raw51.load_raw51_mask(args.raw51_mask, args.raw51_mask_sha256)
    args.raw51_masked_pairs = frozenset(
        (source, int(index)) for source, indices in mask.items() for index in indices
    )
    observable, masked_pairs = ckbw._observable_predicate(args)
    store = ckbu.UnifiedFeatureStore(
        Path(args.gotham_manifest),
        Path(args.gotham_cache),
        Path(args.auxiliary_manifest),
        Path(args.auxiliary_cache),
    )
    aux = ckbu.auxiliary_records(Path(args.auxiliary_plan))
    ton, ton_features, ton_audit = ckbu.ton_records(Path(args.ton_cache))
    position_cache: dict[str, dict[int, int]] = {}
    assemblies = {
        held: ckbw.assemble_protocol(
            held,
            args,
            x_by_role,
            report_frames,
            model_frames,
            t0,
            position_cache,
            aux,
            ton,
            observable,
        )
        for held in protocols
    }
    print("CKBY_DUMP_STAGE assemblies ok", flush=True)
    global_asm = assemblies[None]
    ckbw.assert_global_pool_contract(global_asm)
    for held in protocols[1:]:
        ckbw.assert_protocol_identity(global_asm, assemblies[held])

    # --- Union of records with global-pool tagging (priority: fit > select > report).
    ordered: list = []
    pool_of: dict[str, str] = {}

    def feed(records, pool: str) -> None:
        for record in records:
            uid = str(record.uid)
            if uid not in pool_of:
                pool_of[uid] = pool
                ordered.append(record)

    feed(global_asm["fit_records"], "fit")
    feed(global_asm["select_attack"], "select_attack")
    feed(global_asm["select_benign_observable"], "select_benign")
    for held in protocols:
        feed(assemblies[held]["report_records"], "report-only")
    print(f"CKBY_DUMP_STAGE union ok unique_uids={len(ordered)}", flush=True)

    # --- Features: raw 51-D causal rows (pre-quantile), identical store path.
    feature_map = dict(ton_features)
    store.add(
        [record for record in ordered if not str(record.uid).startswith("ton:")],
        feature_map,
    )
    missing = [str(record.uid) for record in ordered if str(record.uid) not in feature_map]
    if missing:
        raise RuntimeError(f"CKBY snapshot feature coverage missing: {missing[:5]}")

    # --- Contract assertions (erratum 1, section 2).
    fit_records = [record for record in ordered if pool_of[str(record.uid)] == "fit"]
    fit_benign = sum(int(record.label) == 0 for record in fit_records)
    fit_attack = sum(int(record.label) == 1 for record in fit_records)
    if (len(fit_records), fit_benign, fit_attack) != (
        FIT_ROWS,
        FIT_BENIGN_ROWS,
        FIT_ATTACK_ROWS,
    ):
        raise RuntimeError(
            f"CKBY fit cardinality drift: {len(fit_records)}/{fit_benign}/{fit_attack}"
        )
    select_benign = [
        record for record in ordered if pool_of[str(record.uid)] == "select_benign"
    ]
    select_attack = [
        record for record in ordered if pool_of[str(record.uid)] == "select_attack"
    ]
    if len(select_benign) != SELECT_BENIGN_ROWS or len(select_attack) != SELECT_ATTACK_ROWS:
        raise RuntimeError(
            f"CKBY select cardinality drift: {len(select_benign)}/{len(select_attack)}"
        )
    sel_aux = sum(str(record.role) == "aux_select" for record in select_benign)
    sel_ton = sum(str(record.role) == "aux_normal_select" for record in select_benign)
    if (sel_aux, sel_ton) != (3_000, 4_000):
        raise RuntimeError(f"CKBY select composition drift: aux={sel_aux} ton={sel_ton}")

    table_uids = pd.read_csv(args.record_predictions, usecols=["uid"])["uid"].astype(str)
    table_unique = set(table_uids.unique())
    snapshot_uids = {str(record.uid) for record in ordered}
    uncovered = table_unique - snapshot_uids
    if uncovered:
        raise RuntimeError(
            f"CKBY snapshot misses {len(uncovered)} record-table uids: "
            f"{sorted(uncovered)[:5]}"
        )

    # --- Materialize arrays.
    uids = np.asarray([str(record.uid) for record in ordered])
    x = np.vstack([feature_map[uid] for uid in uids]).astype(np.float32)
    if x.shape != (len(ordered), ckbw.INPUT_DIM) or not np.isfinite(x).all():
        raise RuntimeError(f"CKBY snapshot matrix invalid: {x.shape}")
    snapshot_path = out / str(args.snapshot_name)
    np.savez_compressed(
        snapshot_path,
        uid=uids,
        x=x,
        role=np.asarray([str(record.role) for record in ordered]),
        m1_phase=np.asarray([str(record.m1_phase) for record in ordered]),
        source=np.asarray([str(record.source) for record in ordered]),
        device_family=np.asarray([str(record.device_family) for record in ordered]),
        attack_family=np.asarray([str(record.attack_family) for record in ordered]),
        label=np.asarray([int(record.label) for record in ordered], dtype=np.int8),
        recorded_index=np.asarray(
            [int(record.recorded_index) for record in ordered], dtype=np.int64
        ),
        raw51_observable=np.asarray(
            [bool(observable(record)) for record in ordered], dtype=bool
        ),
        global_pool=np.asarray([pool_of[uid] for uid in uids.tolist()]),
        feature_names=np.asarray(ckbw.ckbu.frontend.FEATURE_NAMES),
    )
    digest = sha256_file(snapshot_path)
    audit = {
        "issue": ISSUE,
        "seed": SEED,
        "snapshot": str(snapshot_path),
        "snapshot_sha256": digest,
        "snapshot_rows": int(len(ordered)),
        "feature_dim": int(x.shape[1]),
        "raw_features_pre_quantile": True,
        "fit_rows": len(fit_records),
        "fit_benign_rows": int(fit_benign),
        "fit_attack_rows": int(fit_attack),
        "select_benign_rows": len(select_benign),
        "select_attack_rows": len(select_attack),
        "record_table_rows": int(len(table_uids)),
        "record_table_unique_uids": int(len(table_unique)),
        "record_table_coverage": "100%",
        "raw51_masked_pairs": int(len(masked_pairs)),
        "raw51_observable_rows": int(
            sum(bool(observable(record)) for record in ordered)
        ),
        "pool_counts": {
            pool: int(sum(1 for value in pool_of.values() if value == pool))
            for pool in ("fit", "select_attack", "select_benign", "report-only")
        },
        "protocols": [str(value) for value in protocols],
        "wall_seconds": time.time() - started,
        "status": "CKBY_FEATURE_SNAPSHOT_COMPLETE",
    }
    ckbu.dump_json(out / "ckby_feature_snapshot_audit.json", audit)
    print(json.dumps(audit, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
