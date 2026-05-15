# Claim Boundary

Allowed if validation passes:

- mode-gated arbitration can be evaluated on row-level base and GDA-minimal scores.
- GDA-only high-priority alerts and base-only needs-review rows should be reported separately.
- The base detector and GDA-minimal can coexist through a deployment policy.

Not allowed:

- review rows are confirmed attacks;
- arbitration proves full GDA;
- detector-agnostic adaptation is proven;
- GDA replaces the base detector;
- high-alert attack fraction is deployment precision.
