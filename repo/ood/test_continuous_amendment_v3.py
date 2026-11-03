"""Generated anomaly streams, arithmetic counterexamples, no real data or E3."""
import contextlib
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import torch
import continuous_audit_v3 as a
import continuous_input_v3 as inp
import continuous_evaluate_v3 as ev
import continuous_data_v3 as data
import continuous_model_v3 as model
import continuous_common_v3 as c
import legacy_reference_sample_prepare_v1 as prep
from test_continuous_repair_v3 import packet
from test_continuous_chain_v3 import fixture, DummyProgress


def context(): return inp.Contexts('generated', {'aa'}, prep.old.legacy_runtime()[0])


def target(row, capture='generated'):
    ct=inp.Contexts(capture, {'aa'}, prep.old.legacy_runtime()[0])
    ct.frame=int(row['frame.number'])-1
    owner, ns, event=ct.append(row)
    return dict(uid=prep.digest(['fixture',int(row['frame.number']),owner]), source_sha256='fixture',
                capture_id=capture, owner=owner, session_id=prep.digest(ns), timestamp=event.timestamp,
                protocol=event.ip_proto, frame=int(row['frame.number']), reference_end=-1.,use='QUERY')


class AnomalyContract(unittest.TestCase):
    def test_namespace_regression_poison_cannot_idle_reset(self):
        ct=context(); _,ns,_=ct.append(packet(1,100)); before=copy.deepcopy(ct.states[ns].snapshot())
        ct.append(packet(2,99)); self.assertIn(ns,ct.poisoned)
        with self.assertRaisesRegex(RuntimeError,'FIXED_TARGET_INVALID'):ct.require_target()
        ct.append(packet(3,120*inp.NS));self.assertFalse(ct.query_allowed)
        self.assertEqual(before,ct.states[ns].snapshot())

    def test_cross_key_and_outside_regressions_do_not_poison(self):
        ct=context();ct.append(packet(1,100))
        p=packet(2,90);p['tcp.srcport']='4321';ct.append(p);ct.require_target()
        self.assertEqual(ct.reasons['CAPTURE_REGRESSION_CROSS_KEY'],1)
        p=packet(3,80);p['eth.src']='cc';ct.append(p)
        self.assertEqual(ct.reasons['CAPTURE_REGRESSION_OUTSIDE_SCOPE'],1);self.assertFalse(ct.poisoned)
        ct.append(packet(4,101));ct.require_target()

    def test_payload_truncation_updates_context_and_state_but_not_query(self):
        ct=context();p=packet(1,0);p['frame.cap_len']='54';_,ns,_=ct.append(p)
        self.assertEqual(ct.states[ns].snapshot()[2]['bursts'][0]['frames'],[1])
        with self.assertRaisesRegex(RuntimeError,'PAYLOAD_TRUNCATED_QUERY'):ct.require_target()
        ct.append(packet(2,1));ct.require_target()
        self.assertEqual(ct.states[ns].snapshot()[2]['bursts'][0]['frames'],[1,2])
        self.assertGreater(ct.states[ns].snapshot()[1][0],np.log1p(np.log(2)))

    def test_missing_headers_no_token_no_state_and_taint_beyond_retained72(self):
        ct=context();_,ns,_=ct.append(packet(1,0));before=copy.deepcopy(ct.states[ns].snapshot())
        p=packet(2,1);p['tcp.flags']='';ct.append(p)
        self.assertEqual(ct.states[ns].snapshot(),before)
        for i in range(3,105):ct.append(packet(i,i*1_000_000_000))
        self.assertEqual(ct.states[ns].snapshot(),before)
        with self.assertRaisesRegex(RuntimeError,'MISSING_HEADER_HISTORY'):ct.require_target()

    def test_missing_header_taint_requires_strict_adjacent_idle_gap(self):
        ct=context();p=packet(1,0);p['ip.ttl']='';_,ns,_=ct.append(p)
        self.assertNotIn(ns,ct.states)
        ct.append(packet(2,60*inp.NS));self.assertFalse(ct.query_allowed)
        ct.append(packet(3,120*inp.NS+1));ct.require_target()
        self.assertEqual(ct.states[ns].snapshot()[2]['bursts'][0]['frames'],[3])
        self.assertEqual(ct.states[ns].snapshot()[1][-2:],[0.,0.])

    def test_missing_namespace_does_not_create_zero_port_key(self):
        ct=context();p=packet(1,0);p['tcp.srcport']=''
        with self.assertRaisesRegex(RuntimeError,'MISSING_NAMESPACE_HEADERS'):ct.append(p)
        self.assertFalse(ct.states)

    def test_ns_regression_hidden_by_float_rounding_stops_with_evidence(self):
        base=1_700_000_000*inp.NS
        with tempfile.TemporaryDirectory() as td:
            p=packet(1,base+2)
            audit=a.CaptureAudit(dict(capture_id='generated',sha256='fixture',expected_packets=2),{'aa'},prep.old.legacy_runtime(),
                                 {1:('LEARN',0,target(p))},td)
            try:
                audit.append(packet(1,base+2))
                with self.assertRaisesRegex(RuntimeError,'LEGACY_NS_ANOMALY_IDENTITY'):audit.append(packet(2,base+1))
            finally:audit.close()
            with gzip.open(Path(td)/'generated.anomalies.jsonl.gz','rt') as f:rows=[json.loads(x) for x in f]
            self.assertEqual(rows[-1]['frame'],2)
            self.assertEqual(rows[-1]['current_events'][0]['kind'],'NEW_TIMESTAMP_REGRESSION')
            self.assertEqual(rows[-1]['legacy_anomalies'],[])

    def test_legacy_anomaly_frame_identity_and_fixed_query_poison(self):
        with tempfile.TemporaryDirectory() as td:
            t=target(packet(3,3*inp.NS));spec=dict(capture_id='generated',expected_packets=3,sha256='fixture')
            audit=a.CaptureAudit(spec,{'aa'},prep.old.legacy_runtime(),{3:('LEARN',0,t)},td)
            try:
                audit.append(packet(1,2*inp.NS));audit.append(packet(2,inp.NS))
                with self.assertRaisesRegex(RuntimeError,'POISONED_PREFIX'):audit.append(packet(3,3*inp.NS))
            finally:audit.close()
            with gzip.open(Path(td)/'generated.anomalies.jsonl.gz','rt') as f:lines=[json.loads(x) for x in f]
            self.assertEqual(lines[0]['frame'],2)
            self.assertEqual(lines[0]['namespace'],lines[0]['legacy_namespace'])
            self.assertEqual(lines[-1]['fixed_uid'],t['uid'])

    def test_fixed_target_header_history_stops_before_snapshot(self):
        with tempfile.TemporaryDirectory() as td:
            p=packet(1,inp.NS);p['tcp.window_size_value']=''
            t=target(packet(2,2*inp.NS));audit=a.CaptureAudit(dict(capture_id='generated',sha256='fixture',expected_packets=2),{'aa'},prep.old.legacy_runtime(),{2:('FIT',0,t)},td)
            try:
                audit.append(p)
                with self.assertRaisesRegex(RuntimeError,'MISSING_HEADER_HISTORY'):audit.append(packet(2,2*inp.NS))
            finally:audit.close()

    def test_same_aggregate_different_frames_cannot_reconcile(self):
        x=dict(legacy_anomalies={'NEW_TIMESTAMP_REGRESSION':1},anomaly_identity_sha256='frame1')
        y=dict(x,anomaly_identity_sha256='frame2')
        with self.assertRaisesRegex(RuntimeError,'FRAME_NAMESPACE'):a.reconcile(x,y)

    def test_four_preflight_captures_order_no_e3(self):
        priority=['active-00','active-01','unsw-benign-20180528','unsw-mixed-20180601'];seen=[]
        @contextlib.contextmanager
        def decoded(path,spec,*args):
            seen.append(spec['capture_id']);yield iter([packet(1,inp.NS)])
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'frozen').mkdir();raw=root/'fixture.raw';raw.write_bytes(b'synthetic')
            specs=[dict(capture_id=n,path=str(raw),sha256='fixture',expected_packets=1,external=n.startswith('unsw')) for n in reversed(priority)]
            receipts={n:dict(sha256='fixture',packets=1,anomalies={k:0 for k in a.ANOMALIES}) for n in priority}
            c.write(root/'frozen/anomaly_receipts.json',receipts)
            metadata={'LEARN':[target(packet(1,inp.NS),n) for n in priority]}
            design={'execution_delivery_requirements':{'anomaly_preflight':{'captures':priority}}}
            with patch.object(a,'decode',decoded):
                result=a.preflight(root,root/'preflight',metadata,specs,dict(source_known_macs=['aa'],external_known_macs=['aa'],tshark='NEVER'),design,DummyProgress())
            self.assertEqual(seen,priority);self.assertEqual(len(result),4)
            c.verify(root/'preflight')

    def test_hand_computed_tcp_and_udp_header_oracles(self):
        p=packet(1,0,flags=18,seq=0xfffffff0);p.update({'tcp.ack_raw':'100','tcp.window_size_value':'256'})
        self.assertEqual(inp.headers(p,6,'1.1.1.1',0xffffffe0,80),[20,0,60,0,64,18,256,0,16,0,20,0])
        p=packet(1,0,incoming=True,flags=16,seq=96);p['tcp.ack_raw']='4294967290'
        self.assertEqual(inp.headers(p,6,'1.1.1.1',0xffffffe0,80),[20,0,60,0,64,16,1024,0,16,0,26,0])
        self.assertEqual(inp.headers(packet(1,0,proto=17),17,'1.1.1.1',0,0),[20,0,60,0,64,20])


