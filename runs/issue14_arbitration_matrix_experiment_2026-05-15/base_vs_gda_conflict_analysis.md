# Base vs GDA Conflict Analysis

Conflict analysis was not computed in this pass because GDA-minimal per-sample scores are missing.

Required inputs for this analysis:

- base score and threshold for the same final OOD and attack eval row ids;
- GDA-minimal score and threshold for the same final OOD and attack eval row ids;
- row-level `base_high` and `gda_high`.

Once recovered, the analysis should distinguish:

- GDA-only high samples: `base_high=false`, `gda_high=true`;
- base-only high samples: `base_high=true`, `gda_high=false`;
- both-high samples;
- both-low samples.

Base-only high samples should be routed to review rather than interpreted as confirmed attacks or suppressed.
