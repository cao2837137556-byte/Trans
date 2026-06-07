# issue27be Decision

primary_verdict = `past_only_replay_passed_with_dev_pseudo_caveat_ready_for_attack_region_bank`

- replay matches issue27bd selected report rows: `True`
- forbidden selection role access found: `False`
- new-heavy active candidate stream precedes dev query stream: `True`
- reset_at_split_boundary state audit passed: `True`
- dev pseudo-query calibration caveat present: `True`

Interpretation: the issue27bd signal is reproducible under the frozen replay audit and does not use clean final/report-only roles for selection. It is still a diagnostic result because dev pseudo-query rows participate in gate calibration.
