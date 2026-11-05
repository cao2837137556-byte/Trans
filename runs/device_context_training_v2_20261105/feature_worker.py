"""Raw-frame-only causal features; labels/scores never enter the statistics engine."""
import argparse,collections,gc,hashlib,json,os,struct,time,traceback
from pathlib import Path
from decimal import Decimal
import numpy as np
import psutil
from stream_core import Engine
from source_packets import packets
from source_admission import read,sha,write
HERE=Path(__file__).resolve().parent;PHASE='FEATURE_PREFLIGHT'
def progress(stage,done,total,**kw):write(PHASE+'_PROGRESS.json',dict(stage=stage,done=done,total=total,updated_unix=time.time(),**kw))
def run_capture(capture,spec,query_limit=None):
 path=Path(spec['raw_path']);assert sha(path)==spec['source_sha256'],'RAW_SHA';queryfile=HERE/'queries'/(capture+'.npz');assert sha(queryfile)==spec['query_sha256'];q=np.load(queryfile);order=np.arange(len(q['frame']))
 if query_limit:
  pairs=set(zip(q['role'].tolist(),q['protocol'].tolist()));order=np.asarray(sorted({int(i) for role,proto in pairs for i in np.flatnonzero((q['role']==role)&(q['protocol']==proto))[:query_limit]}))
 frames=q['frame'][order];owners=[v.decode() for v in q['owner'][order]];protocols=q['protocol'][order];target=collections.defaultdict(list)
 for i,f in enumerate(frames):target[int(f)].append(i)
 active_owners=set(spec['owners']);last=int(max(frames)) if query_limit else spec['expected_frames'];lim=read(HERE/'TRAINING_SPEC_FROZEN.json')['engine_limits'];engine=Engine(lim['max_active_queue_entries'],lim['max_active_groups']);replica=None;split=max(1,last//2);binding=dict(raw=spec['source_sha256'],query=spec['query_sha256'],core=sha(HERE/'stream_core.py'));folder=HERE/PHASE/capture;folder.mkdir(parents=True,exist_ok=False)
 out=np.full((len(order),8),np.nan,np.float64);times=np.zeros(len(order),np.int64);inbound=np.zeros(len(order),np.uint8);counts=collections.Counter();reasons=collections.Counter();history=collections.deque();checks=restart=0;clockdebt=0;peak=0;seen=0;oracleclock=None;start=time.monotonic();before=(path.stat().st_size,path.stat().st_mtime_ns)
 for frame,t,p,reason in packets(path):
  event=None;reasons[reason]+=1
  if p and p[-2] in active_owners:
   proto,size,src,dst,sp,dp,md,ms=p;event=(md,proto,size,src,struct.pack('!BIIHH',proto,src,dst,sp,dp));counts['inbound']+=1
  c=engine.advance(frame,t,capture,event);clockdebt=max(clockdebt,c-t)
  if replica is not None:assert replica.advance(frame,t,capture,event)==c
  if query_limit:
   oracleclock=t if oracleclock is None else max(oracleclock,t);assert c==oracleclock,'CLOCK_PARITY'
   while history and history[0][0]<=c-10**10:history.popleft()
   if event:history.append((c,event))
  if frame in target:
   for i in target[frame]:
    assert p is not None,'UNSUPPORTED_QUERY:'+capture+':'+str(frame)+':'+reason
    assert owners[i] in p[-2:] and int(protocols[i])==p[0] and float(Decimal(t)/Decimal(10**9))==q['timestamp'][order[i]],'RAW_QUERY_JOIN:'+capture+':'+str(frame)
    out[i]=engine.features(owners[i],p[0]);times[i]=c;inbound[i]=p[-2]==owners[i];seen+=1
    if replica is not None:assert replica.features(owners[i],p[0])==tuple(out[i]);restart+=1
    if query_limit:
     brute=[]
     for width in [10**9,10**10]:
      ev=[e for tm,e in history if c-width<tm<=c and e[0]==owners[i] and e[1]==p[0]];brute.extend([len(ev)/(width/10**9),sum(e[2] for e in ev)/(width/10**9),len({e[3] for e in ev}),len({e[4] for e in ev})])
     assert np.array_equal(out[i],brute),'INDEPENDENT_PARITY';checks+=1
  if frame==split:
   payload=engine.checkpoint(binding);(folder/'CHECKPOINT.bin').write_bytes(payload);replica=Engine.restore(payload,hashlib.sha256(payload).hexdigest(),binding);write(str(folder.relative_to(HERE)/'CHECKPOINT.json'),dict(frame=frame,sha256=hashlib.sha256(payload).hexdigest(),bytes=len(payload),binding=binding));del payload
  if frame%100000==0:
   peak=max(peak,psutil.Process().memory_info().rss);assert peak<6*1024**3,'FEATURE_PROCESS_RSS';progress('RAW_'+capture,frame,last,frames_per_second=frame/max(.001,time.monotonic()-start),rss_mib=peak/1024**2)
  if frame==last:break
 assert frame==last and seen==len(order) and np.isfinite(out).all() and np.all(out>=0),'FEATURE_COVERAGE'
 assert before==(path.stat().st_size,path.stat().st_mtime_ns),'RAW_CHANGED'
 # Clock quality is an admission result, not a tuning knob chosen from detector scores.
 assert clockdebt<=10**9,'SOURCE_CLOCK_QUALITY:'+capture+':'+str(clockdebt)
 np.savez(folder/'FEATURES.npz',features=out,role=q['role'][order],index=q['index'][order],uid=q['uid'][order],frame=frames,clock_ns=times,inbound=inbound)
 result=dict(status='PASS',capture=capture,queries=seen,frames=frame,seconds=time.monotonic()-start,max_clock_debt_ns=clockdebt,peak_entries=engine.peak_entries,peak_groups=engine.peak_groups,rss_peak_bytes=max(peak,psutil.Process().memory_info().rss),parser_counts=dict(reasons),inbound_frames=counts['inbound'],independent_checks=checks,restart_queries=restart,features_sha256=sha(folder/'FEATURES.npz'),query_sha256=spec['query_sha256'],source_sha256=spec['source_sha256'])
 write(str(folder.relative_to(HERE)/'COMPLETE.json'),result);return result
def main():
 admission=read(HERE/'ADMISSION_RESULT.json');assert admission['status']=='PASS' and sha(HERE/'QUERY_MANIFEST.json')==admission['query_manifest_sha256'];manifest=read(HERE/'QUERY_MANIFEST.json');start=time.monotonic();selected=[]
 if PHASE=='FEATURE_PREFLIGHT':
  # Earliest 8 rows in the smallest file for each represented role/protocol.
  groups={}
  for cap,s in manifest.items():
   q=np.load(HERE/'queries'/(cap+'.npz'));pairs=set(zip(q['role'].tolist(),q['protocol'].tolist()))
   for key in pairs:
    if key not in groups or (s['raw_bytes'],cap)<(manifest[groups[key]]['raw_bytes'],groups[key]):groups[key]=cap
  selected=sorted(set(groups.values()));write('FEATURE_PREFLIGHT_SELECTION.json',dict(rule='smallest registered raw bytes then capture_id per role/protocol, earliest8 queries per represented role/protocol, scores not read',captures=selected,groups={str(k):v for k,v in groups.items()}))
 else:
  assert read(HERE/'FEATURE_PREFLIGHT_RESULT.json')['status']=='PASS';selected=sorted(manifest)
 reports={}
 for i,cap in enumerate(selected):
  progress('CAPTURE_START',i,len(selected),capture=cap);reports[cap]=run_capture(cap,manifest[cap],8 if PHASE=='FEATURE_PREFLIGHT' else None);gc.collect()
 result=dict(status='PASS',phase=PHASE,captures=len(reports),queries=sum(v['queries'] for v in reports.values()),frames=sum(v['frames'] for v in reports.values()),independent_checks=sum(v['independent_checks'] for v in reports.values()),restart_queries=sum(v['restart_queries'] for v in reports.values()),seconds=time.monotonic()-start,details=reports,training_started=False)
 if PHASE=='FEATURE_BUILD':
  metadata=read(HERE/'ADMISSION_RESULT.json');dest=HERE/'features8';dest.mkdir(exist_ok=False);written={}
  arrays={};uids={}
  for role_id,role in enumerate(['LEARN','CIC_DEV','UNSW_DEV']):
   n=metadata['roles'][role]['rows'];arrays[role_id]=np.lib.format.open_memmap(dest/(role+'.npy'),mode='w+',dtype=np.float64,shape=(n,8));written[role_id]=np.zeros(n,bool);uids[role_id]=np.load(HERE/'metadata'/(role+'.npz'))['uid']
  for cap in selected:
   f=HERE/PHASE/cap/'FEATURES.npz';assert sha(f)==reports[cap]['features_sha256'];a=np.load(f)
   for role_id in arrays:
    take=a['role']==role_id;ix=a['index'][take];assert not np.any(written[role_id][ix]) and np.array_equal(a['uid'][take],uids[role_id][ix]);arrays[role_id][ix]=a['features'][take];written[role_id][ix]=True
  for role_id,arr in arrays.items():assert np.all(written[role_id]);arr.flush()
  del arrays
  result['arrays']={role:dict(sha256=sha(dest/(role+'.npy')),bytes=(dest/(role+'.npy')).stat().st_size) for role in ['LEARN','CIC_DEV','UNSW_DEV']}
  assert result['queries']==sum(v['rows'] for v in metadata['roles'].values())
 write(PHASE+'_RESULT.json',result);progress('PASS',1,1)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--phase',choices=['FEATURE_PREFLIGHT','FEATURE_BUILD'],required=True);a=p.parse_args();PHASE=a.phase
 try:main()
 except Exception as e:write(PHASE+'_STOP.json',dict(status='FAIL',error=repr(e),traceback=traceback.format_exc()));raise
