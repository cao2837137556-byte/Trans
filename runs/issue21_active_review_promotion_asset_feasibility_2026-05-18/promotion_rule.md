# Promotion Rule

For each setting, seed, evidence strategy, evidence budget k, and delta threshold:

1. Keep V1 and V2 definitions fixed.
2. Obtain promotion evidence from non-final sources only.
3. Compute `promotion_detection_v1` and `promotion_detection_v2` on confirmed attack evidence.
4. Check `V2 OOD validation alarm <= 1%`.
5. Promote V2 only if `promotion_detection_v2 - promotion_detection_v1 >= delta`; otherwise use V1.

Delta candidates are 0.05, 0.10, and 0.20. All are reported. Final eval is report-only.
