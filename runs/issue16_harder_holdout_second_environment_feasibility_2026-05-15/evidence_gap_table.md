# Evidence Gap Table

| Gap | Current status | Why it matters | Next action |
|---|---|---|---|
| Harder holdout | Existing v7.4 paired hard-holdout evidence exists, but not for current GDA-minimal fixed-guard score pipeline. | Needed to show the deployment mechanism survives harder cross-window attack evaluation. | Run issue16b fixed-config hard-holdout recovery on chrono_late_train_early_eval and one bin holdout. |
| Second environment | BoT-IoT and TON-IoT local assets exist but are not current-protocol ready. | Needed for external validity beyond the current capture. | Build a separate acquisition/conversion plan with feature, label, and role manifests. |
| Adapter upgrade | Paused intentionally. | Upgrading LR before generalization may overfit the current split. | Wait until issue16b reveals whether fixed-guard GDA-minimal transfers. |
| Formal ablation tables | issue11/14/15 provide strong current-split mechanism evidence. | Need final paper integration only after deciding whether issue16b succeeds. | Keep as current evidence, do not rewrite manuscript in this turn. |
| Paper integration | Not modified. | Prevents premature claim drift. | Integrate only after issue16b/external decision. |
