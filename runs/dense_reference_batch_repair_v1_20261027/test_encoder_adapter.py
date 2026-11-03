"""Synthetic tensor/forward tests only: no torch import, checkpoint or model."""
import copy
import gzip
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location('batch_encoder_tested',HERE/'encoder_adapter.py')
adapter=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(adapter)


class Tensor:
    def __init__(self,value):self.value=np.asarray(value)
    @property
    def shape(self):return self.value.shape
    def __len__(self):return len(self.value)
    def __getitem__(self,index):return self.value[index]
    def repeat(self,shape):return Tensor(np.tile(self.value,shape))


def tensor_hash(batch,index):
    import hashlib
    value=hashlib.sha256()
    for key in sorted(batch):
        row=batch[key].value[index]
        value.update(key.encode()+str(row.dtype).encode()+str(row.shape).encode()+row.tobytes())
    return value.hexdigest()


def make_batch(size,shape=(6,3,1)):
    return dict(input_ids=Tensor(np.arange(size*shape[1]*shape[2],dtype=np.int64).reshape(size,-1)),
        protocol=Tensor(np.full(size,shape[0],dtype=np.int64)),
        attention_mask=Tensor(np.ones((size,shape[1]*shape[2]),dtype=np.int64)),
        flow_duration=Tensor(np.zeros(size,dtype=np.float32)))


