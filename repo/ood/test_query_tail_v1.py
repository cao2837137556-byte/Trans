"""Generated-only semantic and lifecycle regression tests; never real assets."""
import copy
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import torch
import query_tail_core_v1 as k
import query_tail_prepare_v1 as p
import query_tail_train_v1 as t
import query_tail_evaluate_v1 as e
import query_tail_runner_v1 as runner
import query_tail_export_v1 as exporter
from continuous_input_v3 import RecentState
from continuous_model_v3 import classifier as original_classifier
from continuous_data_v3 import save_rows
c = k.c


def packet(frame=1, proto=6, flags=2, time='1', outgoing=True):
    return {'frame.number':str(frame), 'frame.time_epoch':time, 'eth.src':'aa' if outgoing else 'bb',
            'eth.dst':'bb' if outgoing else 'aa', 'ip.src':'1' if outgoing else '2', 'ip.dst':'2' if outgoing else '1',
            'ip.hdr_len':'20', 'ip.dsfield':'0', 'ip.len':'40', 'ip.flags':'0', 'ip.ttl':'64',
            'tcp.flags':str(flags), 'tcp.window_size_value':'4096', 'tcp.seq_raw':str(frame),
            'tcp.ack_raw':'1', 'tcp.urgent_pointer':'0', 'udp.length':'20'}


def example(proto=6, flags=2):
    state = RecentState('aa', ['session'], proto); state.append(packet(proto=proto, flags=flags))
    flow, values, provenance = state.snapshot()
    body = dict(flow=flow, state=values, provenance=provenance)
    row = dict(uid='u', partition='LEARN', fit_role='FIT', use='QUERY', protocol=proto, frame=1,
               timestamp=1., session_id=provenance['namespace_sha256'], label=0, device='d', activity='a',
               capture_id='c', component_id='x', source_sha256='s', reference_end=0., label_metric_weight_denominator=1)
    return body, row


class Quiet:
    optimizer_updates = 0
    stage = ''
    def tick(self, *args, **kwargs): pass
    def guard(self): pass


def synthetic_design():
    # Packaged design is read only for constants, not real data or checkpoints.
    root = Path(os.environ.get('QUERY_TAIL_TEST_ROOT', Path(__file__).resolve().parents[2]))
    path = root/'design_contract.json'
    if not path.exists(): path = root/'runs/legacy_query_tail_learning_design_v1_20260930/design_contract.json'
    design = c.read(path); design['synthetic_only'] = True; design['training']['epochs'] = 1
    return design


