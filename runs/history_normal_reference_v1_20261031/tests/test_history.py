"""Generated packet fields, indexes and PCAPNG blocks only; no real input."""
import copy
import hashlib
from pathlib import Path
import sqlite3
import struct
import tempfile
import unittest
from types import SimpleNamespace

import numpy as np

from hnr.common import SALT, digest
from hnr.history import role_binding, chronological_copy, walk_decoded, create_census
from continuous_input_engineering_v1 import Contexts
import legacy_reference_sample_prepare_v1 as prep


DTYPE = [('timestamp_us','<i8'),('block_offset','<u8'),('original_packet_ordinal','<u4'),
         ('captured_bytes','<u4'),('wire_bytes','<u4'),('interface_id','<u4')]


class Progress:
    def __init__(self): self.events=[]
    def update(self, stage, **values): self.events.append((stage, values))


def packet(frame, us, flags=2, port=1234):
    return {'frame.number':str(frame),'frame.time_epoch':f'{us//1000000}.{us%1000000:06d}',
        'frame.len':'74','frame.cap_len':'74','frame.protocols':'eth:ip:tcp',
        'eth.src':'aa','eth.dst':'bb','ip.src':'1.1.1.1','ip.dst':'2.2.2.2',
        'ip.version':'4','ip.proto':'6','ip.hdr_len':'20','ip.dsfield':'0','ip.len':'60',
        'ip.flags':'0','ip.ttl':'64','ip.frag_offset':'0','tcp.flags':str(flags),
        'tcp.flags.syn':str(int(bool(flags&2))),'tcp.flags.ack':str(int(bool(flags&16))),
        'tcp.window_size_value':'1024','tcp.seq_raw':'100','tcp.ack_raw':'0','tcp.urgent_pointer':'0',
        'tcp.srcport':str(port),'tcp.dstport':'80','tcp.hdr_len':'20','tcp.len':'20',
        'udp.srcport':'1234','udp.dstport':'80','udp.length':'20'}


def index_for(times):
    return np.asarray([(t,0,i+1,74,74,0) for i,t in enumerate(times)], dtype=DTYPE)


def block(kind, body):
    size=12+len(body)
    return struct.pack('<II',kind,size)+body+struct.pack('<I',size)


