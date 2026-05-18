# Mode Routing Implication

The current implication is: mode-specific validation/routing should be considered before calling V2 a universal replacement for V1.

If V2 is strong on holdout_bin_2 but regresses in primary low-OOD or chrono_late, it should be treated as a harder-shift repair module rather than a universal V1 replacement. If V2 is non-regressive across these settings, it can enter locked validation as the drift/adaptation-mode candidate.
