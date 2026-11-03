"""Publish the observed V3 startup facts; retain all earlier snapshot receipts."""
import json
from pathlib import Path

REV=Path(__file__).resolve().parent
ROOT=REV.parents[2]
receipt=json.loads((REV/'deployment_20261024/EXECUTION_RECEIPT.json').read_text(encoding='utf-8'))
assert receipt['status']=='STARTUP_ACCEPTED_FULL_CHAIN_RUNNING'
assert receipt['stage']=='validate' and receipt['remote_unittests']['tests_run']==54
note=(
    '**10月24日13:28最新启动验收：** 用户已授权“修复好了，就可以启动实验了。”。'
    '独立V3全链于北京时间13:26:46启动，新root `/srv/paper04/learned_onboarding_20261024_v3`、'
    'unit `paper04-learned-onboarding-20261024-v3`，原V1/V2现场和权重保留。'
    '13:28:17验收为active/running、无异常；真实Python3.9/Torch2.5.1下原49＋新增5＝54项全部通过，'
    'adapter另4项通过（真实目标读取0）。tests/prepare完成，当前validate；资源preflight、真实辅助头/模块训练、CAL和A/B仍待，'
    '科学结果暂无。已验16GiB硬限／8GiB RSS守卫／4线程／单重worker／零自动重试。'
    '普通程序按完整冻结链串行继续，科学FAIL继续配对，技术异常停链。'
    '既有18765页面已切到V3并验connected=true，不持续AI轮询。'
    '见 [执行复核](../learned_onboarding_v1_20261023/numeric_revision_v3_20261024/deployment_20261024/EXECUTION_REVIEW.md)'
    '／[执行回执](../learned_onboarding_v1_20261023/numeric_revision_v3_20261024/deployment_20261024/EXECUTION_RECEIPT.json)。'
    '下方“实验仍停止／未启动”等属于本次授权启动前的历史快照。'
)
for name in ('NEW_CHAT_START_HERE.md','mainline_handoff.md','mainline_experiment_map.md'):
    path=ROOT/'runs/mainline_docs'/name
    body=path.read_text(encoding='utf-8')
    body=body.replace('## 2026-10-24 最新：数值修订已验收，实验未重启',
                      '## 2026-10-24 13:18历史：数值修订已验收，实验未重启',1)
    body=body.replace('**10月24日最新数值修复回执：**',
                      '**10月24日13:18历史数值修复验收（当时尚未重启）：**',1)
    if name=='NEW_CHAT_START_HERE.md':
        body=body.replace('V2数值异常已定位，V3数值修订通过源侧验证；本地页面已恢复，原实验仍停止，全部现场保留，未自动重跑。',
                          'V3数值修订通过源侧验证，用户已授权并启动独立V3全链；原现场保留，进度页已切到V3。',1)
    title,rest=body.split('\n',1)
    heading='## 2026-10-24 13:28最新：独立V3已启动并通过启动验收\n\n' if name!='NEW_CHAT_START_HERE.md' else ''
    path.write_text(title+'\n\n'+heading+note+'\n'+rest,encoding='utf-8',newline='\n')
print('V3 launch facts published in all three navigation documents')
