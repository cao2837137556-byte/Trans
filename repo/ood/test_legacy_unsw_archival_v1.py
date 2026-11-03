"""Generated data only: temporal leakage, identity, counts and frozen numerical parity."""
import contextlib
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import numpy as np
import torch
import legacy_unsw_archival_common_v1 as c
import legacy_unsw_archival_data_v1 as d
import legacy_unsw_archival_score_v1 as s
import legacy_unsw_archival_runner_v1 as runner
import legacy_reference_sample_prepare_v1 as prep


class Quiet:
    stage='SYNTHETIC'
    def tick(self,*args,**kwargs): pass


def fixtures():
    root=Path(__file__).resolve().parents[2]
    folder=root/'fixtures'
    if not folder.exists(): folder=root/'runs/legacy_commissioning_unsw_hpc_delivery_v1_20260926/bundle/fixtures'
    return c.read(folder/'expected.json')


def generated_flow():
    import issue27ckda_d0_resource_pilot_v1 as translator
    return translator.netfound_flow([fixtures()['captures']['synthetic-normal']['rows'][1]])


def tiny_data():
    expected=fixtures(); templates=expected['captures']['synthetic-normal']['rows']
    mac='02:00:00:00:00:01'; normal=[]
    for n,idx in enumerate((1,2,3,4,1,1,2),1):
        row=copy.deepcopy(templates[idx]); row['frame.number']=str(n); row['frame.time_epoch']=str(n)
        normal.append(row)
    mixed=[]
    for n in range(1,4):
        row=copy.deepcopy(expected['captures']['synthetic-mixed']['rows'][0])
        row['frame.number']=str(n); row['frame.time_epoch']=str(10+n)
        mixed.append(row)
    roster=[dict(mac=mac,device_id='synthetic:'+mac,display_name='Netatmo Camera',role=c.ROLE,
        t0=1.,cutoff=4.5,cutoff_frame=4,eligible_reference_components_by_protocol={'6':2,'17':2},
        planned_selected_references_by_protocol={'6':2,'17':2},planned_reference_count=4,
        full_normal_eligible_positions=3,planned_normal_query_count=3,planned_attack_query_count=3,
        normal_later_protocol_counts={'6':3},fallback_protocols=[])]
    intervals=[dict(owner=mac,start=10+n,end=10+n,annotation_id='a'+str(n),rate_metadata=str(n),
        victim_ip='10.250.0.1',attacker_ip='10.250.0.205',target_tcp_port=80,expected_legal_positive_count=1) for n in range(1,4)]
    labels=dict(intervals=intervals)
    specs=[dict(capture_id='normal',sha256='a'*64,kind='normal',packet_count=7,selection_salt='salt'),
           dict(capture_id='mixed',sha256='b'*64,kind='mixed',packet_count=3,intervals=intervals)]
    recipe=dict(normal_queries={'device_budget':20},reference_policy=dict(supported_protocols=[6,17],
        ordering_salt='salt',max_total_components=64),counts={'queries':6,'references':4})
    @contextlib.contextmanager
    def decode(spec): yield iter(copy.deepcopy(normal if spec['kind']=='normal' else mixed))
    return recipe,roster,labels,specs,[mac],decode,normal,mixed


