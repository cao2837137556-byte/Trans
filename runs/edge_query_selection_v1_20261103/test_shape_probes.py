"""Synthetic strict-probe regressions; no Torch, encoder, heads or raw assets."""
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

import numpy as np
from strict_shape_probes import StrictShapeProbes, replaced_attribute


def batch(n=2, width=4, bursts=3):
    return dict(input_ids=np.tile(np.arange(width*bursts), (n,1)),
                dataset_burst_sizes=np.tile(np.array([width-1]*bursts), (n,1)))


def tensor_hash(value, index):
    h = hashlib.sha256()
    for name in sorted(value):
        a = value[name][index]
        h.update(name.encode()+str(a.dtype).encode()+str(a.shape).encode()+a.tobytes())
    return h.hexdigest()


def physical_batch(value, logical, hashes):
    if logical != 1:
        return value, logical
    return {k:np.repeat(v,16,axis=0) for k,v in value.items()},16


class ShapeProbeTests(unittest.TestCase):
    def test_row15_difference_stops_before_ordinary_forward(self):
        calls=[]
        def forward(model, batches, device):
            calls.append(batches[0]['input_ids'].shape[0])
            output=np.zeros((16,768),dtype=np.float32)
            output[15,0]=np.nextafter(np.float32(0),np.float32(1))
            return output
        with tempfile.TemporaryDirectory() as folder:
            gate=StrictShapeProbes({(6,4,3)},[((6,4,3),2)],2,folder,
                                  forward,physical_batch,tensor_hash,lambda:None)
            with self.assertRaisesRegex(ValueError,'OUTPUT_BYTES_DIFFER'):
                gate.forward(None,[batch()])
            self.assertEqual(calls,[16])
            self.assertEqual(gate.cursor,0)
            self.assertEqual(gate.extra_logical,1)
            self.assertEqual(gate.extra_physical,16)
            records=[json.loads(x) for x in (Path(folder)/'STRICT_SHAPE_PROBE_LEDGER.jsonl').read_text().splitlines()]
            self.assertEqual([r['status'] for r in records],['ATTEMPT','FAIL'])
            self.assertEqual(len(records[-1]['input_tensor_sha256']),16)
            diagnosis=json.loads((Path(folder)/'STRICT_SHAPE_PROBE_FAILURE.json').read_text())
            self.assertEqual(diagnosis['status'],'FAIL')
            self.assertEqual(len(diagnosis['output_sha256']),16)

    def test_probe_once_per_required_shape_original_batch_unchanged(self):
        calls=[]
        outputs=[]
        def forward(model,batches,device):
            calls.append(batches[0])
            n=batches[0]['input_ids'].shape[0]
            result=np.zeros((n,768),dtype=np.float32)
            outputs.append(result)
            return result
        with tempfile.TemporaryDirectory() as folder:
            gate=StrictShapeProbes({(6,4,3)},[((6,4,3),2),((6,4,3),2),((17,2,1),1)],5,folder,
                                  forward,physical_batch,tensor_hash,lambda:None)
            first=batch()
            self.assertIs(gate.forward(None,[first]),outputs[-1])
            self.assertIs(calls[-1],first)
            gate.forward(None,[batch()])
            final,_=physical_batch(batch(1,2,1),1,tensor_hash)
            gate.forward(None,[final])
            gate.require_complete()
            self.assertEqual([x['input_ids'].shape[0] for x in calls],[16,2,2,16])
            self.assertEqual(gate.extra_logical,1)
            self.assertEqual(gate.summary()['status'],'PASS')

    def test_total_budget_rejected_before_any_extra_work(self):
        calls=[]
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError,'EXCEEDS_CAP'):
                StrictShapeProbes({(6,4,3)},[((6,4,3),100)],100,folder,
                    lambda *a:calls.append(1),physical_batch,tensor_hash,lambda:None)
            self.assertEqual(calls,[])
            self.assertFalse((Path(folder)/'STRICT_SHAPE_PROBE_LEDGER.jsonl').exists())

    def test_guard_failure_prevents_clone_or_forward(self):
        calls=[]
        def guard():
            raise RuntimeError('TIME_LIMIT')
        with tempfile.TemporaryDirectory() as folder:
            gate=StrictShapeProbes({(6,4,3)},[((6,4,3),2)],2,folder,
                lambda *a:calls.append(1),physical_batch,tensor_hash,guard)
            with self.assertRaisesRegex(RuntimeError,'TIME_LIMIT'):
                gate.forward(None,[batch()])
            self.assertEqual(gate.extra_logical,0)
            self.assertEqual(calls,[])

    def test_missing_shape_and_geometry_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError,'NOT_IN_SLICE'):
                StrictShapeProbes({(17,4,3)},[((6,4,3),2)],2,folder,
                    lambda *a:None,physical_batch,tensor_hash,lambda:None)
            gate=StrictShapeProbes({(6,4,3)},[((6,4,3),2)],2,folder,
                    lambda *a:None,physical_batch,tensor_hash,lambda:None)
            with self.assertRaisesRegex(ValueError,'GEOMETRY'):
                gate.forward(None,[batch(2,5,3)])
            self.assertEqual(gate.extra_logical,0)

    def test_attribute_patch_restores_even_after_failure(self):
        original=object(); other=object()
        target=SimpleNamespace(value=original)
        with self.assertRaisesRegex(RuntimeError,'stop'):
            with replaced_attribute(target,'value',other):
                self.assertIs(target.value,other)
                raise RuntimeError('stop')
        self.assertIs(target.value,original)


if __name__=='__main__':
    unittest.main()
