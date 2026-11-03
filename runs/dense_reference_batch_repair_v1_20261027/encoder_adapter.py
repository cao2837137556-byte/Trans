"""Exact singleton batch repair around the frozen r2 encoder, in its child process.

The frozen dataset selection, tokenizer, ORIGINAL104 byte gate and bank merge
remain unchanged. A logical singleton receives 16 identical physical rows;
only one byte-checked result is returned to the frozen encoder.
"""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import sys
from types import SimpleNamespace

ORIGINAL_SHA = 'ddb94bb9836c9ace0b2a704e875d969c1d3c40c94198212ac795a9d0731db120'
ENCODER_SHA = 'c9648f0468431b55a5fc0a3532b00c42447372c4ad6eec64ccfdf1ee353dc959'
NAMES = ('ORIGINAL104','CIC_DEV','SOURCE_REFS','UNSW_DEV')
POLICY = 'B1_TO_16_IDENTICAL_CLONES_KEEP_ONE_OTHER_BATCHES_UNCHANGED'


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def sha(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024**2),b''):value.update(block)
    return value.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path,value):
    path=Path(path);temp=path.with_name(path.name+'.tmp')
    with temp.open('wb') as stream:
        stream.write(canonical(value)+b'\n');stream.flush();os.fsync(stream.fileno())
    os.replace(temp,path)


def verify_frozen(root):
    """Verify all original r2 bytes before importing any of its Python code."""
    root=Path(root).resolve();manifest=root/'PACKAGE_SHA256SUMS'
    require(sha(manifest)==ORIGINAL_SHA,'ORIGINAL_R2_MANIFEST_SHA')
    entries={}
    for line in manifest.read_text(encoding='utf-8').splitlines():
        checksum,relative=line.split('  ',1);path=PurePosixPath(relative)
        require(len(checksum)==64 and set(checksum)<=set('0123456789abcdef') and
                not path.is_absolute() and '..' not in path.parts and str(path)==relative and
                '\\' not in relative and ':' not in relative and relative not in entries,'ORIGINAL_SEALED_PATH')
        entries[relative]=checksum
    actual=set()
    for path in root.rglob('*'):
        relative=path.relative_to(root)
        if relative.parts[0] in ('.private','runtime','local_progress') or '__pycache__' in relative.parts:continue
        require(not path.is_symlink(),'ORIGINAL_SEALED_SYMLINK')
        if path.is_file() and relative.as_posix()!='PACKAGE_SHA256SUMS':actual.add(relative.as_posix())
    require(actual==set(entries),'ORIGINAL_SEALED_MEMBERS')
    for relative,checksum in entries.items():require(sha(root/relative)==checksum,'ORIGINAL_SEALED_BYTES:'+relative)
    require(sha(root/'vendor/encoding_v2/repo/ood/onboarding_supplement_encoder_r2.py')==ENCODER_SHA,
            'FROZEN_ENCODER_SHA')
    return ORIGINAL_SHA


def rows(path):
    with gzip.open(path,'rt',encoding='utf-8') as stream:
        for line in stream:yield json.loads(line)


def flow_shape(flow,config):
    """The frozen tokenizer's dataset_burst_sizes, without importing a model."""
    proto=int(flow['protocol']);bursts=flow['burst_tokens']
    require(proto in (1,6,17) and bursts and all(isinstance(b,list) and b for b in bursts),'FLOW_SHAPE_SCHEMA')
    header={1:7,6:12,17:6}[proto]
    sizes=[sum(min(header,len(burst)-offset) for offset in range(0,len(burst),header+6))
           if config['strip_payload'] else len(burst) for burst in bursts]
    require(len(sizes)<=config['max_bursts'] and max(sizes)+1<=config['max_burst_length'],
            'FROZEN_TOKENIZER_TRUNCATION_NOT_EXPECTED')
    return proto,max(sizes)+1,len(sizes)


def make_queue(records):
    groups=defaultdict(list)
    for uid,shape in records:groups[tuple(shape)].append(uid)
    queue=[]
    for shape in sorted(groups):
        ids=sorted(groups[shape]);require(len(ids)==len(set(ids)),'QUEUE_DUPLICATE_UID')
        for start in range(0,len(ids),16):queue.append(dict(shape=list(shape),uids=ids[start:start+16]))
    return queue


