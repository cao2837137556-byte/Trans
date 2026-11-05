"""Real streaming/parity/restart/resource gate; never trains a model."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[k]='1'
import argparse,bisect,collections,gc,gzip,hashlib,json,math,struct,subprocess,sys,time,traceback
from pathlib import Path
import psutil
from packet_reader import packets
from stream_core import Engine
HERE=Path(__file__).resolve().parent;PROJECT=Path('/public/home/jiangxinwei.zr/work/paper04');ROOT=PROJECT/'runs/edge_formal_evaluation_resume_v2_20261104/checkout'
PHASE='PREFLIGHT';PROCESS=psutil.Process()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
 return h.hexdigest()
def write(n,v):
 p=HERE/n;t=p.with_suffix('.tmp');t.write_text(json.dumps(v,indent=2,allow_nan=False));t.replace(p)
def progress(stage,done=0,total=1,**kw):write(PHASE+'_PROGRESS.json',dict(stage=stage,done=done,total=total,updated_unix=time.time(),**kw))
def source(role):
 card=read(ROOT/'runs/external_scope_review_codex_20261103/EDGE_EXECUTION_CARD_DRAFT.json');paths=read(PROJECT/'runs/edge_formal_evaluation_resume_v2_20261104/RAW_PATHS.json');spec=card['raw_inputs'][role];path=Path(paths[role]);assert path.stat().st_size==spec['bytes'] and sha(path)==spec['sha256'],'RAW_SHA'
 seg=card['capture_boundaries']['normal_segments'] if role=='NORMAL' else [dict(first_frame=1,last_frame=spec['records'])]
 rr=read(HERE/'SLICES.json')[role]
 if PHASE=='PREFLIGHT':
  base=ROOT/'runs/edge_query_selection_v1_20261103/seal20k';seal=read(base/'QUERY_SELECTION_SEAL.json')['roles'][role];f=base/seal['selected_file'];assert sha(f)==seal['selected_sha256']
  with gzip.open(f,'rt') as stream:allrows=[json.loads(l) for l in stream]
  rr=[r for proto in sorted({r['protocol'] for r in allrows}) for r in sorted([r for r in allrows if r['protocol']==proto],key=lambda r:r['frame'])[:8]]
 return path,spec,seg,sorted(rr,key=lambda r:r['frame'])
def event(p):
 if p is None or p[-2]!='dca632fb69b5':return None
 proto,size,src,dst,sport,dport,md,ms=p
 return ('dca632fb69b5',proto,size,src,struct.pack('!BIIHH',proto,src,dst,sport,dport))
def limits():return read(HERE/'VALIDATION_PLAN.json')['limits']
def stream(role,resume=False):
 path,spec,segs,rr=source(role);before=(path.stat().st_size,path.stat().st_mtime_ns);lim=limits();binding=dict(source_sha256=spec['sha256'],engine_sha256=sha(HERE/'stream_core.py'),plan_sha256=sha(HERE/'VALIDATION_PLAN.json'))
 target={r['frame']:r for r in rr};last=max(target) if PHASE=='PREFLIGHT' else spec['records'];split=last//2;prefix=PHASE+'_'+role
 engine=Engine(lim['max_active_queue_entries'],lim['max_active_groups']);saved_frame=0
 if resume:
  cp=read(HERE/(prefix+'_CHECKPOINT.json'));payload=(HERE/(prefix+'_CHECKPOINT.bin')).read_bytes();engine=Engine.restore(payload,cp['sha256'],binding);saved_frame=engine.frame;assert saved_frame==split
 rows=[];seg=0;rss_peak=PROCESS.memory_info().rss;maxdebt=0;regressions=0;max_stall=0;stall=0;prev_clock=None;prev_raw=None;processed=0;start=time.perf_counter();checkpoint_seconds=0.
 for frame,t,p,reason in packets(path):
  if frame<=saved_frame:continue
  while frame>segs[seg]['last_frame']:seg+=1
  c=engine.advance(frame,t,seg,event(p));processed+=1
  if prev_raw is not None and t<prev_raw:regressions+=1
  stall=stall+1 if c==prev_clock else 0;max_stall=max(max_stall,stall);prev_clock=c;prev_raw=t;maxdebt=max(maxdebt,c-t)
  if frame in target:
   r=target[frame];assert p and r['protocol']==p[0] and r['timestamp_ns']==t and 'dca632fb69b5' in p[-2:],'QUERY_IDENTITY'
   rows.append(dict(uid=r['uid'],frame=frame,segment=seg,protocol=p[0],raw_ns=t,clock_ns=c,integers=list(engine.integers('dca632fb69b5',p[0])),features=list(engine.features('dca632fb69b5',p[0]))))
  if frame==split and not resume:
   st=time.perf_counter();payload=engine.checkpoint(binding);(HERE/(prefix+'_CHECKPOINT.bin')).write_bytes(payload);write(prefix+'_CHECKPOINT.json',dict(sha256=hashlib.sha256(payload).hexdigest(),bytes=len(payload),frame=frame,binding=binding));checkpoint_seconds+=time.perf_counter()-st
  if frame%50000==0:
   rss_peak=max(rss_peak,PROCESS.memory_info().rss);assert rss_peak<=lim['rss_limit_bytes'],'RSS_CAP'
   progress(('RESUME_' if resume else 'STREAM_')+role,frame,last,frames_per_second=processed/max(1e-9,time.perf_counter()-start),active_entries=sum(map(len,engine.queues)),rss_mib=rss_peak/1024**2)
  if frame==last:break
 elapsed=time.perf_counter()-start;rss_peak=max(rss_peak,PROCESS.memory_info().rss)
 assert before==(path.stat().st_size,path.stat().st_mtime_ns) and frame==last and len(rows)==sum(f>saved_frame for f in target)
 result=dict(status='PASS',role=role,resumed=resume,processed_frames=processed,last_frame=frame,seconds=elapsed,frames_per_second=processed/elapsed,rss_peak_bytes=rss_peak,active_peak_entries=engine.peak_entries,active_peak_groups=engine.peak_groups,max_clock_debt_ns=maxdebt,clock_regressions=regressions,max_equal_clock_successors=max_stall,checkpoint_seconds=checkpoint_seconds,rows=rows,source_sha256=spec['sha256'])
 write(prefix+('_RESUME' if resume else '_STREAM')+'.json',result)
 return result
def oracle(role):
 path,spec,segs,_=source(role);result=read(HERE/(PHASE+'_'+role+'_STREAM.json'));rows=result['rows'];groups={};acc={}
 for mode in ['D0','D1']:
  for w in [10**9,10**10]:
   for ix,r in enumerate(rows):
    tm=r['raw_ns'] if mode=='D0' else r['clock_ns'];groups.setdefault((mode,w,r['segment'],r['protocol']),[]).append((tm,r['frame'],ix));acc[(mode,w,ix)]=[0,0,set(),set()]
 for k in groups:groups[k].sort()
 seg=0;clock=None;prevseg=None;checked=0;start=time.perf_counter()
 for frame,t,p,reason in packets(path):
  while frame>segs[seg]['last_frame']:seg+=1
  if seg!=prevseg:clock=t;prevseg=seg
  else:clock=max(clock,t)
  e=event(p)
  if e:
   owner,proto,size,src,conn=e
   for mode,tm in [('D0',t),('D1',clock)]:
    for w in [10**9,10**10]:
     candidates=groups.get((mode,w,seg,proto),[]);lo=bisect.bisect_left(candidates,(tm,-1,-1));hi=bisect.bisect_left(candidates,(tm+w,-1,-1))
     for qt,qf,ix in candidates[lo:hi]:
      if frame<=qf:
       a=acc[(mode,w,ix)];a[0]+=1;a[1]+=size;a[2].add(src);a[3].add(conn)
  if frame%200000==0:progress('ORACLE_'+role,frame,result['last_frame'])
  if frame==result['last_frame']:break
 differences=[];d0=[]
 for ix,r in enumerate(rows):
  values={}
  for mode in ['D0','D1']:
   v=[]
   for w in [10**9,10**10]:
    a=acc[(mode,w,ix)];v.extend([a[0],a[1],len(a[2]),len(a[3])])
   values[mode]=v
  assert values['D1']==r['integers'],'REAL_INTEGER_PARITY'
  f=[float(v) if j not in [4,5] else v/10. for j,v in enumerate(values['D1'])];assert f==r['features'],'REAL_FLOAT_PARITY';checked+=1
  differences.append([abs(a-b) for a,b in zip(values['D0'],values['D1'])]);d0.append(values['D0'])
 resumed=read(HERE/(PHASE+'_'+role+'_RESUME.json'));split=read(HERE/(PHASE+'_'+role+'_CHECKPOINT.json'))['frame'];assert resumed['rows']==[r for r in rows if r['frame']>split],'REAL_RESTART_PARITY'
 out=dict(status='PASS',queries_checked=checked,integer_mismatches=0,float_mismatches=0,restart_rows=len(resumed['rows']),restart_mismatches=0,d0_d1_changed_rows=sum(any(v) for v in differences),d0_d1_max_abs_integer_change=[max(v[j] for v in differences) for j in range(8)],seconds=time.perf_counter()-start,d0_values=d0)
 write(PHASE+'_'+role+'_ORACLE.json',out);return out
def stress():
 from test_core import run
 test=run();plan=read(HERE/'VALIDATION_PLAN.json');lim=limits();n=20000 if PHASE=='PREFLIGHT' else plan['stress']['events'];rate=plan['stress']['virtual_events_per_second'];engine=Engine(lim['max_active_queue_entries'],lim['max_active_groups']);peak=PROCESS.memory_info().rss;start=time.perf_counter();block=[];previous=start
 for i in range(1,n+1):
  engine.advance(i,(i-1)*10**9//rate,0,(str(i%8),17,28,i,struct.pack('!Q',i)))
  if i%10000==0:
   now=time.perf_counter();block.append(10000/(now-previous));previous=now;peak=max(peak,PROCESS.memory_info().rss);assert peak<=lim['rss_limit_bytes'],'STRESS_RSS_CAP'
   if i%100000==0:progress('PRESSURE_STREAM',i,n,rss_mib=peak/1024**2,active_entries=sum(map(len,engine.queues)))
 elapsed=time.perf_counter()-start;before_expiry=sum(map(len,engine.queues));engine.advance(n+1,engine.clock+11*10**9,0,None);assert not any(engine.queues) and not any(engine.groups),'IDLE_STATE_LEAK'
 out=dict(status='PASS',synthetic_regression=test,events=n,seconds=elapsed,events_per_second=n/elapsed,min_10000_event_block_per_second=min(block),rss_peak_bytes=peak,active_peak_entries=engine.peak_entries,active_peak_groups=engine.peak_groups,entries_before_idle=before_expiry,entries_after_idle=0,groups_after_idle=0,parameters_trained=0)
 write(PHASE+'_STRESS.json',out);return out
def cost():
 import torch
 import numpy as np
 from torch import nn
 torch.set_num_threads(1);torch.manual_seed(20261105);out={};iterations=30 if PHASE=='PREFLIGHT' else 200
 for d in [8,782,790]:
  net=nn.Sequential(nn.Linear(d,128),nn.ReLU(),nn.Linear(128,1));original=[p.detach().clone() for p in net.parameters()];x=torch.randn(256,d);negative=torch.randn(128,d);y=torch.arange(256)%2
  timings=[]
  for i in range(iterations+5):
   start=time.perf_counter();net.zero_grad(set_to_none=True);s=net(x).ravel();sn=net(negative).ravel();loss=torch.nn.functional.binary_cross_entropy_with_logits(s,y.float())+torch.nn.functional.softplus(sn[None,:]-s[y==1,None]).mean();loss.backward()
   if i>=5:timings.append(time.perf_counter()-start)
  assert all(torch.equal(p.detach(),q) for p,q in zip(net.parameters(),original)),'BENCHMARK_CHANGED_PARAMETERS'
  t0=time.perf_counter()
  with torch.no_grad():
   for i in range(100):net(x)
  forward_row_seconds=(time.perf_counter()-t0)/(100*256)
  estimate=float(np.quantile(timings,.9))*96560+forward_row_seconds*(5379720+617908+148819)
  wall=max(1800,math.ceil(estimate*3/900)*900);assert wall<=14400,'TRAIN_COST_EXCEEDS_PLAN_CAP'
  out[str(d)]=dict(backward_median_seconds=float(np.median(timings)),backward_p90_seconds=float(np.quantile(timings,.9)),forward_row_seconds=forward_row_seconds,estimated_compute_per_head_seconds=estimate,proposed_wall_seconds=wall,parameters_unchanged=True)
 result=dict(status='PASS',dimensions=out,optimizer_steps=0,real_training_rows=0,limitations='Synthetic forward/backward only, no AdamW update/data loading/tail sorting/checkpoint costs; factor3 reserve and mandatory real training-runtime admission remain',rss_bytes=PROCESS.memory_info().rss)
 write(PHASE+'_COST.json',result);return result
def child(task,role=None,resume=False):
 cmd=[sys.executable,'-X','utf8','-B',str(HERE/'worker.py'),'--phase',PHASE,'--task',task]
 if role:cmd+=['--role',role]
 if resume:cmd+=['--resume']
 name=PHASE+'_'+task+(('_'+role) if role else '')+('_resume' if resume else '')
 with (HERE/(name+'.log')).open('wb') as log:r=subprocess.run(cmd,stdout=log,stderr=log,timeout=1200)
 assert r.returncode==0,'CHILD_FAILED:'+name
def main():
 start=time.perf_counter();plan=read(HERE/'VALIDATION_PLAN.json');assert sha(HERE/'SLICES.json')==plan['slices_sha256'];progress('SYNTHETIC_BOUNDARY_AND_PRESSURE')
 child('stress');summaries={}
 for role in ['NORMAL','HTTP','UDP']:
  child('stream',role);child('stream',role,True);child('oracle',role)
  s=read(HERE/(PHASE+'_'+role+'_STREAM.json'));o=read(HERE/(PHASE+'_'+role+'_ORACLE.json'));s.pop('rows');o.pop('d0_values');summaries[role]=dict(stream=s,oracle=o)
 child('cost');pressure=read(HERE/(PHASE+'_STRESS.json'));costs=read(HERE/(PHASE+'_COST.json'));gates=plan['gates'];fail=[]
 if PHASE=='FULL':
  if pressure['events_per_second']<gates['synthetic_core_min_events_per_second']:fail.append('CORE_THROUGHPUT')
  for role,v in summaries.items():
   if v['stream']['frames_per_second']<gates['full_real_min_frames_per_second']:fail.append(role+'_DECODE_STREAM_THROUGHPUT')
   if v['stream']['max_clock_debt_ns']>gates['max_real_clock_debt_ns']:fail.append(role+'_CLOCK_QUALITY')
   if v['stream']['rss_peak_bytes']>plan['limits']['rss_limit_bytes']:fail.append(role+'_RSS')
   if v['oracle']['queries_checked']!=plan['slice_counts'][role]:fail.append(role+'_SLICE_COVERAGE')
 result=dict(status='PASS' if not fail else 'FAIL',phase=PHASE,seconds=time.perf_counter()-start,failures=fail,plan_sha256=sha(HERE/'VALIDATION_PLAN.json'),stream_source_sha256=sha(HERE/'stream_core.py'),roles=summaries,stress=pressure,cost=costs,real_training=0,optimizer_steps=0,raw_source_writes=0,notes='Stream/resource gate only; no encoder/distance/model-quality verification',hpc_artifacts={p.name:dict(sha256=sha(p),bytes=p.stat().st_size) for p in HERE.glob(PHASE+'_*') if p.is_file() and p.suffix in ['.bin','.json'] and not p.name.endswith(('PROGRESS.json','RESULT.json','STOP.json'))})
 write(PHASE+'_RESULT.json',result)
 assert not fail,'GATE_FAILURE:'+','.join(fail)
 progress('PASS',1,1)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['PREFLIGHT','FULL'],required=True);parser.add_argument('--task',choices=['main','stream','oracle','stress','cost'],default='main');parser.add_argument('--role');parser.add_argument('--resume',action='store_true');a=parser.parse_args();PHASE=a.phase
 try:
  if hasattr(os,'sched_setaffinity'):os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
  if a.task=='main':main()
  elif a.task=='stream':stream(a.role,a.resume)
  elif a.task=='oracle':oracle(a.role)
  elif a.task=='stress':stress()
  else:cost()
 except Exception as e:write(PHASE+'_STOP.json',dict(status='FAIL',task=a.task,error=repr(e),traceback=traceback.format_exc()));raise
