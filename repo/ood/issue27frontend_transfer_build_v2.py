"""Seal a narrow I/O correction and inherited numerical code; no run launch."""
import ast
import json
from pathlib import Path
import sys
import issue27frontend_transfer_control_v2 as control

s=control.s


def closure():
    pending=list((s.ROOT/'repo/ood').glob('issue27frontend_transfer_*.py'));seen=set()
    while pending:
        path=pending.pop().resolve()
        if path in seen:continue
        seen.add(path)
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
            names=[a.name for a in node.names] if isinstance(node,ast.Import) else ([node.module] if isinstance(node,ast.ImportFrom) else [])
            for name in names:
                if name and name.startswith('issue27'):
                    dependency=path.parent/(name.split('.')[0]+'.py')
                    s.require(dependency.exists(),'MISSING_DEPENDENCY');pending.append(dependency)
    return sorted(seen)


def build(test_result):
    result=s.read_json(test_result)
    s.require(result['status']=='PASS' and result['tests_run']==result['tests_passed'],'TEST_FAILURE')
    old=s.ROOT/'runs/frontend_task_knowledge_transfer_implementation_v1_20260911'
    s.manifest(old,'5130c6a473cb7251cbe335b14c11d4e39b1b4c6e7251231890707020efeecfad')
    cfg=s.read_json(old/'config.json')
    for path,h in cfg['code_pins'].items():
        s.require(s.sha(s.ROOT/path)==h,'FROZEN_V1_CODE_CHANGED')
    pins={p.relative_to(s.ROOT).as_posix():s.sha(p) for p in closure()}
    s.require(pins==result['tested_code_pins'],'CODE_CHANGED_SINCE_TESTS')
    pins.update(cfg['code_pins'])
    for p in (s.ROOT/'scripts').glob('*frontend_task_knowledge_transfer_v2.ps1'):
        pins[p.relative_to(s.ROOT).as_posix()]=s.sha(p)
    cfg.update(code_pins=pins,scope='V2 fixes progress I/O using an append-only journal; new real T/E attempt not authorized. Reuse sealed P V1.',
               reused_P_manifest_sha256=control.P_SEAL,test_result_sha256=s.sha(test_result))
    for path,h in cfg['unrelated_tracked_sha256'].items():s.require(s.sha(s.ROOT/path)==h,'UNRELATED_CHANGED')
    s.PACKAGE.mkdir(exist_ok=False)
    s.atomic_json(s.PACKAGE/'config.json',cfg)
    s.atomic_json(s.PACKAGE/'acceptance.json',dict(result,config_sha256=s.sha(s.PACKAGE/'config.json')))
    (s.PACKAGE/'README.md').write_text('# V2进度读写修复\n\n追加式进度日志避免替换读者打开的文件；不重试I/O，不重试训练。\n'
        'P V1复用；T/E使用V2独立目录及新的显式授权。冻结的模型/损失/分母/预算不变。\n',encoding='utf-8')
    s.seal(s.PACKAGE);s.manifest(s.PACKAGE)
    print(json.dumps(dict(status='V2_IMPLEMENTATION_SEALED',tests_passed=result['tests_passed'],source_pins=len(pins),
                         manifest_sha256=s.sha(s.PACKAGE/'SHA256SUMS'),real_V2_started=False)))


if __name__=='__main__':
    build(Path(sys.argv[1]))
