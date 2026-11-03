"""Real frozen encoder orchestration in an inert child; no model/checkpoint load."""
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import encoder_adapter as adapter
from test_encoder_adapter import Tensor,tensor_hash,standin_forward
from inert_test_support import frozen_test_root


def jsonl(path,values):
    path.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(path,'wt',encoding='utf-8') as stream:
        for value in values:stream.write(json.dumps(value)+'\n')


def child(root,bad_clone=False,bad_final=False):
    """Actual frozen encoder.main runs untouched except fake runtime/spooling."""
    root=Path(root);package=root/'frozen/vendor/encoding_v2';output=root/'output'
    package.mkdir(parents=True);(package/'repo/ood').mkdir(parents=True)
    source=frozen_test_root()/'vendor/encoding_v2/repo/ood/onboarding_supplement_encoder_r2.py'
    shutil.copyfile(source,package/'repo/ood/onboarding_supplement_encoder_r2.py')
    (package/'runtime/vendor/netFound-base').mkdir(parents=True)
    checkpoint=root/'inert-checkpoint';checkpoint.write_bytes(b'inert bytes: never model loaded')
    checkpoint_sha=hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    specs=[];datasets={};records={};banks=[];old_bytes={}
    for name in adapter.NAMES:
        size=104 if name=='ORIGINAL104' else 17
        metadata=[];qby={};examples={};planned=[]
        for i in range(size):
            uid=(name+'-'+str(i).zfill(4)).ljust(64,'x')
            shape=(17,2,1) if name=='ORIGINAL104' and i==103 else (6,3,1)
            value=i+1
            row=dict(uid=uid,protocol=shape[0],use='REFERENCE')
            metadata.append(row);qby[uid]=np.full(14,value,dtype=np.float32)
            examples[uid]=dict(protocol=shape[0],value=value,width=shape[1],bursts=shape[2])
            planned.append((uid,shape))
        rel='data/'+name;jsonl(package/(rel+'/rows.jsonl.gz'),metadata)
        qpath=rel+'/q14.npz';np.savez_compressed(package/qpath,uid=np.asarray([r['uid'] for r in metadata]),q14=np.asarray(list(qby.values()),dtype=np.float32))
        spec=dict(name=name,metadata=rel+'/rows.jsonl.gz',snapshots=rel+'/snapshots.jsonl.gz',q14=qpath)
        if name=='ORIGINAL104':
            spec.update(original104_check=True,expected_bank=rel+'/old.npz')
            old=np.asarray([np.full(768,i+1,dtype=np.float32) for i in range(size)])
            np.savez_compressed(package/spec['expected_bank'],uid=np.asarray([r['uid'] for r in metadata]),e3=old,q14=np.asarray(list(qby.values()),dtype=np.float32))
            old_bytes['ORIGINAL104']=old.tobytes()
        datasets[name]=(metadata,{r['uid']:r for r in metadata},qby,examples)
        records[name]=planned;specs.append(spec)
    # Exercise the unchanged original merge with SOURCE_REFS old104 + new17.
    oldrows=datasets['ORIGINAL104'][0];newrows=datasets['SOURCE_REFS'][0];allrows=oldrows+newrows
    jsonl(package/'data/SOURCE_REFS/selected.jsonl.gz',allrows)
    qby=dict(datasets['ORIGINAL104'][2],**datasets['SOURCE_REFS'][2])
    np.savez_compressed(package/'data/SOURCE_REFS/allq14.npz',uid=np.asarray([r['uid'] for r in allrows]),
                        q14=np.asarray([qby[r['uid']] for r in allrows],dtype=np.float32))
    banks.append(dict(name='SOURCE_REFS',metadata='data/SOURCE_REFS/selected.jsonl.gz',q14='data/SOURCE_REFS/allq14.npz',
        existing_bank='data/ORIGINAL104/old.npz',supplement_dataset='SOURCE_REFS'))
    config=dict(datasets=specs,banks=banks,production_runtime_versions={},benchmark_rows_per_dataset=64,
                limits=dict(memory_gib=8,encoding_wall_seconds=60,min_free_gib=0,output_gib=1))
    adapter.write(package/'config.json',config)
    summary=[adapter.summarize(name,adapter.make_queue(records[name])) for name in adapter.NAMES]
    budget=dict(datasets=summary,totals={k:sum(d[k] for d in summary) for k in
               ('logical_rows','physical_positions','clone_positions','singleton_batches','batches')})
    adapter.write(root/'budget.json',budget)
    package_sha='synthetic-frozen-vendor-seal'
    adapter.write(root/'approval.json',dict(package_sha256=package_sha,user_authorized=True,scope='SUPPLEMENT_E3_ONLY'))
    frozen_spec=importlib.util.spec_from_file_location('actual_frozen_encoder_inert_child',source)
    frozen=importlib.util.module_from_spec(frozen_spec);frozen_spec.loader.exec_module(frozen)
    frozen.CHECKPOINT_SHA=checkpoint_sha;frozen.verify_package=lambda p:package_sha
    def spool(package,spec,db,tokenizer,progress):
        name=spec['name'];metadata,by,qby,examples=datasets[name]
        for uid,shape in records[name]:db.execute('INSERT INTO tokens VALUES(?,?,?,?,?,?)',(name,uid,*shape,json.dumps(examples[uid])))
        db.commit();return metadata,by,qby
    frozen.spool_dataset=spool
    calls=[]
    def fake_forward(model,batches,device):
        batch=batches[0];calls.append(len(batch['input_ids']))
        values=standin_forward(model,batches,device)
        if bad_clone and len(batch['input_ids'])==16 and np.all(batch['input_ids'].value==batch['input_ids'].value[:1]):
            values[-1,0]+=np.float32(.5)
        return values
    def collate(examples):
        width=examples[0]['width']*examples[0]['bursts']
        return dict(input_ids=Tensor(np.asarray([[e['value']]*width for e in examples],dtype=np.int64)),
            protocol=Tensor(np.asarray([e['protocol'] for e in examples],dtype=np.int64)),
            attention_mask=Tensor(np.ones((len(examples),width),dtype=np.int64)))
    core=SimpleNamespace(e3_forward_batches=fake_forward)
    runtime=SimpleNamespace(e3_runtime=lambda r:(SimpleNamespace(core=core),None,None,None,collate))
    source_api=SimpleNamespace(verify_batch=lambda examples,batch:None,tensor_hash=tensor_hash)
    environment=SimpleNamespace(_environment=lambda:dict(synthetic_only=True,model_loads=0))
    real_spec_from_file=adapter.importlib.util.spec_from_file_location
    class Loader:
        def create_module(self,spec):return frozen
        def exec_module(self,module):pass
    def spec_hook(name,path,*pos,**kw):
        if name=='frozen_r2_encoder_batch_adapter':return importlib.util.spec_from_loader(name,Loader())
        return real_spec_from_file(name,path,*pos,**kw)
    actual_finish=adapter.BatchAdapter.finish
    def finish_hook(self):
        if bad_final:
            path=self.output/'UNSW_DEV.tensor_receipts.jsonl.gz'
            values=list(adapter.rows(path));values[0],values[1]=values[1],values[0];jsonl(path,values)
        return actual_finish(self)
    with patch.dict(sys.modules,{'legacy_unsw_archival_runtime_v1':runtime,
        'continuous_features_v3':source_api,'constrained_onboarding_reference_v2':environment}),\
        patch.object(adapter,'verify_frozen',return_value=adapter.ORIGINAL_SHA),\
        patch.object(adapter,'build_budget',return_value=budget),\
        patch.object(adapter.importlib.util,'spec_from_file_location',side_effect=spec_hook),\
        patch.object(adapter.BatchAdapter,'finish',finish_hook):
        try:
            adapter.main(['--frozen-root',str(root/'frozen'),'--budget-file',str(root/'budget.json'),
                '--package',str(package),'--checkpoint',str(checkpoint),'--output',str(output),
                '--mode','encode','--approval-file',str(root/'approval.json')])
        except RuntimeError:
            if not bad_clone and not bad_final:raise
    if bad_clone or bad_final:
        stop=adapter.read(output/'status.json')
        assert stop['status']=='EXCEPTION_STOP' and stop['batch_repair_verified'] is False
        assert not (output/'BATCH_REPAIR_RECEIPT.json').exists()
        if bad_final:
            assert adapter.read(output/'RESULT.json')['status']=='EXCEPTION_STOP'
            assert adapter.read(output/'RESULT.json')['batch_repair_verified'] is False
        print(json.dumps(dict(status='EXPECTED_FINAL_GATE_STOP' if bad_final else 'EXPECTED_CLONE_EXCEPTION_STOP',model_loads=0,calls=calls)))
        return
    result=adapter.read(output/'RESULT.json');receipt=adapter.read(output/'BATCH_REPAIR_RECEIPT.json')
    assert result['status']=='COMPLETE' and result['batch_repair_verified'] is True
    assert result['package_sha256']==package_sha
    assert receipt['budget_sha256']==adapter.sha(root/'budget.json')
    assert adapter.read(output/'ORIGINAL104_PARITY.json')['original104_exact_bytes'] is True
    with np.load(output/'ORIGINAL104.npz',allow_pickle=False) as old:
        assert old['e3'].shape==(104,768) and old['e3'].tobytes()==old_bytes['ORIGINAL104']
    with np.load(output/'banks/SOURCE_REFS/bank.npz',allow_pickle=False) as bank:
        assert bank['e3'].shape==(121,768) and len(set(bank['uid'].tolist()))==121
        assert bank['e3'][:104].tobytes()==old_bytes['ORIGINAL104']
    assert receipt['totals']['logical_rows']==155 and receipt['totals']['physical_positions']==215
    assert 1 not in calls
    print(json.dumps(dict(status='INERT_CHILD_INTEGRATION_PASS',model_loads=0,real_model_forwards=0,
                         logical_rows=155,physical_positions=sum(calls),original104_exact=True,bank_rows=121)))


class ChildIntegrationTests(unittest.TestCase):
    def run_child(self,mode='good'):
        with tempfile.TemporaryDirectory() as directory:
            result=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'--inert-child',directory,
                mode],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
        return json.loads(result.stdout.strip().splitlines()[-1])

    def test_frozen_encoder_child_hooks_parity_order_merge_and_logicalrow_preservation(self):
        result=self.run_child()
        self.assertEqual(result['status'],'INERT_CHILD_INTEGRATION_PASS')
        self.assertEqual(result['physical_positions'],215);self.assertEqual(result['bank_rows'],121)

    def test_frozen_encoder_child_clone_mismatch_cannot_emit_complete_bank_or_gate(self):
        self.assertEqual(self.run_child('bad')['status'],'EXPECTED_CLONE_EXCEPTION_STOP')

    def test_frozen_encoder_child_final_gate_overrides_prior_frozen_complete_result(self):
        self.assertEqual(self.run_child('final')['status'],'EXPECTED_FINAL_GATE_STOP')


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--inert-child':child(sys.argv[2],sys.argv[3]=='bad',sys.argv[3]=='final')
    else:unittest.main()
