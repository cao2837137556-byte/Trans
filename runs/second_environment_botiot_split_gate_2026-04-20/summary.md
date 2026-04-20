# BoT-IoT Split Gate Summary

- Run tag: `second_environment_botiot_split_gate_2026-04-20`
- Verdict: `blocked_naive_budget5000_not_supported`
- Reason: No BoT-IoT split candidate can provide enough OOD benign samples for the required `naive_calibrated_budget5000` operating point.

## Raw Benign/Attack Counts
- `10-best full`: benign=477, attack=3668045, total=3668522
- `10-best train`: benign=370, attack=2934447, total=2934817
- `10-best test`: benign=107, attack=733598, total=733705
- `all-feature full4`: benign=477, attack=668045, total=668522

## Gate
- Required naive budget for mainline policy: `5000` OOD benign samples
- Formal benign support threshold: `id>=1000`, `ood>=1000`

## Next
- Do not treat BoT-IoT as formal second-environment closure under current mainline policy set.
- Escalate to TON-IoT fallback for the formal second-environment package.
