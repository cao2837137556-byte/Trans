# Arbitration Matrix Draft

Definitions:

- `base_high = base_score >= base_threshold`
- `gda_high = gda_score >= gda_guarded_threshold`

| base_high | gda_high | output |
|---|---|---|
| false | false | low_priority_or_background |
| true | true | high_priority_alert |
| false | true | GDA_driven_high_priority_alert |
| true | false | needs_review |

Issue14 should compare:

1. base-only
2. GDA-only
3. OR policy
4. AND policy
5. mode-gated arbitration

Issue13 only defines these policies. It does not validate arbitration performance.
