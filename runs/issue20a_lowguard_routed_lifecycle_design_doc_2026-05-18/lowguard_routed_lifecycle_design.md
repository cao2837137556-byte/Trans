# LOW-GUARD-Routed Lifecycle Design

## A. System Motivation

Primary low-OOD and harder attack-side shift impose different constraints. In the primary low-OOD setting, V1 is conservative and stable: detection 0.9295, OOD max 0.0036. V2 is not a safe universal replacement there because OOD max rises to 0.0156, above the 1% budget, while detection changes only slightly.

In holdout_bin_2, always-V1 fails the attack-side shift: detection 0.3264. V2 repairs that failure with detection 0.8093 and OOD max 0.0068. Therefore the scientific conclusion is not "V2 replaces V1"; it is that benign-OOD drift and attack-side shift require mode-specific low-alert adaptation.

## B. Runtime Architecture

```text
Incoming traffic
  -> feature extraction
  -> V1 score and V2 score
  -> drift monitor
  -> promotion / routing gate
  -> high_priority_alert / needs_review / low_priority_or_background
```

The architecture keeps base detector evidence and adapter evidence separate until the routing gate decides which adapter controls high-priority alerting. Review is a bounded safety net, not the main high-priority channel.

## C. Three Operating Modes

### Mode 0: cold-start / ordinary monitoring

Before high-purity confirmed attack supports are available, the system relies on the deployed base detector for cold-start anomaly monitoring. LOW-GUARD adapters are not the primary alerting model in this mode.

### Mode 1: primary low-OOD stable adaptation

V1 is the active champion. It is used when validation evidence indicates primary low-OOD-like traffic and the stricter OOD alarm budget is best served by original100 fixed guard.

### Mode 2: harder attack-side shift adaptation

V2 becomes active only after validation evidence shows a harder attack-side shift and confirms that V2 satisfies the low-alert budget. V2 is not activated merely because it is more sensitive on a prior final evaluation.

## D. Champion-Challenger Lifecycle

- Current champion: the currently active adapter for a specific mode.
- Shadow challenger: a candidate adapter evaluated on validation windows without controlling production high-priority alerting.
- Validation gate: checks attack-side proxy improvement, OOD alarm budget, review burden, provenance, and stability.
- Promotion: challenger becomes champion only inside the mode for which it passed the gate.
- Rejection: challenger remains offline or in shadow if it fails the gate.
- Rollback: if a promoted champion violates runtime alert or review budgets, the system rolls back to the previous champion.
- Retirement: stale models may be archived after enough clean windows, but scores/provenance remain auditable.

## E. Why This Is Not Infinite Nesting

This is a bounded lifecycle, not V1 -> V2 -> V3 unbounded stacking. The system maintains a finite model pool, requires a promotion gate, rejects candidates that fail validation, and uses cooldown or validation windows before promotion. Old champions are fallback references, not infinitely accumulated alerting modules. A new adapter is not allowed to become active simply because it looks better on a final report.
