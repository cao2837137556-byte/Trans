"""Fixed-model evaluation. Scientific failures are reported, never used to select arms."""
import argparse,os,time,traceback,gc,gzip,json
args=argparse.ArgumentParser();args.add_argument('--phase',required=True,choices=['PREFLIGHT','CONTEXT','AB','EDGE']);args=args.parse_args()
os.environ['CONTEXT_EVAL_PHASE']=args.phase
from common import *
import inputs,metrics,edge_context,reporting

def annotate(rows):
 for r in rows:
  r.setdefault('scenario',r.get('activity',r.get('source_role','UNKNOWN')))
  r.setdefault('source_role','NORMAL' if r['label']==0 else r['scenario'])

def forward(data,k,norm,arms):
 predictions={};scores={};margins={}
 for name,arm in arms.items():
  raw=score(k,norm,arm,data['z'],data['q'],data['context']);full=four(raw);scores[name]={'RAW':full};predictions[name]={'RAW':full>arm['cuts']}
  if name!='STATS8':
   corrected=four(correction(raw,data['support'],data['q'],arm['scales']));assert np.all(corrected<=full+1e-12)
   scores[name]['C5_P3']=corrected;predictions[name]['C5_P3']=corrected>arm['cuts']
   margins[name]=metrics.margins(data['rows'],full,corrected,arm['cuts'],arm['scales'],np.arange(len(full)))
 old=data['old_raw'];old=old[:,:3]
 delta=float(np.max(np.abs(scores['OLD782']['RAW'][:,:3]-old)))
 assert delta<=.002,'OLD_FORWARD_PARITY:'+str(delta)
 expected=data.get('old_raw_pred',four(old)>arms['OLD782']['cuts'])
 assert np.array_equal(predictions['OLD782']['RAW'],expected),'OLD_RAW_DECISIONS'
 assert np.array_equal(predictions['OLD782']['C5_P3'],data['old_c5_pred']),'OLD_C5_DECISIONS'
 return predictions,scores,margins,delta

def save_scores(name,data,scores):
 p=HERE/(name+'_SCORES.npz');np.savez(p,uid=np.asarray([r['uid'] for r in data['rows']]),**{a+'_'+m:v for a,methods in scores.items() for m,v in methods.items()})
 return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)

def subset(data,ix):
 return {key:([v[i] for i in ix] if key=='rows' else v[ix]) for key,v in data.items() if key in ['rows','z','q','context','support','old_raw','old_raw_pred','old_c5_pred']}

def cal_report(k,norm,arms):
 plan=read(SOURCE/'ASSET_PLAN.json');resolved=read(SOURCE/'RESOLVED_ASSETS.json');paths={}
 for key,v in plan.items():
  if (v['kind'],v['name']) in [('e3','LEARN.npy'),('prepared','LEARN_q.npy'),('prepared','LEARN.jsonl.gz')]:paths[v['name']]=pin(resolved[key],v['sha256'])
 ix=np.load(SOURCE/'metadata/CAL.npy');wanted=set(map(int,ix));rows=[]
 with gzip.open(paths['LEARN.jsonl.gz'],'rt') as f:
  for i,line in enumerate(f):
   if i in wanted:rows.append(json.loads(line))
 assert np.all(ix[:-1]<ix[1:]) and len(rows)==len(ix)==148819
 assert k.c.uid_sha(r['uid'] for r in rows)==read(HERE/'TRAINING_SPEC_FROZEN.json')['data_identity']['CAL']['uid_sha256']
 annotate(rows);z=np.load(paths['LEARN.npy'],mmap_mode='r')[ix];q=np.load(paths['LEARN_q.npy'],mmap_mode='r')[ix];ctx=np.zeros((len(ix),8),np.float32)
 old=four(score(k,norm,arms['OLD782'],z,q,ctx));pred={'OLD782':{'RAW':old>arms['OLD782']['cuts']}};stored={}
 for name in ('REFIT782','STATS8','FUSION790'):
  values=[]
  for seed in (27,127,227):
   receipt=read(TRAIN/('TRAIN_'+name+'_'+str(seed)+'_RESULT.json'));path=TRAIN/'heads'/(name+'_'+str(seed))/'calibration/cal_logits.npy'
   digest=receipt['calibration']['logits_sha256']['cal'];values.append(np.load(pin(path,digest)))
  logits=four(np.column_stack(values));assert len(logits)==len(rows);pred[name]={'RAW':logits>arms[name]['cuts']}
 labels=np.asarray([r['label'] for r in rows]);w=np.zeros(len(rows))
 for label in (0,1):
  take=np.flatnonzero(labels==label);w[take]=.5*k.class_weights([rows[i] for i in take])
 report=metrics.summarize(rows,pred,{'primary':(np.arange(len(rows)),w)});write('CAL_METRICS.json',report)
 return dict(rows=len(rows),gates=metrics.gates(report,cal=True),metrics_sha256=sha(HERE/'CAL_METRICS.json'))

