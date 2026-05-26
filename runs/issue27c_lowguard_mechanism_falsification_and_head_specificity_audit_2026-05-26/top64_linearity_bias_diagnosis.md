# Top64 Linearity / Representation Bias Diagnosis

The available evidence is consistent with top64 doing a large part of the work: it exposes an attack-separating direction that LR can exploit, while OOD-guarded training suppresses benign-OOD tail. This does not prove that top64 is unfairly biased toward LR, but it makes broad head-agnostic claims unsafe.

What we can say:
- top64 improves the feasible LR operating point versus top32 and original100 in the existing locked summaries.
- issue27b shows raw LR has strong attack detection on top64, but only guarded training makes it low-alert feasible.
- Non-LR original100-vs-top64 controls are not available, so representation-vs-head causality remains only partially resolved.

Required follow-up:
- bounded original100-vs-top64 matrix for LR / DevNet-like / HistGB;
- no topK search;
- final eval report-only.
