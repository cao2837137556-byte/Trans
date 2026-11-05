"""Actual directory-rename race and actual BatchStore schema regression."""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(1,str(HERE.parent/'edge_formal_execution_v4_20261104'))
import os
import tempfile
import unittest
from unittest.mock import patch
from disk_scan import tree_bytes
from checkpoint import BatchStore,require,sha,atomic_json
from formal_acceptance import validate_encoded_binding

def run_runtime_regression(root):
    import numpy as np
    root=Path(root);root.mkdir(parents=True,exist_ok=False)
    scanroot=root/'race';scanroot.mkdir();pending=scanroot/'pending';pending.mkdir()
    batches=scanroot/'batches';batches.mkdir();old=pending/'batch';old.mkdir()
    (old/'payload').write_bytes(b'x'*8192)
    original=os.scandir;renamed=[]
    def race(path):
        if Path(path)==old and not renamed:
            old.rename(batches/'batch');renamed.append(True)
        return original(path)
    size=tree_bytes(scanroot,scandir=race)
    require(renamed==[True] and 0<=size<=8192 and tree_bytes(scanroot)==8192,'REAL_RENAME_SCAN_REGRESSION')
    try:tree_bytes(root/'missing')
    except FileNotFoundError:pass
    else:raise AssertionError('MISSING_ROOT_MUST_FAIL')
    def denied(path):raise PermissionError('fixture denied')
    try:tree_bytes(scanroot,scandir=denied)
    except PermissionError:pass
    else:raise AssertionError('PERMISSION_ERROR_MUST_FAIL')
    # Whole-job monitor uses the same scanner and still enforces disk limits.
    from runtime_control import JobMonitor
    monitor=JobMonitor(scanroot,[],dict(rss_bytes=8*1024**3,disk_bytes=8191,scratch_bytes=1024))
    try:monitor.sample(force_disk=True)
    except ValueError as exc:require('WHOLE_JOB_DISK_BUDGET_STOP' in str(exc),'DISK_LIMIT_EXCEPTION')
    else:raise AssertionError('DISK_LIMIT_MUST_FAIL')
    store=BatchStore(root/'real_batches',dict(execution_card_sha256='actual-fixture'))
    z=np.zeros((2,768),dtype=np.float32);q=np.zeros((2,14),dtype=np.float32)
    store.commit('b0',['u0','u1'],z,q);store.finish([('b0',['u0','u1'])])
    require(validate_encoded_binding(store.root,'actual-fixture'),'ACTUAL_BATCHSTORE_BINDING')
    try:validate_encoded_binding(store.root,'wrong')
    except ValueError:pass
    else:raise AssertionError('WRONG_ENCODING_CARD_MUST_FAIL')
    # Reopening verifies payload SHA, UID and actual arrays; corrupt data fails.
    require(BatchStore(store.root,dict(execution_card_sha256='actual-fixture')).has('b0',['u0','u1']),'REOPEN_REAL_BATCH')
    with (store.batches/'b0/E3.npy').open('ab') as f:f.write(b'corruption')
    try:BatchStore(store.root,dict(execution_card_sha256='actual-fixture'))
    except ValueError:pass
    else:raise AssertionError('CORRUPT_BATCH_MUST_FAIL')
    receipt=dict(status='PASS_RENAME_AND_REAL_BINDING',real_directory_renamed=True,
        next_sample_exact=True,missing_root_rejected=True,permission_error_rejected=True,
        disk_limit_enforced=True,actual_batchstore_wrapper_checked=True,corrupt_batch_rejected=True)
    atomic_json(root/'RESULT.json',receipt)
    return receipt

class Regression(unittest.TestCase):
    def test_runtime_regression(self):
        with tempfile.TemporaryDirectory() as d:self.assertEqual(run_runtime_regression(Path(d)/'probe')['status'],'PASS_RENAME_AND_REAL_BINDING')

if __name__=='__main__':unittest.main(verbosity=2)
