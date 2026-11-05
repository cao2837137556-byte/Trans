"""Bounded, read-only diagnostic; full arrays and paired records remain on HPC."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[k]='1'
import argparse,collections,gc,gzip,hashlib,json,struct,sys,time,traceback
from pathlib import Path
import numpy as np
import cross_stats as cs
import frozen_helpers as h
HERE=Path(__file__).resolve().parent;ROOT=h.ROOT
PHASE='UNSET';START=time.monotonic()
def write(name,d):h.write(name,d)
def progress(stage,done=0,total=1,**kw):
 write(PHASE+'_PROGRESS.json',dict(stage=stage,done=done,total=total,elapsed_seconds=time.monotonic()-START,updated_unix=time.time(),**kw))
def selected():
 base=ROOT/'runs/edge_query_selection_v1_20261103/seal20k';seal=h.read(base/'QUERY_SELECTION_SEAL.json');out={}
 for role in ['NORMAL','HTTP','UDP']:
  s=seal['roles'][role]
  with gzip.open(h.pin(base/s['selected_file'],s['selected_sha256']),'rt') as f:out[role]=[json.loads(l) for l in f]
 return out

def cross_connection():
 progress('RAW_AND_WINDOW_PREFLIGHT' if PHASE=='PREFLIGHT' else 'CROSS_CONNECTION_RAW')
 card=h.read(ROOT/'runs/external_scope_review_codex_20261103/EDGE_EXECUTION_CARD_DRAFT.json');rows=selected();all_data={};details={};real_checks=0
 paths=h.read(h.PROJECT/'runs/edge_formal_evaluation_resume_v2_20261104/RAW_PATHS.json')
 for role,rr in rows.items():
  spec=card['raw_inputs'][role];path=h.pin(Path(paths[role]),spec['sha256']);assert path.stat().st_size==spec['bytes'];before=(path.stat().st_size,path.stat().st_mtime_ns)
  if PHASE=='PREFLIGHT':
   rr=[r for p in sorted({r['protocol'] for r in rr}) for r in sorted([r for r in rr if r['protocol']==p],key=lambda r:r['frame'])[:16]]
  rr=sorted(rr,key=lambda r:r['frame']);targets={r['frame']:i for i,r in enumerate(rr)};assert len(targets)==len(rr)
  segments=card['capture_boundaries']['normal_segments'] if role=='NORMAL' else [dict(first_frame=1,last_frame=spec['records'])]
  events=collections.defaultdict(list);starts={};seen=set();meta=[];exclusions=collections.Counter();regress=0;prev=None;segment=0
  for frame,tm,p,reason in cs.packets(path):
   while frame>segments[segment]['last_frame']:segment+=1;prev=None
   starts.setdefault(segment,tm)
   if prev is not None and tm<prev:regress+=1
   prev=tm;exclusions[reason]+=1
   if p:
    proto,size,src,dst,sport,dport,md,ms=p
    if md=='dca632fb69b5':
     key=struct.pack('!BIIHH',proto,src,dst,sport,dport);events[(segment,proto)].append((tm,frame,size,src,key))
   if frame in targets:
    r=rr[targets[frame]];assert p is not None and p[0]==r['protocol'] and tm==r['timestamp_ns'] and 'dca632fb69b5' in p[-2:],'RAW_SELECTED_IDENTITY'
    seen.add(frame);meta.append(dict(uid=r['uid'],frame=frame,time_ns=tm,segment=segment,protocol=r['protocol'],inbound=p[-2]=='dca632fb69b5',age_ns=tm-starts[segment]))
   if frame%100000==0:progress('RAW_'+role,frame,spec['records'])
   if PHASE=='PREFLIGHT' and frame>=max(targets):break
  assert before==(path.stat().st_size,path.stat().st_mtime_ns),'SOURCE_CHANGED'
  assert len(seen)==len(rr),'RAW_QUERY_COVERAGE'
  if PHASE=='FULL':assert frame==spec['records']
  values=np.empty((len(rr),8),np.float64)
  for (segment,proto),ev in sorted(events.items()):
   ix=[i for i,m in enumerate(meta) if m['segment']==segment and m['protocol']==proto]
   if not ix:continue
   queries=[(meta[i]['time_ns'],meta[i]['frame']) for i in ix]
   for wi,w in enumerate([1,10]):
    progress('WINDOW_'+role+'_'+str(w)+'s',0,len(ix),segment=segment,protocol=proto)
    v=cs.calculate(ev,queries,w,lambda d,n:progress('WINDOW_'+role+'_'+str(w)+'s',d,n,segment=segment,protocol=proto));values[ix,wi*4:wi*4+4]=v
    # First/middle/last by fixed query order, never selected by values.
    check=sorted({0,len(ix)//2,len(ix)-1});assert np.array_equal(v[check],cs.brute(ev,[queries[j] for j in check],w)),'REAL_CAUSAL_RANGE_PARITY';real_checks+=len(check)
  # A protocol can have selected outbound packets but no inbound packets at all.
  for i,m in enumerate(meta):
   if (m['segment'],m['protocol']) not in events:values[i]=0
  assert np.isfinite(values).all() and np.all(values>=0)
  array=HERE/(PHASE+'_'+role+'_CROSS_FEATURES.npz');np.savez_compressed(array,features=values,uid=np.array([m['uid'] for m in meta]),frame=np.array([m['frame'] for m in meta]),protocol=np.array([m['protocol'] for m in meta]),segment=np.array([m['segment'] for m in meta]),inbound=np.array([m['inbound'] for m in meta]),age_ns=np.array([m['age_ns'] for m in meta]))
  all_data[role]=(values,meta);details[role]=dict(queries=len(rr),raw_frames_read=frame,raw_total_frames=spec['records'],source_sha256=spec['sha256'],parser_counts=dict(exclusions),capture_order_regressions=regress,inbound_events=sum(map(len,events.values())),arrays=dict(path=str(array),sha256=h.sha(array),bytes=array.stat().st_size))
  del events;gc.collect()
 names=[f'{name}_{w}s' for w in [1,10] for name in ['packet_rate','IP_byte_rate','source_count','connection_count']]
 summaries={};comparisons={}
 for role,(v,meta) in all_data.items():
  groups={'ALL':np.arange(len(meta))}
  for p in [6,17]:groups['PROTO_'+str(p)]=np.array([i for i,m in enumerate(meta) if m['protocol']==p],dtype=int)
  for seg in sorted({m['segment'] for m in meta}):
   for p in [6,17]:groups['SEG_'+str(seg)+'_PROTO_'+str(p)]=np.array([i for i,m in enumerate(meta) if m['segment']==seg and m['protocol']==p],dtype=int)
  summaries[role]={g:dict(n=len(ix),full_10s=sum(meta[i]['age_ns']>=10**10 for i in ix),features={name:dict(quantiles=cs.quant(v[ix,j]),unique_values=len(np.unique(v[ix,j])),zero_fraction=float(np.mean(v[ix,j]==0)) if len(ix) else None) for j,name in enumerate(names)}) for g,ix in groups.items() if len(ix)}
 nv,nm=all_data['NORMAL']
 for role in ['HTTP','UDP']:
  av,am=all_data[role];proto=6 if role=='HTTP' else 17
  for inbound_only in [False,True]:
   for full_window in [False,True]:
    for seg in [None]+sorted({m['segment'] for m in nm}):
     key=f'{role}/inbound={inbound_only}/full10s={full_window}/normal_segment={seg}'
     ni=[i for i,m in enumerate(nm) if m['protocol']==proto and (seg is None or m['segment']==seg) and (not inbound_only or m['inbound']) and (not full_window or m['age_ns']>=10**10)]
     ai=[i for i,m in enumerate(am) if (not inbound_only or m['inbound']) and (not full_window or m['age_ns']>=10**10)]
     comparisons[key]=dict(normal_n=len(ni),attack_n=len(ai),auc_high_is_attack={name:cs.auc(nv[ni,j],av[ai,j]) for j,name in enumerate(names)})
 result=dict(status='PASS',scope='Edge fixed queries, eight causal features, descriptive only',roles=details,real_brute_force_queries_checked=real_checks,feature_order=names,summary=summaries,comparisons=comparisons,threshold_fit=0,training=0)
 write(PHASE+'_CROSS_SUMMARY.json',result);return result

def single_packet(s):
 body=s['body'];p=body['provenance'];matches=[(hh,tm) for b in p['bursts'] for f,hh,tm in zip(b['frames'],b['headers'],b['times_ns']) if f==s['row']['frame']]
 assert len(matches)==1 and s['row']['protocol']==17
 hh,tm=matches[0];assert len(hh)==6
 flow=dict(flow_duration=0,burst_tokens=[hh+[0]*6],directions=[True],bytes=[hh[2]],iats=[0],counts=[1],protocol=17)
 provenance=dict(p,bursts=[dict(burst_id=s['row']['frame'],frames=[s['row']['frame']],times_ns=[tm],headers=[hh])])
 return flow,provenance,hh

def ablation():
 sys.path[:0]=[str(ROOT/'runs/edge_formal_execution_v4_20261104'),str(ROOT/'repo/ood'),str(ROOT/'runs/history_normal_reference_keyrepair_v1_20261031')]
 from streaming import FrozenBackend,module
 from evaluate import FrozenHeads
 from continuous_features_v3 import tokenize,verify_batch,tensor_hash
 from continuous_input_v3 import verify_tokenized
 from hnr.encoding import physical_batch
 progress('LOAD_FIXED_ABLATION_SAMPLES')
 receipt=h.read(HERE/'SAMPLE_RECEIPT.json')
 with gzip.open(h.pin(HERE/'AB_SAMPLES.json.gz',receipt['payload_sha256']),'rt') as f:samples=json.load(f)
 edge=h.edge_samples();samples+=edge
 if PHASE=='PREFLIGHT':
  groups={}
  for s in samples:groups.setdefault(s['dataset']+'/'+s['group'],s)
  samples=list(groups.values())
 write(PHASE+'_ACTUAL_SELECTION.json',dict(samples=[dict(dataset=s['dataset'],group=s['group'],uid=s['uid']) for s in samples]))
 progress('LOAD_FROZEN_ENCODER',0,len(samples));backend=FrozenBackend();embed,_,model,tokenizer,collator=backend.encoder
 assert not model.training and not any(p.requires_grad for p in model.parameters())
 from safetensors import safe_open
 from loaded_weight_check import verify_weights
 checkpoint=h.pin(ROOT/'runs/diagnostics_c5_step2_package_v1_20261025/local_benchmark_v1/runtime/vendor/netFound-base/model.safetensors','e6237f49ce58840f8bf7d0cafa5ae80f58d05ea158053d031792d0369d7f5105')
 with safe_open(str(checkpoint),framework='pt',device='cpu') as saved:weight_check=verify_weights(model.state_dict(),saved)
 engine=module('_context_engine',ROOT/'runs/edge_external_test1_engineering_v1_20261103/preflight/engine.py');freeze,spec,norm,pins=engine.frozen_assets();heads=FrozenHeads(spec,norm)
 cuts=np.array(freeze['calibration']['cuts']['cuts']+[freeze['calibration']['cuts']['ensemble_cut']]);entries=[];forward_cache={}
 def forward(flow,provenance):
  ex=tokenize(tokenizer,flow);verify_tokenized(flow,provenance,ex);batch=collator([ex]);verify_batch([ex],batch);batch,n=physical_batch(batch,1,tensor_hash);ih=tensor_hash(batch,0)
  if ih not in forward_cache:
   z=embed.core.e3_forward_batches(model,[batch],'cpu');assert z.shape==(16,768) and all(np.array_equal(z[0],x) for x in z);forward_cache[ih]=z[0].copy()
  return forward_cache[ih],ih
 def four(scores):return np.r_[scores,np.mean(scores,dtype=np.float64)]
 detail=HERE/(PHASE+'_PAIRED_ROWS.jsonl')
 with detail.open('w') as f:
  for i,s in enumerate(samples):
   progress('PAIRED_ENCODER_FORWARD',i,len(samples),dataset=s['dataset'],group=s['group'])
   q=h.independent_q(s['body'],s['row']);assert np.array_equal(q,np.asarray(s['expected_q14'],np.float32))
   z,ih=forward(s['body']['flow'],s['body']['provenance']);ze=float(np.max(np.abs(z-np.asarray(s['expected_e3'],np.float32))))
   if 'input_hash' in s:assert ih==s['input_hash']
   baseline=heads.scores(z[None,:],q[None,:])[0];saved=np.asarray(s['expected_scores']);se=float(np.max(np.abs(baseline-saved)))
   assert ze<=.0002 and se<=.002 and np.array_equal(four(baseline)>cuts,four(saved)>cuts),'BASELINE_REPLAY'
   flow,prov,header=single_packet(s);sz,sih=forward(flow,prov);sq=q.copy();sq[-1]=1
   arms=np.stack([four(baseline),four(heads.scores(sz[None,:],q[None,:])[0]),four(heads.scores(sz[None,:],sq[None,:])[0])])
   n=sum(s['body']['flow']['counts'])
   if n==1:assert ih==sih and np.array_equal(q,sq) and np.array_equal(z,sz) and np.array_equal(arms[0],arms[2]),'SINGLE_PACKET_INVARIANCE'
   entry=dict(dataset=s['dataset'],group=s['group'],uid=s['uid'],packets=n,header=header,original_hash=ih,single_hash=sih,q_direction=float(q[-1]),baseline_e3_error=ze,baseline_head_error=se,e3_l2_change=float(np.linalg.norm(z.astype(float)-sz)),scores=arms.tolist(),margins=(arms-cuts).tolist(),alarms=(arms>cuts).tolist())
   entries.append(entry);f.write(json.dumps(entry)+'\n');f.flush()
 groups={}
 for g in sorted({e['dataset']+'/'+e['group'] for e in entries}):
  for context in ['ALL','SINGLE','MULTI']:
   ee=[e for e in entries if e['dataset']+'/'+e['group']==g and (context=='ALL' or (e['packets']==1)==(context=='SINGLE'))]
   if not ee:continue
   scores=np.array([e['scores'] for e in ee]);alarms=scores>cuts;groups[g+'/'+context]=dict(rows=len(ee),packet_counts=cs.quant([e['packets'] for e in ee]),original_unique_inputs=len({e['original_hash'] for e in ee}),single_unique_inputs=len({e['single_hash'] for e in ee}),unique_current_headers=len({tuple(e['header']) for e in ee}),q_direction_false=sum(e['q_direction']==0 for e in ee),e3_l2_change=cs.quant([e['e3_l2_change'] for e in ee]),alarm_counts=alarms.sum(0).tolist(),ensemble_margins=[cs.quant(scores[:,a,3]-cuts[3]) for a in range(3)],ensemble_delta=[cs.quant(scores[:,a,3]-scores[:,0,3]) for a in [1,2]],lost_original_alarms=[(alarms[:,0]&~alarms[:,a]).sum(0).tolist() for a in [1,2]],new_alarms=[(~alarms[:,0]&alarms[:,a]).sum(0).tolist() for a in [1,2]])
 result=dict(status='PASS',rows=len(entries),weight_check=weight_check,frozen_asset_pins=pins,arms=['ORIGINAL','SINGLE_E3_ORIGINAL_Q','SINGLE_E3_SINGLE_Q'],head_order=['27','127','227','ensemble'],cuts=cuts.tolist(),groups=groups,baseline_max_e3_error=max(e['baseline_e3_error'] for e in entries),baseline_max_head_error=max(e['baseline_head_error'] for e in entries),single_packet_invariance_rows=sum(e['packets']==1 for e in entries),unique_forward_calls=len(forward_cache),details=dict(path=str(detail),sha256=h.sha(detail),bytes=detail.stat().st_size),training=0,threshold_fit=0)
 write(PHASE+'_ABLATION_SUMMARY.json',result);return result

def main():
 os.sched_setaffinity(0,{min(os.sched_getaffinity(0))});reg=cs.regression();progress('LOCAL_MATH_REGRESSION_PASS')
 cross=cross_connection();gc.collect();ab=ablation()
 result=dict(status='PASS',phase=PHASE,seconds=time.monotonic()-START,plan_sha256=h.sha(HERE/'PLAN.json'),regression=reg,ablation_rows=ab['rows'],cross_queries={k:v['queries'] for k,v in cross['roles'].items()},summary_pins={n:h.sha(HERE/n) for n in [PHASE+'_CROSS_SUMMARY.json',PHASE+'_ABLATION_SUMMARY.json',PHASE+'_ACTUAL_SELECTION.json']},source_pins=h.PINS,training=0,threshold_fit=0,source_writes=0,scope='Diagnostic gate only, not full C5 distance/engineering rerun or repaired-model acceptance')
 write(PHASE+'_RESULT.json',result);progress('PASS',1,1)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--phase',choices=['PREFLIGHT','FULL'],required=True);PHASE=p.parse_args().phase
 try:main()
 except Exception as e:write(PHASE+'_STOP.json',dict(status='FAIL',error=repr(e),traceback=traceback.format_exc()));raise