def fixture(folder):
    """Small fake parent with unreadable reference bodies to detect accidental reads."""
    folder = Path(folder); base = folder/'base'; base.mkdir(); root = folder/'package'; root.mkdir()
    for name in ('inputs', 'features', 'normalizers', 'spool', 'calibration', 'CIC_DEV', 'UNSW_DEV'): (base/name).mkdir()
    design = synthetic_design(); meta = {}; bodies = []; rng = np.random.default_rng(19)
    for role in k.ROLES:
        rows = []
        splits = ('FIT', 'CAL') if role == 'LEARN' else ('DEV',)
        for split, device, kind in itertools.product(splits, ('a','b'), range(6)):
            label = int(kind >= 3); proto = 17 if kind in (2, 5) else 6
            flags = 2 if kind in (0, 3) else 16
            body, row = example(proto, flags); uid = role+'_'+split+'_'+device+'_'+str(kind)
            row.update(uid=uid, fit_role=split, partition={'LEARN':'LEARN','CIC_DEV':'DEV','UNSW_DEV':'EXTERNAL_ARCHIVAL_EVALUATION'}[role],
                       label=label, device=device, capture_id=uid, component_id=uid, source_sha256=uid,
                       activity=('normal' if label == 0 else 'TCP' if kind == 3 else 'Hydra' if kind == 4 else 'UDP'),
                       label_metric_weight_denominator=6)
            rows.append(row); bodies.append((uid, role, len(rows)-1, proto, 1, 1, 0, json.dumps(body)))
        meta[role] = rows; save_rows(base/'inputs'/(role+'.jsonl.gz'), rows)
        np.save(base/'features'/(role+'.npy'), rng.normal(size=(len(rows),794)).astype(np.float32))
    indices = {role:np.asarray([i for i,r in enumerate(meta['LEARN']) if r['fit_role'] == role], dtype=np.int64) for role in ('FIT','CAL')}
    for split, ix in indices.items(): c.save_arrays(base/'inputs'/(split+'.npz'), indices=ix)
    c.seal(base/'inputs'); c.seal(base/'features')
    norm = np.zeros(768), np.ones(768); c.save_arrays(base/'normalizers/RECENT.npz', mean=norm[0], scale=norm[1]); c.seal(base/'normalizers')
    db = sqlite3.connect(str(base/'spool/snapshots.sqlite'))
    db.execute('CREATE TABLE snapshots(uid TEXT PRIMARY KEY,role TEXT,slot INTEGER,protocol INTEGER,width INTEGER,bursts INTEGER,batch_id INTEGER,body TEXT)')
    db.executemany('INSERT INTO snapshots VALUES(?,?,?,?,?,?,?,?)', bodies)
    for role, n in (('SOURCE_REFS',179),('UNSW_REFS',92)):
        db.executemany('INSERT INTO snapshots VALUES(?,?,?,?,?,?,?,?)', [(role+str(i),role,i,6,1,1,0,'INVALID_REF_BODY_DO_NOT_READ') for i in range(n)])
    db.commit(); db.close()
    counts = {'protocol_%s_label_%s'%(proto,label):sum(r['fit_role']=='FIT' and r['protocol']==proto and r['label']==label for r in meta['LEARN']) for proto in (6,17) for label in (0,1)}
    counts.update(normal_TCP=4, TCP_SYN_without_ACK=4)
    c.write(base/'spool/support.json', dict(counts=counts))
    design['data']['role_counts'] = {role:len(rr) for role,rr in meta.items()}
    design['data']['uid_sha256'] = {role:c.uid_sha(r['uid'] for r in rr) for role,rr in meta.items()}
    for split, ix in indices.items():
        rr = [meta['LEARN'][i] for i in ix]
        design['data'][split] = dict(rows=len(rr), normal=6, attack=6)
        design['data']['fit_cal_identity'][split] = dict(rows=len(rr), uid_sha256=c.uid_sha(r['uid'] for r in rr))
    design['input']['descriptor_rows'] = sum(len(rr) for rr in meta.values())
    for key, rel in [('spool_sha256','spool/snapshots.sqlite'),('input_manifest_sha256','inputs/SHA256SUMS'),('feature_manifest_sha256','features/SHA256SUMS'),('normalizer_manifest_sha256','normalizers/SHA256SUMS')]:
        design['provenance'][key] = c.sha(base/rel)
    c.write(base/'P_COMPLETE.json', dict(status='COMPLETE',rows=1095200,feature_seal=design['provenance']['feature_manifest_sha256']))
    c.write(root/'parent_pins.json', {'P_COMPLETE.json':c.sha(base/'P_COMPLETE.json')})
    c.write(root/'design_contract.json', design)
    # Fake R0 is deterministic and its CAL thresholds are derived in exactly the production way.
    cuts = None
    for pool in ('CAL','CIC_DEV','UNSW_DEV'):
        role = 'LEARN' if pool == 'CAL' else pool; ix = indices['CAL'] if pool == 'CAL' else np.arange(len(meta[role]))
        rr = [meta[role][i] for i in ix]; arrays = np.load(base/'features'/(role+'.npy'))
        scores = {'RECENT_'+str(seed):k.scores(k.classifier(seed,768), arrays, None, ix, norm, 768) for seed in c.SEEDS}
        scores['RECENT_ensemble'] = np.stack(list(scores.values())).mean(0,dtype=np.float64)
        if pool == 'CAL':
            cuts = e.calibrate(rr,scores); c.save_arrays(base/'calibration/base_logits.npz', **scores)
            c.write(base/'calibration/thresholds.json',dict(tau={'RECENT':{s:cuts['RECENT_'+s] for s in e.SUFFIXES}}))
        else:
            c.save_arrays(base/pool/'scores.npz', **scores)
            c.save_arrays(base/pool/'decisions.npz',uid=np.asarray([r['uid'] for r in rr]),**{name:v>cuts[name] for name,v in scores.items()})
    return root,base,design


