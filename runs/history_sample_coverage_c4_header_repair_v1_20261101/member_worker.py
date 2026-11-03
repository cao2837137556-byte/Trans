"""One isolated preparation or frozen-encoding process; no process survives it."""
import argparse
import os
from pathlib import Path
import traceback
import run
from hnr.common import PACKAGE,read,write,require,sha
from worker_runtime import WorkerRuntime

def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','encode']);p.add_argument('--key',required=True);p.add_argument('--status',type=Path,required=True);p.add_argument('--wall-seconds',type=float,required=True);p.add_argument('--encoded-cap',type=int,required=True);a=p.parse_args()
    cfg=read(PACKAGE/'config/EXECUTION.json');spec=next(d for d in cfg['devices'] if d['key']==a.key)
    runtime=WorkerRuntime(a.status,a.wall_seconds,a.encoded_cap);old=run.old_references(arrays=False)
    member=PACKAGE/'outputs/encoding/history'/a.key
    scratch=runtime.output_status.parent/'sqlite_tmp';scratch.mkdir(exist_ok=True);os.environ['SQLITE_TMPDIR']=str(scratch);os.environ['TMPDIR']=str(scratch)
    try:
        if a.stage=='prepare':
            from resume_prepare import prepare_member
            prepared=prepare_member(spec,member,old,runtime,cfg['tshark']);require(prepared['status']=='PREPARED','PREPARE_STATUS')
        else:
            import torch,platform,numpy as np
            env=dict(system=platform.system(),python=platform.python_version(),numpy=np.__version__,torch=str(torch.__version__).split('+')[0])
            require(env==dict(system='Linux',python='3.11.11',numpy='2.0.1',torch='2.5.1'),'FROZEN_WORKER_ENVIRONMENT')
            torch.set_num_threads(4);torch.use_deterministic_algorithms(True)
            from hnr.encoding import new_encoder,encode_member
            encoder,identity=new_encoder(cfg['encoder'])
            encoded=encode_member(member,member/'encoded',dict(cfg['encoder'],old_rows=old),runtime,encoder=encoder,encoder_identity=identity)
            if a.key!='NETATMO':require(not encoded['HIST_DEV']['rows'],'OLD_DEV_REUSED')
            else:
                assets=run.load_assets();frozen=assets.calibration();scored=run.score_dev(run.joined(**encoded['HIST_DEV']),assets,frozen,runtime)
                with (member/'encoded/DEV_LOGITS.npz').open('xb') as f:np.savez(f,uid=np.asarray(scored['feature_uids']),raw_logits=scored['logits'])
                assets.immutable()
        write(a.status.with_name(a.status.stem+'_COMPLETE.json'),dict(status='COMPLETE',stage=a.stage,key=a.key,status_sha256=sha(a.status)))
    except BaseException as e:
        write(a.status.with_name(a.status.stem+'_ERROR.json'),dict(error=str(e),traceback=traceback.format_exc()));raise

if __name__=='__main__':main()