class HistoryTests(unittest.TestCase):
    def test_raw_date_roles_include_unsupported_days_and_stable_ties(self):
        times=[4*86400000000,0,0,1*86400000000,2*86400000000,3*86400000000]
        index=index_for(times); order=np.argsort(index['timestamp_us'],kind='stable')
        binding=role_binding(index,order,{},frozen=False)
        self.assertEqual(binding['bank_end_frame'],5)
        self.assertEqual(len(binding['ref_dates']),4)
        self.assertEqual(binding['first_dev_time_us'],times[0])
        bad=order.copy();bad[0],bad[1]=bad[1],bad[0]
        with self.assertRaisesRegex(ValueError,'UNSTABLE_EQUAL_TIMESTAMP'):
            role_binding(index,bad,{},frozen=False)
        bad=order.copy();bad[-1]=bad[0]
        with self.assertRaisesRegex(ValueError,'ORDER_NOT_PERMUTATION'):
            role_binding(index,bad,{},frozen=False)

    def test_chronological_copy_preserves_identical_packets_as_separate_origins(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            shb=block(0x0a0d0d0a,struct.pack('<IHHq',0x1a2b3c4d,1,0,-1))
            idb=block(1,struct.pack('<HHI',1,0,65535))
            data=b'ABCD'; values=[]; offsets=[]; position=len(shb+idb)
            for t in (30,10,10):
                value=block(6,struct.pack('<IIIII',0,0,t,4,4)+data)
                values.append(value); offsets.append(position); position+=len(value)
            raw=folder/'raw.pcapng';raw.write_bytes(shb+idb+b''.join(values))
            idx=np.asarray([(t,o,i+1,4,4,0) for i,(t,o) in enumerate(zip((30,10,10),offsets))],dtype=DTYPE)
            out=folder/'logical.pcapng'; order=np.asarray([1,2,0],dtype=np.uint32)
            actual=chronological_copy(raw,idx,order,out,Progress())
            expected=shb+idb+values[1]+values[2]+values[0]
            self.assertEqual(out.read_bytes(),expected)
            self.assertEqual(actual,hashlib.sha256(expected).hexdigest())
            self.assertEqual(raw.read_bytes(),shb+idb+b''.join(values))
            with self.assertRaisesRegex(ValueError,'NO_OVERWRITE'):
                chronological_copy(raw,idx,order,out,Progress())

    def _walk(self, folder, packets, *, selected=None, census=None, binding=None):
        spec=dict(capture_id='history-test',partition='EXTERNAL_ARCHIVAL_EVALUATION',
                  device='test',display_name='test',owner='aa',raw=dict(sha256='b'*64),
                  normality_evidence='generated')
        index=index_for([int(float(p['frame.time_epoch'])*1000000) for p in packets])
        order=np.arange(len(index),dtype=np.uint32)
        binding=binding or dict(bank_end_frame=2,reference_end_us=int(index[1]['timestamp_us']),packets=len(index))
        contexts=Contexts('history-test',{'aa'},prep.old.legacy_runtime()[0],
                          storage_path=folder/('ctx-replay.sqlite' if selected is not None else 'ctx.sqlite'),resident_contexts=2)
        snapshots=[]
        try:
            observed=walk_decoded(packets,spec,binding,index,order,'a'*64,contexts,Progress(),
                                  census=census,selected=selected,snapshots=snapshots)
        finally:contexts.close()
        return observed,snapshots

    def test_complete_census_replay_and_context_carry_across_role_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);packets=[packet(1,0),packet(2,1000000),packet(3,5000000)]
            db=create_census(folder/'candidates.sqlite')
            observed,_=self._walk(folder,packets,census=db)
            import json
            selected={uid:json.loads(body) for uid,body in db.execute('SELECT uid,body FROM candidates')}
            db.close()
            self.assertEqual(observed['legal_endpoints'],dict(HIST_REF=2,HIST_DEV=1))
            # Separate bounded state store, same unfiltered traversal, no reset
            # when the last REF and first DEV are only4 seconds apart.
            replay,snapshots=self._walk(folder,packets,selected=selected)
            self.assertEqual(replay['selected_snapshots'],3)
            last=snapshots[-1]
            self.assertEqual(last['row']['use'],'QUERY')
            self.assertEqual(last['body']['provenance']['episode_first_frame'],1)
            self.assertEqual([f for b in last['body']['provenance']['bursts'] for f in b['frames']],[1,2,3])
            self.assertEqual(last['row']['origin_packet_ordinal'],3)
            self.assertEqual(last['row']['component_id'],snapshots[0]['row']['component_id'])
            self.assertNotEqual(last['row']['uid'],snapshots[0]['row']['uid'])

    def test_missing_header_taint_must_observe_unselected_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            bad=packet(2,1000000);bad['tcp.window_size_value']=''
            packets=[packet(1,0),bad,packet(3,2000000),packet(4,63000001)]
            db=create_census(folder/'candidates.sqlite')
            observed,_=self._walk(folder,packets,census=db)
            frames=[r[0] for r in db.execute('SELECT frame FROM candidates ORDER BY frame')]
            db.close()
            self.assertEqual(frames,[1,4])
            self.assertEqual(observed['frontend_reasons']['MISSING_REQUIRED_HEADERS'],1)
            self.assertEqual(observed['frontend_reasons']['MISSING_HEADER_TAINT_RESET'],1)

    def test_incomplete_and_reindexed_decoder_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            packets=[packet(1,0),packet(3,1000000)]
            with self.assertRaisesRegex(ValueError,'CONTIGUOUS_LOGICAL_FRAME'):
                self._walk(folder,packets)


if __name__=='__main__': unittest.main()
