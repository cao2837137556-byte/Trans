"""Build a separate numeric revision; no remote deployment or experiment launch."""
import ast
import difflib
import hashlib
import json
from pathlib import Path
import shutil

REV = Path(__file__).resolve().parent
ROOT = REV.parents[2]
PACKAGE = Path('runs/learned_onboarding_v1_20261023')
BASE = ROOT/PACKAGE/'compatibility_revision_v2_20261024/staging'
STAGING = REV/'staging'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def replace(path, before, after):
    original = path.read_bytes()
    newline = b'\r\n' if b'\r\n' in original else b'\n'
    old = before.encode().replace(b'\n', newline)
    new = after.encode().replace(b'\n', newline)
    assert original.count(old) == 1, ('REPLACEMENT_SCOPE',str(path),before)
    path.write_bytes(original.replace(old,new))


def main():
    assert not STAGING.exists(), 'REVISION_ALREADY_BUILT'
    manifest = json.loads((BASE/'DEPLOYMENT_MANIFEST.json').read_text())
    for name, info in manifest['files'].items():
        source = BASE/name
        assert sha(source)==info['sha256'], 'BASE_IDENTITY:'+name
        destination = STAGING/name
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,destination)
    source = STAGING/PACKAGE/'src'
    shutil.copyfile(REV/'stable_inference.py',source/'stable_inference.py')
    replace(source/'learning.py', 'from common import SPEC_SHA256, uid_hash',
            'from stable_inference import stable_forward, INFERENCE_VERSION\nfrom common import SPEC_SHA256, uid_hash')
    replace(source/'learning.py',
            'scores[ix] = model(torch.from_numpy(_aux_batch(e3, q14, ix, mean, scale))).flatten().numpy()',
            'scores[ix] = stable_forward(model, torch.from_numpy(_aux_batch(e3, q14, ix, mean, scale))).flatten().numpy()')
    replace(source/'learning.py',
            'result[start:start+batch_size] = model(torch.from_numpy(x[start:start+batch_size])).flatten().numpy()',
            'result[start:start+batch_size] = stable_forward(model, torch.from_numpy(x[start:start+batch_size])).flatten().numpy()')
    replace(source/'common.py', 'def environment():\n    import torch',
            'def environment():\n    import torch\n    from stable_inference import INFERENCE_VERSION')
    replace(source/'common.py',
            "device='cpu', numpy_blas_config=output.getvalue(),",
            "device='cpu', numpy_blas_config=output.getvalue(),\n                network_inference_backend=INFERENCE_VERSION,\n                torch_build_config=torch.__config__.show(),\n                torch_cpu_capability=torch.backends.cpu.get_cpu_capability(),")
    replace(source/'pipeline.py',
            "for key in ('python', 'numpy', 'torch', 'numpy_blas_config', 'torch_threads', 'deterministic'):",
            "for key in ('python', 'numpy', 'torch', 'numpy_blas_config', 'torch_threads', 'deterministic',\n                'network_inference_backend', 'torch_build_config', 'torch_cpu_capability'):")
    # Protect every training formula and the original replay gates verbatim.
    before = ast.parse((BASE/PACKAGE/'src/learning.py').read_text())
    after = ast.parse((source/'learning.py').read_text())
    nodes_before = {node.name:ast.dump(node) for node in before.body if isinstance(node,ast.FunctionDef)}
    nodes_after = {node.name:ast.dump(node) for node in after.body if isinstance(node,ast.FunctionDef)}
    changed_functions = sorted(name for name in nodes_before if nodes_before[name]!=nodes_after[name])
    assert changed_functions==['score_auxiliary_head','score_module'], changed_functions
    for name in ('learning.py','common.py','pipeline.py'):
        body = (source/name).read_text()
        ast.parse(body,feature_version=(3,9))
        patch=''.join(difflib.unified_diff((BASE/PACKAGE/'src'/name).read_text().splitlines(True),
            body.splitlines(True),fromfile='v2/src/'+name,tofile='v3/src/'+name))
        (REV/(name+'.patch')).write_text(patch,encoding='utf-8',newline='\n')
    artifact_manifest = STAGING/PACKAGE/'implementation_manifest.json'
    old = json.loads(artifact_manifest.read_text())
    artifacts = old['artifacts']
    for name in ('learning.py','common.py','pipeline.py','stable_inference.py'):
        target = source/name
        artifacts['src/'+name]=dict(sha256=sha(target),bytes=target.stat().st_size)
    artifact_manifest.write_text(json.dumps(dict(schema='learned-onboarding-numeric-revision-v3',
        status='CANDIDATE_NOT_AUTHORIZED_FOR_EXPERIMENT_LAUNCH',spec_sha256=old['spec_sha256'],
        lineage=old['lineage'],parent_parity=old['parent_parity'],
        numeric_execution_changed=True,old256_bitwise_preservation_claimed=False,
        training_functions_unchanged=True,replay_gates_unchanged=True,
        parent_implementation_manifest_sha256=sha(BASE/PACKAGE/'implementation_manifest.json'),
        artifacts=artifacts),indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    names=set(manifest['files'])|{(PACKAGE/'src/stable_inference.py').as_posix()}
    files={name:dict(sha256=sha(STAGING/name),bytes=(STAGING/name).stat().st_size) for name in sorted(names)}
    revision=dict(schema='paper04-numeric-revision-v3-build',
        status='PREPARED_NOT_LAUNCHED',spec_sha256=old['spec_sha256'],
        parent_deployment_manifest_sha256=sha(BASE/'DEPLOYMENT_MANIFEST.json'),
        inference_backend='learned-onboarding-rowwise-float32-v3-20261024',
        training_functions_unchanged=True,replay_gates_unchanged=True,
        changed_learning_functions=changed_functions,numeric_execution_changed=True,
        automatic_resume=False,experiment_launched=False,files=files)
    with (STAGING/'NUMERIC_REVISION_MANIFEST.json').open('x') as stream:
        json.dump(revision,stream,indent=2,sort_keys=True)
    print(json.dumps({key:value for key,value in revision.items() if key!='files'}))


if __name__=='__main__':
    main()
