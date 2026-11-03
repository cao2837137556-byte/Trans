"""Build v1r1 without changing the original v1 release or scientific recipe."""
import ast
import copy
from pathlib import Path
import shutil
import sys
import tarfile

HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[1]
sys.dont_write_bytecode=True; sys.path.insert(0,str(ROOT/'repo/ood'))
import continuous_common_v3 as c
from modern_head_evaluate_v1 import modern_gates,validate_config


def main():
    old=ROOT/'runs/modern_head_comparison_v1_20261018'; previous=c.read(old/'validation.json')
    c.pin(old/previous['archive'],previous['archive_sha256']); c.verify(old/'bundle')
    bundle=HERE/'bundle'; archive=HERE/(HERE.name+'.tar.gz')
    c.require(not bundle.exists() and not archive.exists(),'REVISION_NO_OVERWRITE')
    shutil.copytree(old/'bundle',bundle); (bundle/'SHA256SUMS').unlink()
    for path in (ROOT/'repo/ood').glob('*modern_head*_v1.py'):
        shutil.copyfile(path,bundle/'repo/ood'/path.name)
    shutil.copyfile(ROOT/'repo/ood/constrained_onboarding_query_tail_adapter_v2.py',bundle/'repo/ood/constrained_onboarding_query_tail_adapter_v2.py')
    for path in (HERE/'delivery_scripts').iterdir():
        if path.is_file(): shutil.copyfile(path,bundle/'scripts'/path.name)
    for name in ('README.md','OPERATE_HPC.md','RESOURCE_BUDGET.md','setup_dependencies.py'):
        shutil.copyfile(HERE/name,bundle/name)
    config=c.read(old/'bundle/experiment_contract.json'); config['version']=HERE.name
    inherited=c.read(bundle/'query_tail_design.json'); config['gates']=modern_gates(inherited)
    config['evaluation_scope']='Each family, seed and ensemble receives all inherited attack protections.'
    config['execution_modes']=['full','heads','modules']
    config['mlp_reuse']='Sealed runtime plus actual per-pool replay digests and shared endpoint preconditions; ineligible reuse retrains, corrupt source fails.'
    c.require(config['training']==c.read(old/'bundle/experiment_contract.json')['training'],'SCIENTIFIC_RECIPE_CHANGED')
    validate_config(config,inherited); c.write(bundle/'experiment_contract.json',config,replace=True)
    plan=c.read(old/'bundle/resource_plan.json'); plan['workload_identity']['experiment_contract_sha256']=c.sha(bundle/'experiment_contract.json')
    c.write(bundle/'resource_plan.json',plan,replace=True)
    runtime=c.read(old/'bundle/runtime_contract.json'); runtime['version']=HERE.name
    runtime['experiment_contract_sha256']=c.sha(bundle/'experiment_contract.json'); runtime['resource_plan_sha256']=c.sha(bundle/'resource_plan.json')
    c.write(bundle/'runtime_contract.json',runtime,replace=True)
    from modern_head_resources_v1 import load
    load(bundle/'resource_plan.json')
    for path in bundle.rglob('*.py'): ast.parse(path.read_text('utf-8-sig'),feature_version=(3,9))
    c.seal(bundle); c.verify(bundle)
    with tarfile.open(archive,'x:gz') as tar:
        for path in sorted(bundle.rglob('*')):
            if path.is_file(): tar.add(path,arcname=path.relative_to(bundle).as_posix(),recursive=False)
    archive.with_name(archive.name+'.sha256').write_text(c.sha(archive)+'  '+archive.name+'\n',encoding='ascii')
    installer=HERE/'modern_head_install_v1.py'; shutil.copyfile(old/'modern_head_install_v1.py',installer)
    installer.with_name(installer.name+'.sha256').write_text(c.sha(installer)+'  '+installer.name+'\n',encoding='ascii')
    receipt=dict(status='BUILT_LOCAL_VALIDATION_PENDING',archive=archive.name,archive_sha256=c.sha(archive),archive_bytes=archive.stat().st_size,
        package_seal_sha256=c.sha(bundle/'SHA256SUMS'),previous_archive_sha256=previous['archive_sha256'],
        resource_plan_sha256=c.sha(bundle/'resource_plan.json'),experiment_contract_sha256=c.sha(bundle/'experiment_contract.json'),
        original_scientific_recipe_unchanged=True,resource_allocation_reused=True,real_experiment=False,remote_actions=False)
    c.write(HERE/'build_receipt.json',receipt); print(receipt)


if __name__=='__main__': main()
