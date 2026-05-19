# Proxy Asset Gap Report

Blocking gap: none for issue20b diagnostic construction.

Observed issue20 gap retained:

- issue20 selected V1 in all settings: `True`.
- holdout_bin_2 had missing attack validation proxy in issue20: `True`.
- issue20b can construct support-holdout and tail-margin proxies from local attack train pool plus OOD validation, but these are candidate proxies, not production triggers.
