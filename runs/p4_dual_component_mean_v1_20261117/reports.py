"""Verify both marginal tables against the same-query contingency cells."""
import math

A = 'P4_MAIN'
B = 'P4_DUAL_MEAN'
HEADS = ('27', '127', '227', 'ensemble')
POOLS = ('CIC_DEV', 'UNSW_DEV', 'EDGE')
KEY = ('pool', 'view', 'head', 'group', 'guard_stratum')
TOL = 2e-10
PRIMARY_CELLS = {
    ('CIC_DEV','NORMAL'): (18, 96041), ('CIC_DEV','ATTACK'): (79050, 79056),
    ('UNSW_DEV','NORMAL'): (130, 74444), ('UNSW_DEV','ATTACK'): (72543, 72553),
    ('EDGE','NORMAL'): (0, 20000), ('EDGE','HTTP'): (19958, 20000), ('EDGE','UDP'): (19732, 20000),
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def index(rows):
    result = {tuple(row[k] for k in KEY): row for row in rows}
    require(len(result) == len(rows), 'DUPLICATE_EVALUATION_CELL')
    return result


def matched(metrics, pairs):
    left = index([r for r in metrics if r['config'] == A])
    right = index([r for r in metrics if r['config'] == B])
    changes = index(pairs)
    require(left.keys() == right.keys() == changes.keys(), 'UNPAIRED_METRIC_CELLS')
    for key, r in changes.items():
        a, b = left[key], right[key]
        require(r['left'] == A and r['right'] == B and r['rows'] == a['rows'] == b['rows'] and
                sum(r['n'+v] for v in ('00','01','10','11')) == r['rows'] and
                r['n01'] == 0 and a['alarm_count'] == r['n10'] + r['n11'] and
                b['alarm_count'] == r['n11'], 'ALARM_SUBSET_OR_PAIRED_MARGINALS:' + str(key))
        for v in (a, b):
            require(math.isclose(v['sample_rate'], v['alarm_count']/v['rows'], abs_tol=TOL, rel_tol=0)
                    and math.isclose(v['hierarchical_rate'], v['weighted_numerator']/v['weighted_denominator'],
                                     abs_tol=TOL, rel_tol=0), 'RATE_DENOMINATOR')
        require(abs(a['weighted_denominator'] - r['weighted_denominator']) <= TOL and
                a['weighted_denominator'] == b['weighted_denominator'] and
                abs(b['weighted_numerator'] - r['weighted_n11']) <= TOL and
                abs(a['weighted_numerator'] - r['weighted_n10'] - r['weighted_n11']) <= TOL,
                'WEIGHTED_PAIRED_MARGINALS')
        if 'HT_denominator' in a:
            den = a['HT_denominator']
            require(den == b['HT_denominator'] and
                    abs(a['HT_rate'] - (r['ht_n11'] + r['ht_n10'])/den) <= TOL and
                    abs(b['HT_rate'] - r['ht_n11']/den) <= TOL, 'EDGE_HT_PAIRED_MARGINALS')
        if r['guard_stratum'] == 'GUARD_ON':
            require(r['n10'] == 0, 'BYPASS_WITHDRAWAL')
    return left, right, changes


def headline(metrics, pairs):
    a, b, changes = matched(metrics, pairs)
    report = []
    for pool in POOLS:
        for view in (('full',) if pool == 'EDGE' else ('post_window_primary', 'full')):
            for head in HEADS:
                groups = ('NORMAL','HTTP','UDP') if pool == 'EDGE' else ('NORMAL','ATTACK')
                for group in groups:
                    key = pool, view, head, group, 'ALL'
                    r = changes[key]
                    if head == 'ensemble' and (view == 'post_window_primary' or pool == 'EDGE'):
                        require((a[key]['alarm_count'], r['rows']) == PRIMARY_CELLS[pool, group],
                                'TABLE_9_ENSEMBLE:' + str(key))
                    report.append(dict(pool=pool, view=view, head=head, group=group, rows=r['rows'],
                                       weak=a[key]['alarm_count'], mean=b[key]['alarm_count'],
                                       withdrawn=r['n10'], added=r['n01']))
    return report


def paper_text(headline_rows, pre_job, job, pairs=()):
    rows = [r for r in headline_rows if r['head'] == 'ensemble' and
            (r['view'] == 'post_window_primary' or r['pool'] == 'EDGE')]
    cells = {(r['pool'],r['group']): r['withdrawn'] for r in rows}
    normal = sum(v for (p,g),v in cells.items() if g == 'NORMAL')
    attacks = sum(v for (p,g),v in cells.items() if g != 'NORMAL')
    paragraph = (
        f'在 v12 表 9 的开发对照库和三种子 MLP 集成上，要求两个不同通信组件均已匹配后，'
        f'用两者的平均支持度替代较弱匹配，合计额外撤回 {normal:,} 条正常误报，同时额外撤回 '
        f'{attacks:,} 条原本正确的攻击告警。CIC 建档后分别撤回 {cells["CIC_DEV","NORMAL"]:,} 和 '
        f'{cells["CIC_DEV","ATTACK"]:,} 条，UNSW 建档后分别撤回 {cells["UNSW_DEV","NORMAL"]:,} 和 '
        f'{cells["UNSW_DEV","ATTACK"]:,} 条。Edge 选中查询中，正常、HTTP、UDP 分别撤回 '
        f'{cells["EDGE","NORMAL"]:,}、{cells["EDGE","HTTP"]:,}、{cells["EDGE","UDP"]:,} 条。'
        '三个种子及集成逐查询均无新增告警，所有撤回均发生在协议旁路之外。')
    affected = [r for r in pairs if r['head'] == 'ensemble' and r['guard_stratum'] == 'GUARD_OFF'
                and r['group'].startswith('device:') and ' / protocol:' in r['group'] and r['n10'] > 0
                and (r['view'] == 'post_window_primary' or r['pool'] == 'EDGE')]
    detail = ('\n## 发生撤回的设备和协议\n\n'
              '|测试床|设备、协议与标签|非旁路撤回数|\n|---|---|---:|\n' +
              ''.join(f"|{r['pool']}|{r['group']}|{r['n10']}|\n" for r in affected)
              if affected else '')
    return ('# 双组件均值与较弱匹配对照\n\n' + paragraph +
            f'\n\n预检作业 {pre_job}，正式作业 {job}。下表以同一查询上的撤回数计数。\n\n'
            '|测试床|视图|种子或集成|组|查询数|较弱匹配告警|均值告警|额外撤回|新增|\n'
            '|---|---|---|---|---:|---:|---:|---:|---:|\n' +
            ''.join('|{pool}|{view}|{head}|{group}|{rows}|{weak}|{mean}|{withdrawn}|{added}|\n'.format(**r)
                    for r in headline_rows) + detail +
            '\n[样本级、分层加权与 Edge HT](METRICS.csv) · [分组配对](PAIRED.csv) · '
            '[变化查询的超算位置与 SHA](ARTIFACTS.json) · [正式验收](ACCEPTANCE.json)\n')
