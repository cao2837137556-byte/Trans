"""One ordinary bounded wait/read; no model polling or experiment mutation."""
import json
from pathlib import Path
import execute_source_validation as run

CODE = r'''import json,pathlib,subprocess,time,datetime
root=pathlib.Path('/srv/paper04/learned_onboarding_memory_validation_20261024_v4')
unit='paper04-onboarding-memory-validation-20261024-v4'
names=['source_validation/SOURCE_VALIDATION.json','source_validation/VALIDATION_EXCEPTION.json','source_validation/RESOURCE_EXCEPTION.json']
deadline=time.monotonic()+3800
while time.monotonic()<deadline:
 if any((root/name).is_file() for name in names):break
 q=subprocess.run(['systemctl','show',unit,'--property=ActiveState','--value'],capture_output=True,text=True,timeout=5)
 if q.stdout.strip() not in ('active','activating'):break
 time.sleep(15)
result={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'ordinary_program_wait':True,'original_experiment_restarted':False,'files':{}}
for name in names+['source_validation/status.json','test_state/stages/tests/tests.json','test_state/stages/tests/adapter_validation.json']:
 p=root/name
 if p.is_file():result['files'][name]=json.loads(p.read_text())
q=subprocess.run(['systemctl','show',unit,'--property=ActiveState,SubState,Result,MainPID,ExecMainStatus,NRestarts,MemoryPeak'],capture_output=True,text=True,timeout=5)
result['unit']=q.stdout
for name in ['service.stdout.log','service.stderr.log','tests.log']:
 p=root/name
 if p.is_file():
  with p.open('rb') as stream:
   stream.seek(max(0,p.stat().st_size-10000));result[name]=stream.read().decode('utf-8','replace')
print(json.dumps(result))
'''

if __name__ == '__main__':
    folder = run.HERE/'remote_validation'
    folder.mkdir(exist_ok=False)
    result = run.ssh(CODE, timeout=3900)
    (folder/'COMPLETION_SNAPSHOT.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    for name, value in result['files'].items():
        (folder/Path(name).name).write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')
    final = result['files'].get('source_validation/SOURCE_VALIDATION.json')
    print(json.dumps(dict(source_validation_status=final.get('status') if final else 'EXCEPTION_OR_NO_COMPLETE',
        peak_process_tree_rss=final.get('peak_process_tree_rss') if final else None,
        elapsed_seconds=final.get('elapsed_seconds') if final else None,
        files=list(result['files']),unit=result['unit'])))
