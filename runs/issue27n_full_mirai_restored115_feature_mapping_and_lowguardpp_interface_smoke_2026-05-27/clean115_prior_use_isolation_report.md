# clean115 Prior-Use Isolation Report

The historical `my_gold_mirai_200k` subset appears to be the first 200,000 rows of full Mirai:

- label prefix match: `True`
- sampled feature-row match: `True`

This matters because the prefix contains all available benign rows in the full Mirai label order. After excluding that historical prefix:

- benign remaining: `0`
- attack remaining: `564137`

So strict prior-use isolation makes a clean ID/OOD/final benign split impossible from full Mirai alone. A relaxed split can be used for interface debugging, but not for a clean claim.
