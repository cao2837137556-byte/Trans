"""Derive review numbers from exact downloaded summaries, without model execution."""
from datetime import datetime, timezone
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
POOLS = ('CIC_DEV', 'UNSW_DEV')
BANKS = ('OLD_BANK', 'B0', 'B1', 'B2')
ARMS = ('BASE', 'V3', 'L_STANDARD', 'L_HARD', 'L_QUERY_ONLY')


def read(name):
    return json.loads((ROOT/name).read_text(encoding='utf-8'))


def main():
    output = ROOT/'evaluation/results/evaluation'
    summaries = {tuple(p.relative_to(output/'predictions').parts[:3]):
                 json.loads(p.read_text(encoding='utf-8'))
                 for p in (output/'predictions').rglob('summary.json')}
    main_keys = {(p, b, a) for p in POOLS for b in BANKS for a in ARMS}
    control_keys = {(p, b, a) for p in POOLS for b in ('EMPTY', 'WRONG') for a in ARMS[2:]}
    assert set(summaries) == main_keys | control_keys
    decision = read('evaluation/results/evaluation/decision.json')
    calibration = read('parent/runs/learned_onboarding_v1_20261023/results/calibration/calibration.json')
    status = read('evaluation/state/status.json')
    chain = read('evaluation/state/CHAIN_COMPLETE.json')
    accepted = read('evaluation/state/ACCEPTANCE.json')
    table = []
    for pool in POOLS:
        for bank in BANKS:
            for arm in ARMS:
                s = summaries[pool, bank, arm]
                table.append(dict(pool=pool, bank=bank, arm=arm, rows=s['rows'],
                    normal_rows=s['corrected']['normal']['rows'],
                    fp=s['corrected']['normal']['positive'],
                    raw_fpr=s['corrected']['normal']['rate'],
                    weighted_fpr=s['corrected']['normal']['weighted_rate'],
                    raw_attack_recall=s['corrected']['attack']['rate'],
                    weighted_attack_recall=s['corrected']['attack']['weighted_rate'],
                    new_fn=s['new_fn_count'], fixed_fp=s['corrected_normal_fp'],
                    eligible_fp=s['eligible_normal_fp'],
                    raw_fp_lower_bound=s['normal_fp_lower_bound'],
                    lambda_value=s['lambda_value'], scale=s['scale'],
                    pool_fpr_goal_pass=s['pool_normal_fpr_1pct'],
                    device_fpr_goal=s['device_normal_fpr_2pct']))
    assert all(x['new_fn_count'] == 0 for x in summaries.values())
    assert all(x['corrected']['attack']['rate'] == 1 and
               x['corrected']['attack']['weighted_rate'] == 1 for x in summaries.values())
    assert accepted['prediction_rows'] == sum(s['rows'] for s in summaries.values())
    a = summaries['CIC_DEV', 'B2', 'L_HARD']
    b = summaries['UNSW_DEV', 'B2', 'L_HARD']
    assert a['base']['normal']['positive'] == a['normal_fp_lower_bound']['total_count']+24
    assert a['corrected_normal_fp'] == 0
    cal = {}
    for arm, item in calibration['arms'].items():
        selected = next(x for x in item['candidates'] if x['lambda_value'] == item['selected_lambda'])
        cal[arm] = dict(status=item['status'], selected_lambda=item['selected_lambda'],
            legal_pairs=item['legal_pairs'], cal_attack_rows=item['cal_attack_rows'],
            cap_reachable_detected_attack_count=selected['cap_reachable_detected_attack_count'],
            minimum_positive_margin_over_cap=selected['minimum_positive_margin_over_cap'])
    result = dict(schema='paper04-independent-evaluation-review-v1',
        recorded_at=datetime.now(timezone.utc).isoformat(),
        scientific_scope='QUERY_TAIL seed27, consumed A/B development pools, B2 preregistered primary bank',
        engineering_status='COMPLETE', started_at=status['started_at'], ended_at=chain['ended_at'],
        elapsed_seconds=status['elapsed_seconds'], peak_rss_gib=status['peak_process_tree_rss']/2**30,
        output_bytes=status['output_bytes'], output_gib=status['output_bytes']/2**30,
        main_cells=len(main_keys), control_cells=len(control_keys),
        prediction_records=accepted['prediction_rows'], prior_summaries_identical=accepted['prior_summaries_equal'],
        distinct_queries_per_pool={p:summaries[p, 'B2', 'BASE']['rows'] for p in POOLS},
        all_main_and_control_new_fn_zero=True, all_observed_attack_recall_100pct=True,
        benefit={arm:value['status'] for arm,value in decision['learned_benefit'].items()},
        hard_task_value=decision['hard_task_value']['status'],
        reference_attribution=decision['reference_attribution']['status'],
        wrong_reference_control=decision['reference_attribution']['wrong_control'],
        calibration=cal, primary_bank='B2', b2=[x for x in table if x['bank']=='B2'], all_main_cells=table,
        a_b2_coverage=dict(base_fp=a['base']['normal']['positive'],eligible_fp=a['eligible_normal_fp'],
            ineligible_fp=a['normal_fp_lower_bound']['ineligible_count'],
            cap_unreachable_fp=a['normal_fp_lower_bound']['cap_unreachable_count'],
            theoretically_reachable_fp=24,actually_fixed_fp=a['corrected_normal_fp']),
        b_b2_raw_fp_lower_bound=b['normal_fp_lower_bound'],
        lower_bound_scope='raw counts/rates, NOT weighted FPR; fixed eligibility and current maximum cap',
        final_full_low_fpr_goal_reached=False, development_evidence_only=True, automatic_promotion=False)
    with (ROOT/'ANALYSIS_SUMMARY.json').open('x',encoding='utf-8') as stream:
        json.dump(result,stream,ensure_ascii=False,indent=2,allow_nan=False)
        stream.write('\n')
    print(json.dumps(dict(engineering='COMPLETE',main_cells=40,control_cells=12,
                          hard_task_value=result['hard_task_value'],
                          reference_attribution=result['reference_attribution'],
                          final_full_low_fpr_goal_reached=False),ensure_ascii=False))


if __name__ == '__main__':
    main()
