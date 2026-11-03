"""Seal implementation after generated acceptance; never start real stages."""
import ast
import json
from pathlib import Path
import shutil
import subprocess
import sys
import issue27frontend_transfer_support_v1 as s


def closure():
    pending = list((s.ROOT/'repo/ood').glob('issue27frontend_transfer_*_v1.py'))
    seen = set()
    while pending:
        path = pending.pop().resolve()
        if path in seen:
            continue
        seen.add(path)
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
            names = [x.name for x in node.names] if isinstance(node,ast.Import) else ([node.module] if isinstance(node,ast.ImportFrom) else [])
            for name in names:
                if name and name.startswith('issue27'):
                    source = path.parent/(name.split('.')[0]+'.py')
                    s.require(source.exists(), 'MISSING_LOCAL_DEPENDENCY:'+str(source))
                    pending.append(source)
    return sorted(seen)


def build(test_result):
    r = s.recipe(); result = s.read_json(test_result)
    s.require(result['status'] == 'PASS' and result['tests_run'] == result['tests_passed'], 'SYNTHETIC_ACCEPTANCE_REQUIRED')
    s.require(result['real_model_forwards'] == result['real_teacher_rows'] == result['real_optimizer_steps'] == 0, 'REAL_ACCESS_IN_TESTS')
    paths = closure()+[s.RECIPE,s.ROOT/r['design_document']]
    paths += list((s.ROOT/'scripts').glob('*frontend_task_knowledge_transfer_v1.ps1'))
    code = {p.relative_to(s.ROOT).as_posix():s.sha(p) for p in paths}
    s.require(all(code.get(k) == v for k,v in result['tested_code_pins'].items()), 'CODE_CHANGED_SINCE_TESTS')
    prior = s.read_json(s.ROOT/'runs/frontend_paired_train_implementation_v3_20260910/execution_config.json')
    support = s.read_json(s.ROOT/'runs/frontend_knowledge_transfer_design_v1_20260911/metadata_support.json')
    for path,h in support['unrelated_tracked_sha256_start'].items():
        s.require(s.sha(s.ROOT/path) == h, 'UNRELATED_CHANGED')
    for path,h in prior['runtime_pins'].items():
        s.require(s.sha(Path(path)) == h, 'RUNTIME_DRIFT')
    git = shutil.which('git'); s.require(git is not None, 'GIT_NOT_FOUND')
    head = subprocess.check_output([git,'rev-parse','HEAD'],cwd=s.ROOT,text=True).strip()
    branch = subprocess.check_output([git,'branch','--show-current'],cwd=s.ROOT,text=True).strip()
    s.require(head == r['workspace']['head'] and branch == r['workspace']['branch'], 'WORKSPACE_CHANGED')
    cfg = dict(recipe_sha256=s.RECIPE_SHA,code_pins=code,runtime_pins=prior['runtime_pins'],python_path=str(s.PYTHON),
               git_path=git,git_sha256=s.sha(git),head=head,branch=branch,
               unrelated_tracked_sha256=support['unrelated_tracked_sha256_start'],
               scope='Implementation authorized 2026-09-11; no real P/T/E authorization. Launch requires explicit stage tokens.',
               test_result_sha256=s.sha(test_result))
    s.PACKAGE.mkdir(exist_ok=False)
    s.atomic_json(s.PACKAGE/'config.json',cfg)
    s.atomic_json(s.PACKAGE/'acceptance.json',dict(result,config_sha256=s.sha(s.PACKAGE/'config.json')))
    (s.PACKAGE/'README.md').write_text('# 任务知识迁移实现包\n\n实现与合成验证通过；真实P/T/E未开始。\n\n'
        '方案及代码身份见config.json，验收见acceptance.json。\n'
        '本地阶段按P教师准备→T三臂训练→E固定终点评估顺序执行，异常停止且零自动重试。\n'
        '状态入口：scripts/show_frontend_task_knowledge_transfer_v1.ps1；不启动实验。\n',encoding='utf-8')
    s.seal(s.PACKAGE);s.manifest(s.PACKAGE)
    print(json.dumps(dict(status='IMPLEMENTATION_SEALED',package=str(s.PACKAGE),files_pinned=len(code),tests_passed=result['tests_passed'],real_started=False)))


if __name__ == '__main__':
    build(Path(sys.argv[1]))
