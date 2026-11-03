"""Package the tested dependency closure; never launch a real stage."""
import ast
import shutil
import sys
from pathlib import Path
import issue27dualview_support_v1 as s


def closure():
    pending=list((s.ROOT/'repo/ood').glob('issue27dualview_*_v1.py'));seen=set()
    while pending:
        p=pending.pop().resolve()
        if p in seen:continue
        seen.add(p)
        for n in ast.walk(ast.parse(p.read_text(encoding='utf-8-sig'))):
            names=[a.name for a in n.names] if isinstance(n,ast.Import) else ([n.module] if isinstance(n,ast.ImportFrom) else [])
            for name in names:
                if name and name.startswith('issue27'):
                    child=p.parent/(name.split('.')[0]+'.py');s.require(child.exists(),'DEPENDENCY_MISSING');pending.append(child)
    return sorted(seen)


def code_pins():
    r=s.recipe();paths=closure()+[s.RECIPE]+[s.ROOT/r[k]['path'] for k in ('design','evidence')]
    paths+=list((s.ROOT/'scripts').glob('*unified_dual_view_v1.ps1'))
    return {p.relative_to(s.ROOT).as_posix():s.sha(p) for p in paths}


def build(test_path):
    from issue27dualview_control_v1 import verify_workspace
    result=s.read_json(test_path);r=s.recipe();pins=code_pins()
    s.require(result['status']=='PASS' and result['tests_run']==result['tests_passed'] and result['numeric_access_guard'],'ACCEPTANCE_FAILED')
    s.require(result['tested_code_pins']==pins,'SOURCE_CHANGED_AFTER_ACCEPTANCE')
    s.require(result['real_model_forwards']==result['real_teacher_rows']==result['real_optimizer_steps']==0,'REAL_TEST_ACCESS')
    for group in ('reference_code_pins','unrelated_tracked_sha256'):
        for p,h in r['implementation'][group].items():s.require(s.sha(s.ROOT/p)==h,'PROTECTED_FILE_CHANGED:'+p)
    runtime=r['implementation']['historical_runtime_pins']
    for p,h in runtime.items():s.require(s.sha(p)==h,'RUNTIME_IDENTITY:'+p)
    git=Path(shutil.which('git')).resolve()
    cfg=dict(recipe_sha256=s.RECIPE_SHA,code_pins=pins,runtime_pins=runtime,
             unrelated_tracked_sha256=r['implementation']['unrelated_tracked_sha256'],
             head=r['workspace']['head'],branch=r['workspace']['branch'],git_path=str(git),git_sha256=s.sha(git),
             authorization='Implementation/generated acceptance only; real P/T/E NOT authorized',
             test_result_sha256=s.sha(test_path))
    verify_workspace(cfg);s.require(not any(p.exists() for p in s.OUTPUTS.values()),'REAL_STAGE_ALREADY_EXISTS')
    s.PACKAGE.mkdir(exist_ok=False);s.atomic_json(s.PACKAGE/'config.json',cfg)
    s.atomic_json(s.PACKAGE/'acceptance.json',dict(result,config_sha256=s.sha(s.PACKAGE/'config.json')))
    (s.PACKAGE/'README.md').write_text('# 双视图实现与生成验收\n\n真实 P/T/E 未启动。\n'
        'P 仅TRAIN表示；T 两个新共享头；E 一次完整终点。缓存按授权UID逐行读取，异常停止零重试。\n'
        '下一次明确真实P→T→E授权应包括指定E3缓存行；本次没有该授权。\n',encoding='utf-8')
    s.seal(s.PACKAGE);s.manifest(s.PACKAGE)
    print(s.canonical(dict(status='IMPLEMENTATION_SEALED',manifest_sha256=s.sha(s.PACKAGE/'SHA256SUMS'),tests_passed=result['tests_passed'],real_started=False)).decode())


if __name__=='__main__':build(Path(sys.argv[1]))
