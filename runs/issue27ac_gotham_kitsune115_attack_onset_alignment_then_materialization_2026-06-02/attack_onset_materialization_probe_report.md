# Attack Onset Materialization Probe Report

- primary_verdict: `attack_onset_alignment_partial_ready_for_kitsune115_smoke_expansion`.
- Scope: attack-side PCAP/CSV onset alignment and tiny Kitsune115 extraction probe only.
- No model training, model ranking, AUC, F1, detection, or OOD alarm metrics were computed.
- The previous issue27ab blocker came from using `network-scanning` PCAPs for the first Telnet Brute Force attack window.
- This issue scans all contract attack files and candidate malicious PCAPs by timestamp to find causal first-attack onset windows.
- Selected support/eval roles available: `true`.
- All attack contract files onset-aligned within scan budget: `false`.
- 115D attack-onset probe numeric pass: `true`.
- Few-shot support must be sampled from rows at or after confirmed attack onset; benign prefix rows remain excluded from attack support.
- Attack eval may preserve realistic mixed-flow chronology, but packet/row labels and onset alignment must be carried in sidecar for metric computation.
