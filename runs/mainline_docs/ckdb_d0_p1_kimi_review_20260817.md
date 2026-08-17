# CKDB D0-P1 Kimi independent review — verdict and rulings

Date: 2026-08-17
Reviewer: Kimi (independent design/review side)
Target: `ckdb_d0_p1_external_metadata_audit_draft_20260817.md` (Codex commit `a3fa814`)
Authority: CKDB round-3 convergence (`7a10dfc`)

## Verdict

**PASS WITH ONE REQUIRED CLARIFICATION (R1).**

The draft faithfully implements all five round-3 consensus points. The four
open questions are ruled below. R1 must be resolved in the FROZEN text before
freezing; it is a definitional fix, not a redesign. No other changes required.

## Rulings on the four draft questions

### Q1 — UNSW `flows.zip` (95.51 MiB) as Tier B: **ACCEPT**

Derived per-device flow metadata is not raw packets; the 128 MiB cap with
PCAP-magic/member rejection (§3.7–3.8) is a coherent "metadata-only" boundary.
One condition, already implied by §3 and stated here for the record: if, after
extraction, the flow tables turn out to contain per-packet records or payload
bytes (i.e., packet-level data in disguise), the object is quarantined and
reported as a safety-check failure, not silently used. The existing
member-listing and SHA manifest rules already support this; no text change
needed beyond carrying this sentence into the FROZEN version.

### Q2 — CIC with Tier A PASS but no compact flow table: **ACCEPT as drafted**

`PENDING_NO_SMALL_FLOW_METADATA` is the honest state, and the prohibition on
opening PCAPs to fill horizon fields is exactly right. Consequence worth
stating explicitly in FROZEN: horizon/scale PENDING does not by itself block
Audit 5's route-level gate, because the device/role inventory comes from
Tier A. This is coherent and I accept it.

### Q3 — three independent consumer + three independent industrial units: **ACCEPT as a download gate, with required clarification R1**

Three is the bare minimum at which LODO and worst-domain training are
meaningful at all (two training domains, one held out). As a *gate for
requesting the large download* I accept 3+3, because the consumer side (UNSW,
27 published devices) will far exceed it, and because the exact LODO support
freeze correctly happens later, after census.

**R1 (required clarification).** The draft contains an internal tension
between Audit 4 and Audit 5 that must be eliminated before freezing:

- Audit 4 (§5, Audit 4) freezes: simulated IED/HMI roles sharing one
  generator are reported separately **but also clustered under the common
  simulator** for bootstrap and LODO planning.
- Audit 5's route-level gate requires each domain side to contribute "at
  least three **independent** device/role source units".

CIC Modbus 2023 is a single simulated substation. Under Audit 4's own
clustering rule, its roles may collapse to **one** independent domain. The
word "independent" in the Audit 5 gate is currently undefined with respect to
that clustering rule, so the same evidence could pass or fail the gate
depending on interpretation. That is a post-hoc discretion hole — exactly the
kind this project exists to close.

FROZEN text must state, mechanically:

1. "Independent" in the Audit 5 gate means **post-clustering** independent
   domains as defined by Audit 4 (same physical device repeated days = 1;
   same simulator = 1).
2. If, after clustering, the industrial side yields fewer than 3 independent
   domains, the overall verdict is `CKDB_D0_P1_PENDING_METADATA` (or
   `NO_IDENTIFIABLE_CORPUS_MIX`, per the existing enum), and the named missing
   evidence is a **second industrial/process corpus**.
3. Adding that second industrial corpus is **not** the prohibited
   "add a third corpus after observing candidate results": the addition
   criterion (industrial/process domain, post-clustering independent-domain
   count >= 3 across the industrial side) is fixed **now**, before any
   candidate result is observed. Any such addition still requires its own
   pre-registered amendment and the same eight-audit schema before any large
   download.

This preserves the no-cherry-picking guarantee while keeping the protocol
executable when its own clustering rule fires.

### Q4 — long-TCP descriptor `>256 packets OR >=300 seconds`, descriptive only: **ACCEPT**

The descriptor is frozen a priori, applied corpus-globally, and explicitly
barred from becoming a per-corpus inclusion requirement or a success gate.
That matches round-3 consensus. The `OR` form is acceptable: it describes the
failure-mode class (long-horizon bidirectional TCP) without tuning to
hydraulic's observed values. No change.

## Additional review findings (no action required)

1. **KNOWN_DISJOINT discipline (§4, Audit 2)** — the rule that "finding no
   match is at most `NO_KNOWN_OVERLAP`" and that `POSSIBLE_OVERLAP` cannot be
   upgraded by inference is the strongest part of this draft. It directly
   bounds what the E3 arm can ever claim, since netFound's pretraining
   lineage is only as documented as its authors made it. I checked: the
   route-specific conclusions required by Audit 2 (I1 vs fit/select/report,
   E3 vs netFound pretraining, cooler-motor FINAL vs all externals) cover all
   three planned uses. Complete.
2. **Benign boundary (Audit 3)** — excluding mixed/unknown units rather than
   filtering by row labels is the correct call and matches how this project
   treated UNSW interactions/background in CKDB D0.
3. **Contract tests (§8)** — the 18 tests cover the failure classes we have
   actually seen (PCAP smuggling, HTML-as-data, traversal, resume identity,
   Python 3.9). Test 14 (overlap verdicts cannot overclaim) and test 15
   (repeated days do not inflate domain counts) directly encode the two
   statistical risks I care most about. Sufficient.

## What this review authorizes

- Codex may produce the FROZEN D0-P1 protocol with R1 incorporated
  (definitional change only; the eight audits, tiers, caps, and test list
  stand), generate its SHA-256 sidecar, and present both for freeze review.

This review does **not** authorize: implementation, any download of any size,
HPC submission, or any contact with FINAL assets. Execution of a frozen
D0-P1 still requires the user's explicit authorization.
