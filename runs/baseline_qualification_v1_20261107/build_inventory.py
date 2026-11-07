"""Local read-only historical baseline inventory, no old metric promotion."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
GROUPS={
 'TabM official reusable':['repo/ood/vendor/tabm_v0_0_3/tabm.py','repo/ood/vendor/tabm_v0_0_3/UPSTREAM_PROVENANCE.md','repo/ood/issue27ckbm_tabm_causal_source_calibration_v1.py','runs/modern_head_new_lineage_v1_20261022/target_validation/tabm_batch256.json'],
 'DROCC historical':['repo/ood/issue27ckby_drocc_train_local_v1.py','repo/ood/issue27ckby_drocc_feature_dump_v1.py','repo/ood/issue27ckby_drocc_eval_local_v1.py'],
 'Frontend100 classical and DeepSVDD':['repo/ood/frontend100_external_baselines.py','repo/ood/frontend100_deep_svdd_baseline.py','runs/prism_handoffs/2026-04-08/prism_paper_revision_pack_2026-04-08/evidence_summaries/external_baselines_summary.md'],
}
def main():
 data={}
 for group,paths in GROUPS.items():
  data[group]=[]
  for n in paths:
   p=ROOT/n;assert p.is_file(),n;data[group].append(dict(path=n,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
 old=ROOT/'runs/issue25c_strong_baseline_pack_execution_for_enhanced_lowguard_top64_2026-05-18';assert old.is_dir()
 data['May strong baseline pack']=[dict(path=str(p.relative_to(ROOT)).replace('\\','/'),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(old.glob('*')) if p.is_file() and p.suffix in ('.json','.md','.csv') and p.stat().st_size<2*1024**2]
 (HERE/'EXISTING_INVENTORY.json').write_text(json.dumps(dict(scope='Existing code and historical results; no current790 matched evaluation certified',groups=data),indent=2),encoding='utf8')
 lines=['# 已有基线资产盘点','', '结果：找到可复用官方TabM代码和多轮历史基线；未将旧成绩认作当前790维、当前UID/建档/阈值口径的有效对比。','影响：复用成熟实现与经验，重新做身份和资源资格，不从零编造算法。','下一步：按EXECUTION_CARD完成当前数据的真实预检，再准备正式训练。','', '|资产组|现有材料|本轮用途/限制|','|---|---|---|']
 for group,items in data.items():lines.append('|'+group+'|'+str(len(items))+'份小文件，路径与SHA见JSON|源码/工程经验复用；旧前端、分割、校准或目标口径未与当前合同对齐，成绩不得直接进入主表|')
 lines+=['','已有内部OLD782/REFIT782/STATS8/FUSION790及C5几何消融已进入论文冻结包；这些不算新增外部基线。此次首批TabM、ModernNCA、Disent-AD官方源码分别固定commit，许可证与本地SHA随交付封存。','', '盘点不是穷尽仓库每个历史复制目录；按原实现和可追溯结果归组，避免把重复归档算成新方法。']
 (HERE/'EXISTING_INVENTORY.md').write_text('\n'.join(lines)+'\n',encoding='utf8');print({g:len(v) for g,v in data.items()})
if __name__=='__main__':main()
