"""Seal the verified implementation before the sole authorized real attempt."""
import ast
import json
import sys
from pathlib import Path
import issue27frontend_expanded_eval_runner_v1 as r
import issue27frontend_expanded_eval_control_v1 as control
s=r.s


def main():
    s.require(not s.REAL.exists() and not (s.PACKAGE/'SHA256SUMS').exists(),'ALREADY_FROZEN_OR_STARTED')
    tests=s.read_json(s.PACKAGE/'synthetic_test_results.json')
    s.require(tests['status']=='PASS' and tests['tests_passed']==tests['tests_run']==23,'TESTS')
    original=s.read_json(s.ROOT/'runs/frontend_paired_train_implementation_v3_20260910/execution_config.json')
    config=s.read_json(s.PACKAGE/'config.json')
    config['runtime_pins']=original['runtime_pins']
    config['archive_mtime_ns']=Path(config['archive']).stat().st_mtime_ns
    plan_path=s.ROOT/'runs/frontend_paired_train_implementation_v3_20260910/plan.json'
    s.require(s.sha_file(plan_path)=='2d17743edeab5d51751e9d95c308a414c3763934921e917fc2ab97c495e2e5ef','TRAIN_PLAN_SHA')
    plan=s.read_json(plan_path)
    config['train_feature_prefix_sha256']=sorted({t['feature_prefix_sha256'] for c in plan['contexts'] if c['role']=='train' for t in c['targets']})
    paths=set()
    for mod in list(sys.modules.values()):
        path=getattr(mod,'__file__',None)
        if path:
            path=Path(path).resolve()
            try:rel=path.relative_to(s.ROOT).as_posix()
            except ValueError:continue
            if rel.startswith('repo/ood/') and rel.endswith('.py'):paths.add(rel)
    paths.update(p.relative_to(s.ROOT).as_posix() for p in (s.ROOT/'repo/ood').glob('issue27frontend_expanded_eval_*_v1.py'))
    paths.update('scripts/'+p for p in ('start_frontend_expanded_eval_local.ps1','show_frontend_expanded_eval_status.ps1'))
    document=s.ROOT/'runs/mainline_docs/frontend_expanded_eval_implementation_and_execution_20260910.md'
    side=document.with_suffix('.sha256')
    side.write_text(s.sha_file(document)+'  '+document.name+'\n',encoding='utf-8')
    paths.update([document.relative_to(s.ROOT).as_posix(),side.relative_to(s.ROOT).as_posix()])
    pins={rel:s.sha_file(s.ROOT/rel) for rel in sorted(paths)}
    for rel,h in pins.items():
        if rel.endswith('.py'):ast.parse((s.ROOT/rel).read_text(encoding='utf-8-sig'),filename=rel)
        if rel in original['code_and_document_pins']:s.require(h==original['code_and_document_pins'][rel],'FROZEN_DEPENDENCY_DRIFT:'+rel)
    s.require(pins['repo/ood/issue27frontend_paired_train_model_v1.py']=='970028cdef7ff9f0098930e6d378a3e517c7d47b95105223b9120361e58d8d71','MODEL_SOURCE')
    config['code_pins']=pins
    for path,h in config['runtime_pins'].items():s.require(s.sha_file(path)==h,'RUNTIME_IDENTITY')
    prior=s.read_json(s.ROOT/'runs/frontend_expanded_eval_scope_v1_20260910/scope_readiness.json')
    for rel,h in prior['unrelated_tracked_sha256'].items():s.require(s.sha_file(s.ROOT/rel)==h,'UNRELATED_MODIFICATION_CHANGED')
    config['unrelated_tracked_sha256']=prior['unrelated_tracked_sha256']
    s.atomic_json(s.PACKAGE/'config.json',config)
    s.atomic_json(s.PACKAGE/'synthetic_acceptance.json',{**tests,'config_sha256':s.sha_file(s.PACKAGE/'config.json'),
                  'powershell_scripts_parse':'PASS','code_pins':len(pins),'runtime_pins':len(config['runtime_pins']),
                  'frozen_dependencies_unchanged':True,'unrelated_tracked_unchanged':True})
    s.seal(s.PACKAGE)
    print(json.dumps({'status':'IMPLEMENTATION_SEALED','tests':23,'code_pins':len(pins),
                      'manifest_sha256':s.sha_file(s.PACKAGE/'SHA256SUMS')},ensure_ascii=False))


if __name__=='__main__':main()
