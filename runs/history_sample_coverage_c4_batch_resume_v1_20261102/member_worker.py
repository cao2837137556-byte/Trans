"""One isolated preparation or frozen-encoding process; no process survives it."""
import argparse
import gc
import os
from pathlib import Path
import traceback
import run
import numpy as np
from hnr.common import PACKAGE,read,write,require,sha,digest
from worker_runtime import WorkerRuntime


def dev_logits(member, queries, runtime, *, assets=None, scorer=None, card_sha256=None):
    """Commit DEV logits atomically, separately from durable E3 completion."""
    from hnr.encoding import _durable_file, _durable_json
    member=Path(member);directory=member/'encoded'
    path=directory/'DEV_LOGITS.npz';receipt_path=directory/'DEV_LOGITS_RESULT.json'
    ids=[r['uid'] for r in queries['rows']]
    require(ids and len(set(ids))==len(ids) and all(isinstance(uid,str) and len(uid)<=64 for uid in ids),
            'DEV_LOGITS_QUERY_UIDS')
    encoding_sha=sha(directory/'ENCODE_RESULT.json')
    card_sha256=sha(PACKAGE/'EXECUTION_CARD.json') if card_sha256 is None else card_sha256
    require(path.exists()==receipt_path.exists(),'DEV_LOGITS_ORPHAN_ARRAY_OR_RECEIPT')
    def schema(saved):
        require(set(saved.files)=={'uid','raw_logits'} and saved['uid'].dtype==np.dtype('<U64') and
                saved['uid'].shape==(len(ids),) and saved['uid'].tolist()==ids and
                saved['raw_logits'].dtype==np.float64 and saved['raw_logits'].shape==(len(ids),3) and
                np.isfinite(saved['raw_logits']).all(),'DEV_LOGITS_SCHEMA_UID')
    if receipt_path.exists():
        receipt=read(receipt_path)
        require(receipt['status']=='COMPLETE' and receipt['encoding_result_sha256']==encoding_sha and
                receipt['execution_card_sha256']==card_sha256 and receipt['uid_sha256']==digest(ids) and
                receipt['rows']==len(ids) and receipt['npz_sha256']==sha(path),'DEV_LOGITS_RECEIPT_PIN')
        with np.load(path,allow_pickle=False) as saved:schema(saved)
        return dict(reused=True,rows=len(ids),receipt_sha256=sha(receipt_path))
    assets=run.load_assets() if assets is None else assets
    scorer=run.score_dev if scorer is None else scorer
    scored=scorer(run.joined(**queries),assets,assets.calibration(),runtime)
    require(scored['feature_uids']==ids and scored['logits'].dtype==np.float64 and
            scored['logits'].shape==(len(ids),3) and np.isfinite(scored['logits']).all(),'DEV_LOGITS_SCORED_SCHEMA')
    assets.immutable()
    _durable_file(path,lambda stream:np.savez(stream,uid=np.asarray(ids,dtype='<U64'),raw_logits=scored['logits']))
    _durable_json(receipt_path,dict(status='COMPLETE',rows=len(ids),uid_sha256=digest(ids),
        encoding_result_sha256=encoding_sha,execution_card_sha256=card_sha256,npz_sha256=sha(path),
        head_seeds=[27,127,227],E3_forwards=0,model_training=False))
    return dict(reused=False,rows=len(ids),receipt_sha256=sha(receipt_path))

def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','encode']);p.add_argument('--key',required=True);p.add_argument('--status',type=Path,required=True);p.add_argument('--wall-seconds',type=float,required=True);p.add_argument('--encoded-cap',type=int,required=True);a=p.parse_args()
    cfg=read(PACKAGE/'config/EXECUTION.json');spec=next(d for d in cfg['devices'] if d['key']==a.key)
    runtime=WorkerRuntime(a.status,a.wall_seconds,a.encoded_cap);old=run.old_references(arrays=False)
    member=PACKAGE/'outputs/encoding/history'/a.key
    scratch=runtime.output_status.parent/'sqlite_tmp';scratch.mkdir(exist_ok=True);os.environ['SQLITE_TMPDIR']=str(scratch);os.environ['TMPDIR']=str(scratch)
    try:
        require(a.stage=='encode' and a.key=='NETATMO','FULL_PREPARED_REUSE_ONLY_NO_RAW_SCAN')
        card=read(PACKAGE/'EXECUTION_CARD.json')
        require(a.encoded_cap==card['recovery']['new_encoded_rows'],'EXACT_WORKER_ENCODING_ALLOWANCE')
        require(read(member/'PREPARED_REUSE.json')['status']=='COMPLETE_PREPARED_REUSED','PREPARED_REUSE_REQUIRED')
        if a.stage=='encode':
            import torch,platform
            env=dict(system=platform.system(),python=platform.python_version(),numpy=np.__version__,torch=str(torch.__version__).split('+')[0])
            require(env==dict(system='Linux',python='3.11.11',numpy='2.0.1',torch='2.5.1'),'FROZEN_WORKER_ENVIRONMENT')
            torch.set_num_threads(4);torch.use_deterministic_algorithms(True)
            from hnr.encoding import new_encoder,encode_member
            encoder,identity=new_encoder(cfg['encoder'])
            encoded=encode_member(member,member/'encoded',dict(cfg['encoder'],old_rows=old),runtime,
                encoder=encoder,encoder_identity=identity,resume=True)
            del encoder;gc.collect()
            scored=dev_logits(member,encoded['HIST_DEV'],runtime)
        write(a.status.with_name(a.status.stem+'_COMPLETE.json'),dict(status='COMPLETE',stage=a.stage,key=a.key,
            status_sha256=sha(a.status),encoded_charged=runtime.state['encoded_charged'],
            encode_result_sha256=sha(member/'encoded/ENCODE_RESULT.json'),
            dev_logits_receipt_sha256=scored['receipt_sha256'],dev_logits_reused=scored['reused']))
    except BaseException as e:
        write(a.status.with_name(a.status.stem+'_ERROR.json'),dict(error=str(e),traceback=traceback.format_exc()));raise

if __name__=='__main__':main()
