import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
import numpy as np
from hnr.history import walk_decoded,endpoint_row
from resume_prepare import copy_checked,link_checked

class Progress:
    def update(self,*args,**kwargs):pass

class Contexts:
    query_allowed=True
    reasons={}
    def append(self,packet):
        self.query_allowed=int(packet['frame.number'])!=2
        return 'owner',('scope',(17,'left','right')),SimpleNamespace(ip_proto=17)

class ResumeChecks(unittest.TestCase):
    def fixture(self):
        spec=dict(capture_id='capture',owner='owner',partition='source',device='device',display_name='device',raw=dict(sha256='a'*64),normality_evidence='frozen')
        binding=dict(packets=3,bank_end_frame=2,reference_end_us=2)
        index=np.array([(i,i) for i in (1,2,3)],dtype=[('timestamp_us','i8'),('original_packet_ordinal','i8')])
        packets=[{'frame.number':str(i),'frame.time_epoch':f'0.00000{i}'} for i in (1,2,3)]
        expected=[]
        for frame in (1,3):
            row=endpoint_row(spec,binding,'b'*64,frame,frame,'owner',('scope',(17,'left','right')),SimpleNamespace(ip_proto=17),frame)
            expected.append((frame,row['uid'],json.dumps(row)))
        return spec,binding,index,packets,expected
    def run_case(self,expected=None):
        spec,binding,index,packets,rows=self.fixture()
        return walk_decoded(packets,spec,binding,index,np.arange(3),'b'*64,Contexts(),Progress(),audit_census=iter(rows if expected is None else expected))
    def test_complete_endpoint_identity_replay(self):
        r=self.run_case();self.assertEqual(r['packets'],3);self.assertEqual(r['legal_endpoints'],{'HIST_REF':1,'HIST_DEV':1})
    def test_changed_row_rejected(self):
        *_,rows=self.fixture();row=json.loads(rows[0][2]);row['protocol']=6;rows[0]=(rows[0][0],rows[0][1],json.dumps(row))
        with self.assertRaisesRegex(ValueError,'CHECKPOINT_ENDPOINT_EXACT_REPLAY'):self.run_case(rows)
    def test_missing_census_endpoint_rejected(self):
        *_,rows=self.fixture()
        with self.assertRaisesRegex(ValueError,'CHECKPOINT_ENDPOINT_EXACT_REPLAY'):self.run_case(rows[:1])
    def test_unreplayed_census_endpoint_rejected(self):
        *_,rows=self.fixture()
        with self.assertRaisesRegex(ValueError,'CHECKPOINT_NO_UNREPLAYED_ENDPOINT'):self.run_case(rows+[rows[-1]])
    def test_copy_reuses_bytes_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);data=b'checkpoint'*1000;(p/'source').write_bytes(data)
            r=copy_checked(p/'source',p/'copy',Progress());self.assertEqual(r['bytes'],len(data));self.assertEqual((p/'source').read_bytes(),data);self.assertEqual((p/'copy').read_bytes(),data)
    def test_existing_copy_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'source').write_bytes(b'new');(p/'copy').write_bytes(b'old')
            with self.assertRaisesRegex(ValueError,'NEW_CHECKPOINT_COPY'):copy_checked(p/'source',p/'copy',Progress())
            self.assertEqual((p/'copy').read_bytes(),b'old')
    def test_link_keeps_original_after_cleanup_of_new_name(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'source').write_bytes(b'complete immutable census')
            result=link_checked(p/'source',p/'new',Progress())
            self.assertEqual((p/'new').read_bytes(),(p/'source').read_bytes())
            self.assertEqual(result['bytes'],25)
            (p/'new').unlink()
            self.assertEqual((p/'source').read_bytes(),b'complete immutable census')
    def test_existing_link_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'source').write_bytes(b'new');(p/'new').write_bytes(b'old')
            with self.assertRaisesRegex(ValueError,'NEW_CHECKPOINT_LINK'):link_checked(p/'source',p/'new',Progress())
            self.assertEqual((p/'new').read_bytes(),b'old')

if __name__=='__main__':unittest.main(verbosity=2)