class QueryReadoutTests(unittest.TestCase):
    def test_all_flags_and_udp(self):
        for flags in (1,2,4,8,16,32,64,128,256,511):
            b,r = example(flags=flags); q,info = k.descriptor(b,r)
            self.assertEqual(q.shape,(14,)); self.assertEqual(q[1:10].tolist(),[float(bool(flags&(1<<i))) for i in range(9)])
        b,r=example(17); q,_=k.descriptor(b,r)
        self.assertEqual(q[:10].sum(),0); self.assertEqual(q[11],0); self.assertGreater(q[12],0)

    def test_interleaved_current_not_last_burst(self):
        state=RecentState('aa',['session'],6)
        for frame,time,out in [(1,'1',True),(2,'1.001',False),(3,'1.002',True)]: state.append(packet(frame,time=time,outgoing=out))
        flow,s,prov=state.snapshot(); _,r=example(); r.update(frame=3,timestamp=1.002)
        q,info=k.descriptor(dict(flow=flow,state=s,provenance=prov),r)
        self.assertEqual(prov['bursts'][0]['frames'],[1,3]); self.assertEqual(q[-1],1); self.assertEqual(info['packets'],3)

    def test_equal_time_and_age_boundary(self):
        state=RecentState('aa',['session'],6)
        for f,tm in [(1,'1'),(2,'1'),(3,'61')]: state.append(packet(f,time=tm))
        flow,s,prov=state.snapshot(); _,r=example(); r.update(frame=3,timestamp=61.)
        self.assertEqual(k.descriptor(dict(flow=flow,state=s,provenance=prov),r)[1]['span_seconds'],60)

    def test_missing_future_duplicate_headers_roles(self):
        b,r=example()
        bad=[]
        x=copy.deepcopy(b); x['provenance']['query_frame']=2; bad.append((x,r))
        x=copy.deepcopy(b); x['provenance']['bursts'][0]['times_ns'][0]+=1; bad.append((x,r))
        x=copy.deepcopy(b); x['provenance']['bursts'][0]['headers'][0].pop(); bad.append((x,r))
        x=copy.deepcopy(b); x['flow']['burst_tokens'][0][5]=0; bad.append((x,r))
        x=dict(r,use='REFERENCE'); bad.append((b,x))
        x=copy.deepcopy(b); x['provenance']['bursts'].append(x['provenance']['bursts'][0]); bad.append((x,r))
        for body,row in bad:
            with self.subTest(body=body),self.assertRaises(RuntimeError): k.descriptor(body,row)

    def test_identity_fields_not_predictors(self):
        b,r=example(); q,_=k.descriptor(b,r)
        changed=dict(r,label=1,device='new',owner='zz',uid='new',source_sha256='new',port=443,activity='changed')
        self.assertTrue(np.array_equal(q,k.descriptor(b,changed)[0]))
        b2,r2=example(flags=16); self.assertFalse(np.array_equal(q,k.descriptor(b2,r2)[0]))

    def test_initial_function(self):
        x=torch.randn(8,768); q=torch.randn(8,14)
        for seed in c.SEEDS:
            base=original_classifier(seed,768); new=k.classifier(seed,782)
            # Changing GEMM width changes float32 accumulation, despite zero extra columns.
            self.assertTrue(torch.allclose(base(x),new(torch.cat((x,q),1)),atol=1e-6,rtol=1e-6))
            self.assertTrue(torch.equal(base[0].weight,new[0].weight[:,:768]))
            self.assertEqual(torch.count_nonzero(new[0].weight[:,768:]),0)
            self.assertTrue(torch.allclose(base.double()(x.double()),new.double()(torch.cat((x,q),1).double()),atol=1e-14,rtol=1e-14))


