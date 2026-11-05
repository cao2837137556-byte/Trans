"""Ordinary bounded asset staging, only inputs absent by name/size are uploaded."""
import hashlib,http.client,json,time
from pathlib import Path
import client
H=client.HERE;t=client.t
def progress(stage,**kw):t.write(H/'PROGRESS.json',dict(stage=stage,updated_utc=t.utc(),**kw))
def main():
 plan=t.read(H/'ASSET_PLAN.json');paths=t.read(H/'.private/local_paths.json');deadline=time.monotonic()+240
 while True:
  s=client.request('state');assert s['stage']!='STOP',s
  if s['inventory_ready']:break
  assert time.monotonic()<deadline,'INVENTORY_DEADLINE';progress('HPC_ASSET_INVENTORY');time.sleep(5)
 inv=client.request('inventory');t.write(H/'INVENTORY.json',inv);missing=[k for k,v in inv['files'].items() if not v['candidates']];total=sum(plan[k]['bytes'] for k in missing);offsets=client.request('offsets');done=sum(offsets[k] for k in missing);initial=done;start=time.monotonic();verified={}
 for key in missing:
  spec=plan[key];path=Path(paths[key]);progress('LOCAL_SHA_BEFORE_UPLOAD',file=spec['name'],done=done,total=total,reuse_candidates=len(plan)-len(missing));assert path.stat().st_size==spec['bytes'] and t.sha(path)==spec['sha256'],'LOCAL_PIN:'+key;verified[key]=spec['sha256']
  with path.open('rb') as f:
   retry=0
   while offsets[key]<spec['bytes']:
    assert time.monotonic()-start<12*3600,'TRANSFER_WALL_CAP';offset=offsets[key];f.seek(offset);b=f.read(min(4*1024**2,spec['bytes']-offset))
    try:
     r=client.request('upload/'+key,b,{'X-Offset':str(offset),'X-Chunk-SHA256':hashlib.sha256(b).hexdigest()});assert r['offset']==offset+len(b);offsets[key]=r['offset'];done+=len(b);retry=0
    except (OSError,http.client.HTTPException):
     retry+=1;assert retry<=3,'TRANSFER_RETRY_CAP';remote=client.request('offsets');done+=remote[key]-offsets[key];offsets[key]=remote[key]
    progress('ASSET_UPLOAD',file=spec['name'],done=done,total=total,reuse_candidates=len(plan)-len(missing),bytes_per_second=(done-initial)/max(.01,time.monotonic()-start))
 receipt=dict(status='STAGED_PENDING_REMOTE_SHA',files=len(plan),reused_candidates=len(plan)-len(missing),uploaded=len(missing),uploaded_bytes=total,local_verified=verified,training_submitted=False)
 t.write(H/'ASSET_TRANSFER_COMPLETE.json',receipt);progress('ASSETS_STAGED_PENDING_ADMISSION',done=total,total=total,reuse_candidates=receipt['reused_candidates'])
if __name__=='__main__':
 try:main()
 except Exception as e:progress('STOP',error=repr(e));raise
