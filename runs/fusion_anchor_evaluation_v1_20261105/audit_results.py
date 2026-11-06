"""Audit retrieved small receipts; never fit, select, or download score arrays."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / 'device_context_evaluation_v1_20261105'
ARMS = ['OLD782', 'REFIT782', 'STATS8', 'FUSION790', 'ANCHOR790']
HEADS = ['27', '127', '227', 'ensemble']


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def same(a, b):
    if a is None or b is None:
        assert a is b
    else:
        assert math.isclose(a, b, rel_tol=0, abs_tol=1e-12), (a, b)


def main():
    completion = read(HERE / 'EVALUATION_COMPLETION.json')
    assert completion['status'] == 'PASS'
    for name, digest in completion['receipt_sha256'].items():
        assert sha(HERE / name) == digest, name
    for name, digest in read(HERE / 'ARTIFACT_SHA256.json').items():
        assert sha(HERE / name) == digest, name
    for name, digest in read(HERE / 'PARENT_PINS.json').items():
        assert sha(PRIOR / name) == digest, name

    result = {phase: read(HERE / (phase + '_RESULT.json')) for phase in ['PREFLIGHT', 'AB', 'EDGE']}
    resources = {}
    for phase, r in result.items():
        assert r['status'] == 'PASS'
        assert r['training'] is False and r['threshold_fitting'] is False and r['model_selection'] is False
        job = read(HERE / (phase + '_JOB.json'))
        scheduler = read(HERE / (phase + '_SCHEDULER.json'))
        assert scheduler['returncode'] == 0
        rows = [line.split('|') for line in scheduler['stdout'].splitlines()]
        main_row = next(row for row in rows if row[0] == str(job['job_id']))
        batch = next(row for row in rows if row[0] == str(job['job_id']) + '.batch')
        assert main_row[1:3] == ['COMPLETED', '0:0'] and batch[1:3] == ['COMPLETED', '0:0']
        assert job['cpu'] == 1 and job['memory_gib'] == 8
        h, m, s = map(int, main_row[3].split(':'))
        assert batch[4].endswith('K')
        resources[phase] = dict(job_id=job['job_id'], elapsed_seconds=h*3600+m*60+s,
                               scheduler_maxrss_kib=int(batch[4][:-1]), worker_seconds=r['seconds'],
                               worker_sampled_rss_peak_bytes=r['rss_peak_bytes'])
    pre = result['PREFLIGHT']
    assert pre['real_encoder_distance']['status'] == 'PASS'
    assert pre['real_encoder_distance']['encoded_rows'] == 112
    for key in ['e3_max_abs_error', 'cached_support_error', 'fresh_support_error']:
        assert pre['real_encoder_distance'][key] == 0

    ab = result['AB']; edge = result['EDGE']
    old_ab = read(PRIOR / 'AB_RESULT.json'); old_edge = read(PRIOR / 'EDGE_RESULT.json')
    summary = dict(AB={}, EDGE={}, margins={}, seed_errors={}, baseline_max_errors={})
    checked_baseline_metrics = 0
    for pool, d in ab['pools'].items():
        assert d['rows'] == old_ab['pools'][pool]['rows']
        assert d['primary_rows'] == old_ab['pools'][pool]['primary_rows']
        assert list(d['primary']) == ARMS
        assert d['candidate_gates']['evaluated_candidate'] == 'ANCHOR790'
        summary['AB'][pool] = {}
        summary['baseline_max_errors'][pool] = max(d['baseline_errors'].values())
        assert summary['baseline_max_errors'][pool] <= .002
        for arm, methods in d['primary'].items():
            summary['AB'][pool][arm] = {}
            assert list(methods) == (['RAW'] if arm == 'STATS8' else ['RAW', 'C5_P3'])
            for method, heads in methods.items():
                assert list(heads) == HEADS
                summary['AB'][pool][arm][method] = {}
                for head, info in heads.items():
                    group = info['groups']['pool']
                    for label, v in group.items():
                        assert v['alarm_count'] + v['no_alarm_count'] == v['rows']
                        same(v['unweighted_rate'], v['alarm_count']/v['rows'])
                        if arm != 'ANCHOR790':
                            prev = old_ab['pools'][pool]['primary'][arm][method][head]['groups']['pool'][label]
                            for key in ['rows', 'alarm_count', 'unweighted_rate', 'weighted_rate']:
                                same(v[key], prev[key]); checked_baseline_metrics += 1
                    if method == 'C5_P3':
                        for label, v in group.items():
                            assert v['alarm_count'] <= methods['RAW'][head]['groups']['pool'][label]['alarm_count']
                    summary['AB'][pool][arm][method][head] = dict(pool=group, c5_safety=info['c5_safety']['status'])
        summary['seed_errors'][pool] = d['seed_errors']
    assert edge['rows'] == 60000 and list(edge['arms']) == ARMS
    summary['baseline_max_errors']['EDGE'] = max(edge['baseline_errors'].values())
    assert summary['baseline_max_errors']['EDGE'] <= .002
    for arm, r in edge['arms'].items():
        assert r['query_rows'] == 60000
        summary['EDGE'][arm] = {}
        for method, data in r['methods'].items():
            assert list(data['heads']) == HEADS
            summary['EDGE'][arm][method] = {}
            for head, info in data['heads'].items():
                role_summary = {}
                for role, v in info['roles'].items():
                    assert v['selected_rows'] == 20000
                    assert v['alarm_count'] + v['no_alarm_count'] == 20000
                    same(v['exact_selected_sample_alarm_rate'], v['alarm_count']/20000)
                    if arm != 'ANCHOR790':
                        prev = old_edge['arms'][arm]['methods'][method]['heads'][head]['roles'][role]
                        for key in ['alarm_count', 'exact_selected_sample_alarm_rate', 'ht_population_alarm_estimate', 'selected_hierarchical_alarm_rate', 'normal_component_equal_alarm_rate']:
                            same(v[key], prev[key]); checked_baseline_metrics += 1
                    if method == 'C5_P3':
                        raw = r['methods']['RAW']['heads'][head]['roles'][role]['alarm_count']
                        assert v['alarm_count'] <= raw
                        if role != 'NORMAL':
                            margin = edge['margins'][arm]['scenario:' + role][head]
                            assert raw - v['alarm_count'] == margin['withdrawn_raw_TP']
                    role_summary[role] = {k: v[k] for k in ['selected_rows', 'alarm_count', 'exact_selected_sample_alarm_rate', 'ht_population_alarm_estimate', 'selected_hierarchical_alarm_rate', 'normal_component_equal_alarm_rate']}
                summary['EDGE'][arm][method][head] = dict(roles=role_summary, c5_safety=info['raw_cumulative_safety'])
    summary['seed_errors']['EDGE'] = edge['seed_errors']
    for arm, groups in edge['margins'].items():
        summary['margins'][arm] = {}
        for role in ['HTTP', 'UDP']:
            summary['margins'][arm][role] = {}
            for head, m in groups['scenario:' + role].items():
                assert sum(m['raw_margin_histogram']['counts']) == m['rows'] == 20000
                summary['margins'][arm][role][head] = {k: v for k,v in m.items() if k != 'raw_margin_histogram'}
    write('COMPARISON.json', summary)
    write('REAL_PREFLIGHT_ACCEPTANCE.json', dict(status='PASS', scope='ENGINEERING_ONLY', job_id='182554',
          encoder=pre['real_encoder_distance'], checks=pre['checks'], scheduler=resources['PREFLIGHT']))
    audit = dict(engineering_status='PASS', scientific_status='FAIL', candidate_adopted=False,
                 scope='FROZEN_THREE_DATASET_CONSUMED_DIAGNOSTIC_EVALUATION',
                 receipt_sha256=completion['receipt_sha256'], comparison_sha256=sha(HERE/'COMPARISON.json'),
                 baseline_pool_metric_comparisons=checked_baseline_metrics,
                 baseline_decision_parity='Enforced for all four prior arms in preflight and full workers before PASS',
                 resources=resources, total_scheduler_seconds=sum(v['elapsed_seconds'] for v in resources.values()),
                 max_scheduler_rss_gib=max(v['scheduler_maxrss_kib'] for v in resources.values())/1024**2,
                 ab_original_candidate_gates={p:d['candidate_gates'] for p,d in ab['pools'].items()},
                 edge_c5_safety={h:edge['arms']['ANCHOR790']['methods']['C5_P3']['heads'][h]['raw_cumulative_safety'] for h in HEADS},
                 rejection_reasons=['All three seeds and ensemble have zero Edge UDP detections before C5',
                                    'HTTP ensemble C5 recall falls from 94.995% to 46.51%; withdrawal rises from 967 to 6467',
                                    'Original A/B RAW gates and Edge C5 safety remain FAIL'],
                 interpretation='FPR and inter-seed alarm disagreement improved, but attack gains were not retained. No new tuning, seed or epoch selection.',
                 remote_artifacts={**{p:d['scores'] for p,d in ab['pools'].items()}, 'EDGE':edge['scores']})
    write('FINAL_EVALUATION_ACCEPTANCE.json', audit)

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
    for ax, role in zip(axes, ['HTTP', 'UDP']):
        for arm, color in [('OLD782','#666666'), ('FUSION790','#147d92'), ('ANCHOR790','#b93737')]:
            m = edge['margins'][arm]['scenario:' + role]['ensemble']; hist=m['raw_margin_histogram']
            ax.stairs([x/20000 for x in hist['counts']], hist['edges'], label=arm, color=color, linewidth=1.7)
        ax.axvline(0,color='black',linestyle='--',linewidth=1)
        if role == 'HTTP':
            ax.axvline(edge['margins']['ANCHOR790']['scenario:HTTP']['ensemble']['correction_bound'],color='#b93737',linestyle=':',label='ANCHOR C5 upper bound')
        ax.set(title=role + ' | fixed ensemble', xlabel='RAW score minus frozen threshold', ylabel='Fraction of 20,000 selected queries')
        ax.grid(alpha=.15);ax.legend(fontsize=8)
    fig.suptitle('Consumed Edge diagnostic evaluation; fixed heads and thresholds', fontsize=12)
    fig.savefig(HERE/'EDGE_MARGIN_COMPARISON.png',dpi=170)
    plt.close(fig)
    print(json.dumps({k:audit[k] for k in ['engineering_status','scientific_status','baseline_pool_metric_comparisons','total_scheduler_seconds','max_scheduler_rss_gib']}))


if __name__ == '__main__':
    main()
