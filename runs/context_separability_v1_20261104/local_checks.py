"""Local parser/tokenizer/range checks; not the Linux encoder preflight."""
import ast,collections,gzip,json,struct,sys,time
from pathlib import Path
import numpy as np
import cross_stats as cs
import worker
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def main():
 start=time.monotonic();result=dict(regression=cs.regression(),raw={})
 for p in HERE.glob('*.py'):ast.parse(p.read_text())
 card=json.loads((ROOT/'runs/external_scope_review_codex_20261103/EDGE_EXECUTION_CARD_DRAFT.json').read_text());base=ROOT/'runs/edge_query_selection_v1_20261103/seal20k';seal=json.loads((base/'QUERY_SELECTION_SEAL.json').read_text())
 for role in ['NORMAL','HTTP','UDP']:
  with gzip.open(base/seal['roles'][role]['selected_file'],'rt') as f:rr=[json.loads(l) for l in f]
  rr=[min([r for r in rr if r['protocol']==p],key=lambda r:r['frame']) for p in sorted({r['protocol'] for r in rr})];targets={r['frame']:r for r in rr};ev=collections.defaultdict(list);qs=collections.defaultdict(list)
  for frame,tm,p,reason in cs.packets(Path(card['raw_inputs'][role]['path'])):
   if p and p[-2]=='dca632fb69b5':ev[p[0]].append((tm,frame,p[1],p[2],struct.pack('!BIIHH',p[0],*p[2:6])))
   if frame in targets:
    r=targets[frame];assert p and p[0]==r['protocol'] and tm==r['timestamp_ns'];qs[p[0]].append((tm,frame))
   if frame>=max(targets):break
  for proto,queries in qs.items():
   for w in [1,10]:assert np.array_equal(cs.calculate(ev[proto],queries,w),cs.brute(ev[proto],queries,w))
  assert sum(map(len,qs.values()))==len(rr);result['raw'][role]=dict(frames_read=frame,queries=len(rr))
 sys.path[:0]=[str(ROOT/'runs/diagnostics_step2_r2_v1_20261025/benchmark_deps'),str(ROOT/'repo/ood')]
 import issue27ckda_d0_resource_pilot_v1 as translator
 from continuous_input_v3 import verify_tokenized
 import torch
 torch.set_num_threads(1)
 runtime=ROOT/'runs/diagnostics_c5_step2_package_v1_20261025/local_benchmark_v1/runtime';config_type,collator_type,_,tokenizer_type=translator.import_netfound(runtime/'vendor/netFound');config=config_type.from_pretrained(str(runtime/'vendor/netFound-base'),local_files_only=True);config.pretraining=False;config.compile=False
 tokenizer=tokenizer_type(config=config);tokenizer.pretraining=True;tokenizer.raw_labels=False
 with gzip.open(HERE/'.private/AB_SAMPLES.json.gz','rt') as f:samples=json.load(f)
 for s in samples:
  flow,prov,hh=worker.single_packet(s);e=tokenizer({k:[x] for k,x in flow.items()});verify_tokenized(flow,prov,{k:x[0] for k,x in e.items()})
  assert flow['burst_tokens']==[hh+[0]*6] and flow['bytes']==[hh[2]] and flow['counts']==[1]
 result.update(status='PASS',tokenizer_single_packet_samples=len(samples),seconds=time.monotonic()-start,scope='Local math, real PCAP prefixes and tokenizer only; Linux frozen forward gate still required')
 (HERE/'LOCAL_CHECKS.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
if __name__=='__main__':main()
