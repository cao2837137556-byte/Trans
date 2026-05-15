from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs" / "issue16_harder_holdout_second_environment_feasibility_2026-05-15"
WORKTREES = ROOT.parent


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys: list[str] = []
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def exists(path: Path) -> str:
    return "yes" if path.exists() else "no"


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def load_v74_specs() -> list[dict[str, str]]:
    specs_path = WORKTREES / "kitnet-frontend-f2" / "runs" / "frontend_f2_v7_4_paired_holdout_fairness_2026-04-22" / "frontend_f2_v7_4_holdout_specs.csv"
    if not specs_path.exists():
        return []
    with specs_path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def maybe_read_summary_snippet(path: Path, needle: str | None = None, max_lines: int = 80) -> str:
    if not path.exists():
        return "missing"
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if needle:
        hits = [line for line in lines if needle.lower() in line.lower()]
        if hits:
            return " | ".join(hits[:5])
    return " | ".join(lines[:max_lines])


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    issue13 = ROOT / "runs" / "issue13_deployment_timeline_activation_evidence_pack_2026-05-15"
    issue14b = ROOT / "runs" / "issue14b_gda_minimal_score_recovery_for_arbitration_2026-05-15"
    issue15 = ROOT / "runs" / "issue15_review_budget_constrained_arbitration_2026-05-15"
    issue11 = ROOT / "runs" / "issue11_fixed_config_ood_guard_lr_ablation_2026-05-14"
    issue12 = ROOT / "runs" / "issue12_base_detector_representation_recovery_and_guarded_probe_2026-05-15"
    issue09 = ROOT / "runs" / "issue09_source_rich_representation_probe_2026-05-14"
    issue10 = ROOT / "runs" / "issue10_minimal_ood_guarded_lr_source_rich_2026-05-14"
    e4 = ROOT / "runs" / "e4_second_environment_feasibility_inventory_2026-05-08"

    v74_dir = WORKTREES / "kitnet-frontend-f2" / "runs" / "frontend_f2_v7_4_paired_holdout_fairness_2026-04-22"
    bot_dir = WORKTREES / "data" / "5%"
    ton_csv = WORKTREES / "data" / "Train_Test_Network_dataset" / "train_test_network.csv"
    ton_zip = WORKTREES / "data" / "Train_Test_Network_dataset.zip"

    v74_specs = load_v74_specs()
    v74_spec_summary = "; ".join(
        f"{r.get('holdout_name')} train={r.get('train_bins')} eval={r.get('eval_bins')} attack_eval={r.get('attack_eval_count')}"
        for r in v74_specs[:9]
    ) or "not_found"

    candidate_rows: list[dict[str, object]] = [
        {
            "candidate_name": "current_primary_low_ood_split",
            "candidate_type": "reference_current_split_not_holdout",
            "data_path": rel(issue11),
            "feature_available": "original100/source_rich/current scores available for current split",
            "label_available": "yes",
            "sample_id_alignment_possible": "yes_current_split_only",
            "benign_attack_ood_composition": "ID benign, OOD benign, high-purity attack per current protocol",
            "expected_size": "see issue11/issue14b manifests",
            "can_reuse_current_GDA_model": "yes_current_eval_only",
            "can_reuse_current_threshold": "yes_current_protocol",
            "leakage_risk": "low if only used as current reference; high if mislabeled as holdout",
            "comparability_risk": "not a harder holdout",
            "estimated_effort": "none",
            "recommendation": "not_comparable",
            "notes": "Already the main evaluation split; useful as baseline, not as issue16 validation.",
        },
        {
            "candidate_name": "frontend_f2_v7_4_paired_holdout_fairness",
            "candidate_type": "existing_harder_holdout_evidence",
            "data_path": str(v74_dir),
            "feature_available": "paired original100/source_rich result assets; reusable feature/model artifacts unknown",
            "label_available": "yes_in_existing_results",
            "sample_id_alignment_possible": "partial; existing paired holdout specs exist, but current GDA-minimal row-level model/scaler transfer not established",
            "benign_attack_ood_composition": "paired holdout windows with attack train/eval windows; see specs",
            "expected_size": v74_spec_summary,
            "can_reuse_current_GDA_model": "no_not_without_model_scaler_score_recovery",
            "can_reuse_current_threshold": "no_for_formal_transfer; can define fixed protocol in new run",
            "leakage_risk": "medium; must freeze support/eval windows and avoid final eval thresholding",
            "comparability_risk": "medium; existing v7.4 is source_rich/original100 hard-holdout, not current GDA-minimal",
            "estimated_effort": "medium",
            "recommendation": "needs_recovery",
            "notes": "Best near-term harder-holdout candidate, but it should be run as a separate fixed-config hard-holdout protocol, not as a zero-risk tiny validation.",
        },
        {
            "candidate_name": "v7_4_chrono_late_train_early_eval",
            "candidate_type": "representative_cross_time_hard_holdout",
            "data_path": str(v74_dir / "frontend_f2_v7_4_paired_holdout_summary.csv"),
            "feature_available": "existing summary/result rows; raw aligned GDA feature tensors unknown",
            "label_available": "yes_in_existing_results",
            "sample_id_alignment_possible": "partial",
            "benign_attack_ood_composition": "train attack bins 6,7,8; eval attack bins 2,3,4; attack_eval_count 3426",
            "expected_size": "train_pool=2568; attack_eval=3426; from v7.4 specs",
            "can_reuse_current_GDA_model": "no",
            "can_reuse_current_threshold": "no; needs formal fixed-config protocol",
            "leakage_risk": "medium",
            "comparability_risk": "medium",
            "estimated_effort": "medium",
            "recommendation": "needs_recovery",
            "notes": "Strong candidate for issue16b because it is temporally meaningful and already used as representative hard-holdout evidence.",
        },
        {
            "candidate_name": "v7_4_holdout_bin_2",
            "candidate_type": "leave_one_attack_window_out",
            "data_path": str(v74_dir / "frontend_f2_v7_4_holdout_specs.csv"),
            "feature_available": "existing summary/result rows; raw aligned GDA feature tensors unknown",
            "label_available": "yes_in_existing_results",
            "sample_id_alignment_possible": "partial",
            "benign_attack_ood_composition": "train bins 3,4,5,6,7,8; eval bin 2; attack_eval_count 1348",
            "expected_size": "train_pool=5523; attack_eval=1348",
            "can_reuse_current_GDA_model": "no",
            "can_reuse_current_threshold": "no; needs formal fixed-config protocol",
            "leakage_risk": "medium",
            "comparability_risk": "medium",
            "estimated_effort": "medium",
            "recommendation": "needs_recovery",
            "notes": "Useful supplementary hard-holdout candidate; smaller eval than chrono_late_train_early_eval.",
        },
        {
            "candidate_name": "BoT-IoT_5_percent_local_assets",
            "candidate_type": "external_second_environment_candidate",
            "data_path": str(bot_dir),
            "feature_available": "raw/processed CSV assets present; current original100/source_rich/GDA features absent",
            "label_available": "yes_raw_labels_likely_available",
            "sample_id_alignment_possible": "not_currently",
            "benign_attack_ood_composition": "prior E4 gate found benign support too small for clean low-OOD protocol",
            "expected_size": "prior E4: full10best total 3668522, benign 477, attack 3668045",
            "can_reuse_current_GDA_model": "no",
            "can_reuse_current_threshold": "no",
            "leakage_risk": "high if forced",
            "comparability_risk": "high; feature semantics and benign/OOD definition mismatch",
            "estimated_effort": "high",
            "recommendation": "not_comparable",
            "notes": "Do not force as second environment under current protocol; benign volume blocks clean OOD/control construction.",
        },
        {
            "candidate_name": "TON-IoT_train_test_network_local_asset",
            "candidate_type": "external_second_environment_candidate",
            "data_path": str(ton_csv if ton_csv.exists() else ton_zip),
            "feature_available": "TON numeric feature asset exists; current original100/source_rich/GDA features absent",
            "label_available": "yes_raw_labels_likely_available",
            "sample_id_alignment_possible": "not_currently",
            "benign_attack_ood_composition": "prior local split used ID/OOD/attack but not current original100/source_rich same-protocol representation",
            "expected_size": "prior E4: ID-train 8000, ID-eval 4000, OOD-eval 8000, attack-eval 12000, 16 numeric features",
            "can_reuse_current_GDA_model": "no",
            "can_reuse_current_threshold": "no",
            "leakage_risk": "medium-high",
            "comparability_risk": "high; old cache and different feature space",
            "estimated_effort": "high",
            "recommendation": "needs_recovery",
            "notes": "Potential future second-environment acquisition/conversion task; not ready for issue16b validation.",
        },
        {
            "candidate_name": "issue12_transformer_hidden_current_split",
            "candidate_type": "current_split_representation_integration",
            "data_path": rel(issue12),
            "feature_available": "Transformer hidden recovered for current split",
            "label_available": "yes_current_split",
            "sample_id_alignment_possible": "yes_current_split_only",
            "benign_attack_ood_composition": "current low-OOD split only",
            "expected_size": "see issue12 reports",
            "can_reuse_current_GDA_model": "yes_current_split_only",
            "can_reuse_current_threshold": "yes_current_protocol",
            "leakage_risk": "low for current split, high if treated as generalization",
            "comparability_risk": "not a harder holdout",
            "estimated_effort": "none",
            "recommendation": "not_comparable",
            "notes": "Useful for representation integration evidence, not issue16 harder holdout.",
        },
    ]

    write_csv(OUT / "harder_holdout_candidate_inventory.csv", candidate_rows)

    tiny_validation_rows = [
        {
            "status": "not_run",
            "reason": "No zero-risk usable_now harder holdout was found with aligned current GDA-minimal model/scaler/threshold and held-out feature rows. Existing v7.4 hard-holdout evidence needs protocol recovery before formal validation.",
            "candidate": "",
            "metric": "",
            "value": "",
        }
    ]
    write_csv(OUT / "tiny_validation_results.csv", tiny_validation_rows)

    risk_rows = [
        {
            "risk_name": "non-comparable feature risk",
            "severity": "high",
            "reason": "External assets use different feature spaces and do not have current original100/source_rich/GDA feature manifests.",
            "mitigation": "Require feature extraction/version manifest before validation.",
            "recommend_continue": "no_for_external_now",
        },
        {
            "risk_name": "label mismatch risk",
            "severity": "high",
            "reason": "External datasets may not provide the same ID benign, OOD benign, and high-purity attack roles.",
            "mitigation": "Create dataset-specific role manifest and reject if roles cannot be separated.",
            "recommend_continue": "no_until_manifest",
        },
        {
            "risk_name": "row-id alignment risk",
            "severity": "high",
            "reason": "Current GDA-minimal row-level scores only cover current split; v7.4/external candidates lack aligned row-level GDA scores.",
            "mitigation": "Recover fixed-config score generation with sample_id manifest.",
            "recommend_continue": "yes_for_v74_recovery",
        },
        {
            "risk_name": "threshold transfer risk",
            "severity": "medium",
            "reason": "Reusing current threshold across a changed holdout may be invalid unless strict transfer is the explicit goal.",
            "mitigation": "Separate strict-threshold-transfer from protocol-recalibrated hard-holdout evaluation.",
            "recommend_continue": "yes_with_protocol_split",
        },
        {
            "risk_name": "support leakage risk",
            "severity": "high",
            "reason": "Hard-holdout runs need new support/eval disjointness checks if support pools change.",
            "mitigation": "Emit support_id_provenance and validation CSV for every candidate.",
            "recommend_continue": "yes_with_audit",
        },
        {
            "risk_name": "cherry-pick holdout risk",
            "severity": "medium",
            "reason": "Choosing only one favorable v7.4 window would weaken credibility.",
            "mitigation": "Pre-register representative chrono_late_train_early_eval and at least one bin holdout before running.",
            "recommend_continue": "yes",
        },
        {
            "risk_name": "external dataset conversion risk",
            "severity": "high",
            "reason": "BoT-IoT and TON-IoT need substantial protocol conversion and may not support current low-OOD roles.",
            "mitigation": "Do not download or convert in this turn; plan a separate second-environment acquisition task.",
            "recommend_continue": "no_now",
        },
        {
            "risk_name": "overclaiming generalization risk",
            "severity": "high",
            "reason": "Existing hard-holdout and current-split results do not prove second-environment external validity.",
            "mitigation": "Use limitation language until formal issue16b or external validation is complete.",
            "recommend_continue": "yes_with_boundary",
        },
    ]
    write_csv(OUT / "risk_register.csv", risk_rows)

    evidence_gap = """
# Evidence Gap Table

| Gap | Current status | Why it matters | Next action |
|---|---|---|---|
| Harder holdout | Existing v7.4 paired hard-holdout evidence exists, but not for current GDA-minimal fixed-guard score pipeline. | Needed to show the deployment mechanism survives harder cross-window attack evaluation. | Run issue16b fixed-config hard-holdout recovery on chrono_late_train_early_eval and one bin holdout. |
| Second environment | BoT-IoT and TON-IoT local assets exist but are not current-protocol ready. | Needed for external validity beyond the current capture. | Build a separate acquisition/conversion plan with feature, label, and role manifests. |
| Adapter upgrade | Paused intentionally. | Upgrading LR before generalization may overfit the current split. | Wait until issue16b reveals whether fixed-guard GDA-minimal transfers. |
| Formal ablation tables | issue11/14/15 provide strong current-split mechanism evidence. | Need final paper integration only after deciding whether issue16b succeeds. | Keep as current evidence, do not rewrite manuscript in this turn. |
| Paper integration | Not modified. | Prevents premature claim drift. | Integrate only after issue16b/external decision. |
"""
    write_text(OUT / "evidence_gap_table.md", evidence_gap)

    second_env = f"""
# 第二环境资产缺口

## 1. 已找到的本地资产

- BoT-IoT 5% 本地资产：`{bot_dir}`。上一轮 E4 gate 已发现 10-best full 资产中 benign 只有 477 行、attack 3,668,045 行，无法干净构造当前 low-OOD 协议需要的良性 OOD / 校准 / 评估角色。
- TON-IoT network 资产：`{ton_csv if ton_csv.exists() else ton_zip}`。上一轮 E4 使用过一个 16 维 numeric split（ID-train 8000、ID-eval 4000、OOD-eval 8000、attack-eval 12000），但它不是当前 original100/source_rich/GDA 特征空间。

## 2. 正式第二环境仍缺什么

- 能区分 ID benign、OOD benign、high-purity attack train candidate、validation、final evaluation 的 role manifest。
- 与 original100 可比的特征抽取，或者一个明确说明不可比但自洽的替代表征。
- 能支持 support provenance、threshold provenance 和 final-eval exclusion 检查的 row-id manifest。
- 同一 split 下的 base detector score 与 GDA-minimal score。
- 不使用 final OOD eval 或 attack eval 的预注册阈值协议。

## 3. 建议

不要把 BoT-IoT 或 TON-IoT 当作当前可立即使用的 second-environment validation。如果要推进外部环境验证，应另开 `second_environment_asset_acquisition_and_protocol_conversion` 任务，先补齐数据角色、特征、标签与 row-id manifest，再做模型评估。
"""
    write_text(OUT / "second_environment_asset_gap.md", second_env)

    protocol = """
# 最小 harder-holdout 验证协议草案

## 1. 推荐的首个正式候选

优先使用 `frontend_f2_v7_4_paired_holdout_fairness_2026-04-22`。其中 `chrono_late_train_early_eval` 适合作为代表性跨时间窗口 holdout，`holdout_bin_2` 适合作为补充 bin holdout。

## 2. 模型与固定配置

- 主方法：original100 fixed-guard LR，32-shot。
- 固定 OOD guard：OOD weight = 2，attack weight = 1，ID benign weight = 1。
- 不搜索 OOD weight、C、seed、support pool、threshold 或 scaler。
- source_rich 和 Transformer hidden 只能作为预注册的 secondary/sensitivity，不应作为默认主线。

## 3. 两种评估模式必须区分

1. Strict threshold transfer：
   - 只有当 score generation 与 calibration 语义完全一致时，才复用已有 threshold。
   - 需要明确报告为 strict transfer，并允许结果变差。

2. Protocol-recalibrated hard holdout：
   - 在 hard-holdout train side 上按固定配置重新训练 adapter。
   - threshold 只能来自 ID calibration + OOD validation。
   - final OOD 与 hard-holdout attack evaluation 只用于最终评估。
   - 这是一个单独的 hard-holdout setting，不是当前 row-level score 的直接迁移。

## 4. issue16b 必须输出

- `support_id_provenance.csv`：证明 support 与 eval 窗口 disjoint。
- `threshold_provenance.csv`：证明 final OOD / attack eval 未参与阈值选择。
- `method_comparison_summary.csv`：至少包含 original100 plain、original100 fixed guard，可选 source_rich/hidden fixed guard。
- 如果后续要做 arbitration，还必须输出 row-level score。

## 5. 泄漏控制

- 不从 attack eval window 抽 support。
- 不在 final OOD eval 或 attack eval 上 fit scaler。
- 不在看过 final metric 后选择 holdout window。
- negative 或 infeasible 结果也应作为边界证据如实记录。
"""
    write_text(OUT / "minimal_harder_holdout_protocol.md", protocol)

    recommended = """
# 下一步建议

## 1. 当前决策

暂时不要升级 adapter。只有在恢复 v7.4 hard-holdout 资产的固定配置 feature/model/scaler/score pipeline 后，才启动 `issue16b_harder_holdout_fixed_guard_validation_2026-05-15`。

## 2. 如果使用 v7.4

建议 issue16b 的最小设计为：

1. 预注册候选：`chrono_late_train_early_eval` 和 `holdout_bin_2`。
2. 运行 original100 fixed-guard LR，32-shot，OOD weight = 2；如成本允许，使用 seeds 42-51。
3. 加入 original100 plain LR 作为 paired no-guard control。
4. source_rich 只作为 secondary，因为 issue11 已显示 source_rich 不是稳定主驱动。
5. 必须先输出 support provenance 和 threshold provenance，再解释指标。

## 3. 如果 v7.4 recovery 失败

停止并输出 recovery report。不要强行把 BoT-IoT 或 TON-IoT 塞进当前协议。

## 4. 如果没有 harder-holdout 候选可用

转向 second-environment asset acquisition / protocol conversion 计划，先定义 role manifest 与 feature extraction，再做任何模型实验。

## 5. 论文边界

在 issue16b 或干净第二环境完成前，论文只能说当前机制已经在 primary split 和已有 hard-holdout audit 中获得支持；不能写成完整 external validity 已证明。
"""
    write_text(OUT / "recommended_next_action.md", recommended)

    doc_patch = """
# Suggested Mainline Docs Update

Do not edit the manuscript for issue16. If updating mainline docs later, append:

## 2026-05-15 Issue16 harder-holdout / second-environment feasibility

Issue16 found that the nearest usable harder-holdout asset is the existing frontend-f2 v7.4 paired hard-holdout pack, especially `chrono_late_train_early_eval` and `holdout_bin_2`. However, it is not yet a zero-risk validation target for current GDA-minimal because current fixed-guard model/scaler/row-level score artifacts do not directly transfer. BoT-IoT and TON-IoT local assets exist but are not current-protocol-ready second environments. Recommended next step is issue16b fixed-config hard-holdout validation on v7.4, with no hyperparameter search and full support/threshold provenance.
"""
    write_text(OUT / "doc_update_patch_suggestion.md", doc_patch)

    summary = f"""
# Issue16 harder-holdout / second-environment 可行性盘点总结

## 1. 本轮范围

本轮只做 harder holdout / second environment 的可行性盘点与最小验证设计。没有训练模型、没有调参、没有修改既有结果、没有修改论文主稿，也没有执行正式验证。

## 2. 当前状态

- issue13/14b/15 已经支持当前 primary low-OOD split 下的系统机制：GDA-minimal 作为 adaptation mode 的 high-priority alerting channel，base detector 通过 bounded review 作为可选 safety net。
- 当前最稳主方法仍是 `original100 fixed guard LR 32-shot`。
- 但项目还没有完成正式 harder-holdout 或 second-environment 泛化验证。

## 3. harder-holdout 候选

最接近可用的候选是已有 v7.4 paired hard-holdout pack：

`{v74_dir}`

该资产包含 `chrono_late_train_early_eval`、`holdout_bin_2` 等跨窗口设置。它适合作为 issue16b 的第一优先级候选，但不是“零风险、可立即 tiny validation”的对象，因为当前 GDA-minimal 的 fixed-guard model/scaler/row-level score 不能直接迁移到这些 holdout 窗口。正确做法是把它作为单独的 fixed-config hard-holdout validation，并重新输出 support / threshold provenance。

## 4. second-environment 候选

本地找到了 BoT-IoT 与 TON-IoT 资产，但都不能直接作为当前 same-protocol second environment：

- BoT-IoT 在上一轮 E4 中被 benign support 规模卡死，不适合强行构造当前 low-OOD 协议。
- TON-IoT 有本地 16 维 split/cache，但与 current original100/source_rich/GDA 特征空间不一致。

本轮没有下载或转换任何外部数据。

## 5. tiny validation

未执行 tiny validation。原因是没有候选同时满足：已有 original100/GDA 特征、完整 label、row-id 对齐、可复用 current model/scaler/threshold、且不需要重新训练或调参。

## 6. 下一步建议

如果继续泛化验证，建议启动 `issue16b_harder_holdout_fixed_guard_validation_2026-05-15`：预注册 `chrono_late_train_early_eval` 和一个 bin holdout，固定 OOD weight=2，不搜索超参，完整输出 support / threshold provenance。

如果 v7.4 recovery 失败，不建议马上升级 LR；应先做 second-environment acquisition / protocol conversion 计划。

## 7. 安全检查

- 修改论文主稿：False。
- 修改既有实验数字：False。
- 训练模型：False。
- 超参搜索：False。
- tiny validation：False。
- 新增泛化 claim：False。
"""
    write_text(OUT / "summary.md", summary)

    metadata = {
        "generated_at_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "root": str(ROOT),
        "inputs_checked": {
            "issue13": exists(issue13),
            "issue14b": exists(issue14b),
            "issue15": exists(issue15),
            "issue11": exists(issue11),
            "issue12": exists(issue12),
            "issue09": exists(issue09),
            "issue10": exists(issue10),
            "e4": exists(e4),
            "v7_4": exists(v74_dir),
            "bot_iot": exists(bot_dir),
            "ton_iot_csv": exists(ton_csv),
            "ton_iot_zip": exists(ton_zip),
        },
        "tiny_validation": "not_run",
    }
    write_text(OUT / "run_metadata.json", json.dumps(metadata, indent=2, ensure_ascii=False))

    manifest_rows = []
    for path in sorted(OUT.iterdir()):
        if path.name == "build_issue16_pack.py":
            role = "pack_generation_script"
        elif path.name == "summary.md":
            role = "Chinese feasibility summary"
        elif path.name == "harder_holdout_candidate_inventory.csv":
            role = "candidate inventory"
        elif path.name == "second_environment_asset_gap.md":
            role = "external environment gap report"
        elif path.name == "minimal_harder_holdout_protocol.md":
            role = "issue16b protocol design"
        elif path.name == "tiny_validation_results.csv":
            role = "not-run tiny validation status"
        elif path.name == "risk_register.csv":
            role = "risk register"
        elif path.name == "recommended_next_action.md":
            role = "next-action plan"
        elif path.name == "evidence_gap_table.md":
            role = "evidence gaps"
        elif path.name == "doc_update_patch_suggestion.md":
            role = "optional docs patch suggestion"
        else:
            role = "generated asset"
        manifest_rows.append(
            {
                "file_path": str(path),
                "asset_name": path.name,
                "role": role,
                "created_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            }
        )
    write_csv(OUT / "manifest.csv", manifest_rows, ["file_path", "asset_name", "role", "created_utc"])


if __name__ == "__main__":
    main()
