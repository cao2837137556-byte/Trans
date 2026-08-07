# CKBX veto feasibility diagnostic v2 (read-only, seed 27, jobs 157624 + 153037)
# Question: can a unified C1-margin veto V=[c1_margin >= delta] rescue the attacks
# that CKBW M7 suppresses, without re-firing benign pools?
#   H(delta) = M7 OR V(delta),  M7 = frozen_ckbq_hard AND (tail_margin_score >= tau_n)
# Level-2 variant: fire veto ONLY on M7-suppressed rows (monotone 2D region probe).
# No training, no model change, no FINAL data (cooler-motor, seed 37/47 untouched).
import sys
import json
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(sys.executable).parent.parent.parent))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from daimon_runtime import setup_plot
setup_plot()

BASE = Path(r"D:\study\paper\anomaly_detection\paper04\worktrees")
CKBW = BASE / "_kimi_review/pullback_ckbw_157624/issue27ckbw_tail_margin_dual_control_v1_2026-08-03_seed27_amd_157624/ckbw_record_predictions.csv.gz"
CKBQ = BASE / "kitnet-exp-mainline/_hpc_pullback/issue27ckbq_seed27_amd_153037_recovered/extracted/issue27ckbq_causal_minirocket_consensus_v1_2026-07-17_seed27_amd_153037/ckbq_record_predictions.csv.gz"
OUT = BASE / "kitnet-exp-mainline/runs/mainline_docs/ckbx_veto_feasibility_20260807"
FIG = OUT / "figures"
FIG.mkdir(parents=True, exist_ok=True)

TAU_N = 0.971323
GLOBAL = "GLOBAL_ATTACK_PRESERVATION"
STEALTH = ["Merlin C&C Communication", "Telnet Brute Force", "Ingress Tool Transfer",
           "Reporting", "TCP Scan", "Mirai C&C Communication"]
ZERO_RECALL = ["CoAP Amplification", "UDP Scan"]
BENIGN_BUDGET = 0.01  # legal-leg reference: max tolerated veto fire on benign select

# ---------------------------------------------------------------- load + join
ckbw = pd.read_csv(CKBW)
ckbq = pd.read_csv(CKBQ)
assert not ckbw.duplicated(["held_value", "uid"]).any()
assert not ckbq.duplicated(["held_value", "uid"]).any()
ckbq_cols = ["held_value", "uid", "c1_score", "c1_candidate_threshold",
             "static_attack_score", "temporal_attack_score", "temporal_reliable",
             "history_events", "cold_fail_hard",
             "hard__M1-ShieldedStatic", "hard__M2-ShieldedTemporal",
             "hard__M3-StaticTemporalConsensus"]
m = ckbw.merge(ckbq[ckbq_cols], on=["held_value", "uid"], how="left", indicator=True)
assert len(m) == len(ckbw)
n_ton = int((m["_merge"] == "left_only").sum())
j = m[m["_merge"] == "both"]
assert bool(((j["c1_score"] >= j["c1_candidate_threshold"]) == j["c1_hard"]).all())
C1_THR = float(j["c1_candidate_threshold"].iloc[0])
assert float(j["c1_candidate_threshold"].std()) < 1e-12
print(f"join ok (ton-only={n_ton}); c1_candidate_threshold = {C1_THR:.15f}")

m["c1_margin"] = m["c1_score"] - C1_THR
h0 = m["frozen_ckbq_hard"].astype(bool).to_numpy()
tail = m["tail_margin_score"].to_numpy(dtype=float)
m7_col = m["hard__M7-TabM-TailMargin-DualControl"].astype(bool).to_numpy()
m7_sim = h0 & (tail >= TAU_N)
assert (m7_sim == m7_col).all(), "M7 formula reverse-engineering failed"
print("M7 formula verified: M7 = h0 AND (tail >= %.6f); suppress = h0 AND tail < tau_n" % TAU_N)
suppressed_row = h0 & (tail < TAU_N)

