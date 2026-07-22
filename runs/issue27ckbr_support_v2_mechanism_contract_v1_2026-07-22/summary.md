# CKBR support-v2 mechanism contract

Status: `SUPPORT_V2_CANDIDATE_QUARANTINED_SAME_CAPTURE_FUTURE_ORDER`.

## What is frozen

- Original support v1 is unchanged: train `385`, validation `127`.
- Reproduced validation lineage: fit `58`, select `69`.
- The certified 1M split, 26-source T0 manifest, certified attack query chunks, report rows, and sealed rows are not changed.

## Blocking data-quality findings

The legacy issue27cb exact-label audit treated `recorded_index_within_file` as a processed-CSV row index. It is actually a role-local ordinal. Therefore its 90,000-row label inventory is rejected. The replacement audit uses unique PCAP-packet timestamp to CSV `frame.time` alignment within 2 microseconds. It finds `28,640` exact aligned TCP/Telnet rows, but `0` remain outside the already frozen certified query intervals; they cannot supply a non-overlapping support extension.

The issue27cc `network-scanning` PCAP recommendation was a scenario-name heuristic, not row-level pairing evidence. The selected unused rows occur during the `mirai-infection` capture, whose time range uniquely covers all 160 target timestamps. The contract records this override explicitly rather than silently following the heuristic.

## Quarantined diagnostic candidate

- Source: `processed/iotsim-city-power-1.csv` (already a development support source for other attack mechanisms).
- New mechanisms: `TCP Scan` and `Telnet Brute Force`.
- Diagnostic rows: proposed train `120`, proposed validation `40`.
- The apparent combined counts `505/167` are hypothetical and forbidden. Active support remains train `385`, validation `127` with fit/select `58/69`.
- Each row comes from a distinct exact-label segment, is at least `500` CSV rows from every existing certified query interval, and maps uniquely by time range to `raw/malicious/mirai-infection/iotsim-city-power-1_0-0_to_OpenvSwitch-26_1-0.pcap`.
- All 160 raw CSV labels were verified and their diagnostic 115D vectors can be materialized exactly.
- However, every candidate occurs in the same capture after the already frozen TCP/Telnet future-query interval. Row non-overlap does not make a reverse-chronology split legal. All 160 rows are therefore fail-closed from fit, select, standardization, thresholding, negative sampling, and model selection.

## Scientific boundary

This audit does not broaden active attack supervision and is not a detector result. It does not use stream, hydraulic, ip-camera-street, predictive-maintenance, report, or sealed labels. The frozen support v1 remains the only active support bank.

## Next gate

Find an independent training capture or an external dataset's training split with legal scan/bruteforce process labels and forward chronology. Its test/report split must remain untouched. Do not train on any of these 160 Gotham rows.
