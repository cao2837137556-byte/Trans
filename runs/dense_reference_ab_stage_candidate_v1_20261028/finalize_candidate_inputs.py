"""Freeze relocation and exact asset inventory for review, never authorize/run."""
import copy
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PREP = HERE / 'preparation_r2'
PROJECT_HPC = '/public/home/jiangxinwei.zr/work/paper04'
OLD_SCIENCE_LOCAL = ROOT / 'runs/dense_reference_batch_repair_deployment_20261027/result_retrieval_r2_20261027/evidence179602/science'
OLD_SCIENCE_HPC = PROJECT_HPC + '/runs/dense_reference_batch_repair_v1_20261027_runtime/job_179602/science'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    path = HERE / 'config' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')


def pins(value):
    if isinstance(value, dict):
        if isinstance(value.get('path'), str) and isinstance(value.get('sha256'), str):
            yield value
        for child in value.values():
            yield from pins(child)
    elif isinstance(value, list):
        for child in value:
            yield from pins(child)


def main():
    local = read(PREP / 'MATRIX_CANDIDATE_LOCAL.json')
    readiness = read(PREP / 'INPUT_READINESS.json')
    assert sha(PREP / 'MATRIX_CANDIDATE_LOCAL.json') == readiness['candidate_manifest_sha256']
    known = {item['path']: item for item in readiness['files']}
    remote = copy.deepcopy(local)
    static_files, derived_files = {}, {}
    for before, after in zip(pins(local), pins(remote)):
        path = Path(before['path'])
        path = path if path.is_absolute() else ROOT / path
        item = known[path.relative_to(ROOT).as_posix()]
        assert item['sha256'] == before['sha256']
        if before.get('derived_runtime'):
            relative = path.relative_to(OLD_SCIENCE_LOCAL).as_posix()
            after['path'] = OLD_SCIENCE_HPC + '/' + relative
            derived_files[relative] = dict(path=after['path'], sha256=item['sha256'], bytes=item['bytes'])
        else:
            static_files[item['path']] = dict(item, bundled=False, aliases=[])
        assert before['sha256'] == after['sha256']
    remote['root'] = 'RUNTIME_READONLY_VIEW'
    remote['derived_runtime_roots'] = [OLD_SCIENCE_HPC + '/encode', OLD_SCIENCE_HPC + '/source_cal']
    remote['preparation']['relocation'] = dict(kind='EXPLICIT_PATH_ONLY_PINS_UNCHANGED',
        local_manifest_sha256=readiness['candidate_manifest_sha256'],
        original_source_seal_unmodified=True, source_results_not_refit=True)
    write('MATRIX_CANDIDATE_HPC.json', remote)
    write('RUNTIME_ASSET_MANIFEST.json', dict(schema='dense-reference-ab-stage-static-assets-v1',
        files=sorted(static_files.values(), key=lambda item:item['path']),
        total_bytes=sum(item['bytes'] for item in static_files.values()),
        all_files_exact_registered_inputs=True, remote_presence='NOT_CHECKED',
        required_transfer_policy='Only absent exact SHA-bound files; never overwrite mismatching input.'))
    write('DERIVED_EXISTING_INPUTS.json', dict(schema='dense-reference-ab-stage-existing-derived-v1',
        files=sorted(derived_files.values(), key=lambda item:item['path']),
        total_bytes=sum(item['bytes'] for item in derived_files.values()),
        producer_job_id='179602', required_state='ALREADY_COMPLETE_VERIFIED_READ_ONLY',
        encoding_or_CAL_rerun_allowed=False))
    manifest_sha = sha(HERE / 'config/MATRIX_CANDIDATE_HPC.json')
    write('APPROVAL.template.json', dict(schema='dense-reference-ab-stage-authorization-v1',
        status='NOT_AUTHORIZED', scope='AB_DENSE_STAGE_PENDING_THIRD_POOL',
        protocol_amendment_confirmed=False, evaluated_pools=['CIC_DEV', 'UNSW_DEV'],
        deferred_pool='CIC_THREE_DEVICE_REGRESSION_CONSUMED', allow_target_evaluation=False,
        manifest_sha256=manifest_sha,
        source_cal_result_sha256=readiness['source_cal_result_sha256'],
        package_sha256='BIND_AFTER_PACKAGE_SEAL_AND_EXPLICIT_USER_APPROVAL',
        evidence='', total_wall_seconds=7200, retries=0, automatic_retry=False))
    write('runtime.json', dict(numpy_version='2.0.1',
        numpy_overlay=OLD_SCIENCE_HPC + '/runtime/numpy201',
        environment_sha256='8da8564e759d51df121eaf9230a3e34c358e3abd10d9ce8dc8fe4b92e0763fcf',
        cpu_threads=4, slurm_memory_GiB=16, tree_rss_GiB=8, output_GiB=2,
        min_free_GiB=12, maximum_wall_seconds=7200, retries=0))
    write('CANDIDATE_STATE.json', dict(status='PREPARED_PENDING_PROTOCOL_AND_EXECUTION_APPROVAL',
        production_authorized=False, remote_operations=0, new_target_evaluations=0,
        manifest_sha256=manifest_sha, static_files=len(static_files),
        static_bytes=sum(item['bytes'] for item in static_files.values()),
        existing_derived_files=len(derived_files),
        existing_derived_bytes=sum(item['bytes'] for item in derived_files.values()),
        distance_pairs=912302797, original_registered_matrix_complete=False,
        former_three_pool_protocol_preserved=True))
    print(json.dumps(read(HERE / 'config/CANDIDATE_STATE.json'), ensure_ascii=False))


if __name__ == '__main__':
    main()
