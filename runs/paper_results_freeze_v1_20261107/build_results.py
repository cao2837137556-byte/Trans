"""Build paper tables from sealed small receipts. No inference, training or remote IO."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUN = ROOT / 'runs/same_bank_context_v6_20261106'
EVAL = ROOT / 'runs/device_context_evaluation_v1_20261105'
PRIOR = ROOT / 'runs/context_geometry_attribution_v2_20261106'
pins = {}
checks = 0


def check(ok):
    global checks
    checks += 1
    assert ok, checks


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read(p):
    pins[p.relative_to(ROOT).as_posix()] = sha(p)
    return json.loads(p.read_text(encoding='utf-8-sig'))


def save(name, obj):
    (HERE / name).write_bytes((json.dumps(obj, ensure_ascii=False, indent=2) + '\n').encode())


def table(name, headers, rows, note):
    text = '| ' + ' | '.join(headers) + ' |\n| ' + ' | '.join(['---'] * len(headers)) + ' |\n'
    text += ''.join('| ' + ' | '.join(map(str, r)) + ' |\n' for r in rows)
    (HERE / (name + '.md')).write_bytes((note + '\n\n' + text).encode())
    def esc(v):
        return str(v).replace('_', r'\_').replace('%', r'\%').replace('&', r'\&')
    tex = '% ' + note.replace('\n', ' ') + '\n\\begin{tabular}{' + 'l' * len(headers) + '}\n\\hline\n'
    tex += ' & '.join(map(esc, headers)) + r' \\' + '\n\\hline\n'
    tex += ''.join(' & '.join(map(esc, r)) + r' \\' + '\n' for r in rows)
    tex += '\\hline\n\\end{tabular}\n'
    (HERE / (name + '.tex')).write_bytes(tex.encode())


def pct(x):
    return f'{100*x:.6f}'


def main():
    d = read(RUN / 'DIAGNOSE_RESULT.json')
    acceptance = read(RUN / 'FORMAL_ACCEPTANCE.json')
    check(acceptance['engineering'] == 'PASS' and acceptance['checks'] == 5261)
    for n, h in read(RUN / 'EVALUATION_COMPLETION.json')['receipt_sha256'].items():
        check(sha(RUN / n) == h)
        pins[(RUN / n).relative_to(ROOT).as_posix()] = h
    for n, h in read(RUN / 'DELIVERY.json')['pins'].items():
        check(sha(RUN / n) == h)
        pins[(RUN / n).relative_to(ROOT).as_posix()] = h
    for n, h in read(RUN / 'INPUT_PINS.json').items():
        check(sha(ROOT / n) == h)
        pins[n] = h
    spec = read(RUN / 'SPEC.json')
    read(RUN / 'HISTORY_INPUTS.json')
    read(RUN / 'HISTORY_INVENTORY.json')
    trained = read(EVAL / 'FINAL_TRAINING_ACCEPTANCE.json')
    legacy = read(EVAL / 'METHOD_FREEZE.json')
    read(EVAL / 'OLD_ASSETS.json')
    read(EVAL / 'NORMALIZER.json')
    ab = read(EVAL / 'AB_RESULT.json')
    edge = read(EVAL / 'EDGE_RESULT.json')
    prior = read(PRIOR / 'DIAGNOSE_RESULT.json')
    check(sha(PRIOR / 'DIAGNOSE_RESULT.json') == spec['prior_result_sha256'])
    heads = ['27', '127', '227', 'ensemble']
    candidate = 'C5_3D_OLD'
    rows_all = []
    for pool, p in d['pools'].items():
        for view, methods in p['views'].items():
            for method, hs in methods.items():
                for head, groups in hs.items():
                    for group, m in groups.items():
                        check(abs(m['alarm_count']/m['rows'] - m['sample_rate']) < 1e-12)
                        rows_all.append(dict(pool=pool, view=view, method=method, head=head, group=group, **m))
    save('ALL_METRICS.json', rows_all)
    fields = ['Pool', 'View', 'Method', 'Group', 'Alarms/N', 'Sample (%)', 'Weighted (%)', 'HT (%)']
    def formatted(r):
        return [r['pool'], r['view'], r['method'], r['group'], f"{r['alarm_count']}/{r['rows']}", pct(r['sample_rate']), pct(r['hierarchical_rate']), pct(r['HT_rate']) if 'HT_rate' in r else '--']
    pooled = [r for r in rows_all if not r['group'].startswith('device:')]
    primary = lambda r: r['view'] == ('full' if r['pool'] == 'EDGE' else 'post_window_primary')
    table('T1_MAIN', fields, [formatted(r) for r in pooled if r['head']=='ensemble' and primary(r) and r['method'] in ['RAW','C5_FROZEN',candidate]],
          'Ensemble. NORMAL is FPR; ATTACK/HTTP/UDP are query detection rates. A/B are consumed development pools; Edge is consumed transfer diagnosis. All rate columns are percentages; no event-level claim.')
    table('T2_GEOMETRY_SCALE_ABLATION', fields, [formatted(r) for r in pooled if r['head']=='ensemble' and primary(r) and r['method'].startswith(('C5_2D_', 'C5_3D_'))],
          'Controlled 2x2 ablation: same FUSION790, full reference bank, query UIDs, thresholds and source radii; vary geometry and correction scale only. Not independent external baselines.')
    table('S1_FULL_AND_SEEDS', ['Head']+fields, [[r['head']]+formatted(r) for r in pooled if r['method']==candidate],
          'All three seeds and the fixed ensemble, all registered views; ensemble is not a fourth independent seed. Includes commissioning-period queries in full A/B views.')
    table('S2_DEVICE_BREAKDOWN', ['Head']+fields, [[r['head']]+formatted(r) for r in rows_all if r['method']==candidate and r['group'].startswith('device:')],
          'All available device strata, heads and views for the frozen candidate. Do not replace these with pooled performance.')
    front = []
    for pool, p in ab['pools'].items():
        for arm, methods in p['primary'].items():
            for h in heads:
                for group, m in methods['RAW'][h]['groups']['pool'].items():
                    front.append(dict(pool=pool,view='post_window_primary',method=arm,head=h,group=group.upper(),rows=m['rows'],alarm_count=m['alarm_count'],sample_rate=m['unweighted_rate'],hierarchical_rate=m['weighted_rate']))
    for arm, armdata in edge['arms'].items():
        for h in heads:
            for group,m in armdata['methods']['RAW']['heads'][h]['roles'].items():
                front.append(dict(pool='EDGE',view='full',method=arm,head=h,group=group,rows=m['selected_rows'],alarm_count=m['alarm_count'],sample_rate=m['exact_selected_sample_alarm_rate'],hierarchical_rate=m['selected_hierarchical_alarm_rate'],HT_rate=m['ht_population_alarm_estimate']))
    for r in front:
        check(abs(r['alarm_count']/r['rows']-r['sample_rate']) < 1e-12)
        if r['method']=='FUSION790':
            old = d['pools'][r['pool']]['views'][r['view']]['RAW'][r['head']][r['group']]
            for k in ['rows','alarm_count','sample_rate','hierarchical_rate']:
                check(abs(r[k]-old[k]) < 1e-12)
    save('FRONTEND_RAW_METRICS.json', front)
    table('T3_FRONTEND_RAW', fields, [formatted(r) for r in front if r['head']=='ensemble'],
          'Existing source-trained OLD782/REFIT782/STATS8/FUSION790 RAW comparison; REFIT782 is the matched-retraining control. Each arm keeps its own source-calibrated cut. No C5; not a claim that adding dimensions always improves all datasets. Full A/B frontend tables are not present in these small receipts; do not synthesize them.')
    history_rows=[]
    for pool in ['CIC_DEV','UNSW_DEV','EDGE']:
        view='full' if pool=='EDGE' else 'post_window_primary'
        for method in ['C5_2D_OLD','C5_3D_OLD']:
            for scope,src in [('commissioning_only',prior),('complete_bank',d)]:
                source_metrics = src['pools'][pool]['metrics'] if scope=='commissioning_only' else src['pools'][pool]['views'][view]
                for group,m in source_metrics[method]['ensemble'].items():
                    if group.startswith('device:'): continue
                    check(m['rows']==d['pools'][pool]['views'][view][method]['ensemble'][group]['rows'])
                    history_rows.append([scope]+formatted(dict(pool=pool,view=view,method=method,group=group,**m)))
    table('T4_REFERENCE_COVERAGE', ['Bank']+fields, history_rows,
          'Cross-run bank-scope comparison, fixed OLD scale and FUSION790. Previous commissioning-only and current complete-bank receipts; not a new randomized experiment. Edge bank is unchanged. Includes both 2D and 3D to expose bank-scope confounding.')
    freeze=dict(schema='PAPER_METHOD_FREEZE_V1',date='2026-11-07',status='FROZEN_FOR_PAPER_COMPARISON',
        authority='User: fix this scheme, organize paper main results and ablations, temporarily do not change model.',
        accepted_commit='002524d',method='FUSION790_FULL_HISTORY_C5_3D_OLD',variant_key=candidate,
        training_authorized=False,new_jobs_submitted=0,deployment_changed=False,model_updates_allowed=False,
        seeds=[27,127,227],heads={h:trained['heads']['FUSION790_'+h] for h in heads[:3]},
        ensemble=dict(rule='float64 arithmetic mean in seed order 27,127,227; strict score > cut',cut=trained['ensembles']['FUSION790']['cut']),
        correction=dict(p=legacy['p'],lambda_value=legacy['lambda'],scales=legacy['calibration']['scales']['scales'],scale_origin='OLD782 frozen source FIT scale, not OLD782 classifier or cuts',kernel=legacy['kernel'],guard=legacy['guard']),
        geometry=dict(joint='max(dz/rho_z, dq/rho_q, dc/rho_c)',support='clip(1-second_distinct_component_joint,0,1); two distinct legal components; unavailable=0',source_geometry=legacy['calibration']['geometry'],context_radii=d['calibration']),
        context=dict(window=spec['window'],b_timeline=spec['b_timeline'],a_timeline=spec['a_timeline'],normalizer=read(EVAL/'NORMALIZER.json')),
        references={pool:{'rows':p['reference_rows'],'uid_sha256':p['reference_uid_sha256']} for pool,p in d['pools'].items()},
        result_artifacts={pool:p['artifact'] for pool,p in d['pools'].items()},
        evidence_roles={'CIC_DEV':'CONSUMED_DEVELOPMENT','UNSW_DEV':'CONSUMED_DEVELOPMENT','EDGE':'CONSUMED_TRANSFER_DIAGNOSIS_NOT_UNTOUCHED_TEST'},
        reporting='A/B post_window_primary AND full, device strata, three seeds and ensemble, ordinary/hierarchical; Edge additionally HT; same protocol across pools',
        limitations=acceptance['exceptions'],prior_failed_scientific_gates_preserved=True,
        selection_scope='Pipeline selected after viewing A/B/Edge diagnostics; source-only numeric calibration does not make target evaluation untouched.',
        future_comparison='Any change requires a distinct version; no retrospective baseline or threshold selection on target results.',source_pins=pins)
    save('METHOD_FREEZE.json',freeze)
    save('SOURCE_PINS.json',pins)
    save('BUILD_VALIDATION.json',dict(status='PASS',checks=checks,all_metric_rows=len(rows_all),frontend_rows=len(front),
         source_hashes_verified=True,training=False,inference=False,remote_io=False,new_jobs=0,
         latex_status='generated tabular fragments; not compiled',statistical_intervals='NOT_COMPUTED_FROM_AGGREGATES'))
    print(json.dumps(dict(status='PASS',checks=checks,metrics=len(rows_all),frontend=len(front))))


if __name__ == '__main__':
    main()
