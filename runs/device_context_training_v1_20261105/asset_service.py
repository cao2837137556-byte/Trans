"""Existing-tunnel, append-only pinned asset staging; no authentication or SSH creation."""
import hashlib,hmac,json,os,subprocess,threading,time
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
HERE=Path(__file__).resolve().parent;PROJECT=HERE.parents[1];CFG=json.loads((HERE/'.private.json').read_text());LOCK=threading.Lock()
def read(n):
 p=HERE/n;return json.loads(p.read_text()) if p.exists() else None
def write(n,v):
 p=HERE/n;t=p.with_suffix('.tmp');t.write_text(json.dumps(v));t.replace(p)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
 return h.hexdigest()
def inventory():
 try:
  plan=read('ASSET_PLAN.json');wanted={v['name'] for v in plan.values()};sizes={v['bytes'] for v in plan.values()};found={};visited=0;start=time.monotonic()
  for parent,dirs,files in os.walk(PROJECT):
   dirs[:]=[d for d in dirs if d not in ['.git','__pycache__','node_modules','.venv','site-packages','vendor_py311_v1','numpy201'] and not d.startswith('.')]
   for name in files:
    visited+=1
    if name in wanted:
     p=Path(parent)/name
     if p.is_file() and p.stat().st_size in sizes:found.setdefault((name,p.stat().st_size),[]).append(str(p))
   if time.monotonic()-start>180:raise RuntimeError('INVENTORY_TIME_CAP')
  result={k:dict(candidates=found.get((v['name'],v['bytes']),[]),bytes=v['bytes'],sha256=v['sha256']) for k,v in plan.items()}
  write('INVENTORY.json',dict(status='PASS_METADATA_ONLY',files=result,visited=visited,seconds=time.monotonic()-start));write('STATE.json',dict(stage='INVENTORY_READY',training_jobs=0))
 except Exception as e:write('STATE.json',dict(stage='STOP',error=repr(e)))
def state():
 d=read('STATE.json') or dict(stage='WAITING_PLAN');d['inventory_ready']=(HERE/'INVENTORY.json').exists();return d
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def route(self):
  p=self.path.split('/');assert len(p)>=3 and hmac.compare_digest(p[1],CFG['token']);return p[2:]
 def reply(self,v):
  b=json.dumps(v).encode();self.send_response(200);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  try:
   p=self.route();assert len(p)==1
   if p[0]=='state':return self.reply(state())
   if p[0]=='inventory':return self.reply(read('INVENTORY.json'))
   if p[0]=='offsets':return self.reply({k:(HERE/'assets'/(k+'.part')).stat().st_size if (HERE/'assets'/(k+'.part')).exists() else 0 for k in read('ASSET_PLAN.json')})
   raise ValueError('ACTION')
  except Exception as e:self.send_error(409,type(e).__name__)
 def do_POST(self):
  try:
   p=self.route();n=int(self.headers['Content-Length']);assert 0<=n<=8*1024**2;b=self.rfile.read(n);assert len(b)==n
   with LOCK:
    if p==['plan']:
     assert not (HERE/'ASSET_PLAN.json').exists();plan=json.loads(b)
     for k,v in plan.items():assert k.isalnum() and len(v['sha256'])==64 and v['bytes']>0 and '/' not in v['name'] and '\\' not in v['name']
     write('ASSET_PLAN.json',plan);write('STATE.json',dict(stage='INVENTORY_RUNNING'));threading.Thread(target=inventory,daemon=True).start();return self.reply(dict(status='STARTED'))
    if len(p)==2 and p[0]=='upload':
     key=p[1];spec=read('ASSET_PLAN.json')[key];folder=HERE/'assets';folder.mkdir(exist_ok=True);target=folder/(key+'.part');offset=target.stat().st_size if target.exists() else 0
     assert int(self.headers['X-Offset'])==offset and offset+n<=spec['bytes'] and hashlib.sha256(b).hexdigest()==self.headers['X-Chunk-SHA256']
     with target.open('ab') as f:f.write(b)
     return self.reply(dict(offset=offset+n))
    raise ValueError('ACTION')
  except Exception as e:self.send_error(409,type(e).__name__)
if __name__=='__main__':
 s=ThreadingHTTPServer(('127.0.0.1',18841),Handler);timer=threading.Timer(24*3600,s.shutdown);timer.daemon=True;timer.start();s.serve_forever()
