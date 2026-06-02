# issue27ac Decision

primary_verdict = `attack_onset_alignment_partial_ready_for_kitsune115_smoke_expansion`

The attack-side blocker is no longer the Kitsune115 frontend itself. It is the need to use the correct malicious scenario PCAP and to start attack-labeled materialization only at the processed-CSV first-attack timestamp.

Model experiments remain disallowed. The next step is a broader split-aware Kitsune115 smoke dataset over confirmed onset-aligned PCAP/CSV pairs, plus deeper handling for attack files whose onset was not reached within this scan budget.
