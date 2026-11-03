"""Exact shape parity against frozen numerical retention; no model loads."""
from collections import Counter
import importlib.util
from pathlib import Path
import random
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('edge_shape_census', HERE/'shape_census.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
OWNER = 'dc:a6:32:fb:69:b5'


def row(frame, ns, outgoing, proto):
    return dict({'frame.number': str(frame),
                 'frame.time_epoch': str(ns//10**9)+'.'+str(ns%10**9).zfill(9),
                 'eth.src': OWNER if outgoing else '00:11:22:33:44:55',
                 'eth.dst': '00:11:22:33:44:55' if outgoing else OWNER,
                 'ip.src': '1.2.3.4' if outgoing else '4.3.2.1',
                 'ip.dst': '4.3.2.1' if outgoing else '1.2.3.4',
                 'ip.hdr_len': '20', 'ip.dsfield': '0', 'ip.len': '60',
                 'ip.flags': '0', 'ip.ttl': '64', 'tcp.flags': '0x18',
                 'tcp.window_size_value': '1000', 'tcp.seq_raw': str(frame*60),
                 'tcp.ack_raw': str(max(1,frame-1)*60), 'tcp.urgent_pointer': '0',
                 'udp.length': '40'})


def frozen_shape(state):
    flow, _, _ = state.snapshot()
    return flow['protocol'], max(flow['counts'])*(12 if flow['protocol'] == 6 else 6)+1, len(flow['counts'])


class ShapeCensusContracts(unittest.TestCase):
    def test_randomized_exact_frozen_shape_and_serialization_parity(self):
        rng = random.Random(81602)
        for proto in (6,17):
            original = s.edge.frozen.RecentState(OWNER, ('test',proto), proto)
            shape = s.ShapeState(OWNER, ('test',proto), proto)
            now = 1_000_000_000_000
            for frame in range(1,900):
                now += rng.choice((0, 1, 1_000_000, 10_000_000, 10_000_001,
                                   30_000_000_000, 60_000_000_000, 60_000_000_001))
                packet = row(frame, now, bool(rng.randrange(2)), proto)
                original.append(packet)
                shape.append(packet)
                self.assertEqual(shape.shape(), frozen_shape(original))
                if frame % 17 == 0:
                    shape = s.decode_shape(s.encode_shape(shape))
                    self.assertEqual(shape.shape(), frozen_shape(original))

    def test_burst_packet_and_bidirectional_retention_boundaries(self):
        for proto in (6,17):
            original = s.edge.frozen.RecentState(OWNER, ('cap',proto), proto)
            shape = s.ShapeState(OWNER, ('cap',proto), proto)
            now, frame = 0, 0
            for burst in range(34):
                now += 11_000_000
                for _ in range(9):
                    frame += 1
                    packet = row(frame,now,burst%2==0,proto)
                    original.append(packet)
                    shape.append(packet)
                    self.assertEqual(shape.shape(), frozen_shape(original))
            self.assertEqual(shape.shape(),(proto,73 if proto==6 else 37,12))

    def test_shape_store_eviction_is_lossless(self):
        with tempfile.TemporaryDirectory(prefix='edge-shape-unit-') as tmp:
            store = s.ShapeSpillMap(Path(tmp)/'state.sqlite',1,
                                   encode=s.encode_shape,decode=s.decode_shape)
            try:
                self.assertEqual(store.db.execute('PRAGMA cache_size').fetchone()[0],-131072)
                self.assertEqual(store.db.execute('PRAGMA journal_mode').fetchone()[0],'memory')
                self.assertEqual(store.db.execute('PRAGMA synchronous').fetchone()[0],0)
                a = s.ShapeState(OWNER, ('a',),6)
                a.append(row(1,0,True,6))
                store[('a',)] = a
                b = s.ShapeState(OWNER, ('b',),17)
                b.append(row(2,1,False,17))
                store[('b',)] = b
                restored = store[('a',)]
                self.assertEqual(restored.shape(),a.shape())
                restored.append(row(3,2,True,6))
                store[('b',)]
                self.assertEqual(store[('a',)].shape(),(6,25,1))
                self.assertEqual(len(store),2)
            finally:
                store.close()

    def test_census_extremes_include_rare_width_and_burst_shapes(self):
        counts = Counter({'17,7,1':10000,'6,13,1':500,'6,73,2':1,'6,25,12':2})
        reps = {key:dict(role='HTTP',frame=i+1,shape=list(map(int,key.split(','))))
                for i,key in enumerate(counts)}
        required = s.choose_required(counts,reps)
        self.assertEqual(required['maximum_width'],73)
        self.assertEqual(required['maximum_bursts'],12)
        self.assertIn('6,73,2',required['top10_shapes'])
        self.assertIn('6,25,12',required['top10_shapes'])

    def test_no_numeric_snapshot_and_bad_order_rejected(self):
        state = s.ShapeState(OWNER,None,6)
        state.append(row(1,10,True,6))
        with self.assertRaisesRegex(RuntimeError,'CANNOT_EMIT_NUMERICAL'):
            state.snapshot()
        with self.assertRaisesRegex(RuntimeError,'SHAPE_STATE_ORDER'):
            state.append(row(2,9,True,6))


if __name__=='__main__':
    unittest.main()
