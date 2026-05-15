# Review Burden Tradeoff

High-priority alert burden and review burden are separate operational budgets.

- High-priority burden is controlled by GDA-minimal and remains the primary low-OOD alarm metric.
- Review burden comes from base-high/GDA-low conflicts and should be interpreted as a safety-net queue.
- Review rows are not confirmed attacks.
- `attack_total_captured` includes review rows only as captured-for-review, not as high-priority detections.
