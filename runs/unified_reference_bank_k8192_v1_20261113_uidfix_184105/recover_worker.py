"""Requalify the actual evaluation path using the sealed 184105 reference features."""
from pathlib import Path
from types import SimpleNamespace
import os
import sys
import time
import traceback

import numpy as np

import worker
from frozen_selector import need
from runtime_support import HERE, Progress, asset, digest, read, write

PARENT = 'unified_reference_bank_k8192_v1_20261113_early_183987'


def checkpoint(project,target,progress):
    old = project/'runs'/PARENT
    proof = read(HERE/'RECOVERY_INPUTS.json')
    binding = {}
    with progress.measure('VERIFY_184105_SEALED_REFERENCES'):
        for kind in ('preflight','candidate'):
            previous = old/kind
            pin = proof['seals'][kind]
            manifest = read(previous/'CANDIDATE.json')
            need(digest(previous/'CANDIDATE.json') == pin['receipt_sha256'] and
                 manifest['status'] == pin['status'] and not manifest['query_access'] and
                 asset(previous/'SELECTION.json') == pin['selection'] == manifest['selection'],
                 'PREDECESSOR_CANDIDATE_SEAL:'+kind)
            selection = read(previous/'SELECTION.json')
            for pool,pin_array in pin['pools'].items():
                file = previous/pool/'REFERENCES.npz'
                need(asset(file)==pin_array==manifest['pools'][pool]['feature']['arrays'],
                     'PREDECESSOR_FEATURE_PIN:'+kind+':'+pool)
                rows = previous/(pool+'_HISTORY.jsonl.gz')
                need(asset(rows)['sha256']==selection[pool]['rows']['sha256'],
                     'PREDECESSOR_SELECTION_PIN:'+kind+':'+pool)
                from common_round1 import read_rows, uid_sha
                ids = [r['uid'] for r in read_rows(rows)]
                need(len(ids)==len(set(ids))==selection[pool]['rows']['count'] and
                     uid_sha(ids)==selection[pool]['rows']['uid_sha256'], 'PREDECESSOR_SELECT_UID')
                with np.load(file,allow_pickle=False) as a:
                    need(a['uid'].tolist()==ids,'PREDECESSOR_FEATURE_UID')
                binding[pool] = len(ids)
            (target/kind).symlink_to(previous,target_is_directory=True)
    write(target/'REUSED_184105.json',dict(status='PASS',parent=str(old),
          candidate_rows=binding, seals=proof['seals'], rebuilt_features=0))
    return read(old/'PREPARATION_REUSE.json')['reused_motion']


def main():
    phase,project,target,archive = sys.argv[1:]
    if phase == 'replay':
        return worker.main()
    args=SimpleNamespace(phase=phase,project=Path(project),target=Path(target),archive=Path(archive))
    progress=Progress(args.target,phase)
    start=time.monotonic()
    try:
        need(phase=='prepare','RECOVERY_PHASE')
        worker.runtime(args,read(HERE/'PACKAGE_MANIFEST.json'))
        cfg,geom = read(HERE/'CONFIG.json'),read(HERE/'GEOMETRY.json')
        worker.method_check(cfg,geom)
        motion = checkpoint(args.project,args.target,progress)
        worker.certify_preparation(args,cfg,geom,progress,motion,args.target/'preflight',
                                   args.target/'candidate',False)
        progress('COMPLETE',1,1,force=True)
    except Exception as err:
        write(args.target/f'FAILURE_{phase}.json',dict(status='ENGINEERING_STOP',
            stage=progress.current,error=str(err),traceback=traceback.format_exc(),
            wall_seconds=time.monotonic()-start,peak_rss_kib=progress.rss()))
        raise


if __name__ == '__main__':
    main()
