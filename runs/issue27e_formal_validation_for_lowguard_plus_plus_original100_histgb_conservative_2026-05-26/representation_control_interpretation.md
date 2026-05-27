# Representation-Control Interpretation

issue27d remains important: original100 + HistGB-Conservative looked much stronger than top64 non-LR heads, suggesting the top64 representation may expose a linear direction that helps LR while discarding nonlinear structure useful to conservative trees.

However, issue27e cannot yet elevate that observation into a formal LOW-GUARD++ claim because the candidate configuration is not uniquely frozen. The correct interpretation is:

- LOW-GUARD-LR remains the demonstrated top64 minimal instance.
- original100 + HistGB-Conservative is a serious performance-instance candidate.
- A dual-instance paper story is plausible: LOW-GUARD-LR as minimal instance, LOW-GUARD-HistGB as performance instance.
- That story requires issue27f formal validation with a single frozen config or a pre-registered two-instance sensitivity design with no post-hoc selection.

Claims remain bounded to tested representations, tested heads, and the locked low-alert protocol.
