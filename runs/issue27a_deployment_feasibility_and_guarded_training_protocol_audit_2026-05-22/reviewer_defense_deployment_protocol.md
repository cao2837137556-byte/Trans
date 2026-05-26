# Reviewer Defense: Deployment Protocol

## Q1: How do you obtain 32 attack samples in reality?

From analyst-confirmed incidents, high-confidence IDS rules after review, historical cases, red-team exercises, honeypots, or sandbox-confirmed samples. We do not claim they are free or always available; issue27b should test smaller budgets.

## Q2: Can the OOD benign guard be attack-contaminated?

Yes. That is a core risk. The protocol requires quarantine, analyst confirmation for false-positive promotion, and OOD-contamination simulations before strong deployment claims.

## Q3: Does the training protocol create a feedback loop?

Not in the current scope. LOW-GUARD should be offline and gated. It must not self-train from its own alerts without human confirmation and provenance checks.

## Q4: Is the method only offline?

The current evidence supports offline training plus shadow/canary deployment. Fully autonomous online learning is not validated.

## Q5: Why not directly use DevNet / DeepSAD?

Issue25c tested DevNet-like and DeepSAD-like baselines under a fair low-alert protocol. DevNet-like was competitive in detection but exceeded the 1% OOD alarm budget; DeepSAD-like did not threaten the main method.

## Q6: Why is LR not a weakness?

LR is the minimal auditable adapter. The claim is not "LR is the best possible neural detector"; the claim is that guarded few-shot adaptation under a low-alert protocol works and can be implemented with a simple transparent head.

## Q7: Does OOD alarm <=1% have deployment meaning?

Yes. It bounds analyst workload. For example, 0.45% OOD alarm means about 45 alerts per 10k OOD events, while 1.04% means about 104 alerts per 10k and breaches the official budget.

## Q8: If temporal metadata is missing, are deployment claims too strong?

Temporal-generalization claims would be too strong. Deployment-protocol claims can be made as assumptions and controls, but formal temporal validation remains pending.

## Q9: If cross-dataset validation does not succeed, how can the paper write this?

As a within-dataset low-alert adaptation result with clear external-validity limits. Do not claim universal generalization; use second-environment results as boundary evidence or future work.

## Q10: How does the method go online, get monitored, and roll back?

Deploy through shadow mode, then canary. Roll back if OOD alarm exceeds budget, false positives spike, support contamination is discovered, or incident miss audit fails. Updates should be periodic and offline.
