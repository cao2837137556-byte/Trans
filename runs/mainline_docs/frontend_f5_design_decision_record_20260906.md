# Frontend-F5 design decisions and self-review

Date: 2026-09-06

Status: design review by the drafting agent; **not** independent review and
not an implementation/test/execution receipt.

## Why this is the selected narrow attempt

F4 repaired the demonstrated whole-signature UNK mechanism with fixed lossless
field inputs. Another vocabulary audit would repeat completed work. The next
experiment must test learning on those inputs.

The primary interface is a unified encoder plus its own small head. F1 proved
failure of one student/frozen-P2 realization, not universal information loss;
forcing another 768D output through frozen P2 would retain an avoidable
coordinate compatibility constraint. P2 instead teaches its continuous
decision evidence while the student is free to represent it differently.
Both A and B use one forward function. Incumbent deployment is not replaced.

The teacher term is label-aware and one-sided: correct attacks and correct
benign decisions are protected; the 26 parent wrong-benign teacher decisions
are not imitated. Its scale is fixed before teacher logits are opened. No
score-distribution audit is needed to choose another set of loss weights.

The training objective deliberately gives A/B x attack/benign four equal task
weights, using context means, and adds a worst-in-batch attack penalty. This
changes F1's weighting explicitly. Batch-worst is not called global-worst;
whole-corpus zero-flip gates are the functional test. Sparse B gradients can
still be noisy. No choice here makes successful inheritance certain.

A small auxiliary head predicts four next-event attributes. A lookup-based
next-token head would repeat F3's failure mechanism; it is excluded. The
auxiliary has no claim to be a novel self-supervised method.

## Alternatives not selected

| Alternative | Reason not selected for this attempt |
|---|---|
| New 768D encoder through frozen P2 | Unnecessary interface constraint; no comparison arm required to answer the current unified-function question |
| Clone old E3 vectors | Stronger condition than functional retention; can copy undesirable device geometry |
| Only train B specialist | Does not test the user's intended shared A+B detector |
| Increase old loss weight / seed sweep | Would add outcome-driven choices without repairing the demonstrated input/interface issues |
| New packet fields, encoder family or dataset | F4 already passed input feasibility; no evidence justifies expanding this trial |
| Re-split to improve A validation support | Existing split has been exposed; source movement would create selection discretion |
| Treat a 3-row or 5-row pass as full inheritance | Insufficient and exposed evidence; all claims remain development-limited |
| Require a full geometry/linear-probe experiment first | F5 asks direct functional feasibility, not source-invariant geometry; it cannot claim those separate instruments have passed |

F5 is not promoted to a CE stage or used to waive CE/F0's required instruments.
Its scope and lower claim ceiling are explicitly separate. The later full
attack evaluation and untouched confirmation remain unresolved obligations.

## Count-only checks made while designing

No new score, representation statistic, or model was computed. Existing F4
metadata was read to identify B utility denominators; no source was moved.

- Train: `2179+4667+24+68+1722 = 8660`.
- Validation: `3+1478+2+3+3720 = 5206`.
- Parent: `8660+5206 = 13866`; contexts `4984+4323 = 9307`.
- Teacher training A: `2179+4667+24 = 6870`.
- Parent A: `6870+(3+1478+2) = 8353`; **1,483 validation A teacher values
  stay unmaterialized**.
- Validation B benign: 333/282 combined-cycle, 230/50 domotic-monitor,
  3157/2995 ToN, as target/context counts; totals 3720/3327.
- The per-key target 10% ceilings are 34,23,316, totaling 373, not 372.
- The per-key all-B-benign-context 10% ceilings are 29,5,300, totaling 334.
- Device-family keys are not independent physical-device identities.

The hidden-size/parameter arithmetic uses the documented PyTorch GRU parameter
shapes, not a constructed model: 8,448 projection + 74,496 GRU + 8,321 head =
91,265 inference parameters; 3,483 auxiliary yields 94,748 training parameters.
Actual construction/count assertions belong to the later synthetic battery.

## Remaining scientific risks, before a run exists

1. Exact field preservation does not guarantee useful field separability or
   learnable attack features. Close but distinct inputs may remain difficult.
2. One A validation attack context and two B contexts cannot estimate a stable
   unseen-attack error rate. Repeated epoch selection makes them even less
   suitable as positive evidence. This is not repaired by class balancing.
3. Protocol/length/delta signatures may still be source shortcuts even with
   all endpoint values removed. F5 cannot claim source invariance.
4. Labels and teacher guidance may conflict across near inputs. No loss weight
   here is mathematically guaranteed to satisfy zero-flip and benign-gain gates.
5. Per-key utility prevents the 3,157-row ToN group from masking failure on the
   two smaller keys, but does not establish generalization to new devices.
6. All changes are combined in one trial. A positive result supports the
   combined realization, not an isolated claim about continuous distillation.
7. F2 specified canonical continuous-teacher semantics but stopped at its
   structural input gate before materializing them. The new draft inherits
   numerical semantics, not an executed teacher result or score authorization.
   P remains a new, explicitly scoped teacher open.

The user can judge a concrete numerical protocol now. Implementation should
require no new scientific choices. Future execution can conditionally cover
preflight, teacher materialization, the single trajectory and final checks
under one bounded authorization rather than repeated per-step approvals.

## Design verification receipt

All 19 artifact SHA-256 pins in the draft were recomputed from the named local
files and matched (19/19). This was byte hashing, not numeric loading of the
old representation/model. The parameter arithmetic, five-category target
conservation, teacher scope and utility ceilings were independently recomputed
without constructing a model. The source text of formal P2 scoring and
`apply_threshold` was checked: float32 sigmoid scores must be widened to
float64 before threshold comparison, and that detail is explicit in the draft.

This is the author's static verification, not independent scientific approval.
The actual model, losses, gradients, resume behavior, resource projection and
contract tests have not run; those are later implementation deliverables.
