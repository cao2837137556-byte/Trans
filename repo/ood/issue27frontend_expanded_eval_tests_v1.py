"""Generated inputs only: causal replay equivalence and fixed evaluation contracts."""
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import torch
import issue27frontend_expanded_eval_runner_v1 as r
import issue27frontend_expanded_eval_control_v1 as c
s=r.s


def raw(position,timestamp=0.,tier='H1',reverse=False,pair=('10.0.0.1','10.0.0.2'),variant=0):
    x={k:'' for k in r.zt.TSHARK_FIELDS}
    x.update({'frame.number':str(position+1),'frame.time_epoch':str(timestamp),'frame.len':'100',
              'frame.encap_type':'1','eth.type':'0x0800','tcp.flags':'0x0018','tcp.len':'60','udp.length':''})
    left,right=pair[::-1] if reverse else pair
    if tier in ('H1','H2'):
        x.update({'ip.src':left,'ip.dst':right,'ip.proto':'6' if tier=='H1' else '1'})
    if tier=='H1':
        x.update({'tcp.srcport':'2000' if reverse else '1000','tcp.dstport':'1000' if reverse else '2000'})
    if tier=='H3':
        x.update({'eth.src':left,'eth.dst':right,'eth.type':'0x0806'})
    if tier=='H4':x.update({'eth.type':'0x0806' if variant else '0x0800'})
    return x


def decoded(raws,positions):
    return [(x,r.zt.raw_to_event(r.engine,x,'synthetic_source','synthetic_member',i,'u%d'%i if i in positions else None))
            for i,x in enumerate(raws)]


def replay_new(raws,positions):
    pairs=decoded(raws,positions);targets={i:{'uid':'u%d'%i} for i in positions};out=[]
    last,routes=r.discover(iter(pairs),targets,len(pairs)-1)
    counts=r.replay(iter(pairs),targets,len(pairs)-1,last,routes,out.append)
    by_uid={t['uid']:{'key':a['key'],'event':t['event'],'signatures':a['signatures'][:t['event']+1],'tier':a['tier']}
            for a in out for t in a['targets']}
    return by_uid,counts


