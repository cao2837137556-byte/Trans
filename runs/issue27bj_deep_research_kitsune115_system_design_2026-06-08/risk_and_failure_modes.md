# Risk And Failure Modes

## 1. Raw attack evidence remains weak

Symptom:

- dev attack hard-min stays below `0.80`;
- support_val high but pseudo/query low;
- report-only high but legal dev low.

Interpretation:

- current support/dev task boundary is inconsistent;
- metric objective is not exposing hard query;
- support-query gap remains primary blocker.

Action:

- task-boundary audit before OOD repair;
- inspect attack phase/type/file mismatch;
- do not go full.

## 2. Metric embedding overfits dev pseudo-query

Symptom:

- legal dev pseudo improves but report-only collapses;
- distance distributions become too tight around selected pseudo;
- high variance across seeds.

Action:

- reduce model complexity;
- use leave-file-out pseudo-query;
- add role access audit and seed worst-case reporting.

## 3. OOD negative destroys attack evidence

Symptom:

- adding OOD stress lowers OOD alarm but attack hard-min drops to zero or near zero.

Action:

- decouple attack evidence and OOD risk;
- OOD risk should veto only weak attack evidence;
- do not train one scorer to solve both.

## 4. Prototype shell becomes too narrow

Symptom:

- support_val covered, pseudo/query far;
- strong support-query distance gap;
- unknown/review rate high.

Action:

- learn embedding first;
- use outer shell from legal pseudo/dev only;
- do not expand shell based on report-only.

## 5. Review becomes a trash can

Symptom:

- attack hard increases only because many samples enter review;
- review rate > 5%;
- OOD false positives hidden as review.

Action:

- enforce review budget;
- report hard/review/suppress separately;
- review is not counted as detection unless explicitly defined.

## 6. Region registry grows without bound

Symptom:

- every active-labeled group creates new region;
- online lookup and calibration costs grow linearly;
- old regions are forgotten or underrepresented.

Action:

- region merge/retire/compress policy;
- exemplar budget per region;
- top-k routing;
- periodic utility audit.

## 7. Active labeling assumes future labels

Symptom:

- selection uses final/report-only labels;
- query labels influence support construction;
- clean final is repeatedly inspected during design.

Action:

- selection must be feature-only before labels;
- labels appear only after simulated oracle/human step;
- final/report-only is one-way replay.

## 8. ANN approximate lookup changes security decision

Symptom:

- ANN nearest region differs from exact nearest region for high-risk samples;
- false negatives appear in rare regions.

Action:

- exact fallback for conflict/unknown/high-score cases;
- ANN recall audit;
- index hash/version logging.

## 9. Online state contamination

Symptom:

- future packets influence feature/state for train/support;
- final eval affects threshold or state strategy.

Action:

- retain state-transition logs;
- maintain split-aware extraction;
- final eval report-only.

## 10. Claim overreach

Symptom:

- medium diagnostic described as formal result;
- report-only replay used as model ranking;
- full benchmark implied before gates pass.

Action:

- keep claim boundary explicit;
- no formal benchmark until attack hard-min >= 0.93 and OOD gate later passes.