# ---------------------------------------------------------------- groups
g = m["held_value"].to_numpy()
role = m["role"].to_numpy()
af = m["attack_family"].to_numpy()
sg = m["source_group"].to_numpy()
is_glob = g == GLOBAL
groups = {
    "support_val_69": is_glob & (role == "support_val"),
    "aux_select_3000": is_glob & (role == "aux_select"),
    "aux_normal_select_ton_4000": is_glob & (role == "aux_normal_select"),
    "ood_hydraulic_3000": (g == "iotsim-hydraulic-system") & (role == "ood_val"),
    "ood_ip_camera_street_3000": (g == "iotsim-ip-camera-street") & (role == "sealed_final_ood"),
    "ood_predictive_maintenance_9000": (g == "iotsim-predictive-maintenance") & (role == "aux_report"),
    "ood_stream_consumer_3000": (g == "iotsim-stream-consumer") & (role == "ood_stress"),
    "same_file_query_2486": is_glob & (role == "same_file_query"),
    "sealed_final_attack_110104": is_glob & (role == "sealed_final_attack"),
}
for fam in STEALTH + ZERO_RECALL:
    groups["attack_" + fam] = is_glob & (role == "future_query") & (af == fam)
OOD_POOLS = ["ood_hydraulic_3000", "ood_ip_camera_street_3000",
             "ood_predictive_maintenance_9000", "ood_stream_consumer_3000"]
margin = m["c1_margin"].to_numpy(dtype=float)

# support_val identity: attack validation rows (must stay detected), NOT benign
sup_df = m[groups["support_val_69"]]
print("support_val attack_family:", sup_df["attack_family"].value_counts(dropna=False).to_dict())
print("support_val frozen_ckbq_hard rate: %.3f, m7 rate: %.3f, c1_hard rate: %.3f" % (
    h0[groups["support_val_69"]].mean(), m7_sim[groups["support_val_69"]].mean(),
    float((margin[groups["support_val_69"]] >= 0).mean())))

# ---------------------------------------------------------------- margin quantization
pct_rows = []
qs = [0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]
for name, mask in groups.items():
    mm = margin[mask]; mm = mm[~np.isnan(mm)]
    r = {"group": name, "n": int(mask.sum()), "n_c1_covered": len(mm),
         "m7_hard_rate": float(m7_sim[mask].mean()),
         "frozen_ckbq_hard_rate": float(h0[mask].mean()),
         "c1_hard_rate": float((mm >= 0).mean()) if len(mm) else np.nan}
    for q in qs:
        r[f"margin_p{int(q * 100):02d}"] = float(np.quantile(mm, q)) if len(mm) else np.nan
    pct_rows.append(r)
pd.DataFrame(pct_rows).to_csv(OUT / "group_percentiles.csv", index=False)

qrows = []
for name, mask in groups.items():
    mm = margin[mask]; mm = mm[~np.isnan(mm)]
    if len(mm) == 0:
        qrows.append({"group": name, "n": 0, "distinct_margins": 0, "share_at_group_max": np.nan,
                      "margin_max": np.nan})
        continue
    qrows.append({"group": name, "n": len(mm), "distinct_margins": int(pd.unique(mm).size),
                  "share_at_group_max": float((mm >= mm.max() - 1e-12).mean()),
                  "margin_max": float(mm.max())})
quant = pd.DataFrame(qrows)
quant.to_csv(OUT / "margin_quantization.csv", index=False)
print(quant.to_string())
# per-source constancy
ps = m[groups["aux_select_3000"]].groupby("source_group")["c1_score"].agg(["nunique", "min", "max", "size"])
print("aux_select per-source c1_score:", ps.to_string())

# ---------------------------------------------------------------- frontier engines
def veto_rates(marg, base, fireable, grid):
    """final hard rate, veto fire rate, newly-fired rate for H = base OR (fireable AND marg>=delta).
    Rows without C1 coverage (NaN margin) are never fired; they count as hard iff base."""
    n_total = len(marg)
    nok = np.isnan(marg)
    base_nok = int(base[nok].sum())
    ok = ~nok
    marg, base, fire = marg[ok], base[ok].astype(np.int8), fireable[ok]
    n = len(marg)
    if n == 0:
        r = np.full(len(grid), base_nok / n_total)
        z = np.zeros(len(grid))
        return r, z, z, 0
    order = np.argsort(marg, kind="stable")
    ms, bs, fs = marg[order], base[order], fire[order]
    bf = (bs.astype(bool) & fs).astype(np.int8)
    cumb = np.concatenate([[0], np.cumsum(bs)])
    cumbf = np.concatenate([[0], np.cumsum(bf)])
    cumf = np.concatenate([[0], np.cumsum(fs.astype(np.int8))])
    idx = np.searchsorted(ms, grid, side="left")
    fire_cnt = int(fs.sum()) - cumf[idx]            # fired rows (marg >= delta)
    base_fire = int(bf.sum()) - cumbf[idx]          # fired rows that were already base-hard
    final = (fire_cnt + int(bs.sum()) - base_fire + base_nok) / n_total
    newly = (fire_cnt - base_fire) / n_total
    return final, fire_cnt / n_total, newly, n

