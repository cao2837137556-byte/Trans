"""Bounded ordinary completion report; never submit or retry HPC work."""
import argparse,hashlib,json,time
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[1]
def read(n):return json.loads((P/n).read_text(encoding='utf-8-sig'))
def run():
 receipt=read('EVALUATION_COMPLETION.json')
 for n,h in receipt['receipt_sha256'].items():assert hashlib.sha256((P/n).read_bytes()).hexdigest()==h,n
 d=read('DIAGNOSE_RESULT.json');pre=read('PREFLIGHT_RESULT.json');assert d['status']==pre['status']=='PASS' and not d['training'] and not d['deployment_change']
 for ph in ['PREFLIGHT','DIAGNOSE']:assert '|COMPLETED|0:0|' in read(ph+'_SCHEDULER.json')['stdout']
 e=d['pools']['EDGE'];miss=e['task1_raw_misses'];fp=e['task2_false_alarms'];withdraw=e['task2_http_withdrawals']
 assert miss['UDP']['rows']==268 and miss['HTTP']['rows']==34 and fp['ensemble']['rows']==1158 and withdraw['rows']==967
 old=json.loads((ROOT/'runs/device_context_evaluation_v1_20261105/EDGE_RESULT.json').read_text(encoding='utf-8-sig'))['arms']['FUSION790']['methods']
 raw_strata=old['RAW']['heads']['ensemble']['roles']['HTTP']['strata'];c5_strata=old['C5_P3']['heads']['ensemble']['roles']['HTTP']['strata']
 expected={k:v['alarm_count']-c5_strata[k]['alarm_count'] for k,v in raw_strata.items() if v['alarm_count']!=c5_strata[k]['alarm_count']}
 assert all(v>0 for v in expected.values()) and sum(expected.values())==967
 assert withdraw['strata']==expected=={'PSH_ACK':842,'ACK_ONLY':123,'FIN':1,'RST':1}

 pct=lambda x:f'{x*100:.6f}%'
 lines=['# 四项归因与三维C5离线验证：自动完成回执','','结果：两阶段工程完成、原始回执SHA与关键分母核验通过。','影响：仅离线反事实；原模型、阈值、部署和旧科学门不变。','下一步：依据以下结果作科学验收；自动回执不替代人工解释审查。','','## 固定口径','','FUSION790为唯一修复起点，STATS8只作归因。源FIT合法正常、同设备同协议二阶不同组件距离加权q90拟合rho_c；目标自身建档正常仅作匹配。dc为既有源FIT log1p标准化8维的RMS。rho_z/rho_q、lambda=0.25、p=3、SYN保护及原阈值均不变。','A/B现行封存C5含既有历史正常参考，二维/三维候选均仅使用两小时建档库。维度增益只在同库二维/三维之间比较；相对现行C5的变化也包含去掉历史参考的作用。','OLD尺度为已封存OLD782源FIT尺度，事前指定的非压缩对照，不是此次用Edge挑选的新估计器；本轮没有比较或选择额外尺度。','s=clip(1-second_joint,0,1)，实际扣分核为g(s)=1-(1-s)^3。高支持度与实际扣分、最大cap分别报告。8维没有syn_fraction。','','更正：独立复核文档将余下2条撤警误写为SYN；封存EDGE_RESULT与本次逐行统计均为FIN、RST各1条。原自动报告因此拒绝输出，本修订只修正报告期望来源，未修改远端结果或重跑计算。','','## 任务1：RAW漏检物理分组','','分母是保留的全样本：HTTP/UDP各20000，不删除冷启动、非入站或低速查询。高包率定义为1s或10s包率超过同协议建档正常p99，只是描述性界线。','','|攻击|漏检|<1s|<10s|非入站|暖机或非入站|成熟入站高包率|成熟入站正常包率范围|','|---|---:|---:|---:|---:|---:|---:|---:|']
 for role in ['UDP','HTTP']:
  g=miss[role]['groups'];lines.append('|'+ '|'.join([role,str(miss[role]['rows'])]+[str(g[n]['rows']) for n in ['warm_lt1','warm_lt10','noninbound','warm_or_noninbound','mature_inbound_high_pps','mature_inbound_normal_range_pps']])+'|')
 lines+=['','前3个条件可重叠，最后3类互斥且覆盖全部漏检。低速或暖机不证明物理不可检测；高包率漏检也只证明当前输入/边界未检出，不直接证明E3捷径是原因。真实8维分布、原始裕量与参考p99见DIAGNOSE_RESULT各组。','','### STATS8与FUSION790有符号贡献','','采用固定E3/q、context从标准化零到真实值的解析积分梯度；各维贡献和严格等于完整分数减参考分数。此参考可偏离联合分布，不是训练因果效应。局部梯度为最终点导数，符号与积分贡献可以不同。B采用primary攻击查询。','','各模型/数据分组如下。']
 for pool,group in [('EDGE','UDP'),('UNSW_DEV','label_1')]:
  for arm in ['STATS8','FUSION790']:
   q=d['pools'][pool]['signed_contributions'][arm]['groups']['ensemble'][group]
   lines+=['',f"{arm}/{pool}/{group}：{q['rows']}条，裕量中位数{q['margin']['p50']:.6f}，零context参考裕量中位数{q['baseline_margin']['p50']:.6f}，8维总贡献中位数{q['context_total']['p50']:.6f}。"]
   lines+=['','|模型/数据|特征|平均积分贡献|负贡献比例|局部负梯度比例|','|---|---|---:|---:|---:|']
   for f,v in q['fields'].items():lines.append(f"|{arm}/{pool}|{f}|{v['mean_ig']:.6f}|{pct(v['negative_ig_fraction'])}|{pct(v['gradient_negative_fraction'])}|")
 lines+=['','## 任务2：正常误报支持度/尺度与HTTP撤警','','|头|正常误报|support=0|0<support<0.8|support≥0.8|高支持且裕量超过最大cap|最大cap|','|---|---:|---:|---:|---:|---:|---:|']
 for head,v in fp.items():
  g=v['categories'];lines.append('|'+ '|'.join([head,str(v['rows'])]+[str(g[n]['rows']) for n in ['support_zero','support_low_0_to_08','support_ge08']]+[str(g['support_ge08']['above_max_cap']),f"{v['maximum_cap']:.6f}"])+'|')
 lines += ['',f"HTTP撤警{withdraw['rows']}条，分层{withdraw['strata']}；原匹配的两个组件代表都超出源rho_c的有{withdraw['both_old_matches_outside_context_radius']}条。三维+当前尺度恢复{withdraw['recovered_3d_current']}条，三维+旧尺度恢复{withdraw['recovered_3d_old']}条。",'旧二维匹配dc/rho_c、支持度变化、建档内部不同组件距离分布均见完整摘要；该反事实可以核实几何错配是否影响撤警，不证明泛化因果。','','## 任务3：原阈值下的A/B/Edge直接成绩','','表为集成；全3种子、普通/加权/HT、RAW撤警数均在JSON。','','|数据|方法|正常普通FPR|正常加权FPR|攻击普通检出（A/B）或HTTP/UDP（Edge）|攻击加权检出|','|---|---|---:|---:|---|---|']
 for pool,out in d['pools'].items():
  for method,heads in out['metrics'].items():
   q=heads['ensemble'];attack=['HTTP','UDP'] if pool=='EDGE' else ['ATTACK'];lines.append('|'+ '|'.join([pool,method,pct(q['NORMAL']['sample_rate']),pct(q['NORMAL']['hierarchical_rate']),'/'.join(pct(q[r]['sample_rate']) for r in attack),'/'.join(pct(q[r]['hierarchical_rate']) for r in attack)])+'|')
 high=sum(miss[r]['groups']['mature_inbound_high_pps']['rows'] for r in ['UDP','HTTP'])
 lines+=['','## 任务4：下一步路线（候选，待科学验收）','','任何减分式C5在原阈值下都不能超过RAW检出上限HTTP99.83%、UDP98.66%；因此单靠三维C5+尺度不可能同时满足全样本99.9%。不能把活跃期口径替换原目标。',f'本次成熟入站高包率漏检合计{high}条。若其占比显著，应优先针对这些固定样本检查8维单调性、源支持和表征边界；当前梯度/贡献不能独立证明E3捷径训练因果。', '三维C5和非压缩尺度若显著减少正常误报、恢复HTTP撤警，可作为后处理候选单独冻结验证；不能因此跳过RAW尾部问题。若主要漏检确实集中冷启动/低速，论文可补充场景检出延迟、活跃期召回等指标，同时完整保留全样本成绩。', '若成熟高包率漏检仍突出、局部负向依赖稳定，再设计源内E3块遮盖与受物理约束的单调分支小试；不能预先保证非负权重或遮盖一定改善，不能据本次Edge结果直接进入正式训练。','','## 资源与工件','',f"预检worker {pre['seconds']:.3f}s，完整诊断worker {d['seconds']:.3f}s；采样RSS峰值{max(pre['rss_peak_bytes'],d['rss_peak_bytes'])/2**30:.3f}GiB。Slurm完整计时见两阶段SCHEDULER。",'大数组、逐行梯度、参考距离与物理统计留超算；本地仅小型JSON回执与此报告。本轮不是独立外部测试，不做模型晋升。']
 report=ROOT/'runs/mainline_docs/collab/20261106_context_geometry_attribution_runtime_codex.md'
 report.write_bytes(('\n'.join(lines)+'\n').encode());Path(str(report)+'.sha256').write_bytes((hashlib.sha256(report.read_bytes()).hexdigest()+'  '+report.name+'\n').encode())
 result=dict(status='PASS',scope='ENGINEERING_AND_KEY_COUNTS_NOT_MANUAL_SCIENTIFIC_ACCEPTANCE',report=str(report),review_pending=True,training=False,deployment_change=False)
 (P/'AUTOMATIC_REPORT_RECEIPT.json').write_bytes((json.dumps(result,indent=2)+'\n').encode());print(result)
def main(watch=False):
 deadline=time.monotonic()+36*3600
 while True:
  if (P/'EVALUATION_COMPLETION.json').exists():run();return
  if (P/'CHAIN_STATE.json').exists() and read('CHAIN_STATE.json')['stage']=='STOP':return
  if not watch:raise RuntimeError('COMPLETION_NOT_AVAILABLE')
  if time.monotonic()>deadline:raise RuntimeError('BOUNDED_REPORT_WATCH_EXPIRED')
  time.sleep(10)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--watch',action='store_true');main(p.parse_args().watch)
