# Bounded Attack Region Bank Design

This run is bank-only: it keeps the issue27bd full-Kitsune115 raw detector score and replaces only attack-region routing/shell evidence.

Online decision sketch:

```text
if raw attack score is low: no_alarm
else: route to top-k nearest attack regions in the gate subspace
      if inside region inner shell and score floor: hard_alarm
      elif inside outer shell: conflict-aware hard/review
      else: suppress or unknown/review via existing benign/OOD evidence
```

The selected bank is bounded by prototype budget, max region count, and top-k routing. No final/report-only role is used for bank or gate selection.
