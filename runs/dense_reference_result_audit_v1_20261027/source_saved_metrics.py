"""Read-only source CAL metrics; corrected normal FPR is summary-derived."""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import numpy as np

spec = importlib.util.spec_from_file_location('dense_saved_audit', Path(__file__).with_name('audit_readback.py'))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--science', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    root, science, output = (Path(x).resolve() for x in (args.root, args.science, args.output))
    audit.check(not output.exists(), 'FRESH_METRICS_OUTPUT')
    basepath = root / 'runs/diagnostics_d1_d2_v1_20261022'
    metadata = basepath / 'assets/heads/run/prepared/LEARN.jsonl.gz'
    rows = []
    with gzip.open(metadata, 'rt', encoding='utf-8') as stream:
        for line in stream:
            row = json.loads(line)
            if row['fit_role'] == 'CAL':
                rows.append(row)
    with np.load(basepath / 'output/d1/r2/source_actual_trace.npz', allow_pickle=False) as data:
        audit.check(data['uid'].tolist() == [r['uid'] for r in rows], 'SAVED_TRACE_UID_ORDER')
        decisions = data['original_decisions'].copy()
    normal_ix = np.flatnonzero([r['label'] == 0 for r in rows])
    normal_rows = [rows[i] for i in normal_ix]
    nw = audit.weights(normal_rows)
    normal_decisions = decisions[normal_ix]
    denominator = math.fsum(nw)
    baseline = {suffix: dict(weighted_fpr_percent=100 * math.fsum(nw[normal_decisions[:, k]]) / denominator,
                            raw_fp=int(normal_decisions[:, k].sum()), normal_rows=len(normal_rows))
                for k, suffix in enumerate(audit.SUFFIXES)}
    arms = {}
    for arm in ('R-B2', 'R-DENSE'):
        prep = audit.read(science / 'source_cal' / arm / 'PREPARATION.json')
        selection = audit.read(science / 'source_cal' / arm / 'EPSILON_0p1.json')
        chosen = next(c for c in prep['candidates'] if c['lambda_value'] == selection['selected_lambda'])
        arms[arm] = dict(main_epsilon_pp=0.1, selected_lambda=selection['selected_lambda'],
                        budget_acceptance=selection['selected_budget_acceptance'], suffixes={})
        for suffix in audit.SUFFIXES:
            reduction_pp = 100 * chosen['normal_fp_reduction'][suffix]
            arms[arm]['suffixes'][suffix] = dict(
                normal_fp_reduction_pp_saved_summary=reduction_pp,
                corrected_fpr_percent_derived_from_summaries=baseline[suffix]['weighted_fpr_percent'] - reduction_pp,
                baseline_attack_recall_percent=100 * chosen['overall']['suffixes'][suffix]['baseline_recall'],
                protected_attack_recall_percent=100 * chosen['overall']['suffixes'][suffix]['corrected_recall'],
                attack_recall_loss_pp=chosen['overall']['suffixes'][suffix]['recall_loss_pp'],
                added_fn_count=chosen['overall']['suffixes'][suffix]['added_fn_count'],
                max_device_attack_recall_loss_pp=max(item['suffixes'][suffix]['recall_loss_pp']
                    for item in chosen['devices'].values() if item['weight_mass'] > 0),
                max_annotation_attack_recall_loss_pp=max(item['suffixes'][suffix]['recall_loss_pp']
                    for item in chosen['annotations'].values() if item['weight_mass'] > 0))
    result = dict(status='PASS', created_utc=datetime.now(timezone.utc).isoformat(),
        script_sha256=audit.sha(__file__), source_cal_rows=len(rows), normal_rows=len(normal_rows),
        attack_rows=len(rows) - len(normal_rows), baseline=baseline, arms=arms,
        dense_additional_normal_fpr_reduction_pp={suffix:
            arms['R-DENSE']['suffixes'][suffix]['normal_fp_reduction_pp_saved_summary'] -
            arms['R-B2']['suffixes'][suffix]['normal_fp_reduction_pp_saved_summary'] for suffix in audit.SUFFIXES},
        qualifications=[
            'Baseline FPR reconstructed directly from saved original decisions and frozen hierarchical normal weights.',
            'Corrected normal FPR derived by subtracting the saved weighted FP-reduction summary; corrected query support, UIDs, scores and raw corrected FP counts were not persisted or independently reconstructed.',
            'Attack protection is the conservative union of withdrawals across legal source donors; source CAL safety does not guarantee target safety.',
            'No model forward, distance/CAL recomputation, training, or target evaluation occurred.'
        ])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
