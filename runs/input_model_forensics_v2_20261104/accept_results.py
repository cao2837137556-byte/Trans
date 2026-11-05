"""Accept the bounded runtime and independent raw-input audit, not model efficacy."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,collections
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,d):(HERE/name).write_bytes((json.dumps(d,ensure_ascii=False,allow_nan=False,indent=2)+'\n').encode())
def main():
    retrieval=read(HERE/'RETRIEVAL.json');state=read(HERE/'REMOTE_STATE.json')
    assert state['stage']=='PASS' and not state['FULL_STOP'] and not state['PREFLIGHT_STOP']
    for name,pin in retrieval['sha256'].items():assert sha(HERE/name)==pin,name
    for name,pin in read(HERE/'DELIVERY.json')['pins'].items():
        path=HERE/('.private/AB_SAMPLES.json.gz' if name=='AB_SAMPLES.json.gz' else name)
        assert sha(path)==pin,name
    full=read(HERE/'FULL_RESULT.json');pre=read(HERE/'PREFLIGHT_RESULT.json')
    assert full['status']==pre['status']=='PASS'
    assert '182267|COMPLETED|0:0|00:02:39|' in state['FULL_SCHEDULER']['stdout']
    assert '182266|COMPLETED|0:0|00:00:18|' in state['PREFLIGHT_SCHEDULER']['stdout']
    assert full['same_encoder_checkpoint_as_ab'] and full['encoder_eval'] and full['encoder_frozen']
    assert full['weight_check']['all_exact'] and full['weight_check']['checked_names']==337
    assert len(full['weight_check']['shared_aliases'])==11
    spec=read(ROOT/'runs/history_sample_coverage_c4_batch_resume_v1_20261102/config/ASSETS.json')
    for seed in ['27','127','227']:
        p=spec['heads']['endpoints'][seed]['head.npz'];assert sha(ROOT/p['path'])==p['sha256']==full['same_heads_and_normalizer_pins'][p['path']]
    p=spec['calibration']['normalizer'];assert sha(ROOT/p['path'])==p['sha256']==full['same_heads_and_normalizer_pins'][p['path']]
    samples=full['samples'];assert len(samples)==19 and len({s['uid'] for s in samples})==19
    assert collections.Counter(s['dataset'] for s in samples)=={'CIC_DEV':6,'UNSW_DEV':4,'EDGE':9}
    cut=read(ROOT/'runs/c5_method_freeze_v1_20261102/METHOD_FREEZE.json')['calibration']['cuts']['ensemble_cut']
    assert all(s['e3_max_abs_error']==0 and s['same_seed_decisions'] for s in samples)
    assert all((sum(s['fresh_scores'])/3>cut)==(sum(s['saved_scores'])/3>cut) for s in samples)
    assert all(s['head_max_abs_error']<=.002 and s['numpy_head_max_abs_error']<=.002 for s in samples)
    assert all(s['fresh_e3_std']>0 and any(v!=0 for v in s['e3_zero_branch_score_delta']) and any(v!=0 for v in s['q14_zero_branch_score_delta']) for s in samples)
    byuid={s['uid']:s for s in samples};http=read(HERE/'RAW_HTTP_INPUT_RESULT.json')
    assert len(http['samples'])==5
    for x in http['samples']:
        y=byuid[x['uid']];assert y['dataset']=='EDGE' and y['group']=='HTTP/'+x['stratum']
        assert x['input_sha256']==y['input_sha256'] and x['packets']==y['packets']
    write('RAW_HTTP_INPUT_PARITY.json',dict(status='PASS',rows=5,all_input_tensor_hashes_exact=True,
        raw_reconstruction_sha256=sha(HERE/'RAW_HTTP_INPUT_RESULT.json'),model_replay_sha256=sha(HERE/'FULL_RESULT.json'),
        samples=http['samples'],scope='Independent raw PCAP/context construction versus saved and freshly regenerated model-input tensors; one fixed UID per HTTP stratum'))
    udp=read(HERE/'RAW_UDP_RESULT.json');q=read(HERE/'RAW_Q14_PARITY.json')
    assert udp['status']==q['status']=='PASS' and udp['queries']==20000 and udp['query_prefix_packet_counts']=={'1':20000}
    assert udp['query_is_first_key_frame']==20000 and q['saved_q14_matches_all']
    acceptance=dict(
        result='PASS_BOUNDED_INPUT_MODEL_EXECUTION_AUDIT',
        impact='No model replacement, missing feature branch, checkpoint load failure, or saved-feature/score discrepancy found in the checked scope. This does not reverse the external efficacy FAIL.',
        next='Separate representation design and learned decision-boundary generalization with a preregistered diagnostic ablation; no new model or threshold change has been made.',
        verified_utc=datetime.now(timezone.utc).isoformat(),
        jobs=dict(initial_auditor_stop='182263: 51 seconds; shared-weight serialization assumption; no scientific source change',preflight='182266 COMPLETED/0:0, 18 seconds',full='182267 COMPLETED/0:0, 159 seconds'),
        resources=dict(cpu=1,memory_request_gib=8,full_batch_max_rss_kib=1612744,preflight_max_rss_reliable=False),
        checkpoint_sha256=full['checkpoint_sha256'],live_encoder_names_exact=337,shared_alias_names=11,
        actual_forward_rows=19,datasets=dict(collections.Counter(s['dataset'] for s in samples)),
        max_e3_abs_error=max(s['e3_max_abs_error'] for s in samples),
        max_head_abs_error=max(s['head_max_abs_error'] for s in samples),
        max_independent_numpy_head_abs_error=max(s['numpy_head_max_abs_error'] for s in samples),
        all_seed_and_ensemble_decisions_equal=True,e3_and_q14_branch_sensitivity_observed_all_samples=True,
        raw_udp_queries=20000,raw_udp_first_packet_queries=20000,raw_udp_q14_exact_queries=20000,
        independent_raw_http_tensor_exact_samples=5,
        unchanged_science=dict(training=0,threshold_fit=0,source_writes=0),
        limitations=['19 score-independent forward samples and 5 HTTP raw reconstruction samples are not universal bug absence proofs.',
                     'A/B snapshots were re-encoded but A/B raw packets were not independently reconstructed in this round.',
                     'Zero-branch sensitivity verifies wiring; it is not a trained performance ablation.',
                     'Remaining representation-design versus classifier-generalization causal contributions have not been experimentally separated.',
                     'No new independent Antigravity review.'],
        hpc_source='/public/home/jiangxinwei.zr/work/paper04/runs/edge_formal_evaluation_resume_v2_20261104/outputs/gate_182089',
        files={p.name:dict(sha256=sha(p),bytes=p.stat().st_size) for p in sorted(HERE.iterdir()) if p.is_file() and p.suffix in ['.py','.json','.html'] and p.name not in ['FINAL_ACCEPTANCE.json','CONNECTION.json']})
    write('FINAL_ACCEPTANCE.json',acceptance)
    print('PASS: result SHA, source pins, weights, 19 actual forwards, three heads plus ensemble, 20000 UDP q14 and five HTTP raw-to-input hashes.')
if __name__=='__main__':main()
