# LR Rescue Mechanism Diagnosis

LR P0 shows the core pathology: attack detection is high, but the final OOD tail explodes. LR P1 shows that threshold guard alone is not the mechanism; it satisfies the alarm budget by pushing the threshold so high that attack detection collapses. LR P2 shows the key recovery: adding OOD benign samples during training reshapes the linear score so ID/OOD/support are separated enough that even an ID-only threshold becomes feasible. P3 preserves the P2 behavior while adding the official ID+OOD validation safety gate.

Mechanistic reading:
- The rescue is not "just thresholding".
- The decisive LR mechanism is OOD-guarded training on the frozen top64 representation.
- The threshold guard is still required as a deployment safety gate and for final protocol consistency.
- LR success likely depends on top64 exposing a mostly linear attack-vs-benign-OOD direction.

Key LR P3 locked result: `0.949705` / `0.882629` / `0.004500`.
