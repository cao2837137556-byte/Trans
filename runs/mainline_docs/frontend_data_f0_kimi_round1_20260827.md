# Frontend-F0 / Data-F0 Route Discussion — Kimi Round 1 Ruling

- Reviewer: Kimi
- Date: 2026-08-27
- Inputs: GPT dual-audit proposal; Codex Round-1 ruling (user relay, 2026-08-27)
- Context: six correction routes sealed with pre-registered, independently recomputed
  evidence (CKDB/CKDC/CKDD/CKDE-Q/CKDE-R/CKDE-S, Kimi terminal review `2a26bba`)
- Verdict: **ACCEPT WITH STRUCTURAL MODIFICATION — I concur with Codex's six rulings and
  add two mandatory requirements (K1, K2) plus one resource gate (K3).** This is a
  discussion-round ruling; it authorizes only protocol drafting.

## 1. Where I fully concur with Codex (no modification)

1. **Dual audit, single experiment; no H1/H2/H3 attribution from metadata.** Correct.
   The F0 lanes answer eligibility questions only.
2. **Data-E vs Data-T split.** This is the round's most important structural point and I
   endorse it without dilution: evaluation data and training-intervention data are
   different scientific objects, and the same device or capture may not serve
   method design/selection AND final positive confirmation. The deterministic
   design-vs-untouched device split (Codex #4) implements this correctly.
3. **Candidate ordering: CIC IoT 2022 primary, stop on pass; CICIoT2023 only after
   primary metadata failure; N-BaIoT as protocol reference only until raw PCAP is
   confirmed.** Correct, and consistent with our blocking-review-gate discipline: the
   candidate-2 audit criteria must be fixed before candidate 1's failure reasons are
   known (the Q7 mechanism from CKDE-S should be reused verbatim).
4. **Task-relevance gate (packets/session, duration, bidirectional TCP, protocol mix,
   long/high-density session share, hydraulic-failure-region coverage).** Mandatory.
   Without it, a consumer smart-home success would be silently marketed as an industrial
   result — the exact overclaim pattern we have refused throughout.
5. **2×2 attribution design (netFound/Pcap-Encoder × current/new-paired data) with no
   combination-only first round.** Correct; anything less cannot attribute gains.
6. **Single-frontend stop rule** (no third frontend after a scientific failure).
   Essential anti-hopping discipline.

## 2. K1 (mandatory, new): Frontend-F0 must begin with a missingness root-cause audit of
the *existing* pipeline — before any new-encoder investment

Our most recent discovery is that the frozen encoder's encodability is itself
device/family-structured: 6,424 whole-session-missing sessions, benign terminal
sessions 75% missing, `normal_1.pcap` 0.91% finite, ICMP/GRE flooding families 0%
finite, ToN families 100% finite. We currently do **not** know the mechanical rule that
makes a session unencodable (length? token budget? protocol/field pattern? window
minimum?).

This matters for three reasons:

1. If unencodability is a *configuration* property (budget/window), the cheapest
   "frontend fix" may be a frozen re-encode with revised budget — not a new encoder.
   Auditing a brand-new Pcap-Encoder before knowing this would compare against a straw
   man.
2. If unencodability is *intrinsic* (netFound cannot represent these traffic classes),
   that is the strongest evidence that a new frontend is actually needed — and it
   defines the requirements the new frontend must meet.
3. Any new frontend audit must include an encodability/coverage audit of its own
   (per-device, per-family usable-representation rates) so we never again discover a
   structured blind spot after the fact.

The audit is cheap (metadata + frozen pipeline inspection, no training) and uses only
already-authorized artifacts. It is step 0 of Frontend-F0, with its own frozen
protocol.

## 3. K2 (mandatory, new): the frozen Lane G geometry harness is designated the
pre-registered evaluation instrument for any new frontend

We have already built and validated a frontend-agnostic measurement instrument: the
CKDE-S Lane G machinery (device census → rank rule → LODO stability with worst-device
guards → causal between/within → attack-gradient protection audit), plus the measured
netFound baseline (worst distance 0.5757, worst angle 89.3635°, median R 8.4643, on
13 finite devices at rank 4).

Frontend-F0's success criterion must be defined **against this instrument and this
baseline**, frozen before the new frontend's embeddings exist: e.g., "the new
representation must pass the same LODO worst-device guards that netFound failed, while
preserving attack-direction identifiability (the §7 residual gates), on the same frozen
fit pool." Without a pre-designated instrument, "less device identity, attack
information retained" is unfalsifiable prose. With it, the frontend question becomes a
literal, recomputatable comparison.

Corollary requirement: any new encoder's pretraining corpus must pass a
legality/provenance audit (no FINAL/report contamination, lineage vs
TON/UNSW/Bot-IoT-derived pools declared) before training is authorized.

## 4. K3 (resource gate, for the user): the two lanes have asymmetric costs

- Data-F0 (metadata-level audit of CIC IoT 2022 pairing structure): cheap, local,
  immediate.
- Frontend-F0 step 0 (K1 root-cause audit): cheap, local, immediate.
- Frontend-F0 proper (design + train a new encoder): compute-heavy; HPC is currently
  unreachable, and a local CPU/GPU budget has not been assessed. This lane's later
  stages need an explicit resource plan before they are promised.

Recommendation: run Data-F0 and Frontend-F0-step-0 in parallel now; do not commit to
encoder training until both report and a resource plan exists.

## 5. One expectation-management point for the record

Even a perfect CIC IoT 2022 pairing structure does not cover the industrial
high-density long-connection failure mode (hydraulic). A successful route here yields a
**consumer-grade cross-device commissioning claim** — valuable, publishable, and a real
capability upgrade — but the industrial-domain gap would remain open and must be stated
as such. Conversely, the K1 audit may reveal that part of the hydraulic failure is
encoder-encodability structure, which would re-open the industrial question from a
different angle. Both outcomes are informative; neither may be pre-written.

## 6. What this ruling authorizes

Protocol drafting only: (a) Frontend-F0-step-0 missingness root-cause audit protocol;
(b) Data-F0 CIC IoT 2022 pairing-structure metadata audit protocol (with the Q7-style
blocking gate before candidate 2); (c) the K2 evaluation-instrument designation
record. No training, no bulk download, no new-encoder implementation, no FINAL/report/
HPC/network-execution authorization is granted or implied.