class MetricAmendment(unittest.TestCase):
    def reports(self):
        # A small low-rate group carries half the weight: losing 20/100 while
        # detecting 9900/9900 is 99.8% by rows but only 90% by fixed weights.
        rows=[dict(device='d',protocol=6,attack_rate='low' if i<100 else 'high',activity='x',component_id=str(i),label=1,label_metric_weight_denominator=200 if i<100 else 19800) for i in range(10000)]
        rows.append(dict(device='d',protocol=6,activity='x',component_id='normal',label=0,label_metric_weight_denominator=1))
        for r in rows:r['session_id']=r['component_id']
        pred=np.ones(10001,dtype=bool);pred[:20]=False;pred[-1]=False
        r=ev.report(rows,pred,pred)
        reports={name+'_'+suffix:copy.deepcopy(r) for name in ['RECENT_STATE','RECENT_STATE_LEARNED','RECENT_STATE_RAW'] for suffix in ['ensemble','27','127','227']}
        return reports

    def test_weighted_gate_not_high_rate_packet_majority(self):
        reports=self.reports();design=fixture()[0]
        self.assertAlmostEqual(reports['RECENT_STATE_LEARNED_ensemble']['overall']['attack']['rate'],.998)
        result=ev.gate(design,reports,'UNSW_DEV')
        self.assertIn('ATTACK_BELOW_99',result['reasons'])
        self.assertIn('SEED_ATTACK_BELOW_97_27',result['reasons'])
        groups=reports['RECENT_STATE_ensemble']['groups']['device/attack_rate']
        low=next(g for g in groups if g['group']['attack_rate']=='low')
        self.assertEqual((low['metrics']['attack']['positive'],low['metrics']['attack']['rows']),(80,100))
        self.assertTrue(any(g['group']['attack_rate']=='NOT_AVAILABLE' for g in groups))

    def test_gate_constants_are_contract_driven_historical_stays_unweighted(self):
        reports=self.reports();design=fixture()[0]
        design['evaluation']['attack_recall_ensemble_each_pool_min']=.89
        design['evaluation']['attack_recall_ensemble_each_device_min']=.89
        design['evaluation']['attack_recall_each_seed_each_pool_min']=.89
        self.assertTrue(ev.gate(design,reports,'UNSW_DEV')['core_capability_pass'])
        # Weighted .9 passes this generated gate; row .998 is still too far from .99986.
        self.assertIn('SOURCE_REGRESSION_GT_0_1PP',ev.gate(design,reports,'CIC_DEV')['reasons'])

    def test_zero_vector_stage_deltas_are_not_cumulative_unique_counts(self):
        metrics={s:model.Metric(s) for s in c.SEEDS}
        for m in metrics.values():m(torch.zeros(3,794))
        before=ev.zero_snapshot(metrics)
        for m in metrics.values():m(torch.zeros(2,794))
        got=ev.zero_delta(metrics,before)
        self.assertEqual(got['stage_delta']['27']['e3'],2)
        self.assertEqual(got['cumulative_call_rows']['27']['e3'],5)

    def test_bank_full_end_and_query_time_checked_without_features(self):
        _,refs,fit,_,dev,_=fixture()
        md={'SOURCE_REFS':refs,'LEARN':fit['rows'],'CIC_DEV':dev['rows'],'UNSW_DEV':[],'UNSW_REFS':[]}
        data.validate_banks(md)
        bad=copy.deepcopy(md);bad['SOURCE_REFS'][0]['reference_end']=3.
        with self.assertRaisesRegex(RuntimeError,'BANK_FULL_END'):data.validate_banks(bad)
        bad=copy.deepcopy(md)
        for r in bad['SOURCE_REFS']:r['reference_end']=3.
        with self.assertRaisesRegex(RuntimeError,'EARLY_BANK_QUERY_TIME'):data.validate_banks(bad)


if __name__=='__main__': unittest.main()
