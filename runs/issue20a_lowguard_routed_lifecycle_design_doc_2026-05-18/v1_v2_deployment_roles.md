# V1/V2 Deployment Roles

## V1: LOW-GUARD-minimal

- Role: primary low-OOD stable module.
- Strength: conservative low OOD alarm. Primary low-OOD OOD max is 0.0036.
- Weakness: insufficient attack-side harder-shift detection. holdout_bin_2 detection is 0.3264.
- Use case: primary low-OOD / conservative mode.

## V2: LOW-GUARD+

- Role: harder attack-side shift repair module.
- Strength: strong holdout_bin_2 repair, from 0.3264 to 0.8093; chrono_late also improves from 0.6798 to 0.7315.
- Weakness: primary low-OOD OOD max rises to 0.0156, so V2 is unsafe as a universal replacement.
- Use case: activated only when validation evidence indicates harder attack-side shift and OOD alarm remains controlled.

## Conflict Handling

| V1 high | V2 high | output |
|---|---|---|
| false | false | low_priority_or_background |
| true | true | high_priority_alert |
| true | false | needs_review |
| false | true | high_priority_alert if V2 mode active; otherwise needs_review |

V1 high / V2 low is preserved as review evidence. V1 low / V2 high is high-priority only when V2 has passed the promotion/routing gate for the active mode.
