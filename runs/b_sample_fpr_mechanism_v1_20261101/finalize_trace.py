"""Recover reporting after Path-key JSON serialization failure; no distances."""
import audit as a
import json
from collections import defaultdict
import numpy as np

text=(a.HERE/'TRACE_SUMMARY.json').read_text(encoding='utf-8')
result=json.loads(text.rsplit(',\n  "asset_input_sha256":',1)[0]+'\n}')
assert result['status']=='FROZEN_SUPPORT_AND_ALL_HEAD_DECISIONS_REPRODUCED'
config,rows,saved,q,frozen,primary=a.load()
lookup={r['uid']:i for i,r in enumerate(rows)}
traces=a.rows(a.HERE/'NETATMO_NEIGHBORS.jsonl.gz')
card=a.read(a.HERE/'TRACE_CARD.json')
assert len(traces)==320
cohorts=defaultdict(list)
for r in traces:
    cohorts[r['cohort']].append(r['query']['uid'])
    i=lookup[r['query']['uid']]
    assert np.array_equal(q[i],r['query_q14']) and rows[i]==r['query']
    assert abs(r['support']-float(saved['support'][i]))<1e-12
    assert saved['eligible'][i] and not saved['guard'][i]
    assert len({n['reference']['component_id'] for n in r['neighbors']})==2
    for n in r['neighbors']:
        ref=n['reference']
        assert ref['device']==r['query']['device'] and ref['use']=='REFERENCE' and ref['label']==0
        assert ref['timestamp']<r['query']['timestamp']
    support=max(0.,1.-max(max(n['z_ratio'],n['q_ratio']) for n in r['neighbors']))
    assert abs(support-r['support'])<1e-12
assert dict(cohorts)==card['uids']
assert result['consumed_pairs']==card['requested_pairs']<=card['max_pairs']
assert result['elapsed_seconds']<card['max_seconds']
asset_pins={}
def verify(item):
    if isinstance(item,dict):
        if 'path' in item and 'sha256' in item:
            path=a.ROOT/item['path'];a.pin(path,item['sha256']);asset_pins[str(path.resolve())]=item['sha256']
        else:
            for value in item.values():verify(value)
    elif isinstance(item,list):
        for value in item:verify(value)
verify(config['calibration'])
verify(config['pools']['UNSW_DEV']['query'])
verify(config['pools']['UNSW_DEV']['dense_bank'])
for p,digest in result['input_sha256'].items():assert a.sha(p)==digest
result.update(asset_input_sha256=asset_pins,trace_sha256=a.sha(a.HERE/'NETATMO_NEIGHBORS.jsonl.gz'),
    reporting_recovery=dict(reason='WindowsPath dictionary keys in final JSON; all neighbor replay checks had completed',
        partial_file_preserved=True,repeat_distance_pairs=0,saved_trace_rows_rechecked=320,
        finalizer_sha256=a.sha(__file__),fixed_runner_sha256=a.sha(a.HERE/'trace_netatmo.py')))
a.write('TRACE_SUMMARY_RECOVERED.json',result)
print(json.dumps(dict(status='PASS_RECOVERED_REPORT',rows=320,pairs=result['consumed_pairs'],elapsed=result['elapsed_seconds'])))