def standin_forward(model,batches,device):
    batch=batches[0]
    return np.repeat(batch['input_ids'].value[:,0,None],768,axis=1).astype(np.float32)


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.output=self.root/'encode';self.output.mkdir()
        self.db=sqlite3.connect(':memory:');self.addCleanup(self.db.close)
        self.db.execute('CREATE TABLE tokens(name TEXT,uid TEXT,proto INTEGER,width INTEGER,bursts INTEGER)')

    def make_adapter(self,counts,forward=standin_forward,name='ORIGINAL104'):
        records=[]
        for shape,count in counts:
            for i in range(count):
                uid='%d-%d-%d-%05d'%(*shape,i);records.append((uid,shape))
                self.db.execute('INSERT INTO tokens VALUES(?,?,?,?,?)',(name,uid,*shape))
        queue=adapter.make_queue(records);summary=adapter.summarize(name,queue)
        budget=dict(datasets=[summary],totals={k:summary[k] for k in
                    ('logical_rows','physical_positions','clone_positions','singleton_batches','batches')})
        instance=adapter.BatchAdapter(budget,self.output,tensor_hash,forward)
        instance.select(self.db,name,{u for u,_ in records})
        return instance,queue

    def receipt(self,instance,queue):
        with gzip.open(self.output/(instance.active+'.tensor_receipts.jsonl.gz'),'wt',encoding='utf-8') as stream:
            for batch in queue:
                for uid in batch['uids']:stream.write(json.dumps(dict(uid=uid))+'\n')

    def test_singleton_only_runs16_and_returns_exactly_one_unchanged_logical_row(self):
        seen=[]
        def forward(model,batches,device):
            seen.append(batches[0]);return standin_forward(model,batches,device)
        instance,queue=self.make_adapter([((6,3,1),1)],forward)
        batch=make_batch(1);before={k:v.value.copy() for k,v in batch.items()}
        result=instance.forward(None,[batch])
        self.assertEqual(result.shape,(1,768));self.assertEqual(len(seen[0]['input_ids']),16)
        self.assertEqual(instance.counts['logical_rows'],1);self.assertEqual(instance.counts['physical_positions'],16)
        self.assertEqual(instance.counts['clone_positions'],15)
        for key in batch:self.assertTrue(np.array_equal(before[key],batch[key].value))
        self.receipt(instance,queue);instance.finish_dataset()

    def test_every_nonsingleton_size2through16_preserves_batch_object_and_output_bytes(self):
        for size in range(2,17):
            with self.subTest(size=size):
                instance,queue=self.make_adapter([((6,3,size),size)],name='n'+str(size))
                batch=make_batch(size,(6,3,size));values=standin_forward(None,[batch],'cpu');seen=[]
                instance.original_forward=lambda m,bs,d:(seen.append(bs[0]) or values)
                result=instance.forward(None,[batch])
                self.assertIs(seen[0],batch);self.assertIs(result,values)
                self.assertEqual(instance.counts['physical_positions'],size);self.assertEqual(instance.counts['clone_positions'],0)
                self.assertEqual(result.tobytes(),values.tobytes());self.receipt(instance,queue);instance.finish_dataset()
                instance.ledger.unlink()

    def test_seventeen_rows_remain16plus1_logical_in_uid_order(self):
        instance,queue=self.make_adapter([((6,3,1),17)])
        self.assertEqual([len(b['uids']) for b in queue],[16,1])
        instance.forward(None,[make_batch(16)]);instance.forward(None,[make_batch(1)])
        self.receipt(instance,queue);instance.finish_dataset()
        actual=instance.completed[0]['actual']
        self.assertEqual(actual['logical_rows'],17);self.assertEqual(actual['physical_positions'],32)

    def test_clone_output_difference_even_signed_zero_stops_without_accepting_batch(self):
        def inconsistent(model,batches,device):
            value=np.zeros((16,768),dtype=np.float32);value[15,0]=-0.;return value
        instance,_=self.make_adapter([((6,3,1),1)],inconsistent)
        with self.assertRaisesRegex(RuntimeError,'CLONE_OUTPUT_EXACT_BYTE_IDENTITY'):
            instance.forward(None,[make_batch(1)])
        self.assertTrue(instance.failed);self.assertEqual(instance.index,0)
        self.assertEqual(instance.counts['physical_positions'],16)

    def test_changed_clone_input_stops_before_forward(self):
        instance,_=self.make_adapter([((6,3,1),1)])
        instance.tensor_hash=lambda batch,j:'original' if len(batch['input_ids'])==1 or j<15 else 'changed'
        with patch.object(instance,'original_forward') as forward:
            with self.assertRaisesRegex(RuntimeError,'CLONED_INPUT_TENSOR_IDENTITY'):
                instance.forward(None,[make_batch(1)])
            forward.assert_not_called()

    def test_nan_wrong_dtype_and_wrong_rows_rejected(self):
        for values in (np.full((16,768),np.nan,dtype=np.float32),np.zeros((16,768),dtype=np.float64),
                       np.zeros((1,768),dtype=np.float32)):
            with self.subTest(dtype=str(values.dtype),shape=values.shape):
                instance,_=self.make_adapter([((6,3,1),1)],name=str(values.dtype)+str(values.shape))
                instance.original_forward=lambda m,b,d:values
                with self.assertRaisesRegex(RuntimeError,'PHYSICAL_E3_FINITE_FLOAT32_SCHEMA'):
                    instance.forward(None,[make_batch(1)])
                instance.ledger.unlink()

    def test_forward_exception_counts_attempt_once_and_disallows_reentry(self):
        instance,_=self.make_adapter([((6,3,1),1)])
        with patch.object(instance,'original_forward',side_effect=RuntimeError('standin')) as forward:
            with self.assertRaisesRegex(RuntimeError,'standin'):instance.forward(None,[make_batch(1)])
            with self.assertRaisesRegex(RuntimeError,'ACTIVE_CPU_BATCH_REQUIRED'):instance.forward(None,[make_batch(1)])
            self.assertEqual(forward.call_count,1)
        self.assertEqual(instance.counts['physical_positions'],16)

    def test_wrong_runtime_queue_or_shape_never_enters_model(self):
        instance,queue=self.make_adapter([((6,3,1),1)])
        with patch.object(instance,'original_forward') as forward:
            with self.assertRaisesRegex(RuntimeError,'LOGICAL_BATCH_SHAPE_IDENTITY'):
                instance.forward(None,[make_batch(1,(17,3,1))])
            forward.assert_not_called()
        self.db.execute('UPDATE tokens SET width=4')
        instance.active=None
        with self.assertRaisesRegex(RuntimeError,'RUNTIME_PHYSICAL_BUDGET_OR_UID_QUEUE'):
            instance.select(self.db,'ORIGINAL104',{uid for b in queue for uid in b['uids']})

    def test_duplicate_uid_order_and_incomplete_queue_fail_finalgate(self):
        instance,queue=self.make_adapter([((6,3,1),2)])
        with self.assertRaisesRegex(RuntimeError,'INCOMPLETE_DATASET_BATCH_QUEUE'):instance.finish_dataset()
        instance.forward(None,[make_batch(2)]);queue[0]['uids'].reverse()
        self.receipt(instance,queue)
        with self.assertRaisesRegex(RuntimeError,'ENCODED_UID_ORDER_AND_UNIQUENESS'):instance.finish_dataset()

    def test_final_receipt_keeps_original_result_identity_and_strict104(self):
        instance,queue=self.make_adapter([((6,3,1),1)])
        instance.forward(None,[make_batch(1)]);self.receipt(instance,queue)
        adapter.write(self.output/'RESULT.json',dict(status='COMPLETE',mode='encode',package_sha256='frozen-vendor-identity',
                      datasets=[dict(name='ORIGINAL104',measured_rows=1)]))
        adapter.write(self.output/'ORIGINAL104_PARITY.json',dict(original104_exact_bytes=True,mismatch_count=0,max_abs_error=0.))
        receipt=instance.finish();result=adapter.read(self.output/'RESULT.json')
        self.assertTrue(result['batch_repair_verified']);self.assertEqual(result['package_sha256'],'frozen-vendor-identity')
        self.assertEqual(receipt['clone_rows_in_bank'],0)
        self.assertEqual(result['batch_repair_receipt_sha256'],adapter.sha(self.output/'BATCH_REPAIR_RECEIPT.json'))

    def test_original104_tiny_error_cannot_be_tolerated(self):
        instance,queue=self.make_adapter([((6,3,1),1)])
        instance.forward(None,[make_batch(1)]);self.receipt(instance,queue)
        adapter.write(self.output/'RESULT.json',dict(status='COMPLETE',mode='encode',datasets=[]))
        adapter.write(self.output/'ORIGINAL104_PARITY.json',dict(original104_exact_bytes=False,mismatch_count=1,max_abs_error=1e-9))
        with self.assertRaisesRegex(RuntimeError,'FROZEN_ORIGINAL104_STRICT_GATE_REQUIRED'):instance.finish()
        self.assertFalse((self.output/'BATCH_REPAIR_RECEIPT.json').exists())

    def test_budget_counts_exact_physical_overhead_across_shape_boundaries(self):
        queue=adapter.make_queue([(str(shape)+'_'+str(i),shape) for shape,n in [((6,3,1),17),((17,7,2),32),((17,7,3),1)] for i in range(n)])
        result=adapter.summarize('X',queue)
        self.assertEqual(result['logical_rows'],50);self.assertEqual(result['physical_positions'],80)
        self.assertEqual(result['clone_positions'],30);self.assertEqual(result['singleton_batches'],2)
        self.assertEqual(result['batches'],5)

    def test_shape_matches_frozen_payload_strip_plus_cls_without_tokenizer(self):
        config=dict(strip_payload=True,max_bursts=12,max_burst_length=73)
        self.assertEqual(adapter.flow_shape(dict(protocol=6,burst_tokens=[[0]*18]),config),(6,13,1))
        self.assertEqual(adapter.flow_shape(dict(protocol=17,burst_tokens=[[0]*24,[0]*12]),config),(17,13,2))
        self.assertEqual(adapter.flow_shape(dict(protocol=1,burst_tokens=[[0]*13]),config),(1,8,1))
        with self.assertRaisesRegex(RuntimeError,'FROZEN_TOKENIZER_TRUNCATION_NOT_EXPECTED'):
            adapter.flow_shape(dict(protocol=6,burst_tokens=[[0]*18]*13),config)

    def test_cli_forbids_benchmark_and_missing_budget_before_any_import(self):
        with patch.object(adapter,'verify_frozen') as verify:
            with self.assertRaises(SystemExit):adapter.main(['--mode','benchmark'])
            verify.assert_not_called()


if __name__=='__main__':unittest.main()
