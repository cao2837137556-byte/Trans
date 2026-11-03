"""Bind patch checks to final archive, inherited code and unchanged budget."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / 'onboarding_configured_v1_20261017'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.write_bytes((json.dumps(data, ensure_ascii=False, indent=2)+'\n').encode('utf-8'))


def main():
    build = read(HERE/'build_receipt.json')
    linux = read(HERE/'linux_validation/result.json')
    transfer = read(HERE/'transfer_validation.json')
    previous = read(OLD/'validation.json')
    assert linux['status']==transfer['status']=='PASS'
    assert linux['tests']==22 and transfer['tests']==5
    assert linux['failures']==linux['errors']==linux['skipped']==transfer['failures']==0
    assert sha(HERE/build['archive'])==build['archive_sha256']==linux['archive_sha256']
    assert sha(OLD/previous['archive'])==previous['archive_sha256']==build['previous_archive_sha256']
    assert sha(HERE/'transfer_v1.ps1')==transfer['production_script_sha256']
    assert sha(HERE/'test_transfer_mock.ps1')==transfer['test_script_sha256']
    for name, digest in linux['logs'].items():
        assert sha(HERE/'linux_validation'/name)==digest
    files, changes = {}, []
    for path in sorted((HERE/'bundle').rglob('*')):
        if not path.is_file(): continue
        relative = path.relative_to(HERE/'bundle').as_posix()
        files[relative]=sha(path)
        assert sha(HERE/'linux_clean_install'/relative)==files[relative],relative
        if relative!='SHA256SUMS' and sha(OLD/'bundle'/relative)!=files[relative]:
            changes.append(relative)
    assert changes==build['changed_payload_files']
    assert files['resource_plan.json']==build['resource_plan_sha256']==previous['resource_plan_sha256']
    assert sha(HERE/'RESOURCE_BUDGET.md')==sha(OLD/'RESOURCE_BUDGET.md')
    for path in (HERE/'bundle/repo/ood').glob('*.py'):
        assert sha(path)==sha(OLD/'bundle/repo/ood'/path.name)
    artifacts = ['build_patch.py','build_receipt.json','record_validation.py','test_submit_linux.py',
                 'validate_linux.py','linux_validation/result.json','transfer_v1.ps1',
                 'test_transfer_mock.ps1','transfer_validation.json','transfer_validation.log',
                 'README.md','OPERATE_HPC.md','RESOURCE_BUDGET.md','onboarding_install_v1.py']
    manifest=dict(schema='onboarding-delivery-patch-v1r1',
        archive_sha256=build['archive_sha256'],previous_archive_sha256=build['previous_archive_sha256'],
        package_files=files,changed_payload_files=changes,
        supporting_files={name:sha(HERE/name) for name in artifacts})
    write(HERE/'source_manifest.json',manifest)
    receipt=dict(status='LOCAL_DELIVERY_PATCH_PASS_TARGET_VERIFICATION_PENDING',date='2026-10-17',
        archive=build['archive'],archive_sha256=build['archive_sha256'],
        package_seal_sha256=files['SHA256SUMS'],source_manifest_sha256=sha(HERE/'source_manifest.json'),
        previous_archive_sha256=build['previous_archive_sha256'],changed_payload_files=changes,
        current_checks=27,linux_job_checks=linux,transfer_checks=transfer,
        inherited_checks=dict(count=179,rerun=False,path='../'+OLD.name+'/validation.json',
                              sha256=sha(OLD/'validation.json')),
        unchanged_python_modules=89,resource_budget_recalculated=False,
        resource_plan_sha256=files['resource_plan.json'],allocation=dict(cpus=8,memory_gib=16),
        real_experiment='NOT_STARTED',remote_actions=False,
        limitations=['Real target environment/tokenizer and whole-stage resource measurements remain pending.',
                     'PowerShell transfer checks mock WSL/rsync and do not establish real network or native argument behavior.',
                     'No model performance claims or full-system PASS; previous scientific limitations remain.',
                     'Completed archives contain experiment exit status; final export/job receipts are pulled separately.'])
    write(HERE/'validation.json',receipt)
    print(json.dumps({k:receipt[k] for k in ('status','archive_sha256','current_checks','resource_budget_recalculated')}))


if __name__=='__main__': main()