def summarize(name,queue):
    counts=Counter()
    for batch in queue:counts[tuple(batch['shape'])]+=len(batch['uids'])
    logical=sum(len(b['uids']) for b in queue);singletons=sum(len(b['uids'])==1 for b in queue)
    return dict(name=name,logical_rows=logical,physical_positions=logical+15*singletons,
        clone_positions=15*singletons,singleton_batches=singletons,batches=len(queue),queue_sha256=digest(queue),
        shape_counts=[dict(shape=list(shape),rows=counts[shape]) for shape in sorted(counts)])


def build_budget(frozen_root,verified=False):
    root=Path(frozen_root).resolve()
    if not verified:verify_frozen(root)
    package=root/'vendor/encoding_v2';config=read(package/'config.json')
    tokenizer=read(package/'runtime/vendor/netFound-base/config.json')
    specs=sorted(config['datasets'],key=lambda s:(not s.get('original104_check',False),s['name']))
    require(tuple(s['name'] for s in specs)==NAMES,'FIXED_FOUR_REFERENCE_DATASETS')
    datasets=[];inputs={};new_uids=set()
    for spec in specs:
        metadata=list(rows(package/spec['metadata']));wanted={r['uid']:r for r in metadata}
        require(len(wanted)==len(metadata) and all(r.get('use')=='REFERENCE' for r in metadata),'REFERENCE_UIDS_ONLY')
        if not spec.get('original104_check',False):
            require(not new_uids.intersection(wanted),'SUPPLEMENT_UID_OVERLAP');new_uids.update(wanted)
        records=[];seen=set()
        for snapshot in rows(package/spec['snapshots']):
            uid=snapshot['uid']
            if uid not in wanted:continue
            require(uid not in seen,'SNAPSHOT_DUPLICATE_UID');seen.add(uid)
            shape=flow_shape(snapshot['body']['flow'],tokenizer)
            require(shape[0]==int(wanted[uid]['protocol']),'METADATA_PROTOCOL_IDENTITY')
            records.append((uid,shape))
        require(seen==set(wanted),'SNAPSHOT_UID_COVERAGE')
        datasets.append(summarize(spec['name'],make_queue(records)))
        for relative in (spec['metadata'],spec['snapshots']):inputs[relative]=sha(package/relative)
    totals={key:sum(d[key] for d in datasets) for key in ('logical_rows','physical_positions','clone_positions','singleton_batches','batches')}
    require(datasets[0]['logical_rows']==104 and sum(d['logical_rows'] for d in datasets[1:])==21660,
            'FROZEN_LOGICAL_ENCODING_BUDGET')
    return dict(schema='paper04-r2-singleton-physical-budget-v1',policy=POLICY,original_manifest_sha256=ORIGINAL_SHA,
        encoder_sha256=ENCODER_SHA,datasets=datasets,totals=totals,inputs=inputs,
        logical_new_positions=21660,logical_original104_positions=104,target_query_inputs=0,
        training=False,source_cal=False,target_evaluation=False,real_forwards=0)


