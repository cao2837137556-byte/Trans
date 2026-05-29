# clean115 Split Proposal Report

A relaxed development split is count-feasible, but not clean-claim safe because it uses benign rows from the historical `my_gold` prefix.

A strict prior-use-excluded split is blocked because excluding `my_gold` removes all benign rows.

The timestamped official 100k asset is a useful candidate, but its feature mapping and overlap against full/my_gold remain unresolved. It should be considered in issue27o.