def main():
 start=time.monotonic();verify();progress('IDENTITY_VERIFIED')
 if args.phase=='CONTEXT':
  edge_context.build();result=read(HERE/'CONTEXT_RESULT.json')
 else:
  k,norm,arms=models()
  if args.phase=='PREFLIGHT':
   checks={}
   for pool in ('CIC_DEV','UNSW_DEV'):
    d=inputs.ab(pool);annotate(d['rows']);chosen={}
    for i,r in enumerate(d['rows']):chosen.setdefault((r['device'],r['protocol'],r['label']),i)
    small=subset(d,np.asarray(sorted(chosen.values())));pred,_,_,error=forward(small,k,norm,arms);metrics.summarize(small['rows'],pred,{'primary':(np.arange(len(small['rows'])),np.ones(len(small['rows']))) });checks[pool]=dict(rows=len(small['rows']),old_forward_error=error);del d,small;gc.collect()
   edge_context.build(small=True);d=inputs.edge();annotate(d['rows'])
   from preflight_encoder import run
   checks['real_encoder_distance']=run(d,norm)
   ix,ctx=edge_context.join(d['rows'],small=True);small=subset(d,ix);small['context']=ctx;pred,_,_,error=forward(small,k,norm,arms)
   population=read(ROOT/'runs/edge_formal_execution_v4_20261104/POPULATION_TEMPORAL_CENSUS.json')
   for arm,pp in pred.items():reporting.summarise(small['rows'],pp,population,prediction_uids={m:[r['uid'] for r in small['rows']] for m in pp},independent_methods=())
   checks['edge']=dict(rows=len(ix),old_forward_error=error);result=dict(status='PASS',checks=checks,external_performance_disclosed=False)
  elif args.phase=='AB':
   result=dict(status='PASS',pools={})
   for pool in ('CIC_DEV','UNSW_DEV'):
    d=inputs.ab(pool);annotate(d['rows']);pred,scores,margin,error=forward(d,k,norm,arms)
    report=metrics.summarize(d['rows'],pred,d['views']);write(pool+'_METRICS.json',report);write(pool+'_MARGINS.json',margin)
    result['pools'][pool]=dict(rows=len(d['rows']),primary_rows=len(d['views']['primary'][0]),old_forward_error=error,gates=metrics.gates(report),metrics_sha256=sha(HERE/(pool+'_METRICS.json')),margin_sha256=sha(HERE/(pool+'_MARGINS.json')),scores=save_scores(pool,d,scores),primary=report['primary'])
    del d,pred,scores,margin,report;gc.collect()
   result['source_cal']=cal_report(k,norm,arms)
  else:
   d=inputs.edge();annotate(d['rows']);ix,d['context']=edge_context.join(d['rows']);assert np.array_equal(ix,np.arange(60000))
   pred,scores,margin,error=forward(d,k,norm,arms);population=read(ROOT/'runs/edge_formal_execution_v4_20261104/POPULATION_TEMPORAL_CENSUS.json');reports={}
   for name,pp in pred.items():
    r=reporting.summarise(d['rows'],pp,population=population,prediction_uids={m:[r['uid'] for r in d['rows']] for m in pp},raw_name='RAW',independent_methods=())
    write(name+'_EDGE_METRICS.json',r);r.pop('ordered_query_uids',None);reports[name]=r
   write('EDGE_MARGINS.json',margin)
   result=dict(status='PASS',rows=60000,old_forward_error=error,arms=reports,margins=margin,scores=save_scores('EDGE',d,scores),interpretation='Consumed diagnostic evaluation; all fixed arms; no tuning')
 result.update(seconds=time.monotonic()-start,phase=args.phase,pins_verified=len(PINS));write(args.phase+'_RESULT.json',result);write(args.phase+'_PINS.json',PINS);progress(args.phase+'_COMPLETE',1,1)

if __name__=='__main__':
 try:main()
 except BaseException as e:
  write(args.phase+'_STOP.json',dict(status='STOP',error=type(e).__name__+':'+str(e),traceback=traceback.format_exc()));raise
