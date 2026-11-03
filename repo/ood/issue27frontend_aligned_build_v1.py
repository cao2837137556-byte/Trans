"""Seal the Q/R implementation after generated acceptance. No real stage launch."""
import ast
from pathlib import Path
import sys
import issue27frontend_aligned_support_v1 as s


def closure():
    pending=list((s.ROOT/'repo/ood').glob('issue27frontend_aligned_*_v1.py'));seen=set()
    while pending:
        path=pending.pop().resolve()
        if path in seen:continue
        seen.add(path)
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
            names=[a.name for a in node.names] if isinstance(node,ast.Import) else ([node.module] if isinstance(node,ast.ImportFrom) else [])
            for name in names:
                if name and name.startswith('issue27'):
                    dependency=path.parent/(name.split('.')[0]+'.py')
                    s.require(dependency.exists(),'MISSING_DEPENDENCY:'+str(dependency));pending.append(dependency)
    return sorted(seen)


def code_pins():
    r=s.recipe()
    paths=closure()+[s.RECIPE,s.ROOT/r['design_document']]
    paths+=list((s.ROOT/'scripts').glob('*frontend_task_aligned_transfer_v1.ps1'))
    return {p.relative_to(s.ROOT).as_posix():s.sha(p) for p in paths}


def build(test_path):
    from issue27frontend_aligned_control_v1 import verify_workspace
    r=s.recipe();result=s.read_json(test_path)
    s.require(result['status']=='PASS' and result['tests_run']==result['tests_passed'] and result['numeric_access_guard'],'TEST_FAILURE')
    s.require(result['real_model_forwards']==result['real_teacher_rows']==result['real_optimizer_steps']==0,'REAL_ACCESS_IN_TESTS')
    pins=code_pins();s.require(pins==result['tested_code_pins'],'CODE_CHANGED_SINCE_TESTS')
    old=s.ROOT/'runs/frontend_transfer_diagnostic_implementation_v1_20260912'
    s.manifest(old,'a8cb7b7c1a69c3a2c95beff39c91b21fc00c036019c6c8e57a0afddcc515b42d')
    cfg=s.read_json(old/'config.json')
    for path,h in cfg['code_pins'].items():s.require(s.sha(s.ROOT/path)==h,'FROZEN_CODE_CHANGED:'+path)
    for path,h in cfg['runtime_pins'].items():s.require(s.sha(Path(path))==h,'RUNTIME_DRIFT')
    for path,h in cfg['unrelated_tracked_sha256'].items():s.require(s.sha(s.ROOT/path)==h,'UNRELATED_CHANGED')
    verify_workspace(cfg)
    cfg.update(recipe_sha256=s.RECIPE_SHA,code_pins=pins,
        scope='Implementation and generated verification authorized 2026-09-12; real P/T/E not authorized.',
        test_result_sha256=s.sha(test_path))
    for key in ('reused_P_manifest_sha256','diagnostic_contract_sha256'):cfg.pop(key,None)
    s.PACKAGE.mkdir(exist_ok=False)
    s.atomic_json(s.PACKAGE/'config.json',cfg)
    s.atomic_json(s.PACKAGE/'acceptance.json',dict(result,config_sha256=s.sha(s.PACKAGE/'config.json')))
    (s.PACKAGE/'README.md').write_text('# Q/R 实现与合成验收\n\n真实 P/T/E 未授权、未启动。\n'
        'P仅派生已有训练侧教师缓存；T为Q/R两臂；E为一次固定终点评价。\n'
        '异常停止、零重试；追加式状态，无LLM定时轮询。\n',encoding='utf-8')
    s.seal(s.PACKAGE);s.manifest(s.PACKAGE)
    print(s.canonical(dict(status='IMPLEMENTATION_SEALED',tests_passed=result['tests_passed'],
        source_pins=len(pins),manifest_sha256=s.sha(s.PACKAGE/'SHA256SUMS'),real_started=False)).decode())


if __name__=='__main__':build(Path(sys.argv[1]))