# delta grid: dense in the action zone + exact candidate values
cand = [0.0, 0.001359, 0.001364, 0.001495, 0.001514, 0.001566, 0.001569,
        0.001570, 0.001573, 0.001915, 0.0020]
grid = np.unique(np.concatenate([
    np.linspace(-0.99, -0.001, 100),
    np.linspace(-0.001, 0.0005, 150),
    np.linspace(0.0005, 0.00205, 1200),
    np.array(cand)]))
grid.sort()

rows = []
for name, mask in groups.items():
    fr1, vf1, nw1, n_cov = veto_rates(margin[mask], m7_sim[mask], np.ones(len(m), bool)[mask], grid)
    fr2, vf2, nw2, _ = veto_rates(margin[mask], m7_sim[mask], suppressed_row[mask], grid)
    rows.append(pd.DataFrame({
        "group": name, "delta": grid, "c1_score_at_delta": grid + C1_THR,
        "L1_final_hard_rate": fr1, "L1_veto_fire_rate": vf1, "L1_newly_fired_rate": nw1,
        "L2_final_hard_rate": fr2, "L2_newly_fired_rate": nw2,
        "n_rows": int(mask.sum()), "n_c1_covered": n_cov,
        "m7_hard_rate": float(m7_sim[mask].mean()),
        "frozen_ckbq_hard_rate": float(h0[mask].mean())}))
front = pd.concat(rows, ignore_index=True)
front.to_csv(OUT / "frontier_by_group.csv", index=False)

def curve(name, col="L1_final_hard_rate"):
    d = front[front["group"] == name]
    return d["delta"].to_numpy(), d[col].to_numpy()

delta = grid
ood1 = {p: curve(p)[1] for p in OOD_POOLS}
ood2 = {p: curve(p, "L2_final_hard_rate")[1] for p in OOD_POOLS}
ood_macro1 = np.mean(np.vstack([ood1[p] for p in OOD_POOLS]), axis=0)
ood_macro2 = np.mean(np.vstack([ood2[p] for p in OOD_POOLS]), axis=0)
st1 = {f: curve("attack_" + f)[1] for f in STEALTH}
st2 = {f: curve("attack_" + f, "L2_final_hard_rate")[1] for f in STEALTH}
worst1 = np.vstack([st1[f] for f in STEALTH]).min(axis=0)
worst1_x5 = np.vstack([st1[f] for f in STEALTH if f != "Mirai C&C Communication"]).min(axis=0)
worst2 = np.vstack([st2[f] for f in STEALTH]).min(axis=0)
aux_fire = curve("aux_select_3000", "L1_veto_fire_rate")[1]
aux_new = curve("aux_select_3000", "L1_newly_fired_rate")[1]
sup_recall = curve("support_val_69")[1]
ton_final = curve("aux_normal_select_ton_4000")[1]

# ---------------------------------------------------------------- oracle gate
REC_MIN, OOD_MAX = 0.90, 0.10
useful = (worst1 >= REC_MIN) & (ood_macro1 <= OOD_MAX)
useful_x5 = (worst1_x5 >= REC_MIN) & (ood_macro1 <= OOD_MAX)
useful2 = (worst2 >= REC_MIN) & (ood_macro2 <= OOD_MAX)
print("L1 useful region (6 fam):", useful.any(), "| excl Mirai:", useful_x5.any(), "| L2:", useful2.any())
c1_ceiling = {f: float((margin[groups['attack_' + f]] >= 0).mean()) for f in STEALTH + ZERO_RECALL}
print("veto recall ceiling per family (c1_hard frac):", {k: round(v, 4) for k, v in c1_ceiling.items()})

