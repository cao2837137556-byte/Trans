import hashlib,json,os,time,sys
from pathlib import Path
import psutil
import numpy as np
HERE=Path(__file__).resolve().parent
PROJECT=HERE.parents[1]
TRAIN=PROJECT/'runs/device_context_head_training_v2_20261105'
SOURCE=PROJECT/'runs/device_context_training_v2_20261105'
ROOT=PROJECT/'runs/edge_formal_evaluation_resume_v2_20261104/checkout'
EDGE=PROJECT/'runs/edge_formal_evaluation_resume_v2_20261104/outputs/gate_182089'
PHASE=os.environ.get('CONTEXT_EVAL_PHASE','PREFLIGHT')
PINS={}
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(n,v):
 p=HERE/n;p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix('.tmp');t.write_text(json.dumps(v,indent=2,allow_nan=False));t.replace(p)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
 return h.hexdigest()
def pin(p,digest):
 p=Path(p);assert sha(p)==digest,'SHA:'+str(p);PINS[str(p)]=digest;return p
def progress(stage,done=0,total=1,**kw):
 rss=psutil.Process().memory_info().rss;assert rss<7*1024**3,'RSS_LIMIT'
 write(PHASE+'_PROGRESS.json',dict(stage=stage,done=int(done),total=int(total),rss_mib=rss/2**20,updated_unix=time.time(),**kw))
def verify():
 for n,h in read(HERE/'.private.json')['pins'].items():pin(HERE/n,h)
 for n,h in read(HERE/'TRAINING_DELIVERY.json')['pins'].items():pin(TRAIN/n,h)
 for n,h in read(HERE/'LEGACY_RUNTIME_PINS.json').items():pin(ROOT/n,h)
 for n,h in read(HERE/'SOURCE_FEATURE_ACCEPTANCE.json')['receipt_sha256'].items():pin(SOURCE/n,h)
 a=read(HERE/'FINAL_TRAINING_ACCEPTANCE.json');assert a['result']=='PASS' and a['new_heads']==9
 for n,h in a['receipt_sha256'].items():pin(TRAIN/n,h)
 return a
def extra_normalized(values):
 norm=np.load(pin(TRAIN/'context_normalizer.npz',read(HERE/'NORMALIZER.json')['sha256']))
 out=((np.log1p(values)-norm['mean'])/norm['scale']).astype(np.float32);assert np.isfinite(out).all();return out
def models():
 sys.path.insert(0,str(TRAIN));import torch,context_core as k
 torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
 old=read(HERE/'OLD_ASSETS.json');freeze=read(HERE/'METHOD_FREEZE.json');accepted=read(HERE/'FINAL_TRAINING_ACCEPTANCE.json')
 a=np.load(pin(ROOT/old['calibration']['normalizer']['path'],old['calibration']['normalizer']['sha256']));norm=a['mean'],a['scale'];result={}
 for arm,d in [('OLD782',782),('REFIT782',782),('STATS8',8),('FUSION790',790)]:
  nets=[];cuts=[];scales=[]
  for j,seed in enumerate((27,127,227)):
   if arm=='OLD782':
    s=old['heads']['endpoints'][str(seed)]['head.npz'];path=pin(ROOT/s['path'],s['sha256']);cut=freeze['calibration']['cuts']['cuts'][j];scale=freeze['calibration']['scales']['scales'][j]
   else:
    s=accepted['heads'][arm+'_'+str(seed)];path=pin(TRAIN/'heads'/(arm+'_'+str(seed))/'train/head.npz',s['head_sha256']);cut=s['cut'];scale=s['scale']
   model=k.classifier(seed,d);saved=np.load(path);model.load_state_dict({key:torch.from_numpy(saved[key].copy()) for key in saved.files});model.eval().requires_grad_(False);nets.append(model);cuts.append(cut);scales.append(scale)
  ec=freeze['calibration']['cuts']['ensemble_cut'] if arm=='OLD782' else accepted['ensembles'][arm]['cut']
  result[arm]=dict(models=nets,dimension=d,cuts=np.asarray(cuts+[ec]),scales=np.asarray(scales))
 return k,norm,result
def score(k,norm,arm,z,q,context):
 out=[]
 class Progress:
  def tick(self,d,n):
   if d%16384==0 or d==n:progress('MODEL_FORWARD',d,n)
 for model in arm['models']:out.append(k.scores(model,(z,context),q,np.arange(len(q)),norm,arm['dimension'],Progress()))
 return np.column_stack(out).astype(np.float64)
def four(x):return np.column_stack((x,np.stack([x[:,j] for j in range(3)]).mean(0,dtype=np.float64)))
def correction(raw,support,q,scales):
 assert np.isfinite(support).all() and np.all((support>=0)&(support<=1))
 g=np.where(support>0,1.-np.power(1.-support,3),0.);x=raw.copy()
 for j,scale in enumerate(scales):x[g>0,j]=raw[g>0,j]-(.25*scale)*g[g>0]
 guard=(q[:,0]==1)&(q[:,2]==1)&(q[:,5]==0);x[guard]=raw[guard]
 return x