class TailMathTests(unittest.TestCase):
    def test_tail_ties_mass_and_weighted_boundary(self):
        for x,w,expected in [([3,2,1],[.005,.5,.495],[.5,.5,0]),([3,3,1],[.1,.3,.6],[.25,.75,0]),([1,1,1],[.1,.3,.6],[.1,.3,.6]),([1,3,2],[.2,.4,.4],[0,1,0])]:
            np.testing.assert_allclose(k.tail_distribution(x,w),expected,atol=1e-14)

    def test_tail_order_invariance(self):
        x=np.array([2,3,3,1]); w=np.array([.1,.2,.3,.4]); perm=[3,1,0,2]
        h=k.tail_distribution(x,w); hp=k.tail_distribution(x[perm],w[perm]); np.testing.assert_allclose(h[perm],hp)

    def test_invalid_tail(self):
        for x,w in [([np.nan],[1]),([1],[0]),([1,2],[.5]),([1,2],[-1,2])]:
            with self.subTest(x=x),self.assertRaises(RuntimeError): k.tail_distribution(x,w)

    def test_sampler_roles_uid_order_and_determinism(self):
        rows=[dict(uid=u,partition='LEARN',fit_role='FIT',label=0) for u in ('b','a')]
        a=k.TailSampler(rows,[.25,.75],27,0).draw(128)
        b=k.TailSampler(rows[::-1],[.75,.25],27,0).draw(128)
        self.assertEqual([rows[i]['uid'] for i in a],[rows[::-1][i]['uid'] for i in b])
        self.assertLess(len(set(a)),len(a))
        for field,value in [('partition','DEV'),('fit_role','CAL'),('label',1)]:
            bad=copy.deepcopy(rows);bad[0][field]=value
            with self.assertRaises(RuntimeError): k.TailSampler(bad,[.25,.75],27,0)

    def test_pair_gradients_both_sides(self):
        pos=torch.tensor([0.],requires_grad=True); neg=torch.tensor([0.],requires_grad=True)
        k.objective(pos,torch.ones(1),np.array([.5]),1,neg).backward()
        self.assertLess(pos.grad.item(),0); self.assertGreater(neg.grad.item(),0)

    def test_batch_estimator_exhaustive_and_partial(self):
        x=torch.tensor([-2.,1.,2.]); y=torch.tensor([0.,1.,1.]); w=np.array([.5,.1,.4]); neg=torch.tensor([-.3,.7])
        target=k.objective(x,y,w,3,neg).item()
        for b in (1,2,3):
            vals=[k.objective(x[list(ix)],y[list(ix)],w[list(ix)],3,neg).item() for ix in itertools.combinations(range(3),b)]
            self.assertAlmostEqual(np.mean(vals),target,places=7)

    def test_zero_positive_batch(self):
        x=torch.tensor([0.],requires_grad=True); y=torch.zeros(1); w=np.array([.5]); neg=torch.tensor([1.],requires_grad=True)
        bce=k.objective(x,y,w,2); loss=k.objective(x,y,w,2,neg)
        self.assertEqual(loss.item(),bce.item()/2); loss.backward(); self.assertIsNone(neg.grad)

    def test_source_only_weights_and_calibration(self):
        _,row=example(); rr=[dict(row,uid='0'),dict(row,uid='1',label=1)]
        np.testing.assert_allclose(k.weights(rr),[.5,.5])
        for role in ('CAL','DEV','REFERENCE'):
            with self.assertRaises(Exception): k.weights([dict(r,fit_role=role) for r in rr])
        cal=[dict(row,fit_role='CAL',uid='n'),dict(row,fit_role='CAL',uid='a',label=1)]
        a=e.calibrate(cal,{'x':np.array([1.,99.])}); b=e.calibrate(cal,{'x':np.array([1.,-99.])})
        self.assertEqual(a,b)
        with self.assertRaises(Exception): e.calibrate([dict(r,partition='DEV') for r in cal],{'x':np.ones(2)})


