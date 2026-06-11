# Claim Boundary

## Safe Current Claims

Allowed:

- The medium diagnostic has a strong candidate system.
- The current combination of attack evidence, certified OOD-risk, and past-only temporal evidence is promising.
- Past-only temporal evidence improves the medium diagnostic frontier.
- Parent OOD-risk is certified for medium diagnostic use, not formal/full use.
- No final/report-only roles were used for fit or selection in issue27bu.

## Unsafe Current Claims

Not allowed:

- The method solves zero-day detection.
- The method learns true causal relations.
- The method is proven in real deployment.
- Full benchmark is complete.
- Current final/report-only replays are clean formal final tests.
- The no-parent unified two-head fully replaces the parent OOD-risk channel.

## Recommended Wording

Use:

```text
past-only temporal evidence
causal-inspired temporal evidence
interaction-aware evidence
medium diagnostic
larger sanity
report-only replay
```

Avoid:

```text
true causal layer
deployment proven
external generalization proven
paper ready
full benchmark passed
```

## Paper Framing

The current paper problem should be framed as:

```text
Low-false-alarm few-shot online NIDS under dual distribution shift:
benign OOD drift causes false alarms;
attack support-query drift causes missed detections.
```

The method should be framed as an evidence-and-controller protocol, not merely a new model head.