# ---------------------------------------------------------------- legal leg
aux_margins = margin[groups["aux_select_3000"]]
aux_margins = aux_margins[~np.isnan(aux_margins)]
legal_ok = aux_fire <= BENIGN_BUDGET
if legal_ok.any():
    i_b = int(np.flatnonzero(legal_ok)[0])
    delta_b = float(delta[i_b])
else:
    i_b, delta_b = len(delta) - 1, float(delta[-1])
print(f"legal reference delta_b (aux fire<=1%): {delta_b:.6f} -> stealth worst recall "
      f"{worst1[i_b]:.4f}, ood macro {ood_macro1[i_b]:.4f}, rescued-nothing check")
# LOFO over 5 aux sources: recompute delta_b without one source, measure held-out fire
aux_src = sg[groups["aux_select_3000"]]
lofo_rows = []
for s in sorted(pd.unique(aux_src)):
    rest = aux_margins[aux_src != s]
    held = aux_margins[aux_src == s]
    db = float(rest.max()) + 1e-12  # smallest delta that never fires on the 4 retained sources
    lofo_rows.append({"held_out_source": s, "n_held_out": len(held),
                      "delta_b_lofo": db, "held_out_fire_rate": float((held >= db).mean()),
                      "stealth_worst_recall_at_db": float(worst1[int(np.searchsorted(delta, db))])})
lofo_df = pd.DataFrame(lofo_rows)
lofo_df.to_csv(OUT / "lofo_aux_sources.csv", index=False)
print(lofo_df.to_string())

def metrics_at(i):
    out = {"delta": float(delta[i]), "c1_score": float(delta[i] + C1_THR),
           "ood_macro_L1": float(ood_macro1[i]), "worst_stealth_L1": float(worst1[i]),
           "worst_stealth_excl_mirai_L1": float(worst1_x5[i]),
           "ood_macro_L2": float(ood_macro2[i]), "worst_stealth_L2": float(worst2[i]),
           "aux_select_fire": float(aux_fire[i]), "support_recall": float(sup_recall[i]),
           "ton_final_hard": float(ton_final[i])}
    for f in STEALTH:
        out["recall_" + f] = float(st1[f][i])
    for p in OOD_POOLS:
        out["ood_" + p] = float(ood1[p][i])
    return out
i_zero = int(np.searchsorted(delta, 0.0))
eval_table = {"at_c1_hard_boundary(delta=0)": metrics_at(i_zero),
              "at_legal_budget_delta_b": metrics_at(i_b)}
with open(OUT / "eval_points.json", "w") as f:
    json.dump(eval_table, f, indent=2)
print(json.dumps(eval_table, indent=1)[:1800])

# ---------------------------------------------------------------- 27-row audit
benign_sel = is_glob & ((role == "aux_select") | (role == "aux_normal_select"))
hard27 = m[benign_sel & m["frozen_ckbq_hard"].astype(bool)].copy()
bs = margin[benign_sel]; bs = bs[~np.isnan(bs)]
hard27["c1_margin"] = hard27["c1_score"] - C1_THR
hard27["margin_quantile_in_benign_select"] = hard27["c1_margin"].map(
    lambda v: float((bs < v).mean()) if not np.isnan(v) else np.nan)
def branch(r):
    if pd.isna(r["hard__M3-StaticTemporalConsensus"]):
        return "ton_no_c1_coverage"
    p = []
    if r["hard__M1-ShieldedStatic"]: p.append("M1-static")
    if r["hard__M2-ShieldedTemporal"]: p.append("M2-temporal")
    if r["hard__M3-StaticTemporalConsensus"]: p.append("M3-consensus")
    return "+".join(p) if p else "none"
hard27["ckbq_branch"] = hard27.apply(branch, axis=1)
hard27[["held_value", "uid", "role", "source_group", "device_family", "c1_score", "c1_margin",
        "margin_quantile_in_benign_select", "tail_margin_score", "tabm_process_score",
        "hard__M1-ShieldedStatic", "hard__M2-ShieldedTemporal", "hard__M3-StaticTemporalConsensus",
        "ckbq_branch", "static_attack_score", "temporal_attack_score", "temporal_reliable",
        "history_events", "cold_fail_hard"]].to_csv(OUT / "audit_benign_select_baseline_hard.csv", index=False)
print(f"27-row audit written (n={len(hard27)}); branch counts:",
      hard27["ckbq_branch"].value_counts().to_dict())