class LifecycleTests(unittest.TestCase):
    def test_CAL_labels_do_not_change_training_endpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,base,design=fixture(tmp)
            metadata,indices=p.load_metadata(base,design); rr=metadata['LEARN']
            arrays,norm=p.arrays(base,design); q=np.zeros((len(rr),14),np.float32); stages=np.zeros(len(rr),np.uint8)
            t.train(design,rr,arrays['LEARN'],q,norm,indices['FIT'],stages,'QUERY_TAIL',27,root/'a',Quiet(),synthetic=True)
            changed=copy.deepcopy(rr)
            for r in changed:
                if r['fit_role']=='CAL':r['label']=1-r['label']
            t.train(design,changed,arrays['LEARN'],q,norm,indices['FIT'],stages,'QUERY_TAIL',27,root/'b',Quiet(),synthetic=True)
            with np.load(root/'a/head.npz') as a,np.load(root/'b/head.npz') as b:
                self.assertTrue(all(np.array_equal(a[key],b[key]) for key in a.files))
            del arrays

    def test_nonfinite_and_truncated_features_rejected(self):
        for mode in ('nonfinite','truncated'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                root,base,design=fixture(tmp); path=base/'features/LEARN.npy'
                a=np.load(path);a[0,0]=np.nan
                np.save(path,a if mode=='nonfinite' else a[:-1])
                # Exact manifest must reject either corruption without an automatic cache fallback.
                with self.assertRaises(RuntimeError):p.arrays(base,design)
                self.assertFalse((root/'runs').exists())

    def test_duplicate_slot_and_role_mismatch_rejected(self):
        for mode in ('slot','role'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                root,base,design=fixture(tmp);run=root/'run';run.mkdir()
                db=sqlite3.connect(str(base/'spool/snapshots.sqlite'))
                uid=db.execute("SELECT uid FROM snapshots WHERE role='LEARN' AND slot=1").fetchone()[0]
                if mode=='slot':db.execute('UPDATE snapshots SET slot=0 WHERE uid=?',(uid,))
                else:db.execute("UPDATE snapshots SET role='CIC_DEV' WHERE uid=?",(uid,))
                db.commit();db.close();design['provenance']['spool_sha256']=c.sha(base/'spool/snapshots.sqlite')
                with self.assertRaises(RuntimeError):p.prepare(root,base,run,design,Quiet())
                self.assertFalse((run/'P_COMPLETE.json').exists())

    def test_full_generated_P_T_K_export_and_isolation(self):
        torch.set_num_threads(4)
        with tempfile.TemporaryDirectory() as tmp:
            root,base,design=fixture(tmp); run=root/'runs/query_tail'; run.mkdir(parents=True); (run/'endpoints').mkdir()
            before={str(f.relative_to(base)):c.sha(f) for f in base.rglob('*') if f.is_file()}
            metadata,indices,arrays,norm=p.prepare(root,base,run,design,Quiet())
            for arm,seed in itertools.product(k.ARMS,c.SEEDS):
                q=np.load(run/'prepared/LEARN_q.npy'); windows=np.load(run/'prepared/LEARN_window.npy')
                t.train(design,metadata['LEARN'],arrays['LEARN'],q,norm,indices['FIT'],windows['stage'],arm,seed,run/'endpoints'/(arm+'_'+str(seed)),Quiet(),synthetic=True)
            result=e.evaluate(root,base,run,design,metadata,indices,arrays,norm,Quiet())
            self.assertEqual(result['primary'],'QUERY_TAIL'); self.assertEqual(result['reference_adaptation_gain'],'NOT_TESTED')
            self.assertEqual(len(result['attack_group_protection']),20)
            for seed in c.SEEDS:
                endpoints=[c.read(run/'endpoints'/(a+'_'+str(seed))/'endpoint.json') for a in k.ARMS]
                self.assertTrue(all(r['order_hashes']==endpoints[0]['order_hashes'] for r in endpoints))
            self.assertEqual(before,{str(f.relative_to(base)):c.sha(f) for f in base.rglob('*') if f.is_file()})
            exporter.export(root); self.assertTrue((root/'query_tail_pullback.tar.gz.sha256').exists())
            with self.assertRaises(RuntimeError): exporter.export(root)
            del arrays

    def test_tampered_missing_extra_seal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'a').write_bytes(b'good'); c.seal(root); c.verify(root)
            (root/'extra').write_bytes(b'bad')
            with self.assertRaises(RuntimeError): c.verify(root)
            (root/'extra').unlink(); (root/'a').write_bytes(b'bad')
            with self.assertRaises(RuntimeError): c.verify(root)

    def test_no_authority_before_assets(self):
        with self.assertRaisesRegex(RuntimeError,'NOT_AUTHORIZED'): runner.authorize('MISSING_ROOT',False)

    def test_failure_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'logs').mkdir(); (root/'logs/failure.txt').write_text('IMPORT_FAIL')
            exporter.export(root); manifest=c.read(root/'export_manifest.json')
            self.assertIn('logs/failure.txt',manifest['included'])

    def test_resource_guards_and_persistent_stop(self):
        for mode in ('memory','wall','disk','user'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                limits=dict(wall_seconds=3600,memory_gib=16,disk_gib=1)
                monitor=runner.Progress(Path(tmp)/'monitor',limits)
                try:
                    if mode=='memory': limits['memory_gib']=0
                    if mode=='wall': monitor.started-=4000
                    if mode=='disk': limits['disk_gib']=0
                    if mode=='user': (monitor.out/'STOP_REQUESTED').write_bytes(b'')
                    monitor._last_guard=0
                    with self.assertRaises(RuntimeError): monitor.guard()
                    monitor.record_failure(RuntimeError('test_stop'),mode)
                    monitor.stop('STOPPED_NO_RETRY',error='test_stop')
                    self.assertEqual(c.read(monitor.out/'status.json')['status'],'STOPPED_NO_RETRY')
                    self.assertTrue((monitor.out/'first_failure.json').exists())
                finally:
                    monitor.closed.set(); monitor.thread.join(timeout=5)

    def test_support_failure_does_not_launch_training(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,base,design=fixture(tmp); run=root/'run';run.mkdir()
            # Alter one snapshot current flag and its exact flow tokens consistently, then re-pin only the generated fixture.
            db=sqlite3.connect(str(base/'spool/snapshots.sqlite'))
            for uid,text in db.execute("SELECT uid,body FROM snapshots WHERE role='LEARN'").fetchall():
                body=json.loads(text)
                if body['flow']['protocol']==6:
                    body['provenance']['bursts'][0]['headers'][0][5]=16; body['flow']['burst_tokens'][0][5]=16
                    db.execute('UPDATE snapshots SET body=? WHERE uid=?',(json.dumps(body),uid))
            db.commit();db.close();design['provenance']['spool_sha256']=c.sha(base/'spool/snapshots.sqlite')
            counts=c.read(base/'spool/support.json');counts['counts']['TCP_SYN_without_ACK']=0;c.write(base/'spool/support.json',counts,replace=True)
            with self.assertRaisesRegex(RuntimeError,'FIT_SYN_SUPPORT'):p.prepare(root,base,run,design,Quiet())
            self.assertFalse((run/'P_COMPLETE.json').exists());self.assertTrue((run/'prepared/source_support.json').exists())


if __name__=='__main__': unittest.main()
