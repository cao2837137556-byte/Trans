"""Generated-only end-to-end endpoints, calibration, reporting and stop tests."""
import copy
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import contextlib
import os
import numpy as np
import torch
import continuous_common_v3 as c
import continuous_model_v3 as m
import continuous_train_v3 as t
import continuous_evaluate_v3 as e
import continuous_runner_v3 as runner


class DummyProgress:
    optimizer_updates=0
    def tick(self,*args,**kwargs): pass


def fixture():
    design=dict(synthetic_only=True,training=dict(epochs=2,batch_size=16,lr=.0003,
        weight_decay=.0001,betas=[.9,.999],eps=1e-8,reference_budgets=[2,8,'ALL'],reference_subset_salt='fixture'),
        data=dict(CAL=dict(normal=8,attack=8,attack_donor_pairs=16)))
    design['evaluation'] = c.read(Path(__file__).resolve().parents[2]/'design_contract.json')['evaluation'] if (Path(__file__).resolve().parents[2]/'design_contract.json').exists() else c.read(Path(__file__).resolve().parents[2]/'runs/legacy_continuous_input_core_repair_design_v3_20260929/design_contract.json')['evaluation']
    def row(uid,device,partition,role,label,use='QUERY',protocol=6):
        return dict(uid=uid,device=device,partition=partition,fit_role=role,label=label,use=use,protocol=protocol,
            timestamp=0. if use=='REFERENCE' else 2.,reference_end=1.,component_id=uid,session_id=uid,
            capture_id='capture-'+device,activity='fixture',label_metric_weight_denominator=8)
    refs=[row('r'+str(i), 'd'+str(i//2),'LEARN','FIT',0,'REFERENCE') for i in range(4)]
    rows=[row('fit'+str(i),'d'+str(i%2),'LEARN','FIT',i%2) for i in range(32)]
    cal=[row('cal'+str(i),'d'+str(i%2),'LEARN','CAL',i%2) for i in range(16)]
    dev=[row('dev'+str(i),'d'+str(i%2),'DEV','DEV',i%2) for i in range(16)]
    rng=np.random.default_rng(99)
    def data(rr):
        x=rng.normal(size=(len(rr),794)).astype(np.float32)
        return dict(rows=rr,OLD_MATCHED=x[:,:768]+.01,RECENT=x[:,:768],RECENT_STATE=x)
    return design,refs,data(rows),data(cal),data(dev),rng.normal(size=(4,794)).astype(np.float32)


class ChainContract(unittest.TestCase):
    def test_generated_decode_spool_features_merge(self):
        import continuous_features_v3 as f
        import continuous_input_v3 as inp
        import legacy_reference_sample_prepare_v1 as prep
        from legacy_unsw_archival_runtime_v1 import e3_runtime
        from test_continuous_repair_v3 import packet
        vendor=Path(os.environ.get('CONTINUOUS_TEST_ROOT',Path(__file__).resolve().parents[2]/'runs/legacy_commissioning_unsw_recovery_delivery_v2_20260927/bundle'))
        runtime_object=e3_runtime(vendor,synthetic=True)
        source=[packet(i,i*20_000_000) for i in range(1,25)]
        contexts=inp.Contexts('generated',{'aa'},prep.old.legacy_runtime()[0]);rr=[]
        for row in source:
            owner,ns,event=contexts.append(row)
            rr.append(dict(uid=prep.digest(['synthetic-sha',int(row['frame.number']),owner]),owner=owner,
                session_id=prep.digest(ns),source_sha256='synthetic-sha',capture_id='generated',timestamp=event.timestamp,
                protocol=6,frame=int(row['frame.number']),reference_end=0.,use='QUERY',fit_role='FIT',label=0,
                device='generated',component_id=prep.digest(ns)))
        @contextlib.contextmanager
        def decoded(*args,**kwargs):yield iter(source)
        with tempfile.TemporaryDirectory() as td:
            run=Path(td);raw=run/'generated.raw';raw.write_bytes(b'generated-only')
            runtime=dict(known_macs=['aa'],tshark='never-invoked',synthetic_only=True,feature_workers=2,
                limits=dict(wall_seconds=120,memory_gib=12,disk_gib=1))
            metadata={'LEARN':rr};design={'input':{'checkpoint_sha256':'SYNTHETIC_STANDIN'}}
            class P(DummyProgress):
                stage='GENERATED'
            with patch.object(f,'e3_runtime',return_value=runtime_object),patch.object(f,'decode',decoded):
                f.spool(vendor,run/'spool',metadata,[dict(capture_id='generated',path=str(raw),sha256='synthetic-sha',expected_packets=24)],runtime,P())
                c.write(run/'spool_pin.json',dict(sha256=c.sha(run/'spool/snapshots.sqlite')))
                c.write(run/'launch.json',dict(design_sha256=c.DESIGN_SHA))
                with patch.object(c,'authorize',return_value=(design,runtime)):
                    for shard in range(2):f.feature_worker(vendor,run,shard,True)
                f.merge_features(run,metadata,runtime)
            values=np.load(run/'features/LEARN.npy',allow_pickle=False)
            self.assertEqual(values.shape,(24,794));self.assertTrue(np.isfinite(values).all())
            self.assertEqual(c.read(run/'spool/receipt.json')['query_frame_to_token_verified'],24)

    def test_all_twelve_endpoints_calibration_reports_controls(self):
        design,refs,fit,cal,dev,ref_values=fixture();p=DummyProgress()
        norms={a:m.fit_normalizer(fit[a],fit['rows'],list(range(32))) for a in c.ARMS}
        bank=m.Bank(refs,m.normalized(ref_values,slice(None),norms['RECENT_STATE']),{'LEARN'})
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);heads={a:{} for a in c.ARMS};metrics={}
            for arm in (*c.ARMS,'LEARNED'):
                for seed in c.SEEDS:
                    base='RECENT_STATE' if arm=='LEARNED' else arm
                    target=root/(arm+'_'+str(seed))
                    t.train(design,fit['rows'],fit[base],norms[base],np.arange(32),bank if arm=='LEARNED' else None,
                            arm,seed,target,p,synthetic=True)
                    loaded=t.load_model(target,arm,seed,design)
                    (metrics if arm=='LEARNED' else heads[arm])[seed]=loaded
                    self.assertEqual(c.read(target/'endpoint.json')['updates'],4)
            tau,cuts=e.calibrate(design,heads,metrics,cal,norms,bank,root/'cal',p)
            rr=copy.deepcopy(refs)
            for r in rr:r['partition']='DEV' if r['device']=='d0' else 'LEARN'
            db=m.Bank(rr,bank.values,{'LEARN','DEV'})
            qr=[r for r in dev['rows'] if r['device']=='d0']
            ctrl=dict(status='MATCHED',device='d0',donor='d1',protocol=6,count=2,rows=len(qr),query_uid_sha256=c.uid_sha(r['uid'] for r in qr),
                correct_reference_uids=['r0','r1'],wrong_reference_uids=['r2','r3'])
            result=e.evaluate(design,heads,metrics,dev,norms,db,tau,cuts,[ctrl],'UNSW_DEV',root/'dev',p)
            self.assertFalse(result['automatic_promotion']);self.assertEqual(result['independent_ID'],'NOT_RUN')
            with np.load(root/'dev/decisions.npz',allow_pickle=False) as saved:
                for suffix in ['ensemble','27','127','227']:
                    self.assertFalse((saved['RECENT_STATE_LEARNED_'+suffix] & ~saved['RECENT_STATE_'+suffix]).any())
            self.assertEqual(len(c.read(root/'dev/reports.json')),20)
            ctrl['donor']='d0'
            with self.assertRaisesRegex(RuntimeError,'CONTROL_OWNER_PROTOCOL'):
                e.evaluate(design,heads,metrics,dev,norms,db,tau,cuts,[ctrl],'UNSW_DEV',root/'bad',p)

    def test_fit_external_cal_rejected_and_no_restart(self):
        design,refs,fit,_,_,rv=fixture();norm=m.fit_normalizer(fit['RECENT'],fit['rows'],list(range(32)))
        with tempfile.TemporaryDirectory() as td:
            target=Path(td)/'head'
            rr=copy.deepcopy(fit['rows']);rr[0]['fit_role']='CAL'
            with self.assertRaisesRegex(RuntimeError,'TRAIN_FIT_ONLY'):
                t.train(design,rr,fit['RECENT'],norm,np.arange(32),None,'RECENT',27,target,DummyProgress(),synthetic=True)
            self.assertFalse(target.exists())
            target.mkdir()
            with self.assertRaises(FileExistsError):
                t.train(design,fit['rows'],fit['RECENT'],norm,np.arange(32),None,'RECENT',27,target,DummyProgress(),synthetic=True)

    def test_extra_file_rejected_and_nested_seal(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'sub').mkdir();c.write(p/'sub/a.json',{});c.seal(p/'sub');c.seal(p);c.verify(p)
            (p/'extra').write_text('x')
            with self.assertRaisesRegex(RuntimeError,'FILE_SET'):c.verify(p)

    def test_progress_first_cause_and_user_stop(self):
        with tempfile.TemporaryDirectory() as td:
            p=c.Progress(Path(td)/'run',dict(wall_seconds=60,memory_gib=8,disk_gib=1))
            try:
                p.optimizer_updates=17;p.tick(2,4,force=True)
                self.assertEqual(c.read(p.out/'status.json')['optimizer_updates'],17)
                p.record_failure(RuntimeError('FIRST'),'fixture');p.record_failure(RuntimeError('SECOND'),'fixture')
                self.assertIn('FIRST',c.read(p.out/'first_failure.json')['exception'])
                with self.assertRaisesRegex(RuntimeError,'FIRST'):p.guard()
            finally:p.stop('STOPPED_NO_RETRY',error='FIRST')

    def test_scope_before_root_access(self):
        with self.assertRaisesRegex(RuntimeError,'NOT_AUTHORIZED'):runner.run_chain('/absent',False)

    def test_eligibility_is_metadata_only(self):
        _,refs,fit,_,_,rv=fixture();bank=m.Bank(refs,torch.from_numpy(rv),{'LEARN'})
        fit['rows'][0]['protocol']=17
        ix=runner.eligible(fit['rows'],np.arange(32),bank)
        self.assertEqual(len(ix),31);self.assertNotIn(0,ix)

    def test_frozen_eligibility_excludes_singleton_but_loss_supports_it(self):
        _,refs,fit,_,_,rv=fixture();bank=m.Bank(refs[:3],torch.from_numpy(rv[:3]),{'LEARN'})
        ix=runner.eligible(fit['rows'],np.arange(32),bank)
        self.assertEqual(len(ix),16)
        _,valid=bank.own(torch.zeros(1,794),[fit['rows'][1]],m.Raw(),{'training':{}},minimum=1)
        self.assertTrue(valid.item())

    def test_cic_evaluation_loads_frozen_source_donors(self):
        _,refs,_,_,_,rv=fixture()
        for r in refs[:2]:r['partition']='DEV'
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'features').mkdir();np.save(p/'features/SOURCE_REFS.npy',rv)
            bank=runner.bank_from(p,{'SOURCE_REFS':refs},'SOURCE_REFS',{'LEARN','DEV'},(np.zeros(794),np.ones(794)))
            self.assertEqual(set(bank.by_uid),{'r0','r1','r2','r3'})


if __name__=='__main__':unittest.main()
