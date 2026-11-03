"""Seal reviewed C4 code, reused inputs, and real-bank pair ceilings."""
from pathlib import Path
import json
import shutil
import subprocess
import sys
import numpy as np
from hnr.common import PACKAGE,ROOT,sha,read,write,digest,rows,require
from run import semantic

def main():
    require(not (PACKAGE/'EXECUTION_CARD.json').exists(),'CONTRACT_ALREADY_FROZEN')
    inputs={};history_arrays={};dev_arrays={}
    for key in ('TP_LINK','WEMO_POWER','SAMSUNG'):
        old=ROOT/f'runs/history_normal_reference_d2_trace_v1_20261031/retrieved/history/{key}/encoded'
        target=PACKAGE/f'inputs/{key}_references.jsonl.gz';target.parent.mkdir(exist_ok=True)
        require(not target.exists(),'OLD_METADATA_ALREADY_STAGED');shutil.copyfile(old/'references.jsonl.gz',target)
        history_arrays[key]=(old/'references.npz').relative_to(ROOT).as_posix()
        inputs[history_arrays[key]]=sha(old/'references.npz')
        dev_arrays[key]=f'runs/history_normal_reference_c2_syn_guard_v1_20261031/retrieved/history/{key}/queries.npz'
        inputs[dev_arrays[key]]=sha(ROOT/dev_arrays[key])
    refs=dict(dev_rows='runs/history_normal_reference_d2_trace_v1_20261031/retrieved/dev/QUERIES.jsonl.gz',
        dev_decisions='runs/history_normal_reference_c2_syn_guard_v1_20261031/output/dev/DECISIONS.npz',
        c3_result='runs/history_normal_reference_c3_progress_repair_v1_20261101/output/RESULT.json')
    for rel in refs.values():inputs[rel]=sha(ROOT/rel)
    c3_decisions={p:f'runs/history_normal_reference_c3_progress_repair_v1_20261101/output/ab/{p}/DECISIONS.npz' for p in ('CIC_DEV','UNSW_DEV')}
    for rel in c3_decisions.values():inputs[rel]=sha(ROOT/rel)
    assets=read(PACKAGE/'config/ASSETS.json')
    def pin_values(v):
        if isinstance(v,dict):
            if 'path' in v and 'sha256' in v:
                inputs[v['path']]=v['sha256'];require(sha(ROOT/v['path'])==v['sha256'],'UPSTREAM_PIN')
            else:
                for x in v.values():pin_values(x)
        elif isinstance(v,list):
            for x in v:pin_values(x)
    pin_values(assets)
    for p in (ROOT/'repo/ood').rglob('*.py'):inputs[p.relative_to(ROOT).as_posix()]=sha(p)
    for name in ('matrix.py','metrics.py'):
        rel='runs/dense_reference_ab_stage_candidate_v1_20261028/src/'+name;inputs[rel]=sha(ROOT/rel)
    spec=assets['pools']['UNSW_DEV'];rr=list(rows(ROOT/spec['query']['rows']['path']));dense=list(rows(ROOT/spec['dense_bank']['rows']['path']))
    from collections import Counter
    queries=Counter((r['device'],r['protocol']) for r in rr);banks=Counter((r['device'],r['protocol']) for r in dense)
    old=Counter()
    for p in (PACKAGE/'inputs').glob('*references.jsonl.gz'):old.update((r['device'],r['protocol']) for r in rows(p))
    device_specs=read(PACKAGE/'config/EXECUTION.json')['devices'];plans=[]
    for d in device_specs:
        for proto in (6,17):
            key=(d['device'],proto)
            extra=0 if d['key']=='TP_LINK' and proto==17 else 4096
            if extra==0:require(old[key]==3683,'TP_UDP_SATURATION')
            n=banks[key]+old[key]+extra
            plans.append(dict(device=d['device'],protocol=proto,query_rows=queries[key],dense_rows=banks[key],old_history_rows=old[key],maximum_additional_rows=extra,maximum_bank=n,pair_upper_bound=queries[key]*n))
    ab=sum(r['pair_upper_bound'] for r in plans);dev=117440512
    require(ab==879576985 and ab+dev==997017497,'ACTUAL_DENSE_BANK_BUDGET')
    with np.load(ROOT/c3_decisions['UNSW_DEV'],allow_pickle=False) as z:
        attack=np.array([r['label']==1 for r in rr]);require(int(attack.sum())==72553 and np.all(z['guard'][attack]),'B_ATTACK_SCOPE')
    manifest=dict(local_inputs=inputs,history_arrays=history_arrays,dev_arrays=dev_arrays,c3_decisions=c3_decisions,**refs)
    write(PACKAGE/'INPUT_MANIFEST.json',manifest)
    codepaths=[*PACKAGE.glob('*.py'),*PACKAGE.glob('hnr/*.py'),*PACKAGE.glob('inputs/*'),*PACKAGE.glob('hpc/*.slurm'),PACKAGE/'config/ASSETS.json',PACKAGE/'config/ENCODER_RUNTIME_FILES.json',PACKAGE/'INPUT_MANIFEST.json']
    code={p.relative_to(PACKAGE).as_posix():sha(p) for p in sorted(codepaths)}
    card=dict(candidate='C4_HISTORY_SAMPLE_COVERAGE_TOPUP',code_sha256=code,
        config_semantic_sha256=digest(semantic(read(PACKAGE/'config/EXECUTION.json'))),
        ref_cap=4096,dev_sampling='C1_ALL_COMPONENT_ROUND_ROBIN_THEN_UNIFORM_TIME',
        pair_limit=1000000000,dev_pair_upper_bound=dev,AB_pair_upper_bound=ab,total_pair_upper_bound=ab+dev,pair_groups=plans,
        limits=dict(cpu=4,rss_bytes=8*2**30,output_bytes=20*2**30,total_wall_seconds=28800,encoded=36864),
        baseline='C3_ADMITTED_SMALL_BANK_COMPLETE',lambda_value=.25,all_AB_consumed_development=True,
        acceptance='HIST_DEV: no new alarm any head/device, strict Netatmo vs RAW and pooled plus Samsung/Power improvement. Terminal: all original protection gates, B no extra misses any head/view, A/Motion exact, strict B sample FPR improvement; 2% separately reported.',
        no_salt_capacity_lambda_search=True,freeze_after_one_evaluation=True,
        attack_scope=dict(B_attack_rows=72553,guarded_attack_rows=72553,ACK_UDP_protection_tested=False))
    write(PACKAGE/'EXECUTION_CARD.json',card)
    (PACKAGE/'EXECUTION_CARD.json.sha256').write_text(sha(PACKAGE/'EXECUTION_CARD.json')+'  EXECUTION_CARD.json\n',encoding='utf-8')
    print(json.dumps(dict(status='CONTRACT_FROZEN',code_files=len(code),input_files=len(inputs),pair_bound=ab+dev)))

if __name__=='__main__':main()
