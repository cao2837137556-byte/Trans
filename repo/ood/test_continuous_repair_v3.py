"""Generated packets and arrays only; no real cache, PCAP or checkpoint access."""
import copy
import math
import os
from pathlib import Path
import tempfile
import unittest
import numpy as np
import torch
import continuous_common_v3 as c
import continuous_input_v3 as inp
import continuous_model_v3 as model


def packet(frame, ns, incoming=False, flags=2, size=60, proto=6, seq=100):
    src,dst=('2.2.2.2','1.1.1.1') if incoming else ('1.1.1.1','2.2.2.2')
    return {'frame.number':str(frame),'frame.time_epoch':'%d.%09d'%(ns//10**9,ns%10**9),
        'frame.len':str(size+14),'frame.cap_len':str(size+14),'frame.protocols':'eth:ip:tcp',
        'eth.src':'bb' if incoming else 'aa','eth.dst':'aa' if incoming else 'bb',
        'ip.src':src,'ip.dst':dst,'ip.version':'4','ip.proto':str(proto),'ip.hdr_len':'20',
        'ip.dsfield':'0','ip.len':str(size),'ip.flags':'0','ip.ttl':'64','ip.frag_offset':'0',
        'tcp.flags':str(flags),'tcp.flags.syn':str(int(bool(flags&2))),'tcp.flags.ack':str(int(bool(flags&16))),
        'tcp.window_size_value':'1024','tcp.seq_raw':str(seq),'tcp.ack_raw':'0','tcp.urgent_pointer':'0',
        'tcp.srcport':'80' if incoming else '1234','tcp.dstport':'1234' if incoming else '80',
        'tcp.hdr_len':'20','tcp.len':str(max(0,size-40)),'udp.srcport':'1234','udp.dstport':'80','udp.length':'20'}


def state(proto=6):return inp.RecentState('aa',('aa','capture',(proto,('1.1.1.1',1234),('2.2.2.2',80))),proto)


class InputContract(unittest.TestCase):
    def test_dense_late_changed_packet_is_present(self):
        s=state()
        for i in range(1,101):s.append(packet(i,i*1_000_000,flags=2 if i<100 else 20))
        flow,values,p=s.snapshot()
        self.assertEqual(p['bursts'][0]['frames'],list(range(95,101)))
        self.assertEqual(p['bursts'][0]['headers'][-1][5],20)
        self.assertEqual(len(values),26)
    def test_sparse_bursts_roll(self):
        s=state()
        for i in range(1,40):s.append(packet(i,i*20_000_000))
        _,_,p=s.snapshot();self.assertEqual([b['frames'][0] for b in p['bursts']],list(range(28,40)))
    def test_two_directions_current_always_retained(self):
        s=state()
        for i in range(1,200):
            s.append(packet(i,i*11_000_000,incoming=bool(i%2)))
            _,_,p=s.snapshot();self.assertIn(i,[f for b in p['bursts'] for f in b['frames']])
            self.assertLessEqual(sum(len(b['frames']) for b in p['bursts']),72)
    def test_exact_10ms_boundary(self):
        s=state();s.append(packet(1,0));s.append(packet(2,10_000_000));self.assertEqual(len(s.snapshot()[0]['counts']),1)
        s.append(packet(3,20_000_001));self.assertEqual(len(s.snapshot()[0]['counts']),2)
    def test_exact_60s_boundary_and_no_syn_reset(self):
        s=state();s.append(packet(1,0));s.append(packet(2,60*10**9));self.assertEqual(s.episode_first_frame,1)
        s.append(packet(3,120*10**9+1));self.assertEqual(s.episode_first_frame,3)
        self.assertEqual(s.snapshot()[1][-2:],[0.,0.])
    def test_out_of_order_fails(self):
        s=state();s.append(packet(1,100))
        with self.assertRaisesRegex(RuntimeError,'ORDER'):s.append(packet(2,99))
    def test_same_time_increasing_frame(self):
        s=state();s.append(packet(1,1));s.append(packet(2,1));self.assertEqual(s.snapshot()[1][-2:],[0.,1.])
    def test_immutable_snapshot(self):
        s=state();row=packet(1,0);s.append(row);before=copy.deepcopy(s.snapshot())
        row['tcp.flags']='999';s.append(packet(2,1,flags=4));self.assertEqual(before[0]['burst_tokens'][0][5],2)
        self.assertEqual(before[2]['query_frame'],1)
    def test_stream_stats_match_explicit_history(self):
        s=state();events=[(0,False,2,60),(500_000_000,True,16,100),(2_000_000_000,False,4,70)]
        for i,(t,d,f,b) in enumerate(events,1):s.append(packet(i,t,d,f,b))
        got=s.snapshot()[1]
        expected=[]
        for d in (False,True):
            for h in (1,10):
                v=np.zeros(6)
                for t,di,f,b in events:
                    if di==d:v+=2**(-(events[-1][0]-t)/1e9/h)*np.array([1,b,bool(f&2) and not bool(f&16),bool(f&16),bool(f&4),bool(f&1)])
                expected.extend([math.log1p(v[0]*math.log(2)/h),math.log1p(v[1]*math.log(2)/h),*(v[2:]/max(v[0],1e-12))])
        np.testing.assert_allclose(got[:24],expected,rtol=1e-13)
    def test_identical_headers_different_rate_enters_state(self):
        a,b=state(),state()
        for i in range(1,10):a.append(packet(i,i*100_000_000));b.append(packet(i,i*1_000_000_000))
        self.assertNotEqual(a.snapshot()[1],b.snapshot()[1])
    def test_udp_flags_zero(self):
        s=state(17);s.append(packet(1,0,proto=17,flags=255));v=s.snapshot()[1]
        self.assertTrue(all(v[i]==0 for start in (0,6,12,18) for i in range(start+2,start+6)))
    def test_window_anchor_and_payload_placeholders(self):
        s=state()
        for i in range(1,8):s.append(packet(i,i*1_000_000,seq=100+i))
        flow,_,p=s.snapshot();self.assertEqual(p['bursts'][0]['frames'][0],2)
        self.assertEqual(p['bursts'][0]['headers'][0][7:9],[0,0])
        self.assertEqual(flow['burst_tokens'][0][12:18],[0]*6)
    def test_future_provenance_fails(self):
        s=state();s.append(packet(1,0));flow,_,p=s.snapshot()
        ex=dict(input_ids=[[65537]+[v+1 for v in p['bursts'][0]['headers'][0]]],attention_mask=[[1]*13],dataset_burst_sizes=[12])
        self.assertEqual(inp.verify_tokenized(flow,p,ex),[0,1,12])
        p['bursts'][0]['times_ns'][0]=1
        with self.assertRaisesRegex(RuntimeError,'FUTURE'):inp.verify_tokenized(flow,p,ex)
    def test_missing_current_token_detected(self):
        s=state();s.append(packet(1,0));flow,_,p=s.snapshot()
        ex=dict(input_ids=[[65537]],attention_mask=[[1]],dataset_burst_sizes=[0])
        with self.assertRaises(RuntimeError):inp.verify_tokenized(flow,p,ex)


class ModelContract(unittest.TestCase):
    def test_matched_initial_functions_and_gradient_to_state(self):
        torch.set_num_threads(1)
        a,b=model.classifier(27,768),model.classifier(27,794)
        z=torch.randn(5,794)
        torch.testing.assert_close(a[0].weight,b[0].weight[:,:768],rtol=0,atol=0)
        self.assertEqual(torch.count_nonzero(b[0].weight[:,768:]).item(),0)
        torch.testing.assert_close(a(z[:,:768]),b(z),rtol=1e-6,atol=1e-6)
        b(z).sum().backward();self.assertGreater(float(b[0].weight.grad[:,768:].abs().sum()),0)
    def test_safe_zero_not_invalid(self):
        v=torch.zeros(3,794);self.assertTrue(torch.equal(model.metric_input(v),v))
        self.assertTrue(torch.equal(model.Metric(27)(v),torch.zeros(3,64)))
    def test_nonfinite_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'NONFINITE'):model.unit(torch.tensor([[float('nan')]]))
    def test_normalizer_excludes_cal(self):
        rr=[dict(partition='LEARN',fit_role='FIT'),dict(partition='LEARN',fit_role='CAL')]
        x=np.array([[2,3],[1e8,1e8]],dtype=np.float32)
        mean,scale=model.fit_normalizer(x,rr,[0]);np.testing.assert_array_equal(mean,[2,3])
        with self.assertRaisesRegex(RuntimeError,'FIT_ONLY'):model.fit_normalizer(x,rr,[0,1])
    def test_threshold_strict_ties(self):
        rr=[dict(partition='LEARN',fit_role='CAL',label=0,device='d',activity='a',capture_id='c',session_id='s') for _ in range(100)]
        x=np.r_[np.zeros(98),[1,1]]
        self.assertEqual(model.threshold(x,rr),1)
        x[-1]=2;self.assertEqual(model.threshold(x,rr),1)
    def test_threshold_rejects_dev(self):
        with self.assertRaisesRegex(RuntimeError,'CAL_NORMAL_ONLY'):model.threshold(np.array([0.]),[dict(partition='DEV')])
    def test_authorization_before_file_read(self):
        with self.assertRaisesRegex(RuntimeError,'NOT_AUTHORIZED'):c.authorize('/path/not/present',False)
    def test_bank_same_protocol_time_and_singleton(self):
        rr=[dict(uid=str(i),partition='LEARN',use='REFERENCE',label=0,timestamp=0,reference_end=1,component_id=str(i),device='d',protocol=6) for i in range(2)]
        z=torch.randn(2,794);b=model.Bank(rr,z,{'LEARN'});cfg={'training':{}}
        rows=[dict(device='d',protocol=p,timestamp=t) for p,t in [(6,2),(17,2),(6,1)]]
        _,valid=b.own(torch.randn(3,794),rows,model.Raw(),cfg);self.assertEqual(valid.tolist(),[True,False,False])
        _,valid=b.own(torch.randn(3,794),rows,model.Raw(),cfg,override={('d',6):['0']});self.assertFalse(valid.any())
    def test_query_reference_gradients(self):
        from legacy_qref_model_v1 import top_score
        a=torch.randn(3,794,requires_grad=True);b=torch.randn(2,794,requires_grad=True);w=model.Metric(27)
        top_score(w(a),w(b)).sum().backward()
        self.assertGreater(float(a.grad.abs().sum()),0);self.assertGreater(float(b.grad.abs().sum()),0)
    def test_seal_detects_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);c.write(p/'a.json',dict(a=1));c.seal(p);c.verify(p);(p/'a.json').write_text('changed')
            with self.assertRaisesRegex(RuntimeError,'IDENTITY'):c.verify(p)


