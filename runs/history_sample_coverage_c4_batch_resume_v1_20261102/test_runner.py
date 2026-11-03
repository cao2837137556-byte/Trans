"""Boundary tests for C4 acceptance, singleton preservation and global origins."""
import copy
import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest
import json
from unittest.mock import patch
import numpy as np
from gates import dev_gate,final_gate,GROUP,NET,HEAVY
from hnr.history import create_census
from hnr.runtime import display_write,Runtime
from hnr.encoding import physical_batch,concatenate

class RunnerChecks(unittest.TestCase):
    def data(self):
        rr=[dict(uid=f'{j}-{i}',device=d,label=0,use='QUERY') for j,d in enumerate(sorted(GROUP)) for i in range(3)]
        before=np.ones((len(rr),4),dtype=bool);after=before.copy()
        after[next(i for i,r in enumerate(rr) if r['device']==NET)]=False
        after[next(i for i,r in enumerate(rr) if r['device'] in HEAVY)]=False
        return rr,before,after
    def test_tp_plateau_allowed(self):
        rr,b,a=self.data();self.assertEqual(dev_gate(rr,b,a)['status'],'PASS_DEV')
    def test_netatmo_improvement_mandatory(self):
        rr,b,a=self.data()
        for i,r in enumerate(rr):
            if r['device']==NET:a[i]=b[i]
        self.assertIn('NETATMO_NO_STRICT_IMPROVEMENT_VS_RAW',dev_gate(rr,b,a)['failures'])
    def test_samsung_power_improvement_mandatory(self):
        rr,b,a=self.data()
        for i,r in enumerate(rr):
            if r['device'] in HEAVY:a[i]=b[i]
        self.assertIn('SAMSUNG_POWER_NO_STRICT_IMPROVEMENT',dev_gate(rr,b,a)['failures'])
    def test_single_head_regression_rejected(self):
        rr,b,a=self.data();b[-1,0]=False;a[-1,0]=True
        self.assertIn('ANY_HEAD_NEW_NORMAL_ALARM',dev_gate(rr,b,a)['failures'])
    def test_missing_device_and_attack_rejected(self):
        rr,b,a=self.data()
        with self.assertRaises(ValueError):dev_gate(rr[3:],b[3:],a[3:])
        rr[0]['label']=1
        with self.assertRaises(ValueError):dev_gate(rr,b,a)
    def reports(self,fp):
        report=dict(protection=dict(status='PASS'),corrected=dict(normal=dict(rows=74444,positive=fp,rate=fp/74444)))
        view=dict(retained_uid_sha256='same',weights_sha256='same',reports={s:copy.deepcopy(report) for s in ('27','127','227','ensemble')})
        return {p:dict(views={v:copy.deepcopy(view) for v in ('full','post_window_primary')}) for p in ('CIC_DEV','UNSW_DEV')}
    def test_improvement_not_target_is_adopted(self):
        r=final_gate(self.reports(8494),self.reports(3000),0,0,True)
        self.assertEqual(r['status'],'ADOPT_C4');self.assertFalse(r['target_2pct_met'])
    def test_target_exact_integer_boundary(self):
        self.assertTrue(final_gate(self.reports(8494),self.reports(1488),0,0,True)['target_2pct_met'])
        self.assertFalse(final_gate(self.reports(8494),self.reports(1489),0,0,True)['target_2pct_met'])
    def test_attack_withdrawal_blocks_even_very_good_fpr(self):
        self.assertEqual(final_gate(self.reports(8494),self.reports(0),0,1,True)['status'],'REJECT_C4_KEEP_C3')
    def test_population_change_is_error(self):
        now=self.reports(1000);now['UNSW_DEV']['views']['full']['weights_sha256']='different'
        with self.assertRaises(ValueError):final_gate(self.reports(8494),now,0,0,True)
    def test_global_origin_uniqueness_outlives_selector_heap(self):
        with tempfile.TemporaryDirectory() as td:
            db=create_census(Path(td)/'census.sqlite')
            db.execute('INSERT INTO physical_origins VALUES (?,?,?,?)',('a'*64,1,'owner','uid1'));db.commit();db.close()
            db=sqlite3.connect(Path(td)/'census.sqlite')
            with self.assertRaises(sqlite3.IntegrityError):db.execute('INSERT INTO physical_origins VALUES (?,?,?,?)',('a'*64,1,'owner','uid2'))
            db.close()
    def test_empty_protocol_array_is_legal(self):
        empty=dict(rows=[],e3=np.empty((0,768)),q14=np.empty((0,14)))
        r=concatenate([empty]);self.assertEqual(r['e3'].shape,(0,768));self.assertEqual(r['q14'].shape,(0,14))
    def test_singleton_clone_uses_same_tensor(self):
        import torch,hashlib
        batch={'a':torch.tensor([[1,2,3]])}
        def h(b,i):return hashlib.sha256(b['a'][i].numpy().tobytes()).hexdigest()
        expanded,n=physical_batch(batch,1,h)
        self.assertEqual(n,16);self.assertTrue(all(h(expanded,j)==h(batch,0) for j in range(16)))
    def test_display_sharing_violation_is_nonfatal(self):
        state={}
        with patch('hnr.runtime.write',side_effect=PermissionError('busy')):display_write(Path('STATUS.json'),state)
        self.assertIn('display_write_warning',state)
    def test_no_silent_distance_budget_overrun(self):
        with tempfile.TemporaryDirectory() as td:
            r=Runtime(Path(td)/'run',synthetic=True,limits=dict(cpu=1,rss_bytes=2**30,output_bytes=2**30,wall_seconds=60,pairs=2,encoded=0),monitor=False)
            with patch.object(r,'checkpoint'):
                r.pairs(2)
                with self.assertRaises(ValueError):r.pairs(1)

    def test_real_census_selector_netatmo_roles_and_replay(self):
        from hnr.selection import select_candidates
        from hnr.component_selection import point_rank
        from hnr.common import digest,rows
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'config').mkdir()
            spec=dict(key='NETATMO',device=NET,raw=dict(sha256='a'*64),owner='owner',reference_end_us=10,bank_end_frame=10)
            (p/'config/EXECUTION.json').write_text(json.dumps(dict(devices=[spec])))
            db=create_census(p/'census.sqlite')
            for i in range(1,21):
                role='HIST_REF' if i<=10 else 'HIST_DEV'
                r=dict(uid=digest(i),device=NET,protocol=6,component_id=digest(i%2),timestamp=i/1e6,timestamp_us=i,frame=i,
                    history_role=role,use='REFERENCE' if i<=10 else 'QUERY',label=0,owner='owner',origin_raw_sha256='a'*64,
                    origin_packet_ordinal=i,reference_end_us=10,bank_end_frame=10)
                db.execute('INSERT INTO candidates VALUES (?,?,?,?,?,?,?,?,?)',(r['uid'],NET,6,r['component_id'],r['timestamp'],i,role,point_rank(r['uid'])[0],json.dumps(r)))
                db.execute('INSERT INTO physical_origins VALUES (?,?,?,?)',('a'*64,i,'owner',r['uid']))
            db.commit();db.close()
            with patch('hnr.selection.PACKAGE',p):
                a=select_candidates(p/'census.sqlite',[],p/'first',devices=[NET])
                b=select_candidates(p/'census.sqlite',[],p/'replay',devices=[NET])
            self.assertEqual(a['ref_rows']['rows'],10);self.assertEqual(a['dev_rows']['rows'],10)
            self.assertEqual(a['ref_rows']['sha256'],b['ref_rows']['sha256'])
            self.assertEqual(a['dev_rows']['sha256'],b['dev_rows']['sha256'])

if __name__=='__main__':unittest.main(verbosity=2)