class ReplayTests(unittest.TestCase):
    def equivalent(self,raws,positions):
        pairs=decoded(raws,positions)
        specs=[r.engine.TargetSpec('u%d'%i,'synthetic_source','synthetic_member',i) for i in positions]
        semantic=r.engine.SemanticPrototype().process_member([x[1] for x in pairs],specs)
        targets={t.target_packet_ordinal:{'uid':t.uid,'expected_context_key':'synthetic_member\x1f%s\x1f%d'%(t.causal_context_id,t.context_epoch),
                 'expected_event_index':t.context_event_count-1,'scope':'generated','source_group':'synthetic_source'} for t in semantic}
        old,_=r.f3b.replay_member_once(r.engine,r.zt,r.f1,r.f3,iter(pairs),targets,len(pairs)-1)
        new,counts=replay_new(raws,positions)
        self.assertEqual(counts['targets'],len(positions))
        for t in old:
            n=new[t['uid']]
            self.assertEqual(n['key'],t['context_key']);self.assertEqual(n['event'],t['event_index'])
            self.assertEqual(n['signatures'],t['l1_signatures'])
            matrix=r.f4.encode_context(t['l1_signatures']);payload=r.feature_payload(n['signatures'])
            self.assertEqual(payload,matrix.astype('<f4').tobytes())
            self.assertEqual(r.prefix_hash(payload,n['event']),hashlib.sha256(r.f4.prefix_bytes(matrix,n['event'])).hexdigest())
        return new

    def test_h1_reversed_direction(self):
        got=self.equivalent([raw(i,i*.01,reverse=bool(i%2)) for i in range(12)],[1,7,11])
        self.assertEqual(got['u7']['signatures'][-1].split('\x1f')[1],'B_TO_A')

    def test_h2_nontransport(self):
        got=self.equivalent([raw(i,i*.01,'H2',bool(i%2)) for i in range(9)],[0,4,8])
        self.assertEqual(got['u8']['tier'],'H2')

    def test_h3_nonip(self):
        self.equivalent([raw(i,i*.01,'H3',bool(i%2)) for i in range(9)],[0,4,8])

    def test_h4_interleaved_eviction(self):
        xs=[raw(0,0,'H4'),raw(1,1,'H1'),raw(2,2,'H4'),raw(3,3,'H4',variant=1),raw(4,4,'H4')]
        got=self.equivalent(xs,[0,2,4]);self.assertEqual(got['u2']['event'],1);self.assertEqual(got['u4']['event'],0)

    def test_event_256_split(self):
        got=self.equivalent([raw(i,i*.01) for i in range(260)],[0,254,255,256,259])
        self.assertEqual(got['u255']['event'],255);self.assertEqual(got['u256']['event'],0)

    def test_idle_boundary(self):
        got=self.equivalent([raw(i,t) for i,t in enumerate([0,60,120.001,120.01])],[0,1,2,3])
        self.assertEqual(got['u1']['event'],1);self.assertEqual(got['u2']['event'],0)

    def test_span_boundary(self):
        got=self.equivalent([raw(i,t) for i,t in enumerate([0,60,120,180,240,300,300.001])],list(range(7)))
        self.assertEqual(got['u5']['event'],5);self.assertEqual(got['u6']['event'],0)

    def test_timestamp_regression(self):
        got=self.equivalent([raw(i,t) for i,t in enumerate([1,1.5,1.4,1.6])],[0,2,3])
        self.assertEqual(got['u2']['signatures'][-1].split('\x1f')[11],'true')

    def test_unselected_endpoint_token_order(self):
        xs=[raw(0,0,pair=('20.0.0.1','10.0.0.2')),raw(1,1),raw(2,2,reverse=True)]
        self.equivalent(xs,[2])

    def test_future_targets_do_not_change_prefix(self):
        xs=[raw(i,i*.02) for i in range(25)]
        a,_=replay_new(xs[:6],[5]);b,_=replay_new(xs,[5,24]);self.assertEqual(a['u5'],b['u5'])

    def test_discovery_missing_target_stops(self):
        with self.assertRaisesRegex(RuntimeError,'CONSERVATION'):
            r.discover(iter(decoded([raw(0)],{0})),{0:{'uid':'u0'},2:{'uid':'u2'}},2)

    def test_duplicate_target_uid_stops(self):
        pairs=decoded([raw(0),raw(1)],{0,1});last,routes=r.discover(iter(pairs),{0:{'uid':'u0'},1:{'uid':'u1'}},1)
        with self.assertRaisesRegex(RuntimeError,'REPLAY_TARGET'):
            r.replay(iter(pairs),{0:{'uid':'u0'},1:{'uid':'u0'}},1,last,routes,lambda x:None)

    def test_discovery_replay_route_drift_stops(self):
        pairs=decoded([raw(0)],{0});ts={0:{'uid':'u0'}};last,routes=r.discover(iter(pairs),ts,0)
        routes['u0']='bad'
        with self.assertRaisesRegex(RuntimeError,'ROUTE_DRIFT'):r.replay(iter(pairs),ts,0,last,routes,lambda x:None)

    def test_target_metadata_does_not_enter_features(self):
        pairs=decoded([raw(0),raw(1,1)],{1});ts={1:{'uid':'u1'}}
        last,routes=r.discover(iter(pairs),ts,1);a=[];b=[]
        r.replay(iter(pairs),ts,1,last,routes,a.append)
        r.replay(iter(pairs),{1:{'uid':'u1','label':1,'old_hard':0,'teacher':object()}},1,last,routes,b.append)
        self.assertEqual(a,b)

    def test_nonfinite_target_stops(self):
        xs=[raw(0,float('nan'))]
        with self.assertRaisesRegex(RuntimeError,'SEMANTICS'):replay_new(xs,[0])

    def test_corrupt_nontarget_does_not_advance_context(self):
        self.equivalent([raw(0,0),raw(1,float('nan')),raw(2,1)],[0,2])

    def test_interleaved_routes_generated(self):
        import random
        rng=random.Random(127);xs=[]
        for i in range(900):
            j=rng.randrange(8);tier=('H1','H2','H3','H4')[j%4]
            xs.append(raw(i,i*.5-(.8 if i%17==0 else 0),tier,bool(i%2),('10.0.%d.1'%j,'10.0.%d.2'%j),j//4))
        self.equivalent(xs,sorted(set(range(0,900,11))|{899}))


def metric_rows():
    return [dict(uid=str(i),label=y,ab_hard=a,old_hard=o,pool='attack' if y else 'benign',role='future_query',
                 attack_family='a' if y else 'benign',owner='A',source_group='source',context_key=str(i//2),
                 context_in_ab_train=False,member_in_ab_train=False) for i,(y,o,a) in enumerate([(1,1,0),(1,0,1),(0,1,0),(0,0,1)])]


class MeasurementTests(unittest.TestCase):
    def test_attack_flips_separate_from_benign_gain(self):
        result=s.metrics(metric_rows());a=result['attack']
        self.assertEqual((a['old_correct_new_wrong'],a['old_wrong_new_correct']),(1,1))
        self.assertEqual(result['overall']['ab_fpr'],.5)

    def test_zero_denominator(self):
        self.assertIsNone(s.metrics([])['attack']['ab_recall'])

    def test_metrics_survive_serialization(self):
        value=s.metrics(metric_rows());self.assertEqual(value,json.loads(json.dumps(value)))

    def test_seal_exists_only_after_complete(self):
        with tempfile.TemporaryDirectory(dir=s.ROOT/'tmp') as d:
            folder=Path(d);(folder/'a').write_text('a');s.seal(folder)
            self.assertEqual((folder/'SHA256SUMS').read_text().split('  ')[0],s.sha_file(folder/'a'))
            self.assertFalse((folder/'SHA256SUMS.tmp').exists())

    def test_student_causal_prefix_and_batch(self):
        r.m.configure();model=r.m.Student().eval();before=r.m.state_hash(model)
        x=torch.randn(31,131);y=torch.randn(8,131)
        with torch.inference_mode():
            full=model([x],['x'])[0];prefix=model([x[:12]],['x'])[0];batch=model([y,x],['y','x'])[1]
        torch.testing.assert_close(full[:12],prefix,atol=1e-6,rtol=1e-5)
        torch.testing.assert_close(full,batch,atol=1e-6,rtol=1e-5)
        self.assertEqual(before,r.m.state_hash(model))

    def test_supervisor_failure_stops_once(self):
        with tempfile.TemporaryDirectory(dir=s.ROOT/'tmp') as d:
            out=Path(d)/'attempt';cfg={'authorization':'SYNTHETIC_ONLY','caps':dict(s.CAPS,wall_seconds=30)}
            value=c.supervise(cfg,[str(s.PYTHON),'-c','raise SystemExit(7)'],out,synthetic=True)
            self.assertEqual(value['status'],'INPUT_OR_EXECUTION_STOP');self.assertEqual(value['retries'],0)
            self.assertFalse((out/'result.md').exists());self.assertTrue(c.status(out)['final'])
            with self.assertRaises(FileExistsError):c.supervise(cfg,[],out,synthetic=True)


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    s.atomic_json(s.PACKAGE/'synthetic_test_results.json',{'status':'PASS' if result.wasSuccessful() else 'FAIL',
                  'tests_run':result.testsRun,'tests_passed':result.testsRun-len(result.failures)-len(result.errors),
                  'failures':[(str(t),v) for t,v in result.failures+result.errors],
                  'real_model_loads':0,'real_model_forwards':0,'raw_archive_decodes':0,'optimizer_steps':0})
    raise SystemExit(0 if result.wasSuccessful() else 1)
