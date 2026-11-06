"""Bounded, read-only export of nine sealed training logs; no model/data inference."""
import array, ast, hashlib, json, math, struct, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent/'device_context_head_training_v2_20261105'

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024**2), b''): h.update(b)
    return h.hexdigest()

def read(p): return json.loads(p.read_text())

def export():
    started=time.monotonic(); expected=read(HERE/'PINS.json'); result={}
    for arm in ['REFIT782','STATS8','FUSION790']:
        for seed in [27,127,227]:
            key=f'{arm}_{seed}'; folder=PARENT/'heads'/key/'train'; pins={}
            for line in (folder/'SHA256SUMS').read_text().splitlines():
                digest,rel=line.split('  ',1); p=(folder/rel).resolve()
                assert p.is_relative_to(folder.resolve()) and rel not in pins
                assert sha(p)==digest, 'SEAL:'+key+':'+rel
                pins[rel]=digest
            actual={p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file() and p.name not in ['SHA256SUMS','status.json','STOP_REQUESTED']}
            assert actual==set(pins), 'SEAL_FILE_SET'
            for file,field in [('head.npz','head_sha256'),('initial.npz','initial_sha256'),('endpoint.json','endpoint_sha256')]:
                assert pins[file]==expected[key][field], 'LOCAL_PARENT_PIN:'+key+':'+file
            schema=read(folder/'diagnostics_schema.json'); endpoint=read(folder/'endpoint.json')
            assert schema['status']=='COMPLETE' and schema['written_rows']==schema['completed_optimizer_updates']==96560
            assert endpoint['updates']==96560 and endpoint['epochs']==40 and endpoint['arm']==arm and endpoint['seed']==seed
            epochs=[read(folder/f'epoch_{i:02d}.json') for i in range(1,41)]
            probes=[json.loads(line) for line in (folder/'fixed_probes.jsonl').read_text().splitlines()]
            assert len(probes)==schema['probe_rows']==120
            assert [(p['epoch'],p['batch'],p['global_update']) for p in probes]==[(e,b,(e-1)*2414+b) for e in range(1,41) for b in [1,1207,2414]]
            with (folder/'batch_losses.npy').open('rb') as f:
                assert f.read(8)==b'\x93NUMPY\x01\x00'
                header=ast.literal_eval(f.read(struct.unpack('<H',f.read(2))[0]).decode())
                assert header==dict(descr='<f8',fortran_order=False,shape=(96560,3)), header
                losses=array.array('d');losses.fromfile(f,96560*3);assert not f.read(1)
                if sys.byteorder!='little':losses.byteswap()
            assert all(math.isfinite(v) for v in losses), 'NONFINITE_LOSS'
            max_error=0.; sum_error=0.
            for i,e in enumerate(epochs):
                assert e['epoch']==i+1 and e['updates']==(i+1)*2414 and e['bce_visits']==617908
                assert e['tail_sample_count']==2414*128 and e['order_sha256']==endpoint['order_hashes'][i]
                for j,name in enumerate(['bce_loss','tail_loss','loss']):
                    v=sum(losses[((i*2414+b)*3)+j]*(256 if b<2413 else 617908-2413*256)/617908 for b in range(2414))
                    max_error=max(max_error,abs(v-e[name]));assert abs(v-e[name])<1e-8
            for i in range(96560):sum_error=max(sum_error,abs(losses[3*i]+losses[3*i+1]-losses[3*i+2]))
            assert sum_error<1e-8
            result[key]=dict(endpoint=endpoint,schema=schema,epochs=epochs,probes=probes,
                             file_sha256=pins,seal_sha256=sha(folder/'SHA256SUMS'),
                             batch_losses=dict(rows=96560,all_finite=True,epoch_reduction_max_error=max_error,component_sum_max_error=sum_error))
    out=dict(status='PASS',scope='READ_ONLY_EXISTING_TRAIN_LOGS',heads=result,seconds=time.monotonic()-started,
             training_jobs=0,external_data_read=False,large_arrays_exported=False,
             limitation='Only initial/final checkpoints exist. No epoch score trajectories; no claim of normal-score drift onset or causal training attribution.')
    (HERE/'RESULT.json').write_text(json.dumps(out,separators=(',',':'),allow_nan=False)+'\n')
    print('NINE_TRAINING_LOGS_VERIFIED',len(result),round(out['seconds'],2),flush=True)

if __name__=='__main__': export()
