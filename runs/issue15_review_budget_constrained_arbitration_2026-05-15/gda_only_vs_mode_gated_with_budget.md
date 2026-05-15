# GDA-only vs Budgeted Mode-Gated Arbitration

GDA-only corresponds to `review_off`.

Budgeted mode-gated arbitration preserves the same high-priority GDA channel and adds a bounded review queue for base-high/GDA-low conflicts. Its value should be judged by whether the added review burden is operationally acceptable and whether it preserves useful base-only attack evidence.

If review attack gain is weak, the conservative paper framing is: GDA-minimal is the main high-priority alerting channel, while review is an optional safety-net mechanism.
