"""Reject corrupt or evaluated previous attempts before reusing real arrays."""
import json
from pathlib import Path
import tempfile
import unittest
import hashlib
import numpy as np
from unittest.mock import patch
import recovery
from hnr.common import write,write_rows,sha,digest

class RecoveryChecks(unittest.TestCase):
    def fixture(self,p):
        member=p/'outputs/encoding/history/TP_LINK';encoded=member/'encoded';encoded.mkdir(parents=True);(member/'selection').mkdir()
        r=dict(uid='one',use='REFERENCE',history_role='HIST_REF')
        write_rows(encoded/'references.jsonl.gz',[r]);write_rows(encoded/'queries.jsonl.gz',[])
        e3=np.zeros((1,768),dtype=np.float32);q14=np.zeros((1,14),dtype=np.float32)
        np.savez(encoded/'references.npz',uid=np.array(['one']),e3=e3,q14=q14)
        np.savez(encoded/'queries.npz',uid=np.array([],dtype='<U64'),e3=e3[:0],q14=q14[:0])
        write_rows(encoded/'tensor_receipts.jsonl.gz',[dict(uid='one',slot=0,batch_id=0,feature_sha256=hashlib.sha256(e3[0].tobytes()).hexdigest())])
        write_rows(encoded/'BATCH_LEDGER.jsonl',[dict(batch=0,logical_rows=1,uid_sha256=digest(['one']),status=s) for s in ('ATTEMPT','COMPLETE')])
        write_rows(member/'selection/HIST_REF.jsonl.gz',[r]);write(member/'selection/SELECTION.json',dict(ref_rows=dict(rows=1),dev_rows=dict(rows=0)))
        write(member/'LOGICAL_INPUT.json',dict(source='retained'));write_rows(member/'selected_snapshots.jsonl.gz',[r])
        write(member/'PREPARE_RESULT.json',dict(status='PREPARED',logical_input_sha256=sha(member/'LOGICAL_INPUT.json'),snapshots_sha256=sha(member/'selected_snapshots.jsonl.gz')))
        write(member/'INTERMEDIATE_CLEANUP.json',dict(selected_evidence_retained=True))
        write(encoded/'ENCODE_RESULT.json',dict(status='COMPLETE',synthetic_only=False,rows=1,prepared_receipt_sha256=sha(member/'PREPARE_RESULT.json'),files={q.name:sha(q) for q in encoded.iterdir()}))
        return member
    def test_exact_retained_outputs_can_be_reused(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);member=self.fixture(p)
            with patch('recovery.PREVIOUS',p),patch.dict('recovery.EXPECTED',TP_LINK=1):
                r=recovery.reuse_member('TP_LINK',p/'copy');self.assertEqual(r['rows'],1)
                self.assertEqual(sha(p/'copy/encoded/references.jsonl.gz'),sha(member/'encoded/references.jsonl.gz'))
    def test_changed_completed_file_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);member=self.fixture(p);(member/'encoded/references.jsonl.gz').write_bytes(b'changed')
            with patch('recovery.PREVIOUS',p),patch.dict('recovery.EXPECTED',TP_LINK=1),self.assertRaisesRegex(ValueError,'REUSED_ENCODE_PIN'):
                recovery.check_member('TP_LINK')
    def test_changed_source_receipt_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);member=self.fixture(p);write(member/'LOGICAL_INPUT.json',dict(source='modified'))
            with patch('recovery.PREVIOUS',p),patch.dict('recovery.EXPECTED',TP_LINK=1),self.assertRaisesRegex(ValueError,'PREPARE_SOURCE_LINK'):
                recovery.check_member('TP_LINK')
    def test_partial_member_cannot_be_adopted(self):
        with self.assertRaisesRegex(ValueError,'ONLY_COMPLETED_MEMBERS'):recovery.check_member('NETATMO')

if __name__=='__main__':unittest.main(verbosity=2)
