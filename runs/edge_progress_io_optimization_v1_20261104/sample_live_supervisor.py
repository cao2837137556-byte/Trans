import os,pathlib,time,json,collections
needle='/edge_formal_gate_deployment_v2_20261103/job_entry.py'
pids=[]
for p in pathlib.Path('/proc').iterdir():
 if p.name.isdigit():
  try:
   args=(p/'cmdline').read_bytes().split(b'\0')
   if any(a.decode(errors='replace').endswith(needle) for a in args): pids.append(p)
  except (OSError,PermissionError): pass
assert len(pids)==1, str([p.name for p in pids])
p=pids[0]
def snap():
 s=(p/'stat').read_text().split(') ',1)[1].split()
 return dict(state=s[0],utime=int(s[11]),stime=int(s[12]),io=(p/'io').read_text())
start=snap();samples=[]
for i in range(24):
 x={'wchan':(p/'wchan').read_text()}
 try:
  sc=(p/'syscall').read_text().split();x['syscall']=sc[:2]
  if len(sc)>1 and sc[0] in ('1','74','75','262','257'):
   try:x['fd_path']=os.readlink(p/'fd'/str(int(sc[1],16)))
   except OSError:pass
 except OSError as e:x['syscall_error']=str(e)
 samples.append(x);time.sleep(.5)
r=dict(schema='EDGE_LIVE_READONLY_PROC_SAMPLE_V1',job_id='181645',pid=int(p.name),seconds=12,clock_ticks=os.sysconf('SC_CLK_TCK'),start=start,end=snap(),samples=samples)
text=json.dumps(r,sort_keys=True)
path=pathlib.Path('/public/home/jiangxinwei.zr/work/paper04/runs/edge_formal_gate_deployment_v2_20261103/LIVE_PROC_DIAGNOSTIC.json')
with path.open('x') as f:f.write(text+'\n')
print(text)
