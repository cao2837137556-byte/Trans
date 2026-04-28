# Section 5 Exact Numbers Patch for Prism

Date: 2026-04-25  
Target file for Prism: `drafts/paper_draft_fewshot_mainline.md`  
Target section: Section 5 only  
Purpose: provide self-contained exact numbers for revising Section 5 after Prism wrote only qualitative descriptions.

This patch is self-contained. Prism does not need to read the local CSV files to apply it.

Source files checked:
- `runs/prism_handoffs/fewshot_paper_main_table_2026-04-25.csv`
- `runs/prism_handoffs/fewshot_dataset_split_budget_summary_2026-04-25.csv`
- `runs/prism_handoffs/handoff_fewshot_target_alignment_2026-04-25.md`
- `runs/prism_handoffs/handoff_collapse_sanity_audit_2026-04-25.md`

---

## 1. Exact Numbers to Insert into Section 5

### 1.1 dA Guarded Collapse Reference

Use this as the unsupervised reference under the guarded low-OOD-alarm operating point.

| Method | Role | AUC | OOD alarm | Detection | Boundary |
|---|---|---:|---:|---:|---|
| dA, guarded | unsupervised reference | 0.8064 | 0.0108 | 0.0029 | Not a same-label-information competitor to few-shot models |

Suggested wording:

> Under the guarded low-OOD-alarm rule, the dA unsupervised reference still has nontrivial ranking ability (AUC = 0.8064), but its final OOD alarm is 0.0108 and attack detection collapses to 0.0029. We therefore use it as an unsupervised operating-point reference, not as a same-label-information competitor to few-shot target-aligned detectors.

### 1.2 original100 Few-Shot Guarded Official Control

These are the core Section 5 numbers for the official control. The role is to show that target alignment is the main lever.

| Representation | Budget | AUC mean | AUC min | AUC max | OOD alarm mean | OOD alarm max | Detection mean | Detection min | Feasible rate | Role |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| original100 | 16-shot | 0.9907 | 0.9580 | 1.0000 | 0.0044 | 0.0092 | 0.9676 | 0.9142 | 1.0000 | 目标对齐主控制组 |
| original100 | 32-shot | 0.9846 | 0.9676 | 0.9999 | 0.0065 | 0.0098 | 0.9407 | 0.9207 | 1.0000 | 确认少样本目标对齐稳定性 |

Suggested wording:

> The original100 few-shot official control already reverses the low-alarm collapse. With only 16 high-purity attack positives, the guarded setting reaches AUC mean/min/max = 0.9907 / 0.9580 / 1.0000, OOD alarm mean/max = 0.0044 / 0.0092, and detection mean/min = 0.9676 / 0.9142, with feasible rate = 1.0000. With 32 positives, it remains stable: AUC mean/min/max = 0.9846 / 0.9676 / 0.9999, OOD alarm mean/max = 0.0065 / 0.0098, detection mean/min = 0.9407 / 0.9207, and feasible rate = 1.0000.

### 1.3 source_rich v7.2 Guarded Current-Split Evidence

These numbers can appear after original100 as current-split source-rich evidence. They must not be written as proof that source_rich is universally better than original100.

| Representation | Budget | AUC mean | AUC min | OOD alarm mean | OOD alarm max | Detection mean | Detection min | Feasible rate | Boundary |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| source_rich v7.2 | 16-shot | 0.9776 | 0.9646 | 0.0056 | 0.0088 | 0.9487 | 0.9273 | 1.0000 | Positive source-rich current-split evidence; does not prove average superiority over original100 |
| source_rich v7.2 | 32-shot | 0.9776 | 0.9682 | 0.0074 | 0.0109 | 0.9587 | 0.9476 | 0.8000 | Some seeds exceed strict 1% OOD alarm; wording must be conservative |

Suggested wording:

> source_rich also supports the target-alignment result on the current split. At 16-shot, source_rich v7.2 obtains AUC mean/min = 0.9776 / 0.9646, OOD alarm mean/max = 0.0056 / 0.0088, detection mean/min = 0.9487 / 0.9273, and feasible rate = 1.0000. At 32-shot, it obtains AUC mean/min = 0.9776 / 0.9682 and detection mean/min = 0.9587 / 0.9476, but OOD alarm mean/max = 0.0074 / 0.0109 and feasible rate = 0.8000, so this should be described as strong but not all-seed alarm-stable evidence.

### 1.4 v7.4 Hard-Holdout Bridge for Section 5

Only introduce this briefly in Section 5 as a transition to Section 6. Detailed hard-holdout and auditability discussion belongs to Section 6.

| Holdout case | Representation | Budget | AUC mean | AUC min | OOD alarm mean | OOD alarm max | Detection mean | Detection min | Feasible rate | Section 5 role |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| chrono_late_train_early_eval | source_rich | 32-shot | 0.9644 | 0.9494 | 0.0071 | 0.0099 | 0.8966 | 0.8549 | 1.0000 | Short transition to Section 6 |

Suggested wording:

> As a bridge to the source-rich analysis in Section 6, the cleanest v7.4 hard-holdout case is `chrono_late_train_early_eval` with source_rich at 32-shot under the guarded rule: AUC mean/min = 0.9644 / 0.9494, OOD alarm mean/max = 0.0071 / 0.0099, detection mean/min = 0.8966 / 0.8549, and feasible rate = 1.0000. Section 5 should only introduce this as a transition; the detailed hard-holdout and auditability claims belong to Section 6.

