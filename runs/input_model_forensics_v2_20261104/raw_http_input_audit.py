"""Independent HTTP PCAP context reconstruction, then frozen tokenizer input hash.

Does not import production packet decoder, context state or snapshot code.
No encoder forward. Uses score-independent first UID per frozen HTTP stratum.
"""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
import collections,gzip,hashlib,json,struct,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
    return h.hexdigest()
def packets(path):
    with path.open('rb') as f:
        head=f.read(24);assert head[:4]==bytes.fromhex('d4c3b2a1') and struct.unpack_from('<I',head,20)[0]==1
        frame=0
        while h:=f.read(16):
            sec,micro,cap,wire=struct.unpack('<IIII',h);b=f.read(cap);assert len(b)==cap;frame+=1
            if len(b)<54 or b[12:14]!=b'\x08\x00' or b[23]!=6:continue
            ihl=(b[14]&15)*4;off=14+ihl;frag=struct.unpack_from('!H',b,20)[0]
            if frag&0x3fff or len(b)<off+20:continue
            src,dst=b[26:30],b[30:34];sport,dport,seq,ack=struct.unpack_from('!HHII',b,off)
            key=tuple(sorted(((src,sport),(dst,dport))))
            value=dict(frame=frame,time_ns=(sec*1000000+micro)*1000,src=src.hex(),key=key,
                direction=0 if b[6:12].hex()=='dca632fb69b5' else 1,owner='dca632fb69b5' in (b[:6].hex(),b[6:12].hex()),
                ihl=ihl,ds=b[15],length=struct.unpack_from('!H',b,16)[0],ipflags=frag>>13,ttl=b[22],
                flags=((b[off+12]&1)<<8)|b[off+13],window=struct.unpack_from('!H',b,off+14)[0],seq=seq,ack=ack,urgent=struct.unpack_from('!H',b,off+18)[0])
            yield value