class BatchAdapter:
    def __init__(self,budget,output,tensor_hash,forward,budget_file_sha256=None):
        self.budget=budget;self.output=Path(output);self.tensor_hash=tensor_hash;self.original_forward=forward
        self.budget_file_sha256=budget_file_sha256 or hashlib.sha256(canonical(budget)+b'\n').hexdigest()
        self.active=None;self.queue=[];self.index=0;self.completed=[];self.counts=Counter();self.failed=False
        self.ledger=self.output/'BATCH_REPAIR_BATCHES.jsonl'
        self.ledger.open('x',encoding='utf-8').close()

    def select(self,db,name,selected):
        self.finish_dataset()
        require(name==self.budget['datasets'][len(self.completed)]['name'],'DATASET_EXECUTION_ORDER')
        records=[(uid,(p,w,b)) for uid,p,w,b in db.execute(
            'SELECT uid,proto,width,bursts FROM tokens WHERE name=? ORDER BY proto,width,bursts,uid',(name,)) if uid in selected]
        require(len(records)==len(selected) and len(selected)==len(set(selected)),'SELECTED_UID_COVERAGE')
        queue=make_queue(records)
        require(summarize(name,queue)==self.budget['datasets'][len(self.completed)],'RUNTIME_PHYSICAL_BUDGET_OR_UID_QUEUE')
        self.active=name;self.queue=queue;self.index=0;self.counts=Counter()

    def finish_dataset(self):
        if self.active is None:return
        require(not self.failed and self.index==len(self.queue),'INCOMPLETE_DATASET_BATCH_QUEUE')
        expected=self.budget['datasets'][len(self.completed)]
        for key in ('logical_rows','physical_positions','clone_positions','singleton_batches','batches'):
            require(self.counts[key]==expected[key],'DATASET_ACTUAL_PHYSICAL_BUDGET:'+key)
        actual=[r['uid'] for r in rows(self.output/(self.active+'.tensor_receipts.jsonl.gz'))]
        wanted=[uid for batch in self.queue for uid in batch['uids']]
        require(actual==wanted and len(actual)==len(set(actual)),'ENCODED_UID_ORDER_AND_UNIQUENESS')
        self.completed.append(dict(expected,actual=dict(self.counts)));self.active=None

    def forward(self,model,batches,device='cpu'):
        import numpy as np
        require(self.active is not None and not self.failed and device=='cpu','ACTIVE_CPU_BATCH_REQUIRED')
        batches=list(batches);require(len(batches)==1 and self.index<len(self.queue),'ONE_FROZEN_BATCH_REQUIRED')
        batch=batches[0];expected=self.queue[self.index];logical=len(expected['uids'])
        require(tuple(batch['input_ids'].shape)==(logical,expected['shape'][1]*expected['shape'][2]) and
                len(batch['protocol'])==logical and all(int(batch['protocol'][j])==expected['shape'][0] for j in range(logical)),
                'LOGICAL_BATCH_SHAPE_IDENTITY')
        physical=16 if logical==1 else logical;clone=physical-logical;prepared=batch;input_hash=None
        if logical==1:
            input_hash=self.tensor_hash(batch,0);prepared={}
            for key,value in batch.items():
                require(hasattr(value,'shape') and len(value.shape)>=1 and value.shape[0]==1 and hasattr(value,'repeat'),
                        'SINGLETON_TENSOR_ONLY')
                prepared[key]=value.repeat((16,)+(1,)*(len(value.shape)-1))
            require(all(self.tensor_hash(prepared,j)==input_hash for j in range(16)),'CLONED_INPUT_TENSOR_IDENTITY')
        record=dict(dataset=self.active,batch_index=self.index,shape=expected['shape'],uid_sha256=digest(expected['uids']),
            logical_rows=logical,physical_positions=physical,clone_positions=clone,singleton_clone=logical==1,
            status='FORWARD_ATTEMPT',input_tensor_sha256=input_hash)
        self.counts.update(logical_rows=logical,physical_positions=physical,clone_positions=clone,
                           singleton_batches=int(logical==1),batches=1)
        # Persist the actual attempted compute before entering the model.
        with self.ledger.open('a',encoding='utf-8') as stream:stream.write(canonical(record).decode()+'\n');stream.flush();os.fsync(stream.fileno())
        try:
            values=self.original_forward(model,[prepared],device)
            require(isinstance(values,np.ndarray) and values.dtype==np.float32 and values.shape==(physical,768) and
                    np.isfinite(values).all(),'PHYSICAL_E3_FINITE_FLOAT32_SCHEMA')
            if logical==1:
                first=values[0].tobytes()
                require(all(values[j].tobytes()==first for j in range(16)),'CLONE_OUTPUT_EXACT_BYTE_IDENTITY')
            result=values[:logical].copy() if logical==1 else values
            completed=dict(dataset=self.active,batch_index=self.index,status='FORWARD_COMPLETE',
                singleton_clone=logical==1,all_cloned_input_tensors_equal=True if logical==1 else None,
                all_16_clone_outputs_byte_equal=True if logical==1 else None,
                first_feature_sha256=hashlib.sha256(values[0].tobytes()).hexdigest())
            with self.ledger.open('a',encoding='utf-8') as stream:
                stream.write(canonical(completed).decode()+'\n');stream.flush();os.fsync(stream.fileno())
            self.index+=1
            write(self.output/'BATCH_REPAIR_PROGRESS.json',dict(status='RUNNING',dataset=self.active,
                completed_batches=self.index,total_batches=len(self.queue),actual=dict(self.counts),policy=POLICY))
            return result
        except BaseException:
            self.failed=True;raise

    def finish(self):
        self.finish_dataset()
        require(len(self.completed)==len(self.budget['datasets']),'ALL_REFERENCE_DATASETS_REQUIRED')
        result=read(self.output/'RESULT.json');parity=read(self.output/'ORIGINAL104_PARITY.json')
        require(result.get('status')=='COMPLETE' and result.get('mode')=='encode' and
                parity.get('original104_exact_bytes') is True and parity.get('mismatch_count')==0 and
                parity.get('max_abs_error')==0,'FROZEN_ORIGINAL104_STRICT_GATE_REQUIRED')
        require([(d['name'],d['measured_rows']) for d in result['datasets']]==
                [(d['name'],d['logical_rows']) for d in self.budget['datasets']],'FROZEN_RESULT_LOGICAL_COUNTS')
        receipt=dict(status='COMPLETE',policy=POLICY,budget_sha256=self.budget_file_sha256,
            budget_content_sha256=digest(self.budget),datasets=self.completed,
            totals=self.budget['totals'],batch_ledger_sha256=sha(self.ledger),original104_exact_bytes=True,
            logical_uids_unchanged=True,clone_rows_in_bank=0,target_query_inputs=0,retries=0)
        write(self.output/'BATCH_REPAIR_RECEIPT.json',receipt)
        result.update(batch_repair_verified=True,batch_repair_receipt_sha256=sha(self.output/'BATCH_REPAIR_RECEIPT.json'))
        write(self.output/'RESULT.json',result)
        write(self.output/'BATCH_REPAIR_PROGRESS.json',dict(receipt,status='COMPLETE'))
        return receipt


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frozen-root',required=True);parser.add_argument('--budget-file',required=True)
    parser.add_argument('--package',required=True);parser.add_argument('--checkpoint',required=True)
    parser.add_argument('--output',required=True);parser.add_argument('--mode',choices=('encode',),required=True)
    parser.add_argument('--approval-file',required=True);args=parser.parse_args(argv)
    root=Path(args.frozen_root).resolve();package=Path(args.package).resolve();output=Path(args.output).resolve()
    require(package==root/'vendor/encoding_v2','FROZEN_ENCODER_PACKAGE_PATH')
    verify_frozen(root)
    budget=read(args.budget_file);require(budget==build_budget(root,verified=True),'EXACT_SEALED_INPUT_PHYSICAL_BUDGET')
    require(not output.exists() and not output.is_relative_to(root),'FRESH_EXTERNAL_ENCODER_OUTPUT')
    sys.path.insert(0,str(package/'repo/ood'))
    spec=importlib.util.spec_from_file_location('frozen_r2_encoder_batch_adapter',package/'repo/ood/onboarding_supplement_encoder_r2.py')
    encoder=importlib.util.module_from_spec(spec);spec.loader.exec_module(encoder)
    runtime=importlib.import_module('legacy_unsw_archival_runtime_v1');original_runtime=runtime.e3_runtime
    actual_indices=encoder.sample_indices;state={}
    def wrapped_runtime(*pos,**kw):
        values=original_runtime(*pos,**kw);embed=values[0]
        source=importlib.import_module('continuous_features_v3')
        state['adapter']=BatchAdapter(budget,output,source.tensor_hash,embed.core.e3_forward_batches,
                                      budget_file_sha256=sha(args.budget_file))
        proxy=SimpleNamespace(**vars(embed));proxy.core=SimpleNamespace(**vars(embed.core))
        proxy.core.e3_forward_batches=state['adapter'].forward
        return (proxy,)+tuple(values[1:])
    def wrapped_indices(db,name,limit):
        selected,shapes=actual_indices(db,name,limit)
        state['adapter'].select(db,name,selected)
        return selected,shapes
    runtime.e3_runtime=wrapped_runtime;encoder.sample_indices=wrapped_indices
    try:
        encoder.main(['--package',str(package),'--checkpoint',args.checkpoint,'--output',str(output),
            '--mode','encode','--approval-file',args.approval_file])
        require('adapter' in state,'ENCODER_ADAPTER_NOT_INSTALLED')
        state['adapter'].finish()
        return 0
    except BaseException as exc:
        if output.is_dir():
            stop=dict(status='EXCEPTION_STOP',stage='BATCH_REPAIR_ENCODER',reason=str(exc),retries=0,
                      evidence_preserved=True,batch_repair_verified=False)
            write(output/'BATCH_REPAIR_PROGRESS.json',stop)
            write(output/'status.json',stop)
            if (output/'RESULT.json').exists():
                result=read(output/'RESULT.json');result.update(stop);write(output/'RESULT.json',result)
        raise
    finally:
        runtime.e3_runtime=original_runtime;encoder.sample_indices=actual_indices


if __name__=='__main__':
    sys.exit(main())
