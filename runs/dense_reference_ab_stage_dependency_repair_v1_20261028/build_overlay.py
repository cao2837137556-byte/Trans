"""Copy the frozen recursive vendor dependency closure; never alter the parent."""
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ORIGINAL = ROOT / 'runs/dense_reference_matrix_v1_20261027/vendor/encoding_v2/repo/ood'
PARENT = ROOT / 'runs/dense_reference_ab_stage_candidate_v1_20261028'
ACCEPTED = ROOT / 'runs/dense_reference_batch_repair_deployment_20261027/result_retrieval_r2_20261027'
ENTRYPOINTS = ('constrained_onboarding_core_v3', 'onboarding_budget_v1')
THIRD_PARTY = {'numpy'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def closure(root, entrypoints=ENTRYPOINTS):
    answer, queue = {}, list(entrypoints)
    while queue:
        name = queue.pop(0)
        if name in answer:
            continue
        path = Path(root) / (name + '.py')
        if not path.is_file():
            raise RuntimeError('MISSING_FROZEN_LOCAL_DEPENDENCY:' + name)
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports += [(alias.name.split('.')[0], node.lineno) for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    raise RuntimeError('UNRESOLVED_RELATIVE_IMPORT:' + name)
                imports.append((node.module.split('.')[0], node.lineno))
            elif isinstance(node, ast.Call):
                dynamic = (isinstance(node.func, ast.Name) and node.func.id == '__import__') or (
                    isinstance(node.func, ast.Attribute) and node.func.attr == 'import_module')
                if dynamic:
                    if not node.args or not isinstance(node.args[0], ast.Constant) or not isinstance(node.args[0].value, str):
                        raise RuntimeError('UNRESOLVED_DYNAMIC_IMPORT:' + name)
                    imports.append((node.args[0].value.split('.')[0], node.lineno))
        local = []
        for dependency, line in imports:
            if (Path(root) / (dependency + '.py')).is_file():
                local.append(dict(module=dependency, line=line))
                queue.append(dependency)
            elif dependency not in sys.stdlib_module_names and dependency not in THIRD_PARTY:
                raise RuntimeError('UNRESOLVED_IMPORT:' + name + ':' + dependency)
        answer[name] = dict(module=name, bytes=path.stat().st_size, sha256=sha(path),
            local_imports=sorted(local, key=lambda item:(item['line'], item['module'])),
            all_imports_including_function_local=[dict(module=module, line=line) for module, line in imports])
    return answer


def main():
    vendor = HERE / 'vendor/ood'
    if vendor.exists():
        raise RuntimeError('OVERLAY_VENDOR_ALREADY_EXISTS_NEVER_OVERWRITE')
    dependencies = closure(ORIGINAL)
    if set(dependencies) != {'constrained_onboarding_core_v3', 'onboarding_budget_v1',
        'indexed_features_v1', 'legacy_qref_data_v1', 'legacy_qref_common_v1', 'causal_reference_overlap_v1'}:
        raise RuntimeError('UNEXPECTED_DEPENDENCY_CLOSURE_REQUIRES_REVIEW')
    vendor.mkdir(parents=True)
    for name, entry in dependencies.items():
        source = ORIGINAL / (name + '.py')
        target = vendor / source.name
        shutil.copyfile(source, target)
        if sha(target) != entry['sha256']:
            raise RuntimeError('DEPENDENCY_COPY_BYTES_CHANGED')
        original_parent = PARENT / 'vendor/encoding_v2/repo/ood' / source.name
        if original_parent.exists() and sha(original_parent) != entry['sha256']:
            raise RuntimeError('ORIGINAL_PARENT_DEPENDENCY_MISMATCH')
    config = HERE / 'config'
    config.mkdir()
    for source, name in (
        (PARENT / 'config/MATRIX_CANDIDATE_HPC.json', 'MATRIX_CANDIDATE_HPC.json'),
        (PARENT / 'preparation_r2/MATRIX_CANDIDATE_LOCAL.json', 'MATRIX_CANDIDATE_LOCAL.json'),
        (ACCEPTED / 'evidence179602/science/source_cal/INPUT_SEAL.json', 'SOURCE_INPUT_SEAL.json'),
        (ACCEPTED / 'manifest.json', 'ACCEPTED_RESULT_MANIFEST.json')):
        shutil.copyfile(source, config / name)
    result = dict(schema='paper04-dense-ab-dependency-overlay-v1', status='PREPARED_NOT_EXECUTED',
        created_utc=datetime.now(timezone.utc).isoformat(), original_parent_modified=False,
        scientific_parameters_changed=False, source_seal_bytes_changed=False,
        parent_package_sha256='6870ae7c60ecfb82e4e8c0bc8a18306cad6ee0cf62ed640a82ca254da1fa8f61',
        parent_manifest_sha256='3c7d04a6a32b2a033b62bdfefc93172809eb6a7e6375b7fd7be7828a27ad1199',
        parent_archive_sha256='b37e9213bf7546134205cfcc52192c54d493fb99d4f393a78383d51dbf417937',
        accepted_result_manifest_sha256='8ff70fedb1e4c0892acd066c937a7aeed9d3c0b38ccd22956862c50c3a67b72d',
        entrypoints=list(ENTRYPOINTS), dependencies=dependencies,
        missing_in_parent=[name for name in dependencies if not
            (PARENT / 'vendor/encoding_v2/repo/ood' / (name + '.py')).exists()],
        config_files={p.name:dict(sha256=sha(p), bytes=p.stat().st_size) for p in sorted(config.iterdir())},
        permits_model_forward=False, permits_support_computation=False,
        permits_new_CAL=False, permits_target_score_evaluation=False, permits_scheduler_submission=False)
    assert result['missing_in_parent'] == ['causal_reference_overlap_v1']
    (HERE / 'DEPENDENCY_CLOSURE.json').write_text(json.dumps(result, indent=2, sort_keys=True)+'\n', encoding='utf-8')
    print(json.dumps(dict(status=result['status'], dependencies=len(dependencies),
        missing_in_parent=result['missing_in_parent'], dependency_bytes=sum(e['bytes'] for e in dependencies.values()))))


if __name__ == '__main__':
    main()
