# Reviewer Defense: Raw Provenance And Clean Split

## Q1: Did you find raw packet / timestamp provenance?

Yes, pcap and extracted TSV assets exist for the current original100 sources. The mapping is recoverable by deterministic extraction order, but a formal row-level sidecar manifest has not yet been persisted.

## Q2: Do HH separators use future information?

No future packet use was found in the feature code. The extractor updates and reports sequential state for the current packet. The remaining risk is split-boundary state carryover and capture/window conditions, not explicit future labels.

## Q3: Why not run clean independent validation now?

Because a clean unused split with sufficient attack rows and independent OOD evidence is not currently available. Bin 9 is too small for formal validation, and current OOD eval is not a new independent object.

## Q4: Does this mean LOW-GUARD++ failed?

No. It means the clean-claim gate is blocked by provenance/split construction. The proper next step is rebuilding row-level manifests and constructing purged or capture-disjoint validation.
