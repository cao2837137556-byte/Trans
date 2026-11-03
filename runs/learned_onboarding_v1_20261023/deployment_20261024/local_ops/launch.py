"""Launch the verified new chain once on the already-authorized idle instance."""
import json
import deploy

code = r'''import datetime,json,os,pathlib,subprocess,psutil
root=pathlib.Path('/srv/paper04/learned_onboarding_20261024')
package=root/'runs/learned_onboarding_v1_20261023'
unit='paper04-learned-onboarding-20261024-v1'
def capture(args):
 return subprocess.run(args,text=True,capture_output=True,check=True).stdout.strip()
def write(name,value):
 with (root/name).open('x') as f:json.dump(value,f,indent=2)
assert os.geteuid()==0,'SYSTEMD_PERMISSION'
assert not (root/'state').exists(),'PREVIOUS_EXECUTION_EXISTS'
assert not (package/'results').exists(),'PREVIOUS_RESULTS_EXIST'
assert (root/'DEPLOYMENT_VERIFIED.json').is_file(),'DEPLOYMENT_NOT_VERIFIED'
assert (root/'inputs/source_head_archive/BACKUP_INDEX.json').is_file(),'SOURCE_ARCHIVE_NOT_READY'
active=capture(['systemctl','list-units','--all','--no-legend','--plain',
 '--state=running,activating,deactivating','paper04-*'])
assert not active,'EXISTING_ACTIVE_PAPER04_UNIT:'+active
load=capture(['systemctl','show',unit,'--property=LoadState','--value'])
assert load=='not-found','UNIT_ALREADY_EXISTS:'+load
workers=[]
for p in psutil.process_iter(['pid','name','cmdline']):
 try:
  cmd=p.info['cmdline'] or []
  if 'python' not in (p.info['name'] or '').lower():continue
  joined=' '.join(cmd)
  # The progress-page reader is a short, read-only inline Python query.
  reader='-c' in cmd and 'reference_forward' in joined and 'modern_heads' in joined
  if '/srv/paper04/' in joined and not reader:workers.append(dict(pid=p.pid,command=joined))
 except (psutil.NoSuchProcess,psutil.AccessDenied):pass
assert not workers,'EXISTING_PAPER04_PYTHON_WORKER:'+repr(workers)
memory=psutil.virtual_memory()
disk=psutil.disk_usage(str(root))
assert memory.available>=16*1024**3,'EXCLUSIVE_MEMORY_NOT_AVAILABLE'
assert disk.free>=12*1024**3,'DISK_HEADROOM'
idle=dict(status='EXCLUSIVE_EXISTING_INSTANCE_READY',at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
 active_paper04_units=active,python_workers=workers,memory_available_bytes=memory.available,
 disk_free_bytes=disk.free,frontend_extraction=False,new_resource_purchase=False,hpc_submission=False)
write('EXECUTION_SLOT_RECEIPT.json',idle)
command=['systemd-run','--unit='+unit,'--description=Paper04 learned onboarding frozen V1',
 '--property=Type=exec','--property=Restart=no','--property=KillMode=control-group',
 '--property=MemoryAccounting=yes','--property=MemoryMax=16G','--property=MemorySwapMax=0',
 '--property=CPUAccounting=yes','--property=CPUQuota=800%',
 '--property=WorkingDirectory='+str(root),
 '--property=StandardOutput=append:'+str(root/'service.stdout.log'),
 '--property=StandardError=append:'+str(root/'service.stderr.log'),
 '--setenv=OMP_NUM_THREADS=4','--setenv=MKL_NUM_THREADS=4',
 '--setenv=OPENBLAS_NUM_THREADS=4','--setenv=NUMEXPR_NUM_THREADS=4',
 '--setenv=PYTHONUNBUFFERED=1','--setenv=PYTHONDONTWRITEBYTECODE=1',
 '/opt/paper04-venv/bin/python','-u',str(package/'deployment_20261024/run_chain.py'),
 '--root',str(root),'--config',str(package/'deployment_20261024/remote_config.json'),
 '--state',str(root/'state'),'--source-assets',str(package/'results/source_assets')]
result=subprocess.run(command,text=True,capture_output=True)
receipt=dict(status='SERVICE_SUBMITTED' if result.returncode==0 else 'LAUNCH_EXCEPTION_STOP',
 unit=unit,at=datetime.datetime.now(datetime.timezone.utc).isoformat(),command=command,
 returncode=result.returncode,stdout=result.stdout,stderr=result.stderr,
 automatic_retry=False,slot=idle)
write('LAUNCH_RECEIPT.json',receipt)
print(json.dumps(receipt))
assert result.returncode==0,'SYSTEMD_LAUNCH_FAILED_NO_RETRY'
show=capture(['systemctl','show',unit,'--property=LoadState,ActiveState,SubState,MainPID,InvocationID,MemoryMax,MemorySwapMax,CPUQuotaPerSecUSec,Restart,KillMode,ControlGroup,Environment'])
values=dict(line.split('=',1) for line in show.splitlines() if '=' in line)
assert values['MemoryMax']==str(16*1024**3),'SYSTEMD_MEMORY_MAX'
assert values['MemorySwapMax']=='0','SYSTEMD_SWAP_MAX'
assert values['CPUQuotaPerSecUSec']=='8s','SYSTEMD_CPU_QUOTA'
assert values['Restart']=='no' and values['KillMode']=='control-group','SYSTEMD_RESTART_POLICY'
write('SERVICE_HARD_LIMIT_RECEIPT.json',dict(status='PASS',properties=values))
print(json.dumps(dict(status='SERVICE_HARD_LIMIT_PASS',properties=values)))
'''
deploy.remote(code, 'REMOTE_LAUNCH_RECEIPT.json', timeout=60)
