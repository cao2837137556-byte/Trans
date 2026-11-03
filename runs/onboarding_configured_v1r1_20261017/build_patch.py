"""Clone the verified v1 release and replace only the delivery script/docs."""
import ast
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tarfile

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / 'onboarding_configured_v1_20261017'
OLD_NAME, NAME = OLD.name, HERE.name
sys.dont_write_bytecode = True
sys.path.insert(0, str(OLD / 'bundle/repo/ood'))
import continuous_common_v3 as c


def text(path, value):
    path.write_bytes(value.replace('\r\n', '\n').encode('utf-8'))


def main():
    original = c.read(OLD / 'validation.json')
    c.pin(OLD / original['archive'], original['archive_sha256'])
    c.verify(OLD / 'bundle')
    bundle = HERE / 'bundle'
    if bundle.exists():
        raise RuntimeError('PATCH_BUILD_NO_OVERWRITE')
    shutil.copytree(OLD / 'bundle', bundle)
    (bundle / 'SHA256SUMS').unlink()
    text(bundle / 'scripts/run.slurm', (HERE / 'delivery_scripts/run.slurm').read_text(encoding='utf-8'))
    intro = ('\n本次 v1r1 只修复交付状态：实验与导出分别记录；导出失败时作业返回非零。'
             '实验退出码优先保留，最终两份状态在导出后生成并单独回传。'
             '原科学代码、资源计划及 runtime_contract 逐字节继承 v1，runtime version 表示继承的计算协议。'
             '旧179项检查为继承证据，本次新增/重跑范围以 validation.json 为准。\n')
    for name in ('README.md', 'OPERATE_HPC.md'):
        body = (OLD / name).read_text(encoding='utf-8').replace(OLD_NAME, NAME)
        if name == 'README.md':
            body = body.replace('独立交付 v1（', '独立交付 v1r1（')
            first, rest = body.split('\n', 1)
            body = first + '\n' + intro + rest
        else:
            body += ('\n## 分开的退出状态\n\n'
                     '`experiment_exit_code.txt`记录实验/准备流程退出码，归档内保留；'
                     '`export_exit_code.txt`和`exit_code.txt`分别记录导出和整个作业的退出码，'
                     '在归档完成后产生，由回传脚本先单独取回。只有两者均成功，作业才返回0；'
                     '两者都失败时保留实验退出码，同时记录导出错误。\n\n'
                     '导出失败不代表需要重跑实验。保留远端结果，先检查原因，修复后仅重新导出；'
                     '原作业失败状态不改写成实验失败或伪造成功。回传脚本如发现导出失败会停止拉归档，'
                     '但已保存状态；手工补导出后的新归档需单独校验/拉取，原状态仍作为历史证据。\n')
        text(HERE / name, body)
        text(bundle / name, body)
    shutil.copyfile(OLD / 'RESOURCE_BUDGET.md', HERE / 'RESOURCE_BUDGET.md')
    changed = []
    for path in sorted(bundle.rglob('*')):
        if path.is_file():
            rel = path.relative_to(bundle).as_posix()
            if c.sha(path) != c.sha(OLD / 'bundle' / rel): changed.append(rel)
    assert changed == ['OPERATE_HPC.md', 'README.md', 'scripts/run.slurm'], changed
    for path in bundle.rglob('*.py'):
        ast.parse(path.read_text(encoding='utf-8-sig'), feature_version=(3, 9))
    c.seal(bundle)
    c.verify(bundle)
    archive = HERE / (NAME + '.tar.gz')
    with tarfile.open(archive, 'x:gz') as tar:
        for path in sorted(bundle.rglob('*')):
            if path.is_file(): tar.add(path, arcname=path.relative_to(bundle).as_posix(), recursive=False)
    installer = HERE / 'onboarding_install_v1.py'
    shutil.copyfile(OLD / 'onboarding_install_v1.py', installer)
    for path in (archive, installer):
        text(path.with_name(path.name + '.sha256'), c.sha(path) + '  ' + path.name + '\n')
    c.write(HERE / 'build_receipt.json', dict(status='BUILT_VALIDATION_PENDING',
        archive=archive.name, archive_sha256=c.sha(archive), archive_bytes=archive.stat().st_size,
        package_seal_sha256=c.sha(bundle / 'SHA256SUMS'),
        previous_archive_sha256=original['archive_sha256'],
        changed_payload_files=changed, unchanged_python_modules=89,
        resource_plan_sha256=c.sha(bundle / 'resource_plan.json'),
        runtime_contract_unchanged=True, resource_budget_reused=True,
        real_experiment=False, remote_actions=False))
    print(json.dumps(c.read(HERE / 'build_receipt.json')))


if __name__ == '__main__': main()
