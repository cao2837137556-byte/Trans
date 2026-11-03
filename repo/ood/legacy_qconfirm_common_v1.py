"""Explicit once-only confirmation scope; no protected asset reads on import."""
from pathlib import Path
import gzip,json,time,os
import numpy as np
import legacy_qref_common_v1 as c

DESIGN='runs/legacy_qref_device_confirmation_design_v1_20260923'
DESIGN_SHA='092d57859cc36b40ec241281355bca1a9861d38e355755a8d5e3511fcf7efc47'
IMPLEMENTATION='runs/legacy_qref_device_confirmation_implementation_v1_20260923'
STAGES=['HOLDOUT_FEATURES','FROZEN_EVALUATION','REPORT']

def recipe(root):
    return c.read(c.pin(c.confined(root,DESIGN+'/confirmation_recipe.json'),DESIGN_SHA))

def authorize(scope,root,out,explicit,worker=False):
    # All checks here are structural; callers must run these before opening any assets.
    c.require(explicit and scope.get('execution_authorized') is True,'CONFIRMATION_NOT_AUTHORIZED')
    c.require(scope.get('recipe_sha256')==DESIGN_SHA and scope.get('stages')==STAGES,'CONFIRMATION_SCOPE')
    c.require(scope.get('training') is False and scope.get('calibration') is False and
              scope.get('retries')==0 and scope.get('holdout_owner')=='THIS_HPC_JOB_ONLY','CONFIRMATION_BOUNDARY')
    root=Path(root).resolve();out=Path(out).resolve()
    c.require(Path(scope['root']).resolve()==root and Path(scope['output']).resolve()==out,'SCOPE_PATH')
    c.require(out.parent==root/'runs','OUTPUT_NOT_TOP_LEVEL_RUN')
    if not worker:c.require(not out.exists(),'OUTPUT_EXISTS_NO_RETRY')
    c.require(1<=scope.get('workers',0)<=8,'WORKERS')
    return out

def implementation_check(root):
    folder=Path(root)/IMPLEMENTATION;c.verify(folder)
    a=c.read(folder/'acceptance.json')
    c.require(a['status']=='PASS' and a['real_query_reads']==a['real_model_forwards']==a['real_optimizer_updates']==0,'IMPLEMENTATION_NOT_ACCEPTED')
    for n,h in c.read(folder/'code_pins.json').items():c.pin(c.confined(root,n),h)
    for n,h in c.read(folder/'input_pins.json').items():c.pin(c.confined(root,n),h)
    return recipe(root)

class Progress(c.Progress):
    def __init__(self,out,hours=72):
        self.work_done=0;self.work_total=0;self.last_emit=0;self.heldout_opened=False
        super().__init__(out,0,hours=hours,ram_gib=128,disk_gib=16)
    def guard(self):
        c.require(not (self.out/'STOP_REQUESTED').exists(),'USER_STOP_REQUESTED')
        now=time.monotonic()
        c.require(now<self.deadline,'WALL_TIME_LIMIT')
        c.require(c.rss_bytes()<=self.ram,'MEMORY_LIMIT')
        if now-self.last_disk>=30:
            used=0
            for path in self.out.rglob('*'):
                try:
                    if path.is_file():used+=path.stat().st_size
                except FileNotFoundError:
                    # A worker may rename its unique .pending status between enumeration and stat.
                    continue
            c.require(used<=self.disk,'OUTPUT_DISK_LIMIT');self.last_disk=now
    def emit(self,status='RUNNING',**extra):
        self.sequence+=1
        value=dict(status=status,stage=self.stage,completed_updates=0,total_updates=0,
                   completed_stages=self.completed[:],elapsed_seconds=time.monotonic()-self.start,
                   retries=0,heldout_opened=self.heldout_opened,**extra)
        target=self.out/'progress'/('%08d.json'%self.sequence);tmp=target.with_suffix('.pending')
        c.write(tmp,value);os.rename(str(tmp),str(target));return value
    def tick(self,updates=0,**extra):
        c.require(updates==0,'OPTIMIZER_FORBIDDEN');self.guard();self.work_done+=1
        now=time.monotonic()
        if now-self.last_emit>=5 or self.work_done==self.work_total:
            self.emit(work_done=self.work_done,work_total=self.work_total,**extra);self.last_emit=now
    def begin(self,stage,total):
        self.stage=stage;self.work_done=0;self.work_total=total;self.emit(work_done=0,work_total=total)

def dump_rows(path,rows):
    with gzip.open(path,'wt',encoding='utf-8') as f:
        for r in rows:f.write(json.dumps(r,separators=(',',':'),allow_nan=False)+'\n')

def load_source(root,spec):
    values=c.rows(c.pin(c.confined(root,spec['path']),spec['sha256']))
    c.require(len(values)==spec['rows'] and c.uid_sha(r['uid'] for r in values)==spec['sorted_uid_lines_sha256'],'MANIFEST_IDENTITY')
    c.require(len({r['uid'] for r in values})==len(values),'DUPLICATE_UID')
    return values