# ---------------------------------------------------------------- suppressed pools
attack_mask = is_glob & ((role == "future_query") | (role == "sealed_final_attack"))
sup_att = attack_mask & suppressed_row
sup_df2 = m[sup_att].copy()
sup_df2["c1_margin"] = sup_df2["c1_score"] - C1_THR
by_fam = sup_df2.groupby("attack_family").agg(
    n_suppressed=("c1_margin", "size"),
    c1_hard_frac=("c1_margin", lambda s: float((s >= 0).mean())),
    rescued_frac_at_delta0=("c1_margin", lambda s: float((s >= 0).mean())),
    margin_p50=("c1_margin", "median"),
    margin_p95=("c1_margin", lambda s: float(np.quantile(s, 0.95))),
    margin_max=("c1_margin", "max")).reset_index()
by_fam.to_csv(OUT / "suppressed_attack_rescue_by_family.csv", index=False)
benign_pools = {p: groups[p] for p in OOD_POOLS}
benign_pools["aux_select_3000"] = groups["aux_select_3000"]
cost_rows = []
for p, mask in benign_pools.items():
    mm = margin[mask & ~m7_sim]  # rows that would otherwise stay clean
    mm = mm[~np.isnan(mm)]
    cost_rows.append({"pool": p, "n_clean_under_M7": len(mm),
                      "fired_at_delta0": float((mm >= 0).mean()),
                      "fired_at_0.0015": float((mm >= 0.0015).mean()),
                      "fired_at_delta_b": float((mm >= delta_b).mean()),
                      "margin_p50": float(np.quantile(mm, 0.5)),
                      "margin_p99": float(np.quantile(mm, 0.99)), "margin_max": float(mm.max())})
cost = pd.DataFrame(cost_rows)
cost.to_csv(OUT / "veto_cost_by_pool.csv", index=False)
print(cost.to_string())
print(f"suppressed attacks total: {int(sup_att.sum())}; c1_hard among them: "
      f"{float((sup_df2['c1_margin'] >= 0).mean()):.4f}")

# ---------------------------------------------------------------- verdict
oracle_separable = bool(useful.any())
if not oracle_separable:
    verdict = "STATE_1_ORACLE_INSEPARABLE_GO_EPISODE_B"
elif delta_b <= float(delta[useful].max()) and delta_b >= float(delta[useful].min()):
    verdict = "STATE_4_CHECK_LOFO"
else:
    verdict = "STATE_2_SEPARABLE_BUT_NOT_LEGALLY_SELECTABLE_NO_HPC"
reasons = []
if not oracle_separable:
    reasons.append("worst stealth family recall < 0.90 at EVERY delta: "
                   "veto ceilings (c1_hard frac) = " +
                   ", ".join(f"{k}={v:.3f}" for k, v in c1_ceiling.items()))
    reasons.append("benign aux_select (legal select pool) sits at the GLOBAL score max "
                   "(c1_score=1.0, margin=0.001915) for 100% of rows; any delta that rescues "
                   "stealth attacks fires on all of them")
verdict_blob = {"verdict": verdict, "reasons": reasons,
                "oracle_useful_region_exists_L1_6fam": bool(useful.any()),
                "oracle_useful_region_excl_mirai": bool(useful_x5.any()),
                "oracle_useful_region_L2_suppressed_only": bool(useful2.any()),
                "legal_delta_b_aux_budget_1pct": delta_b,
                "stealth_worst_recall_at_delta_b": float(worst1[i_b]),
                "c1_recall_ceiling_per_family": c1_ceiling,
                "suppressed_attacks": int(sup_att.sum()),
                "suppressed_attacks_c1_hard_frac": float((sup_df2["c1_margin"] >= 0).mean()),
                "ton_rows_no_c1_coverage": n_ton,
                "c1_threshold": C1_THR, "tau_n": TAU_N,
                "note": "VIEWED diagnostic pools used for oracle leg; qualitative hypothesis only, "
                        "no numeric cut may be carried into CKBX prereg from these pools."}
with open(OUT / "verdict.json", "w") as f:
    json.dump(verdict_blob, f, indent=2)
print("VERDICT:", verdict)
for r in reasons:
    print("  -", r)

# ============================================================ figures
rng = np.random.default_rng(27)

