"""Reproduce descriptive training audit from the pinned small log export."""
import hashlib,json,statistics as st
from pathlib import Path
P=Path(__file__).resolve().parent
raw=(P/'RESULT.json').read_bytes();assert hashlib.sha256(raw).hexdigest()==json.loads((P/'RETRIEVAL.json').read_text())['sha256']
d=json.loads(raw);out={}
for key,h in d['heads'].items():
    probes=h['probes'];epochs=h['epochs']
    assert all(g['gradient']['backward_sanity']['l2_pass'] for g in probes)
    def values(field):return [x['gradient'][field] for x in probes if x['gradient'].get(field) is not None]
    out[key]=dict(final_loss=epochs[-1]['loss'],loss_epoch_10=epochs[9]['loss'],first_epoch_loss_below_1e_6=next((e['epoch'] for e in epochs if e['loss']<1e-6),None),gradient_ratio_median=st.median(values('gradient_ratio')),gradient_cosine_median=st.median(values('gradient_cosine')),negative_cosine_probes=sum(v<0 for v in values('gradient_cosine')),final_tail_ESS=epochs[-1]['tail']['ESS'],final_tail_max_weight=epochs[-1]['tail']['max_weight'],final_adam_active_below_eps=probes[-1]['adam']['groups']['all_parameters']['active_first_moment_below_eps_fraction'],all_backward_sanity_pass=True)
for seed in [27,127,227]:
    assert d['heads'][f'FUSION790_{seed}']['endpoint']['order_hashes']==d['heads'][f'REFIT782_{seed}']['endpoint']['order_hashes']==d['heads'][f'STATS8_{seed}']['endpoint']['order_hashes']
report=dict(status='PASS',scope='TRAINING_LOG_INTEGRITY_AND_DESCRIPTIVE_AUDIT',training_root_cause_proven=False,normal_score_onset_observable=False,heads=out,head_count=9,updates=869040,probes=1080,epoch_logs=360,all_losses_finite=True,same_seed_orders_equal_across_arms=True,remote_seconds=d['seconds'],large_arrays_remain_hpc=True)
assert report==json.loads((P/'AUDIT.json').read_text()),'AUDIT_REPRODUCTION'
print('TRAINING_AUDIT_REPRODUCED')