def reconstruct(rr):
    # Separately implement the documented 60s / last12 bursts / last6 packets rule.
    groups=[collections.deque(maxlen=12),collections.deque(maxlen=12)];last=[None,None];previous=None
    for r in rr:
        now=r['time_ns'];assert previous is None or now>=previous
        if previous is not None and now-previous>60*10**9:groups=[collections.deque(maxlen=12),collections.deque(maxlen=12)];last=[None,None]
        d=r['direction']
        if last[d] is None or now-last[d]>10**7:groups[d].append(collections.deque(maxlen=6))
        groups[d][-1].append(r);last[d]=now;previous=now
    chosen=sorted([b for g in groups for b in g],key=lambda b:b[-1]['frame'])[-12:]
    chosen=[[r for r in b if previous-r['time_ns']<=60*10**9] for b in chosen];chosen=[b for b in chosen if b]
    chosen.sort(key=lambda b:(b[0]['time_ns'],b[0]['frame']));ordered=sorted([r for b in chosen for r in b],key=lambda r:r['frame'])
    first=ordered[0];anchor_seq=first['seq'];anchor_ack=first['ack'] or (ordered[1]['seq'] if len(ordered)>1 else 0)
    flow=dict(flow_duration=(previous-first['time_ns'])//1000,burst_tokens=[],directions=[],bytes=[],iats=[],counts=[],protocol=6)
    old=chosen[0][0]['time_ns'];headers=[]
    for burst in chosen:
        hh=[]
        for r in burst:
            forward=r['src']==first['src'];seq=(r['seq']-(anchor_seq if forward else anchor_ack))&0xffffffff
            ack=(r['ack']-anchor_ack)&0xffffffff if forward and anchor_ack else 0 if forward else (r['ack']-anchor_seq)&0xffffffff
            hh.append([r['ihl'],r['ds'],r['length'],r['ipflags'],r['ttl'],r['flags'],r['window'],seq>>16,seq&65535,ack>>16,ack&65535,r['urgent']])
        flow['burst_tokens'].append([v for h in hh for v in h+[0]*6]);headers.append(hh)
        flow['directions'].append(burst[0]['src']==first['src']);flow['bytes'].append(sum(r['length'] for r in burst))
        flow['counts'].append(len(burst));flow['iats'].append(burst[0]['time_ns']-old);old=burst[0]['time_ns']
    return flow,headers
def main():
    import psutil
    proc=psutil.Process();proc.cpu_affinity([proc.cpu_affinity()[0]]);start=time.monotonic()
    card=read(ROOT/'runs/external_scope_review_codex_20261103/EDGE_EXECUTION_CARD_DRAFT.json');spec=card['raw_inputs']['HTTP'];path=Path(spec['path']);assert sha(path)==spec['sha256']
    base=ROOT/'runs/edge_query_selection_v1_20261103/seal20k';seal=read(base/'QUERY_SELECTION_SEAL.json')['roles']['HTTP'];selected=base/seal['selected_file'];assert sha(selected)==seal['selected_sha256']
    with gzip.open(selected,'rt') as f:rows=[json.loads(x) for x in f]
    chosen={}
    for r in sorted(rows,key=lambda x:x['uid']):chosen.setdefault(r['stratum'],r)
    byframe={r['frame']:r for r in chosen.values()};targets={}
    for r in packets(path):
        if r['frame'] in byframe:
            assert r['owner'] and r['time_ns']==byframe[r['frame']]['timestamp_ns'];targets[r['frame']]=r['key']
    assert len(targets)==5
    buffers={k:[] for k in targets.values()};flows=[]
    for r in packets(path):
        if r['key'] not in buffers or not r['owner']:continue
        buffers[r['key']].append(r)
        if r['frame'] in targets:
            flow,headers=reconstruct(buffers[r['key']]);flows.append(dict(row=byframe[r['frame']],flow=flow,headers=headers))
    # Only tokenizer/collator are instantiated; no model or stand-in forward.
    sys.path[:0]=[str(ROOT/'runs/diagnostics_step2_r2_v1_20261025/benchmark_deps'),str(ROOT/'repo/ood')]
    import issue27ckda_d0_resource_pilot_v1 as translator
    import torch
    torch.set_num_threads(1)
    runtime=ROOT/'runs/diagnostics_c5_step2_package_v1_20261025/local_benchmark_v1/runtime'
    config_type,collator_type,_,tokenizer_type=translator.import_netfound(runtime/'vendor/netFound')
    config=config_type.from_pretrained(str(runtime/'vendor/netFound-base'),local_files_only=True);config.pretraining=False;config.compile=False
    tokenizer=tokenizer_type(config=config);tokenizer.pretraining=True;tokenizer.raw_labels=False;collator=collator_type(pad_token_id=tokenizer.pad_token_id)
    results=[]
    for v in flows:
        encoded=tokenizer({k:[x] for k,x in v['flow'].items()});example={k:x[0] for k,x in encoded.items()}
        assert example['input_ids']==[[65537]+[x+1 for h in hh for x in h] for hh in v['headers']]
        batch=collator([example]);digest=hashlib.sha256()
        for key in ['input_ids','attention_mask','direction','iats','bytes','pkt_count','protocol','dataset_burst_sizes']:
            arr=batch[key][0].contiguous().numpy();digest.update(key.encode()+str(arr.dtype).encode()+str(arr.shape).encode()+arr.tobytes())
        import numpy as np
        digest.update(b'position_ids'+np.arange(batch['input_ids'].shape[1],dtype=np.int64).tobytes())
        results.append(dict(uid=v['row']['uid'],stratum=v['row']['stratum'],frame=v['row']['frame'],packets=sum(v['flow']['counts']),input_sha256=digest.hexdigest()))
    (HERE/'RAW_HTTP_INPUT_RESULT.json').write_text(json.dumps(dict(status='RECONSTRUCTED_AWAITING_REMOTE_HASH_COMPARISON',raw_sha256=spec['sha256'],samples=results,seconds=time.monotonic()-start,source_writes=0,new_model_forward=0),indent=2))
    print(json.dumps(results))
if __name__=='__main__':main()