# ---- fig 1: margin ECDF
fig, ax = plt.subplots(figsize=(9, 5.5))
ecdf_groups = [("support_val_69", "support 攻击验证 69"),
               ("aux_select_3000", "aux select 良性 3000 (合法池)"),
               ("ood_hydraulic_3000", "OOD hydraulic"),
               ("ood_ip_camera_street_3000", "OOD ip-camera-street"),
               ("ood_predictive_maintenance_9000", "OOD predictive-maint"),
               ("ood_stream_consumer_3000", "OOD stream-consumer")]
for name, lab in ecdf_groups:
    mm = margin[groups[name]]; mm = mm[~np.isnan(mm)]
    xs = np.sort(mm); ys = np.arange(1, len(xs) + 1) / len(xs)
    ax.plot(xs, ys, label=lab, lw=1.4)
stealth_all = np.concatenate([margin[groups["attack_" + f]] for f in STEALTH])
stealth_all = stealth_all[~np.isnan(stealth_all)]
xs = np.sort(stealth_all); ys = np.arange(1, len(xs) + 1) / len(xs)
ax.plot(xs, ys, label="隐蔽攻击 6 族合并", lw=2.2, color="black")
ax.axvline(0, color="gray", ls=":", lw=1, label="c1_hard 边界")
ax.set_xlim(-0.01, 0.0022)
ax.set_xlabel("c1_margin = c1_score − 0.998085")
ax.set_ylabel("ECDF")
ax.set_title("各组 C1 margin 分布：合法良性 aux_select 压在全局最大值，\n比绝大多数隐蔽攻击更靠右——veto 轴方向反了")
ax.legend(fontsize=8, loc="center left")
fig.savefig(FIG / "fig1_margin_ecdf.png", bbox_inches="tight", dpi=150)
plt.close(fig)

# ---- fig 2: 2D scatter
fig, ax = plt.subplots(figsize=(9, 6.5))
def sample(mask, nmax):
    idx = np.flatnonzero(mask)
    return rng.choice(idx, min(len(idx), nmax), replace=False)
idx = np.flatnonzero(groups["support_val_69"])
ax.scatter(margin[idx], tail[idx], s=45, label="support 攻击验证 69", marker="o")
idx = sample(groups["aux_select_3000"], 3000)
ax.scatter(margin[idx], tail[idx], s=8, label="aux select 良性 (合法池)", alpha=0.6)
ood_all = np.zeros(len(m), bool)
for p in OOD_POOLS:
    ood_all |= groups[p]
idx = sample(ood_all, 18000)
ax.scatter(margin[idx], tail[idx], s=4, label="held OOD 4 池", alpha=0.25)
stealth_mask = np.zeros(len(m), bool)
for f in STEALTH:
    stealth_mask |= groups["attack_" + f]
idx = sample(stealth_mask, 15000)
ax.scatter(margin[idx], tail[idx], s=4, label="future 隐蔽攻击 6 族", alpha=0.25)
ax.axhline(TAU_N, color="purple", ls="--", lw=1.2, label=f"τn={TAU_N}（下方=M7 压掉区）")
ax.axvline(0, color="gray", ls=":", lw=1, label="c1_hard 边界")
ax.set_xlim(-0.01, 0.0022)
ax.set_xlabel("c1_margin")
ax.set_ylabel("tail_margin_score（51D）")
ax.set_title("τn 线以下是被 M7 压掉的行：攻击与良性在 c1_margin 轴上\n高度重叠，且良性 aux_select 占满最右端——冲突信号不足以做 veto")
ax.legend(fontsize=8, markerscale=3, loc="upper left")
fig.savefig(FIG / "fig2_scatter_2d.png", bbox_inches="tight", dpi=150)
plt.close(fig)

# ---- fig 3: metrics vs delta
fig, axes = plt.subplots(1, 3, figsize=(16, 4.8), sharex=True)
ax = axes[0]
for p in OOD_POOLS:
    ax.plot(delta, ood1[p], lw=1.1,
            label=p.replace("ood_", "").replace("_3000", "").replace("_9000", ""))
ax.plot(delta, ood_macro1, lw=2.4, color="black", label="macro")
ax.axhline(OOD_MAX, color="red", ls=":", lw=1)
ax.set_title("良性 OOD final hard rate vs δ"); ax.set_ylabel("rate"); ax.legend(fontsize=7)
ax = axes[1]
for f in STEALTH:
    ax.plot(delta, st1[f], lw=1.1, label=f.replace(" Communication", ""), )
