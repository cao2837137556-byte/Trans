"""One read-only completion audit and exact small-evidence download; no job actions."""
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import operate


REMOTE = r'''
import base64,datetime,hashlib,importlib.util,json,os,pathlib,psutil,subprocess
root=pathlib.Path('/srv/paper04/learned_onboarding_eval_20261025_v1')
parent=pathlib.Path('/srv/paper04/learned_onboarding_20261024_v4')
spec=importlib.util.spec_from_file_location('completion_audit_runner',root/'run_evaluation.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
contract,inventory=runner.verify_payload(root,expected_manifest_sha256)
runner.verify_inventory(parent,inventory,full=False)
chain=runner.read(root/'state/CHAIN_COMPLETE.json')
accepted=runner.read(root/'state/ACCEPTANCE.json')
assert chain['status']=='COMPLETE' and accepted['status']=='PASS','COMPLETION_RECEIPTS'
assert not (root/'state/EXCEPTION_STOP.json').exists(),'EXCEPTION_RECEIPT_PRESENT'
output=root/'results/evaluation'
seal=runner.verify_seal(output,chain['evaluation_seal_sha256'])
assert accepted['evaluation_seal_sha256']==runner.sha(output/'SEAL.json'),'ACCEPTANCE_SEAL_BINDING'
main,controls=runner.expected_cells()
summaries={tuple(p.relative_to(output/'predictions').parts[:3]):p for p in (output/'predictions').rglob('summary.json')}
assert set(summaries)==main|controls,'MATRIX'
paired=runner.read(output/'paired_summary.json')
embedded={(x['pool'],x['bank'],x['arm']):x['summary'] for x in paired['cells']}
assert set(embedded)==main,'PAIRED_MATRIX'
prior=0
for key,path in summaries.items():
 value=runner.read(path)
 if key in main:assert embedded[key]==value,'PAIRED_SUMMARY_CHANGED'
 assert all(value[k]==v for k,v in inventory['pool_identities'][key[0]].items()),'QUERY_IDENTITY'
 previous=parent/runner.PACKAGE/'results/evaluation/predictions'/path.relative_to(output/'predictions')
 if previous.is_file():
  assert runner.read(previous)==value,'PRIOR_SUMMARY_CHANGED'
  prior+=1
assert prior==accepted['prior_summaries_equal']==49,'PRIOR_SUMMARY_COUNT'
query=subprocess.run(['systemctl','show',runner.UNIT,'--property=LoadState,ActiveState,SubState,MainPID,Result,ExecMainStatus,NRestarts,InvocationID,ExecMainStartTimestamp,ExecMainExitTimestamp'],capture_output=True,text=True,timeout=10,check=True)
unit=dict(line.split('=',1) for line in query.stdout.splitlines() if '=' in line)
workers=[]
for process in psutil.process_iter(['pid','name','cmdline']):
 try:
  args=process.info['cmdline'] or []
  if process.pid!=os.getpid() and 'python' in (process.info['name'] or '').lower() and any(str(root) in arg for arg in args):
   workers.append(dict(pid=process.pid,args=args))
 except (psutil.NoSuchProcess,psutil.AccessDenied):pass
journal=subprocess.run(['journalctl','--no-pager','-u',runner.UNIT,'-n','40','-o','short-iso'],capture_output=True,text=True,timeout=10)
files={}
def add(prefix,base,path):
 raw=path.read_bytes();assert len(raw)<16*1024**2,'SMALL_EVIDENCE_ONLY:'+str(path)
 files[prefix+'/'+path.relative_to(base).as_posix()]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),base64=base64.b64encode(raw).decode())
for path in root.glob('*.json'):
 if path.name!='parent_inventory.json':add('evaluation',root,path)
for path in (root/'state').rglob('*.json'):add('evaluation',root,path)
for path in output.rglob('*.json'):
 if path.name!='control_plan.json':add('evaluation',root,path)
package=parent/runner.PACKAGE
for relative in ('state/status.json','state/EXCEPTION_STOP.json'):
 add('parent',parent,parent/relative)
for folder,names in (
 ('calibration',('calibration.json','input_binding.json','runtime.json','SEAL.json')),
 ('fit',('FIT_COMPLETE.json','source_signal.json','source_task_receipt.json','hard_task_receipt.json','sampling_receipt.json','SEAL.json'))):
 for name in names:
  path=package/'results'/folder/name
  if path.is_file():add('parent',parent,path)
for name in ('service.stdout.log','service.stderr.log','state/stages/evaluation/output.log'):
 path=root/name
 if path.is_file():add('evaluation',root,path)
proof=dict(status='PASS',checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
 unit=unit,workers=workers,journal_returncode=journal.returncode,journal_tail=journal.stdout[-16000:],
 seal_files_sha256_verified=len(seal['files']),main_cells=len(main),control_cells=len(controls),
 prior_summaries_identical=prior,parent_inventory_stat_and_census_verified=len(inventory['files']),
 parent_original_status=runner.read(parent/'state/status.json')['status'],
 parent_chain_complete_exists=(parent/'state/CHAIN_COMPLETE.json').exists(),
 gzip_crc_and_row_count='recorded PASS in final ACCEPTANCE; exact sealed bytes rehashed in this audit',
 remote_mutations=0,experiment_actions=0)
print(json.dumps(dict(proof=proof,files=files)))
'''


def main():
    destination = operate.HERE/'analysis/completion_review_20261025'
    destination.mkdir(parents=True, exist_ok=False)
    expected = operate.sha(operate.HERE/'DEPLOYMENT_MANIFEST.json')
    raw = operate.ssh_code('expected_manifest_sha256='+repr(expected)+'\n'+REMOTE,
                           'COMPLETION_READ_ONLY_AUDIT', timeout=180)
    downloaded = json.loads(raw)
    manifest = {}
    for name, item in downloaded['files'].items():
        path = (destination/name).resolve()
        assert destination.resolve() in path.parents, 'LOCAL_PATH_ESCAPE'
        data = base64.b64decode(item['base64'], validate=True)
        assert len(data) == item['bytes'] and hashlib.sha256(data).hexdigest() == item['sha256'], name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(data)
        manifest[name] = {k: item[k] for k in ('bytes', 'sha256')}
    receipt = dict(schema='paper04-v4-evaluation-completion-download-v1', status='PASS',
                   downloaded_at=datetime.now(timezone.utc).isoformat(),
                   remote_root=operate.NEW, manifest_sha256=expected,
                   file_count=len(manifest), total_bytes=sum(v['bytes'] for v in manifest.values()),
                   all_downloaded_file_sha256_verified=True, full_predictions_downloaded=False,
                   remote_mutations=0, files=manifest)
    operate.save(destination/'DOWNLOAD_VERIFIED.json', receipt)
    operate.save(destination/'REMOTE_COMPLETION_AUDIT.json', downloaded['proof'])
    print(json.dumps(dict(status='PASS', files=len(manifest), bytes=receipt['total_bytes'],
                          local=str(destination), proof=downloaded['proof']), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