class Contracts(unittest.TestCase):
    def setUp(self): torch.set_num_threads(2)

    def test_largest_remainder_hand_calculated(self):
        # Residual quotas 20/9, 12/9, 4/9: the last seat belongs to c.
        self.assertEqual(d.quotas({'a':6,'b':4,'c':2},7),{'a':3,'b':2,'c':2})

    def test_quota_tie_and_all(self):
        self.assertEqual(d.quotas({'b':3,'a':3},3),{'b':1,'a':2})
        self.assertEqual(d.quotas({'b':1,'a':1},20),{'b':1,'a':1})

    def test_insufficient_budget_stops(self):
        with self.assertRaisesRegex(RuntimeError,'COMPONENTS_EXCEED'): d.quotas({'a':2,'b':2},1)

    def test_no_authority_before_reads(self):
        with patch.object(c,'verify',side_effect=AssertionError('read')):
            with self.assertRaisesRegex(RuntimeError,'NOT_AUTHORIZED'): runner.authorize('missing','missing',False)

    def test_output_not_restartable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); out=root/'runs/real_evaluation'; out.mkdir(parents=True)
            with self.assertRaisesRegex(RuntimeError,'NO_RETRY'): runner.authorize(root,out,True)

    def test_path_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError,'PATH_ESCAPE'): c.confined(tmp,'../escape')

    def test_seal_detects_mutation_and_extra(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp); c.write(p/'a.json',{}); c.seal(p); self.assertEqual(c.verify(p),1)
            c.write(p/'extra',{})
            with self.assertRaisesRegex(RuntimeError,'FILE_SET'): c.verify(p)
            (p/'a.json').write_text('changed',encoding='utf-8')
            with self.assertRaisesRegex(RuntimeError,'SHA_MISMATCH'): c.verify(p)

    def test_exact_label_rejects_wrong_ip_port_ack_time_owner(self):
        _,roster,labels,_,_,_,_,mixed=tiny_data(); row=mixed[0]; api=prep.old.legacy_runtime()[0]
        self.assertIsNotNone(d.attack_label(row,api.event_from_tshark(row),roster[0]['mac'],labels['intervals']))
        for field,value in [('ip.src','10.250.0.204'),('ip.dst','10.250.0.2'),('tcp.dstport','81'),
                            ('tcp.flags.ack','1'),('frame.time_epoch','99'),('eth.dst','02:00:00:00:00:02')]:
            bad=dict(row); bad[field]=value
            self.assertIsNone(d.attack_label(bad,api.event_from_tshark(bad),roster[0]['mac'],labels['intervals']),field)

    def test_attacker_mac_not_new_label_condition(self):
        _,roster,labels,_,_,_,_,mixed=tiny_data(); row=dict(mixed[0]); row['eth.src']='02:aa:bb:cc:dd:ee'
        api=prep.old.legacy_runtime()[0]
        self.assertIsNotNone(d.attack_label(row,api.event_from_tshark(row),roster[0]['mac'],labels['intervals']))

    def test_whole_materialization_and_weights(self):
        recipe,roster,labels,specs,known,decode,_,_=tiny_data()
        with tempfile.TemporaryDirectory() as tmp:
            q,r=d.materialize(tmp,Path(tmp)/'out',recipe,roster,labels,specs,known,decode,Quiet())
            self.assertEqual((len(q),len(r)),(6,4)); self.assertTrue(all(x['device']==roster[0]['device_id'] for x in q))
            self.assertTrue(all(x['partition']==c.ROLE for x in q+r))
            self.assertEqual(sum(x['label'] for x in q),3)
            self.assertAlmostEqual(sum(1/x['label_metric_weight_denominator'] for x in q if x['label']==0),1)
            self.assertEqual(c.verify(Path(tmp)/'out'),6)

    def test_missing_population_stops_before_features(self):
        recipe,roster,labels,specs,known,decode,_,_=tiny_data(); roster[0]['full_normal_eligible_positions']=4
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError,'NORMAL_POPULATION'):
                d.materialize(tmp,Path(tmp)/'out',recipe,roster,labels,specs,known,decode,Quiet())
            self.assertFalse((Path(tmp)/'out/SHA256SUMS').exists())

    def test_missing_attack_interval_stops(self):
        recipe,roster,labels,specs,known,decode,_,_=tiny_data(); labels['intervals'][0]['expected_legal_positive_count']=2
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError,'INTERVAL_COUNTS'):
                d.materialize(tmp,Path(tmp)/'out',recipe,roster,labels,specs,known,decode,Quiet())

    def test_causal_snapshot_immutable_and_future_independent(self):
        import issue27ckda_d0_resource_pilot_v1 as translator
        recipe,roster,labels,specs,known,decode,normal,_=tiny_data()
        with tempfile.TemporaryDirectory() as tmp:
            q,r=d.materialize(tmp,Path(tmp)/'out',recipe,roster,labels,specs,known,decode,Quiet())
            targets=[x for x in q+r if x['capture_id']=='normal']
            first=list(d.selected_snapshots(iter(normal),specs[0],targets,known,prep.old.legacy_runtime(),translator))
            changed=copy.deepcopy(normal); changed[-1]['tcp.seq_raw']='555555'
            second=list(d.selected_snapshots(iter(changed),specs[0],targets,known,prep.old.legacy_runtime(),translator))
            self.assertEqual(first[:-1],second[:-1])
            self.assertNotEqual(first[-1],second[-1])
            self.assertEqual(set(first[0][1]),{'flow_duration','burst_tokens','directions','bytes','iats','counts','protocol'})

    def test_prefix_matches_original_snapshot_directly(self):
        import issue27ckda_d0_resource_pilot_v1 as translator
        recipe,roster,labels,specs,known,decode,normal,_=tiny_data(); runtime=prep.old.legacy_runtime()
        with tempfile.TemporaryDirectory() as tmp:
            q,r=d.materialize(tmp,Path(tmp)/'out',recipe,roster,labels,specs,known,decode,Quiet())
            targets=[x for x in q+r if x['capture_id']=='normal']; adapter=dict(d.selected_snapshots(iter(normal),specs[0],targets,known,runtime,translator))
            contexts=prep.ScopedPrefixes('normal',known,runtime[1],retain_full_rows=True); byframe={x['frame']:x for x in targets}
            for row in normal:
                event=runtime[0].event_from_tshark(row); _,ns,_=contexts.append(row,event)
                target=byframe.get(int(row['frame.number']))
                if target: self.assertEqual(adapter[target['uid']],contexts.snapshot(ns,translator))

    def test_snapshot_rejects_foreign_uid(self):
        import issue27ckda_d0_resource_pilot_v1 as translator
        recipe,roster,labels,specs,known,decode,normal,_=tiny_data()
        with tempfile.TemporaryDirectory() as tmp:
            q,r=d.materialize(tmp,Path(tmp)/'out',recipe,roster,labels,specs,known,decode,Quiet())
            target=dict(r[0]); target['uid']='wrong'
            with self.assertRaisesRegex(RuntimeError,'IDENTITY_DRIFT'):
                list(d.selected_snapshots(iter(normal),specs[0],[target],known,prep.old.legacy_runtime(),translator))

    def test_reference_round_robin_cap_and_no_duplicate(self):
        refs=[dict(protocol=p,component_id=str(p)+'-'+str(i),uid=str(p)+'-'+str(i)) for p,n in ((6,603),(17,20)) for i in range(n)]
        out=d.select_references(refs,dict(supported_protocols=[6,17],ordering_salt='x',max_total_components=64))
        self.assertEqual(sum(x['protocol']==6 for x in out),44)
        self.assertEqual(len({x['uid'] for x in out}),64)

    def test_q_arithmetic_exact_existing_runner(self):
        from legacy_qref_runner_v1 import q_scores
        torch.manual_seed(27); z=torch.randn(257,768); h=torch.randn(257,128); b=torch.randn(257)
        models={'Q_'+str(seed):s.Residual('Q').eval() for seed in c.SEEDS}
        for model in models.values(): torch.nn.init.normal_(model.last.weight)
        registered=torch.ones(257,dtype=torch.bool); registered[::3]=False
        actual=s.predict_q(models,z,h,b,registered,Quiet()); expected=q_scores(models,z,h,b,Quiet(),registered)
        for key in actual: self.assertTrue(np.array_equal(actual[key],expected[key]),key)
        self.assertTrue(np.array_equal(actual['Q'][::3],b.numpy()[::3]))

    def test_metric_exact_existing_runner(self):
        from legacy_qref_evaluate_v1 import score_models
        recipe,roster,labels,specs,known,decode,_,_=tiny_data()
        with tempfile.TemporaryDirectory() as tmp:
            q,r=d.materialize(tmp,Path(tmp)/'out',recipe,roster,labels,specs,known,decode,Quiet())
            z=torch.randn(len(q),768); rz=torch.randn(len(r),768); bank=s.Bank(r,rz,{c.ROLE})
            models={'FULL_'+str(seed):s.Metric(seed) for seed in c.SEEDS}; models['RAW']=s.Raw()
            actual,valid=s.evidences(models,z,q,bank,Quiet())
            expected,mask=score_models(models,z,q,bank,{'evaluation':{'control_salt':'UNUSED_NO_SUBSETTING'}},Quiet())
            for key in actual: self.assertTrue(np.array_equal(actual[key],expected[key]),key)
            self.assertTrue(np.array_equal(valid,mask))

    def test_singleton_preserves_q_and_threshold_strict(self):
        self.assertTrue(s.veto([True],[1.],[False],0.)[0])
        self.assertTrue(s.veto([True],[.5],[True],.5)[0])
        self.assertFalse(s.veto([True],[.6],[True],.5)[0])

    def test_nonfinite_score_stops(self):
        with self.assertRaises(Exception): s.veto([True],[np.nan],[True],.5)

    def test_metric_population_estimate_distinct(self):
        rows=[dict(label=0,label_metric_weight_denominator=2,population_group_count=90,selected_group_count=1),
              dict(label=0,label_metric_weight_denominator=2,population_group_count=10,selected_group_count=1)]
        m=s.measure(rows,np.array([True,False]),np.array([True,True]))['normal']
        self.assertEqual(m['rate'],.5); self.assertEqual(m['weighted_rate'],.5)
        self.assertEqual(m['population_size_corrected_FPR_estimate'],.9)

    def test_feature_merge_missing_and_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp); w=out/'worker_00'; w.mkdir(); c.write(w/'status.json',{'status':'COMPLETE'}); c.write(w/'uids.json',['a','a'])
            np.save(w/'features.npy',np.ones((2,768),np.float32)); c.seal(w)
            with self.assertRaisesRegex(RuntimeError,'SHARD_UID'): runner.merge_features(out,[{'uid':'a'},{'uid':'b'}],[],1)

    def test_full_synthetic_scoring_and_exports(self):
        recipe,roster,labels,specs,known,decode,_,_=tiny_data()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); out=root/'runs/real_evaluation'; out.mkdir(parents=True)
            q,r=d.materialize(tmp,out/'manifests',recipe,roster,labels,specs,known,decode,Quiet())
            keys=['normalizer_mean','normalizer_scale','p2__0.weight','p2__0.bias','p2__3.weight','p2__3.bias']
            state=dict(normalizer_mean=np.zeros(768,np.float64),normalizer_scale=np.ones(768,np.float64),
                **{'p2__0.weight':np.zeros((128,769),np.float32),'p2__0.bias':np.zeros(128,np.float32),
                   'p2__3.weight':np.zeros((1,128),np.float32),'p2__3.bias':np.zeros(1,np.float32)})
            np.savez(root/'state.npz',**state); heads={}; cuts={'RAW':.84,'FULL':.001,'NO_CF':.001}
            for arm in ('Q','FULL','NO_CF'):
                for seed in c.SEEDS:
                    name=arm+'_'+str(seed); model=s.Residual('Q') if arm=='Q' else s.Metric(seed)
                    path=root/(name+'.npz'); np.savez(path,**{k:v.detach().numpy() for k,v in model.state_dict().items()})
                    heads[name]=path.name
                    if arm!='Q': cuts[name]=.001
            c.write(root/'runtime_contract.json',{'models':{'state':'state.npz','heads':heads}})
            recipe.update(immutable_e3={'state_array_allowlist':keys},immutable_detector={'Q_probability_threshold':.06,'cuts':cuts},claim='SYNTHETIC_ONLY')
            rng=np.random.default_rng(27); features=rng.normal(size=(10,768)).astype(np.float32)
            gate=s.evaluate(root,out/'evaluation',recipe,roster,{'controls':[]},q,r,features,Quiet())
            self.assertFalse(gate['paper_or_deployment_certified'])
            self.assertEqual(c.read(out/'evaluation/report.json')['independent_ID'],'NOT_RUN')
            self.assertEqual(c.verify(out/'evaluation'),6)
            c.write(out/'status.json',{'status':'COMPLETE'}); (out/'flows').mkdir(); (out/'flows/large').write_bytes(b'flow')
            c.seal(out); runner.export(root)
            export=c.read(root/'export_manifest.json')
            self.assertIn('runs/real_evaluation/flows/large',export['omitted'])
            self.assertIn('runs/real_evaluation/evaluation/report.json',export['included'])

    def test_user_stop_guard(self):
        from legacy_unsw_archival_runtime_v1 import Progress
        with tempfile.TemporaryDirectory() as tmp:
            progress=Progress(Path(tmp)/'run',{'wall_seconds':60,'memory_gib':128,'disk_gib':10})
            try:
                (progress.out/'STOP_REQUESTED').touch()
                with self.assertRaisesRegex(RuntimeError,'USER_STOP'): progress.guard()
            finally: progress.stop('STOPPED_NO_RETRY','synthetic stop')

    def test_terminal_success_cannot_hide_watchdog_failure(self):
        from legacy_unsw_archival_runtime_v1 import Progress
        with tempfile.TemporaryDirectory() as tmp:
            progress=Progress(Path(tmp)/'run',{'wall_seconds':60,'memory_gib':128,'disk_gib':10})
            try:
                progress.error='COMBINED_MEMORY_LIMIT'
                with self.assertRaisesRegex(RuntimeError,'MEMORY_LIMIT'): progress.stop('COMPLETE')
            finally: progress.stop('STOPPED_NO_RETRY','synthetic watchdog')

    def test_time_regression_fails(self):
        recipe,roster,labels,specs,known,decode,normal,mixed=tiny_data(); normal[-1]['frame.time_epoch']='1'
        @contextlib.contextmanager
        def bad(spec): yield iter(normal if spec['kind']=='normal' else mixed)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError,'TIME_REGRESSION'):
                d.materialize(tmp,Path(tmp)/'out',recipe,roster,labels,specs,known,bad,Quiet())


if __name__=='__main__': unittest.main()
