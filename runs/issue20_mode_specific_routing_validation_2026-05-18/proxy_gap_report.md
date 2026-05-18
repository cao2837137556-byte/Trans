# Proxy Gap Report

The current routing validation exposes a proxy gap.

- primary_lowood has an attack validation proxy and selects V1.
- chrono_late has an attack validation proxy, but the proxy favors V1 even though final evaluation oracle favors V2.
- holdout_bin_2 lacks a usable attack validation proxy in the generated routing table, so `delta_proxy` is missing and the rule defaults to V1.

This means issue20 should not be written as successful routing validation. The correct next step is to build or pre-register a stronger validation-side trigger for harder attack-side shift before making a LOW-GUARD-Routed claim.
