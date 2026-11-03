import datetime,hashlib,json,pathlib,psutil,subprocess
root=pathlib.Path('/srv/paper04/learned_onboarding_20261024_v4')
package=root/'runs/learned_onboarding_v1_20261023';unit='paper04-learned-onboarding-20261024-v4'
assert not (root/'state').exists() and not (package/'results').exists(),'FRESH_OUTPUTS_REQUIRED'
assert (root/'DEPLOYMENT_VERIFIED.json').is_file(),'DEPLOYMENT_NOT_VERIFIED'
assert (root/'inputs/source_head_archive/BACKUP_INDEX.json').is_file(),'SOURCE_ARCHIVE_NOT_READY'
manifest=json.loads((root/'DEPLOYMENT_MANIFEST.json').read_text())
for name,item in manifest['files'].items():
 path=root/name
 assert hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256'] and path.stat().st_size==item['bytes'],name
active=subprocess.run(['systemctl','list-units','--all','--no-legend','--plain','--state=running,activating,deactivating','paper04-*'],capture_output=True,text=True,check=True).stdout.strip()
assert not active,'PAPER04_SLOT_BECAME_BUSY:'+active
state=subprocess.run(['systemctl','show',unit,'--property=LoadState','--value'],capture_output=True,text=True)
assert state.stdout.strip()=='not-found','V4_UNIT_ALREADY_EXISTS'
workers=[]
for process in psutil.process_iter(['pid','name','cmdline']):
 try:
  args=process.info['cmdline'] or [];command=' '.join(args)
  reader='-c' in args and 'reference_forward' in command and 'modern_heads' in command
  if 'python' in (process.info['name'] or '').lower() and '/srv/paper04/' in command and not reader:workers.append(dict(pid=process.pid,command=command))
 except (psutil.NoSuchProcess,psutil.AccessDenied):pass
assert not workers,'PAPER04_WORKER_SLOT_BUSY:'+repr(workers)
slot=dict(status='EXCLUSIVE_EXISTING_INSTANCE_READY',at=datetime.datetime.now(datetime.timezone.utc).isoformat(),active_units=active,workers=workers,memory_available=psutil.virtual_memory().available,disk_free=psutil.disk_usage(root).free)
assert slot['memory_available']>=16*1024**3 and slot['disk_free']>=12*1024**3,'RESOURCE_SLOT_NOT_READY'
with (root/'EXECUTION_SLOT_RECEIPT.json').open('x') as stream:json.dump(slot,stream,indent=2)
command=['systemd-run','--unit='+unit,'--description=Paper04 learned onboarding V4 memory repair','--property=Type=exec','--property=Restart=no','--property=KillMode=control-group','--property=MemoryAccounting=yes','--property=MemoryMax=16G','--property=MemorySwapMax=0','--property=CPUAccounting=yes','--property=CPUQuota=800%','--property=WorkingDirectory='+str(root),'--property=StandardOutput=append:'+str(root/'service.stdout.log'),'--property=StandardError=append:'+str(root/'service.stderr.log')]
command+=['--setenv='+key+'=4' for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS')]
command+=['--setenv=PYTHONUNBUFFERED=1','--setenv=PYTHONDONTWRITEBYTECODE=1','/opt/paper04-venv/bin/python','-u',str(package/'deployment_20261024/run_chain.py'),'--root',str(root),'--config',str(package/'deployment_20261024/remote_config.json'),'--state',str(root/'state'),'--source-assets',str(package/'results/source_assets')]
completed=subprocess.run(command,capture_output=True,text=True,timeout=30)
receipt=dict(status='SERVICE_SUBMITTED' if completed.returncode==0 else 'LAUNCH_EXCEPTION_STOP',unit=unit,at=datetime.datetime.now(datetime.timezone.utc).isoformat(),command=command,returncode=completed.returncode,stdout=completed.stdout,stderr=completed.stderr,slot=slot,automatic_retry=False)
with (root/'LAUNCH_RECEIPT.json').open('x') as stream:json.dump(receipt,stream,indent=2)
assert completed.returncode==0,'SYSTEMD_LAUNCH_FAILED_NO_RETRY:'+completed.stderr
query=subprocess.run(['systemctl','show',unit,'--property=LoadState,ActiveState,SubState,MainPID,InvocationID,MemoryMax,MemorySwapMax,CPUQuotaPerSecUSec,Restart,KillMode,Environment'],capture_output=True,text=True,check=True,timeout=10)
properties=dict(line.split('=',1) for line in query.stdout.splitlines() if '=' in line)
assert properties['MemoryMax']==str(16*1024**3) and properties['MemorySwapMax']=='0','SYSTEMD_MEMORY_LIMIT'
assert properties['CPUQuotaPerSecUSec']=='8s' and properties['Restart']=='no' and properties['KillMode']=='control-group','SYSTEMD_RESOURCE_POLICY'
limits=dict(status='PASS',properties=properties)
with (root/'SERVICE_HARD_LIMIT_RECEIPT.json').open('x') as stream:json.dump(limits,stream,indent=2)
print(json.dumps(dict(launch=receipt,hard_limits=limits)))
