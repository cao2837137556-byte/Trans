# Claim Update After issue27bm

- The prior attack-side contract was too drift-heavy for model repair to be interpretable.
- issue27bm rebuilds a legal development-side phase-balanced attack contract without using attack_eval labels.
- The new contract is suitable for attack-only diagnostic replay, not for formal benchmark claims.
- OOD-gate repair and full benchmark remain blocked until attack-side detection is stable under the legal dev contract.
