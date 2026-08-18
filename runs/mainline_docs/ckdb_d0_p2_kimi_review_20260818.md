# CKDB D0-P2 Kimi review — PASS (draft accepted for freezing)

Date: 2026-08-18
Reviewer: Kimi
Target: `ckdb_d0_p2_second_industrial_corpus_amendment_draft_20260818.md`
(Codex commit `aa8fa57`)

## Verdict: PASS — the five questions are ruled below; Codex may produce the FROZEN amendment and SHA sidecar

## Independent fact-check of the candidate (done before ruling)

I verified the candidate against the official PNNL DataHub page
(`data.pnnl.gov/group/nodes/dataset/13470`, authority S) rather than trusting
the draft's summary:

- The dataset exists and is titled "Electricity and Gas IDS";
- "high-fidelity, **hardware in the loop** experimentation on **simulated
  models of representative electric and natural gas distribution systems**"
  — two process sectors confirmed in the official text;
- scenario 1 is explicitly "**Normal traffic** — to establish the baseline
  operation of the devices" — a named benign baseline exists;
- named device fleets differ by sector: electrical side SAGE RTU / SEL 451 /
  GE D30 with DNP3; gas side ROC 800 / FloBoss / ControlWave with Modbus —
  consistent with `DISTINCT_FIELD_DEVICE_FLEET` being provable;
- **system-fault scenarios exist as their own class** (faults on the OPAL-RT
  microgrid simulator and on the gas distribution simulator) — physically
  abnormal states that are neither baseline nor cyber-attack;
- multiple real attack classes exist (unauthorized IP, bad-CRC, spoofing,
  fuzzing, MitM) — the corpus is mixed, so the benign-boundary gate in §6 is
  load-bearing, not decorative.

The taxonomy-selection rationale is therefore factually supported, and the
selection reason (INDUSTRIAL_PROCESS with two sectors and an official normal
baseline) is not a hydraulic-resemblance patch.

## Rulings on the five questions

1. **One fixed candidate, no fallback: ACCEPT.** This is exactly the
   pre-frozen remedy shape from D0-P1. The no-silent-third-corpus rule and
   the NO-GO exit are required discipline, not obstacles.
2. **Four-condition independence gate: ACCEPT.** The conjunction
   (distinct process model ∧ distinct device fleet ∧ distinct control
   enclave ∧ separable normal unit) is the correct operationalization of
   post-clustering independence for a two-sector testbed. The fail-closed
   rules are right: `UNKNOWN` is not TRUE; one orchestration host or shared
   campaign dates do not collapse domains; a shared simulator/enclave or
   inseparable normal unit does. Conditions 1–3 look provable from Tier A
   metadata; condition 4 is the genuine risk (see Q3).
3. **No pre-open normal-member inventory → `PENDING_METADATA`, not NO-GO:
   RULED PENDING.** §9 state 2's "unresolved benign boundary" clause fires
   only when primary metadata *proves* the boundary cannot be separated.
   `PENDING_ARCHIVE_INVENTORY` (single opaque tar, no server-side member
   listing) proves nothing either way, so it belongs to state 3 with the
   named reason code. Required consequence, to be written into FROZEN: the
   later large-download protocol must contain a post-download, pre-use
   benign-boundary verification step that fails closed to NO-GO — i.e., we
   accept the risk of one possibly wasted large download rather than weaken
   the boundary rule. This mirrors the CIC horizon-PENDING precedent from
   D0-P1.
4. **Exclude system-fault scenarios: ACCEPT, and I want the rationale on
   record.** A system fault is an abnormal *physical* state: not an attack,
   not baseline. Mixing fault physics into "benign" training material would
   contaminate the normality model with exactly the kind of non-attack
   abnormality we want the detector to treat carefully. Exclusion until a
   future protocol defines their scientific role is the only defensible
   choice. (They may later become a valuable robustness split — but that
   decision belongs to its own preregistration.)
5. **Success = eligibility to draft, never authorization: ACCEPT.**
   `large_download_authorized=false` even in state 4, consistent with every
   prior gate in this project.

## Non-blocking notes for the FROZEN text

- **N1 (lineage timeline)**: Audit 2 should record the OSTI/DataCite
  publication/capture dates as the PNNL timeline anchor, same as we now do
  for UNSW. The bibliographic JSON is already in the Tier A allowlist.
- **N2 (protocol is not domain)**: PNNL gas side speaks Modbus, same
  protocol family as CIC Modbus 2023. Domain independence here rests on
  process model/device fleet/enclave, not protocol; the coverage matrix
  should record protocol families descriptively so later LODO planning does
  not confuse "same protocol" with "same domain" (or vice versa).
- **N3 (manual registration)**: the draft correctly bars automated account
  creation. Restate in FROZEN that if the route ever reaches the large
  download, the PNNL DataHub registration is the user's manual action, same
  as the CIC form.

## What this review authorizes

- Codex may freeze the D0-P2 amendment (with the Q3 consequence and N1–N3
  carried in), generate the SHA-256 sidecar, and present both for freeze
  verification.

This review does **not** authorize: implementation, any PNNL retrieval
(including HEAD requests), account creation, any download, HPC, training,
or FINAL contact.
