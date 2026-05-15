# Arbitration Policy Table

| base_high | gda_high | base_only | gda_only | OR_policy | AND_policy | mode_gated_arbitration |
|---|---|---|---|---|---|---|
| false | false | low_priority_or_background | low_priority_or_background | low_priority_or_background | low_priority_or_background | low_priority_or_background |
| false | true | low_priority_or_background | high_priority_alert | high_priority_alert | low_priority_or_background | GDA_driven_high_priority_alert |
| true | false | high_priority_alert | low_priority_or_background | high_priority_alert | low_priority_or_background | needs_review |
| true | true | high_priority_alert | high_priority_alert | high_priority_alert | high_priority_alert | high_priority_alert |

`needs_review` is reported separately from high-priority alerts. It is not counted as confirmed attack detection.