class ActualTokenizer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from legacy_unsw_archival_runtime_v1 import e3_runtime
        root=Path(os.environ.get('CONTINUOUS_TEST_ROOT',Path(__file__).resolve().parents[2]/'runs/legacy_commissioning_unsw_recovery_delivery_v2_20260927/bundle'))
        cls.runtime=e3_runtime(root,synthetic=True)
    def test_full_tcp_udp_current_survives_vendor_tokenizer(self):
        from continuous_features_v3 import tokenize
        for proto in (6,17):
            s=state(proto)
            for i in range(1,100):s.append(packet(i,i*1_000_000,proto=proto))
            f,_,p=s.snapshot();e=tokenize(self.runtime[3],f)
            j,start,length=inp.verify_tokenized(f,p,e)
            self.assertEqual(start,1+5*(12 if proto==6 else 6))
            self.assertLessEqual(start+length,73)
    def test_exact_shape_peer_tensor_identity(self):
        from continuous_features_v3 import tokenize,tensor_hash,verify_batch
        a,b=state(),state()
        for i in range(1,7):a.append(packet(i,i*1_000_000));b.append(packet(i,i*1_000_000,flags=16))
        ea,eb=[tokenize(self.runtime[3],s.snapshot()[0]) for s in (a,b)]
        one=self.runtime[4]([ea]);two=self.runtime[4]([eb,ea])
        verify_batch([ea],one);verify_batch([eb,ea],two)
        self.assertEqual(tensor_hash(one,0),tensor_hash(two,1))
    def test_wrong_shape_batch_changes_layout_prevented_by_contract(self):
        from continuous_features_v3 import tokenize
        a,b=state(),state();a.append(packet(1,0));b.append(packet(1,0));b.append(packet(2,1000))
        x,y=[tokenize(self.runtime[3],s.snapshot()[0]) for s in (a,b)]
        self.assertNotEqual(max(x['dataset_burst_sizes']),max(y['dataset_burst_sizes']))


if __name__=='__main__':unittest.main()
