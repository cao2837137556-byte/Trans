"""Supplementary bounded identity audit; no model forward or optimizer calls."""
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time

HERE=Path(__file__).resolve().parent
PACKAGE=Path('/srv/paper04/learned_onboarding_20261024_v2/runs/learned_onboarding_v1_20261023')
FIT=PACKAGE/'results/fit'
CACHE=Path('/srv/paper04/cache/coupon_resume_20261020_v2')
sys.dont_write_bytecode=True
sys.path.insert(0,str(PACKAGE/'src'))


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    import numpy as np
    import common
    import learning
    start=time.monotonic()
    binding=common.read(FIT/'input_binding.json')
    files={}
    def pin(path,expected):
        observed=sha(path)
        assert observed==expected,'INPUT_IDENTITY:'+str(path)
        files[str(path)]=observed
    pin(CACHE/'inputs/SHA256SUMS',binding['input_manifest_sha256'])
    pin(CACHE/'features/SHA256SUMS',binding['feature_manifest_sha256'])
    pins={line.split('  ',1)[1]:line.split('  ',1)[0]
          for line in (CACHE/'inputs/SHA256SUMS').read_text().splitlines()}
    pin(CACHE/'inputs/FIT.npz',pins['FIT.npz'])
    pin(CACHE/'inputs/LEARN.jsonl.gz',pins['LEARN.jsonl.gz'])
    pin(CACHE/'features/LEARN.npy',binding['learn_feature_sha256'])
    pin(PACKAGE/'results/source_assets/run/prepared/LEARN_q.npy',binding['q14_sha256'])
    ix=np.load(CACHE/'inputs/FIT.npz')['indices']
    fields=('uid','device','label','activity','capture_id','session_id','component_id')
    values=[]
    with gzip.open(FIT/'source_metadata.jsonl.gz','rt') as stream:
        for line in stream:
            row=json.loads(line)
            assert row['fit_role']=='FIT' and row['partition']=='LEARN'
            values.append(tuple(row[key] for key in fields))
    assert len(ix)==len(values)==617908
    positions={int(global_slot):slot for slot,global_slot in enumerate(ix)}
    matched=0
    with gzip.open(CACHE/'inputs/LEARN.jsonl.gz','rt') as stream:
        for global_slot,line in enumerate(stream):
            slot=positions.get(global_slot)
            if slot is None:
                continue  # No CAL row metadata is parsed or used in this audit.
            row=json.loads(line)
            assert row['fit_role']=='FIT' and row['partition']=='LEARN'
            assert values[slot]==tuple(row[key] for key in fields),'FIT_SLOT_JOIN'
            matched+=1
    assert matched==len(ix)
    groups=[]
    for name in ('AUX_G0','AUX_G1'):
        isolation=common.read(FIT/name/'isolation.json')
        train_uids=[r[0] for r in values if r[1] in isolation['train_devices']]
        held_uids=[r[0] for r in values if r[1] in isolation['held_devices']]
        checkpoint=FIT/name/'final.pt'
        _,_,_,item=learning.load_auxiliary_head(checkpoint)
        assert item['fit_uids']==train_uids,'CHECKPOINT_TRAIN_ORDER'
        assert item['fit_uid_hash']==item['normalizer_uid_hash']==isolation['fit_uid_sha256']
        assert common.uid_hash(held_uids,ordered=True)==isolation['held_uid_sha256']
        groups.append(dict(head=name,train_rows=len(train_uids),held_rows=len(held_uids),
                           checkpoint_sha256=sha(checkpoint),train_uid_join_equal=True,
                           train_uid_sha256=item['fit_uid_hash'],held_uid_sha256=isolation['held_uid_sha256']))
    result=dict(schema='paper04-source-identity-supplement-v3',status='PASS',
        input_binding_sha256=sha(FIT/'input_binding.json'),verified_input_sha256=files,
        fit_ordered_metadata_rows_matched=matched,groups=groups,
        target_queries_read=0,cal_rows_parsed=0,model_forward_calls=0,optimizer_updates=0,
        elapsed_seconds=time.monotonic()-start)
    with (HERE/'SOURCE_IDENTITY_SUPPLEMENT.json').open('x') as stream:
        json.dump(result,stream,indent=2)
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    main()