---

## 2. Dataset / Split / Budget Clarification

Section 5 should include a short clarification so readers do not mistake few-shot budget for evaluation-set size.

### 2.1 Current Final Split

| Data block | Train rows | Validation rows | Calibration rows | Eval rows | Train candidate pool rows |
|---|---:|---:|---:|---:|---:|
| ID benign | 8000 | 2000 | 5000 | 35000 | N/A |
| OOD benign | 8000 | 2000 | N/A | 10000 | N/A |
| high-purity attack | N/A | 1374 | N/A | 1375 | 4122 |

### 2.2 Few-Shot Budget Meaning

Required clarification:

- `16-shot` / `32-shot` means the number of high-purity attack positive samples used to train the logistic head.
- `16-shot` / `32-shot` is not the evaluation-set size.
- Negatives come from ID benign + OOD benign.
- The reported metrics are computed on held-out OOD benign and held-out high-purity attack eval rows.
- Final OOD eval does not participate in threshold selection.
- Attack eval does not participate in threshold selection.
- Positive sampling seeds are `42,43,44,45,46`.

Suggested wording:

> The few-shot budgets refer only to the number of high-purity attack positives used to train the logistic head. They are not the evaluation-set size. In the current final split, ID benign has 8000 / 2000 / 5000 / 35000 train / validation / calibration / eval rows, OOD benign has 8000 / 2000 / 10000 train / validation / eval rows, and high-purity attack has a 4122-row training candidate pool, 1374 validation rows, and 1375 evaluation rows. Final OOD eval and attack eval are not used for threshold selection. Positive sampling is repeated over seeds 42,43,44,45,46.

---

## 3. Writing Boundaries for Prism

When modifying Section 5, Prism must avoid the following:

- Do not write that few-shot completely solves open-world IDS.
- Do not write that source_rich is comprehensively or universally better than original100.
- Do not write that dA and few-shot are fair same-label-information competitors.
- Do not write that 16/32-shot is the evaluation scale.
- Do not write that Transformer ensemble is the current main method.
- Do not write Sections 6-9.

Allowed Section 5 framing:

- dA is the unsupervised guarded-collapse reference.
- original100 few-shot is the official control showing that target alignment is the main lever.
- source_rich v7.2 is positive current-split evidence, but not universal superiority evidence.
- v7.4 `chrono_late_train_early_eval` is only a bridge to the Section 6 source-rich hard-holdout/auditability discussion.

---

## 4. Copy-Paste Instruction for Prism

Use the following instruction directly with Prism:

```text
Please modify only `drafts/paper_draft_fewshot_mainline.md`.

Do not create a new version file.
Do not modify Sections 1-4.
Do not write Sections 6-9.
Only revise Section 5 by inserting the exact numbers and budget clarification below.

Section 5 must include:

1. dA guarded collapse reference:
   AUC = 0.8064, OOD alarm = 0.0108, detection = 0.0029.
   State that dA is an unsupervised reference, not a same-label-information competitor to few-shot models.

2. original100 few-shot guarded official control:
   16-shot: AUC mean/min/max = 0.9907 / 0.9580 / 1.0000; OOD alarm mean/max = 0.0044 / 0.0092; detection mean/min = 0.9676 / 0.9142; feasible rate = 1.0000.
   32-shot: AUC mean/min/max = 0.9846 / 0.9676 / 0.9999; OOD alarm mean/max = 0.0065 / 0.0098; detection mean/min = 0.9407 / 0.9207; feasible rate = 1.0000.
   State that this is the official control showing target alignment is the main lever.

3. source_rich v7.2 guarded current-split evidence:
   16-shot: AUC mean/min = 0.9776 / 0.9646; OOD alarm mean/max = 0.0056 / 0.0088; detection mean/min = 0.9487 / 0.9273; feasible rate = 1.0000.
   32-shot: AUC mean/min = 0.9776 / 0.9682; OOD alarm mean/max = 0.0074 / 0.0109; detection mean/min = 0.9587 / 0.9476; feasible rate = 0.8000.
   State that source_rich is positive current-split evidence but does not prove average superiority over original100. For 32-shot, mention that some seeds exceed strict 1% OOD alarm.

4. v7.4 bridge only:
   `chrono_late_train_early_eval`, source_rich, 32-shot, guarded: AUC mean/min = 0.9644 / 0.9494; OOD alarm mean/max = 0.0071 / 0.0099; detection mean/min = 0.8966 / 0.8549; feasible rate = 1.0000.
   Use this only as a transition to Section 6. Do not write the Section 6 hard-holdout/auditability discussion yet.

5. Dataset/split/budget clarification:
   16-shot / 32-shot means the number of high-purity attack positives used to train the logistic head, not the evaluation-set size.
   Current final split:
   ID benign train/val/calib/eval = 8000 / 2000 / 5000 / 35000.
   OOD benign train/val/eval = 8000 / 2000 / 10000.
   high-purity attack train candidate pool / val / eval = 4122 / 1374 / 1375.
   Final OOD eval and attack eval do not participate in threshold selection.
   Positive sampling seeds = 42,43,44,45,46.

Do not claim that few-shot completely solves open-world IDS.
Do not claim that source_rich universally beats original100.
Do not compare dA and few-shot as same-label-information competitors.
Do not resurrect Transformer ensemble as the current main method.
```