ax.plot(delta, worst1, lw=2.4, color="black", label="最差族")
ax.axhline(REC_MIN, color="red", ls=":", lw=1)
ax.set_title("隐蔽攻击召回 vs δ\n（天花板=c1_hard 比例，5/6 族到不了 0.9）"); ax.legend(fontsize=7)
ax = axes[2]
ax.plot(delta, aux_fire, lw=2.0, label="aux_select veto 命中率")
ax.plot(delta, aux_new, lw=1.4, ls="--", label="aux_select 新增误报率")
ax.plot(delta, sup_recall, lw=1.4, label="support 攻击召回（恒 1.0）")
ax.plot(delta, ton_final, lw=1.4, ls=":", label="ToN 4000 final（无 C1 覆盖）")
ax.axvline(delta_b, color="red", ls="--", lw=1, label=f"δ_b={delta_b:.5f}")
ax.set_title("合法 select 池 vs δ"); ax.legend(fontsize=7)
for ax in axes:
    ax.set_xlabel("δ（c1_margin 阈值）")
    ax.set_xlim(-0.001, 0.0021)
fig.suptitle("两层 frontier：没有任何 δ 能同时满足 最差族召回≥0.9 且 OOD macro≤0.1", y=1.03)
fig.savefig(FIG / "fig3_metrics_vs_delta.png", bbox_inches="tight", dpi=150)
plt.close(fig)

# ---- fig 4: money plot - rescue of suppressed attacks vs newly-fired benign
sup_per_fam = {}
for f in STEALTH:
    mask_f = sup_att & (af == f)
    mm = margin[mask_f]; mm = mm[~np.isnan(mm)]
    n = len(mm)
    cnt = n - np.searchsorted(np.sort(mm), delta, side="left")
    sup_per_fam[f] = cnt / max(int(sup_att.sum()), 1)  # share of ALL suppressed attacks
mm = margin[sup_att]; mm = mm[~np.isnan(mm)]
resc_all = (len(mm) - np.searchsorted(np.sort(mm), delta, side="left")) / max(int(sup_att.sum()), 1)
fig, ax = plt.subplots(figsize=(9, 5.2))
ax.plot(delta, resc_all, lw=2.6, color="black", label="被压攻击获救比例（全体 16k+）")
for p in ["aux_select_3000"] + OOD_POOLS:
    mask_p = groups[p] & ~m7_sim
    mm = margin[mask_p]; mm = mm[~np.isnan(mm)]
    fired = (len(mm) - np.searchsorted(np.sort(mm), delta, side="left")) / max(len(mm), 1)
    ax.plot(delta, fired, lw=1.3,
            label=p.replace("ood_", "OOD ").replace("_3000", "").replace("_9000", "") + " 新增误报")
ax.set_xlabel("δ（c1_margin 阈值）")
ax.set_ylabel("比例")
ax.set_xlim(-0.001, 0.0021)
ax.set_title("veto 的收益-代价曲线：收益（黑）永远代价（彩色）的零头——\n任何获救攻击的 δ 都会先把合法良性池打成筛子")
ax.legend(fontsize=8)
fig.savefig(FIG / "fig4_rescue_vs_cost.png", bbox_inches="tight", dpi=150)
plt.close(fig)

# ---- fig 5: per-family veto ceiling bar
fig, ax = plt.subplots(figsize=(8.5, 4.5))
fams = list(c1_ceiling.keys())
vals = [c1_ceiling[f] for f in fams]
colors = ["steelblue" if f in STEALTH else "gray" for f in fams]
ax.barh([f.replace(" Communication", "") for f in fams], vals, color=colors)
ax.axvline(0.9, color="red", ls="--", lw=1.2, label="最差族召回要求 0.90")
ax.set_xlabel("veto 召回天花板 = c1_hard 比例（δ→−∞ 时的上限）")
ax.set_title("各攻击 family 的 veto 理论上限：8 族里 7 族达不到 0.90")
ax.legend(fontsize=8)
fig.savefig(FIG / "fig5_veto_ceiling_by_family.png", bbox_inches="tight", dpi=150)
plt.close(fig)

print("figures + tables written to", OUT)
print("DONE")
