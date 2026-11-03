"""Assemble isolated modern-head release; reuse frozen code and budgets."""
import ast
import json
from pathlib import Path
import shutil
import sys
import tarfile

HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[1]
sys.dont_write_bytecode=True; sys.path.insert(0,str(ROOT/'repo/ood'))
import continuous_common_v3 as c
from modern_head_models_v1 import default_training_config,FAMILIES


def text(path,value): path.write_bytes(value.replace('\r\n','\n').encode('utf-8'))


def main():
    source=ROOT/'runs/onboarding_configured_v1r1_20261017/bundle'
    source_receipt=c.read(source.parent/'validation.json'); c.pin(source.parent/source_receipt['archive'],source_receipt['archive_sha256']); c.verify(source)
    bundle=HERE/'bundle'; archive=HERE/(HERE.name+'.tar.gz')
    c.require(not archive.exists(),'SEALED_RELEASE_NO_OVERWRITE')
    if bundle.exists(): raise RuntimeError('BUILD_DIRECTORY_EXISTS')
    shutil.copytree(source,bundle); (bundle/'SHA256SUMS').unlink()
    for path in (ROOT/'repo/ood').glob('*modern_head*_v1.py'): shutil.copyfile(path,bundle/'repo/ood'/path.name)
    vendor=bundle/'repo/ood/vendor/tabm_v0_0_3'; vendor.mkdir(parents=True)
    for name in ('tabm.py','LICENSE'): shutil.copyfile(ROOT/'repo/ood/vendor/tabm_v0_0_3'/name,vendor/name)
    for path in (HERE/'delivery_scripts').iterdir(): text(bundle/'scripts'/path.name,path.read_text(encoding='utf-8-sig'))
    shutil.copytree(HERE/'wheelhouse',bundle/'wheelhouse')
    for name in ('README.md','OPERATE_HPC.md','RESOURCE_BUDGET.md','setup_dependencies.py'): shutil.copyfile(HERE/name,bundle/name)
    query=c.read(ROOT/'runs/query_tail_configured_v2r3_20261017/validation.json')
    config=dict(schema='modern-head-comparison-v1',version=HERE.name,synthetic_only=False,families=list(FAMILIES),
        seeds=list(c.SEEDS),onboarding_families=['TabM','LightGBM'],training=default_training_config(),
        gates=c.read(bundle/'query_tail_design.json')['gates'],
        evaluation_scope='All three families and every seed/ensemble receive inherited attack protections; original applies_to text is historical.',
        input=dict(features=782,fit_rows=617908,cal_rows=148819,CIC_DEV=179886,UNSW_DEV=148316),
        mlp_reuse='Requires sealed exact numeric_runtime fingerprint and all three pools bitwise replay; otherwise retrain common MLP.',
        maximum_training_endpoints=9,selection='No automatic winner; TabM and LightGBM paired candidates fixed before target results',
        score=dict(TabM='logmeanexp(logsigmoid(z))-logmeanexp(logsigmoid(-z))',LightGBM='binary raw margin',
                   external_ensemble='float64 mean of three seed logits',cut='source CAL normal weighted1%, strict >'),
        protocol_sha256=c.sha(bundle/'protocol.json'),query_tail_design_sha256=c.sha(bundle/'query_tail_design.json'))
    c.write(bundle/'experiment_contract.json',config)
    evidence=bundle/'resource_evidence'
    shutil.copyfile(source/'resource_plan.json',evidence/'inherited_onboarding_resource_plan.json')
    for name in ('tabm_generated_step_resource.json','tabm_generated_steady_resource.json'): shutil.copyfile(HERE/name,evidence/name)
    c.write(evidence/'modern_static_budget.json',dict(fit_rows=617908,fit_float32_bytes=617908*782*4,
        shared_uid_output=True,model_parameters=dict(MLP=100353,TabM=1097184),
        no_real_training=True,whole_phase_peak='ESTIMATED',checkpoint_and_head_reports_gib_allowance=1))
    plan=c.read(HERE/'resource_plan.template.json'); plan['workload_identity']['experiment_contract_sha256']=c.sha(bundle/'experiment_contract.json')
    for phase in plan['phases'].values():
        for ref in phase['evidence']: ref['sha256']=c.sha(bundle/ref['path'])
    for name in ('TABM_TRAIN',):
        plan['phases'][name]['evidence'].extend(dict(path='resource_evidence/'+n,sha256=c.sha(evidence/n))
            for n in ('tabm_generated_step_resource.json','tabm_generated_steady_resource.json'))
    c.write(bundle/'resource_plan.json',plan,replace=True)
    from modern_head_resources_v1 import load
    load(bundle/'resource_plan.json')
    work='/public/home/jiangxinwei.zr/work'
    runtime=dict(version=HERE.name,experiment_contract_sha256=c.sha(bundle/'experiment_contract.json'),
        resource_plan_sha256=c.sha(bundle/'resource_plan.json'),retries=0,export_included_limit_gib=plan['export_included_limit_gib'],
        query_tail_package_seal_sha256=query['package_seal_sha256'],onboarding_package_seal_sha256=source_receipt['package_seal_sha256'],
        paths=dict(parent=work+'/legacy_continuous_input_repair_v3_20260929/runs/real_repair',
                   prepared_run=work+'/query_tail_configured_v2r3_20261017/runs/query_tail',
                   onboarding_root=work+'/onboarding_configured_v1r1_20261017'),
        versions=dict(numpy='2.0.1',torch='2.5.1',lightgbm='4.6.0',**{'rtdl-num-embeddings':'0.0.12',
            'scipy':'1.13.1','typing_extensions':'4.14.1'}),real_execution_authorized=False)
    c.write(bundle/'runtime_contract.json',runtime,replace=True)
    c.write(bundle/'dependency_provenance.json',dict(tabm=dict(version='0.0.3',
        upstream='https://github.com/yandex-research/tabm',commit='a507095893d784c5702059d737ddfbd1299c41dd',
        source_sha256=c.sha(vendor/'tabm.py'),license_sha256=c.sha(vendor/'LICENSE')),
        wheels={p.name:c.sha(p) for p in sorted((bundle/'wheelhouse').glob('*.whl'))}))
    for path in bundle.rglob('*.py'): ast.parse(path.read_text(encoding='utf-8-sig'),feature_version=(3,9))
    c.seal(bundle); c.verify(bundle)
    with tarfile.open(archive,'x:gz') as tar:
        for path in sorted(bundle.rglob('*')):
            if path.is_file(): tar.add(path,arcname=path.relative_to(bundle).as_posix(),recursive=False)
    text(archive.with_name(archive.name+'.sha256'),c.sha(archive)+'  '+archive.name+'\n')
    # Standalone standard-library installer, preserving verified extraction logic.
    installer=HERE/'modern_head_install_v1.py'
    body=(ROOT/'repo/ood/onboarding_delivery_io_v1.py').read_text(encoding='utf-8')
    body=body.replace("VERSION = 'onboarding-delivery-io-v1-20261017'","VERSION = 'modern-head-delivery-io-v1-20261018'")
    body=body.replace("'onboarding_pullback.tar.gz'","'modern_head_pullback.tar.gz'").replace("'onboarding_export_manifest.json'","'modern_head_export_manifest.json'")
    text(installer,body); text(installer.with_name(installer.name+'.sha256'),c.sha(installer)+'  '+installer.name+'\n')
    receipt=dict(status='BUILT_LOCAL_VALIDATION_PENDING',archive=archive.name,archive_sha256=c.sha(archive),
        archive_bytes=archive.stat().st_size,package_seal_sha256=c.sha(bundle/'SHA256SUMS'),
        resource_plan_sha256=c.sha(bundle/'resource_plan.json'),experiment_contract_sha256=c.sha(bundle/'experiment_contract.json'),
        parent_query_tail_sha256=query['archive_sha256'],parent_onboarding_sha256=source_receipt['archive_sha256'],
        real_experiment=False,remote_actions=False)
    c.write(HERE/'build_receipt.json',receipt); print(json.dumps(receipt))


if __name__=='__main__': main()
