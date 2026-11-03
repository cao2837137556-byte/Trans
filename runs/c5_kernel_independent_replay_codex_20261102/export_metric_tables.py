"""Render the completed independent replay; no scoring or distance calculation."""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
data = json.loads((BASE / 'ab/RESULT.json').read_text(encoding='utf-8'))


def pct(value):
    return 'NA' if value is None else f'{100 * value:.9f}'


lines = [
    '# C5 独立复算完整指标表', '',
    '2026-11-02；CONSUMED_DEVELOPMENT_ONLY。所有率均为百分比。', '',
    'A=CIC_DEV，B=UNSW_DEV；primary 为 7200 秒观察窗后主视图，full 为全时段。', '',
    '加权率沿用冻结组件权重；逐样本率直接按查询行计数。二者不可混称。', '',
    '保护门对 RAW 的累计撤警计算，不以 C4 为安全基线；新增漏报列单列相对 C4 的变化。', '',
    '## 两池、两视图、四头：80 行', '',
    '|p|池|视图|头|正常N|FP|逐样本FPR%|加权FPR%|攻击N|FN|逐样本召回%|加权召回%|新增FN vs C4|RAW累计保护门|设备宏平均逐样本FPR%|设备宏平均逐样本召回%|',
    '|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|',
]
pool_rows = 0
device_rows = 0
for p in data['candidate_order']:
    p = str(p)
    for pool, pd in data['pools'].items():
        for view, vd in pd['candidates'][p]['views'].items():
            for head, report in vd['reports'].items():
                n, a = report['corrected']['normal'], report['corrected']['attack']
                macro = report['macro_sample']
                values = [p, pool, view, head, n['rows'], n['positive'], pct(n['rate']),
                          pct(n['weighted_rate']), a['rows'], a['negative'], pct(a['rate']),
                          pct(a['weighted_rate']), report['new_attack_misses_vs_C4'],
                          report['protection']['status'], pct(macro['device_macro_sample_fpr']),
                          pct(macro['device_macro_sample_recall'])]
                lines.append('|' + '|'.join(map(str, values)) + '|')
                pool_rows += 1
lines += ['', '## 逐设备：全部候选、视图和头', '',
          '|p|池|视图|头|设备|正常N|FP|逐样本FPR%|加权FPR%|攻击N|FN|逐样本召回%|加权召回%|',
          '|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
for p in data['candidate_order']:
    p = str(p)
    for pool, pd in data['pools'].items():
        for view, vd in pd['candidates'][p]['views'].items():
            for head, report in vd['reports'].items():
                for group in report['groups']['device']:
                    n, a = group['corrected']['normal'], group['corrected']['attack']
                    values = [p, pool, view, head, group['group']['device'], n['rows'],
                              n['positive'], pct(n['rate']), pct(n['weighted_rate']), a['rows'],
                              a['negative'], pct(a['rate']), pct(a['weighted_rate'])]
                    lines.append('|' + '|'.join(map(str, values)) + '|')
                    device_rows += 1
lines += ['', '## A 新增漏报：相对 C4 的完整分账', '',
          '|p|头|新增行数|池攻击权重质量|设备|活动|TCP flags|capture|annotation|',
          '|---|---|---:|---:|---|---|---|---|---|']
for p in data['candidate_order']:
    p = str(p)
    for head, delta in data['pools']['CIC_DEV']['candidates'][p]['added_attack_vs_C4'].items():
        groups = delta['groups']
        values = [p, head, delta['rows'], f"{delta['weighted_attack_mass']:.16g}"]
        values += [json.dumps(groups[k], ensure_ascii=False, sort_keys=True)
                   for k in ['device', 'activity', 'tcp_flags', 'capture_id', 'annotation_id']]
        lines.append('|' + '|'.join(map(str, values)) + '|')
lines += ['', '## HIST_DEV 四头及逐设备计数', '',
          '|p|设备/合计|正常N|FP27|FP127|FP227|FPensemble|',
          '|---|---|---:|---:|---:|---:|---:|']
for p, candidate in data['dev']['candidates'].items():
    for name, item in [('ALL', candidate), *candidate['devices'].items()]:
        values = [p, name, item['rows']] + [item['fp_by_head'][h] for h in ['27', '127', '227', 'ensemble']]
        lines.append('|' + '|'.join(map(str, values)) + '|')
lines += ['', f'表内共 {pool_rows} 行池级指标、{device_rows} 行逐设备指标。', '',
          '机器全精度、全部分组保护细节见 ab/RESULT.json；逐 UID 新增漏报见 ab/*_new_attack_misses.jsonl.gz。', '']
assert pool_rows == 80
assert device_rows == 280
(BASE / 'METRIC_TABLES.md').write_text('\n'.join(lines), encoding='utf-8')
print(json.dumps({'status': 'PASS', 'pool_rows': pool_rows, 'device_rows': device_rows,
                  'output': str(BASE / 'METRIC_TABLES.md')}, ensure_ascii=False))
