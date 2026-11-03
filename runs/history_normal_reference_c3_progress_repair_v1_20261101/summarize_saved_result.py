"""Reporting only: read the verified one-shot result; no models or distances."""
from common import *
from hnr.assets import helpers
from hnr import evaluation as ev


def rates(report):
    n, a = report['corrected']['normal'], report['corrected']['attack']
    return dict(fpr_percent=100 * n['weighted_rate'], normal_rows=n['rows'],
                fp=n['positive'], unweighted_fpr_percent=100 * n['rate'],
                recall_percent=100 * a['weighted_rate'] if a['rows'] else None,
                attack_rows=a['rows'], fn=a['negative'])


def main():
    acceptance = read(HERE / 'FINAL_ACCEPTANCE.json')
    need(acceptance['status'] == 'PASS', 'VERIFIED_RESULT_REQUIRED')
    result = read(HERE / 'output/RESULT.json')
    old = read(C2 / 'output/RESULT.json')
    need(sha(HERE / 'output/RESULT.json') == acceptance['result_sha256'], 'RESULT_PIN')
    summary = dict(status=result['status'], adoption=result['adoption'],
                   evidence=result['evidence'], target_failures=result['target_failures'],
                   distance_pairs=result['distance_pairs'], pools={}, devices={})
    for pool in ev.POOLS:
        summary['pools'][pool] = {}
        for view in ('full', ev.PRIMARY):
            summary['pools'][pool][view] = {}
            for head in ev.SUFFIXES:
                before = old['pools'][pool]['views'][view]['reports'][head]
                after = result['pools'][pool]['views'][view]['reports'][head]
                summary['pools'][pool][view][head] = dict(
                    C2=rates(before), C3=rates(after),
                    relative_C2=after['relative_C2'],
                    added_attack_misses_vs_RAW=after['added_attack_misses'],
                    protection=after['protection']['status'])
        before = old['pools'][pool]['views'][ev.PRIMARY]['reports']['ensemble']
        after = result['pools'][pool]['views'][ev.PRIMARY]['reports']['ensemble']
        prior = {g['group']['device']: g for g in before['groups']['device']}
        summary['devices'][pool] = {g['group']['device']: dict(C2=rates(prior[g['group']['device']]), C3=rates(g))
                                   for g in after['groups']['device']}
    spec = read(C1 / 'config/ASSETS.json')['pools']['CIC_DEV']
    rr = list(rows(ROOT / spec['query']['rows']['path']))
    metrics = helpers().metrics
    ix = np.flatnonzero(metrics.post_window_mask(rr, spec['windows']))
    subset = [rr[int(i)] for i in ix]
    weights = metrics.hierarchical_weights(subset, 'CIC_DEV')
    with np.load(HERE / 'output/ab/CIC_DEV/DECISIONS.npz', allow_pickle=False) as z:
        before, after = z['c2_corrected'][ix, 3], z['corrected'][ix, 3]
    mask = np.array([r['device'] == HEIM and r['label'] == 0 for r in subset])
    device_mass = weights[mask].sum()
    def describe(selected):
        return dict(rows=int(selected.sum()), c2_fp=int((selected & before).sum()),
                    c3_fp=int((selected & after).sum()),
                    fixed=int((selected & before & ~after).sum()),
                    added=int((selected & ~before & after).sum()),
                    c2_device_fpr_contribution_pp=100 * weights[selected & before].sum() / device_mass,
                    c3_device_fpr_contribution_pp=100 * weights[selected & after].sum() / device_mass)
    summary['heim_protocols'] = {str(proto): describe(mask & np.array([r['protocol'] == proto for r in subset]))
                                 for proto in (6, 17)}
    summary['heim_captures'] = {capture: describe(mask & np.array([r['capture_id'] == capture for r in subset]))
                               for capture in sorted({r['capture_id'] for r in subset if r['device'] == HEIM and r['label'] == 0})}
    summary['input_sha256'] = {
        'C3_RESULT': sha(HERE / 'output/RESULT.json'),
        'C2_RESULT': sha(C2 / 'output/RESULT.json'),
        'FINAL_ACCEPTANCE': sha(HERE / 'FINAL_ACCEPTANCE.json'),
        'C3_A_DECISIONS': sha(HERE / 'output/ab/CIC_DEV/DECISIONS.npz'),
        'A_QUERY_ROWS': sha(ROOT / spec['query']['rows']['path']),
        'reporting_script': sha(Path(__file__)),
    }
    write(HERE / 'RESULT_READOUT.json', summary, exclusive=True)
    compact = dict(status=summary['status'], adoption=summary['adoption'],
                   primary={p: summary['pools'][p][ev.PRIMARY]['ensemble'] for p in ev.POOLS},
                   devices=summary['devices'], heim_protocols=summary['heim_protocols'],
                   heim_captures=summary['heim_captures'], target_failures=summary['target_failures'])
    print(json.dumps(serial(compact), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