def validate_metadata(plan,rows,refs):
    from legacy_qref_data_v1 import metadata_valid,class_weights
    metadata_valid(rows,{'DEVICE_HOLDOUT'});metadata_valid(refs,{'DEVICE_HOLDOUT'},True)
    c.require(len(rows)==plan['data']['query_rows'] and len(refs)==plan['data']['own_reference_rows'],'ROW_COUNT')
    c.require(not {r['uid'] for r in rows}&{r['uid'] for r in refs},'REFERENCE_QUERY_UID_OVERLAP')
    c.require(len({r['component_id'] for r in refs})==len(refs),'REFERENCE_COMPONENT_DUPLICATE')
    devices={d['device']:d for d in plan['data']['devices']}
    c.require({r['device'] for r in rows}==set(devices)=={r['device'] for r in refs},'DEVICE_SET')
    end={}
    for r in refs:c.require(end.setdefault(r['device'],r['reference_end'])==r['reference_end'],'REFERENCE_END')
    for r in rows:
        c.require(r['use']!='REFERENCE' and r['reference_end']==end[r['device']]<r['timestamp'],'QUERY_REFERENCE_TIME')
    for name,d in devices.items():
        rr=[r for r in rows if r['device']==name];ss=[r for r in refs if r['device']==name]
        c.require(sum(r['label']==0 for r in rr)==d['normal'] and sum(r['label']==1 for r in rr)==d['attack'],'DEVICE_CLASS_COUNT')
        c.require(len(ss)==d['references'],'REFERENCE_COUNT')
        for protocol in (6,17):c.require(sum(r['protocol']==protocol for r in ss)==d['reference_components_by_protocol'][str(protocol)],'REFERENCE_PROTOCOL_COUNT')
    # Packet identity at identical timestamps cannot cross reference/query roles.
    keys=lambda rr:{(r['packet_sha256'],r['timestamp']) for r in rr if 'packet_sha256' in r}
    c.require(not keys(rows)&keys(refs),'PACKET_TIME_OVERLAP')
    for label in (0,1):
        rr=[r for r in rows if r['label']==label];w=class_weights(rr)
        c.require(np.allclose(w,[1/r['label_metric_weight_denominator'] for r in rr],rtol=0,atol=1e-15),'WEIGHT_DRIFT')

def validate_controls(plan,refs):
    by={r['uid']:r for r in refs};c.require(len(by)==len(refs),'DUPLICATE_REFERENCE_UID')
    for control in plan['arms']['controls']:
        if control['status']!='MATCHED':continue
        own=[by[u] for u in control['correct_reference_uids']];wrong=[by[u] for u in control['wrong_reference_uids']]
        k=control['count'];c.require(k>=2 and len(own)==len(wrong)==k,'CONTROL_COUNT')
        for rr in (own,wrong):
            c.require(len({r['component_id'] for r in rr})==k and all(r['protocol']==control['protocol'] and r['label']==0 and r['use']=='REFERENCE' for r in rr),'CONTROL_PROTOCOL_COMPONENT')
        c.require(all(r['device']==control['device'] and r['partition']=='DEVICE_HOLDOUT' for r in own),'CONTROL_OWN')
        c.require(all(r['device']==control['donor'] and r['partition']=='LEARN' and r['reference_end']<control['recipient_observation_start'] for r in wrong),'CONTROL_DONOR_TIME_ROLE')

def read_donors(root,cache,plan,oldrecipe):
    """Load only pinned REFERENCE rows/array of existing LEARN_DEV cache."""
    spec=oldrecipe['data']['cache']['REFERENCE'];cache=Path(cache)
    descriptor=c.read(cache/'cache.json');c.require(descriptor['roles']['REFERENCE']==spec,'DONOR_CACHE_IDENTITY')
    rr=c.rows(c.pin(c.confined(cache,spec['metadata']),spec['metadata_sha256']))
    arr=np.load(c.pin(c.confined(cache,spec['features']),spec['features_sha256']),allow_pickle=False,mmap_mode='r')
    c.require(len(rr)==spec['rows'] and arr.shape==(len(rr),768) and arr.dtype==np.float32,'DONOR_SCHEMA')
    c.require(c.uid_sha(r['uid'] for r in rr)==spec['uid_sha256'],'DONOR_UIDS')
    ids={u for ctrl in plan['arms']['controls'] if ctrl['status']=='MATCHED' for u in ctrl['wrong_reference_uids']}
    ix=[i for i,r in enumerate(rr) if r['uid'] in ids]
    c.require({rr[i]['uid'] for i in ix}==ids and all(rr[i]['partition']=='LEARN' for i in ix),'DONOR_ROLE')
    values=np.array(arr[ix]);c.require(bool(np.isfinite(values).all()),'DONOR_NONFINITE')
    return [rr[i] for i in ix],values
