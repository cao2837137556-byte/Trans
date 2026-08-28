# Data-F0 candidate-1 metadata audit — result

- Date: 2026-08-28
- Frozen contract: `data_f0_paired_corpus_metadata_audit_frozen_20260828.md`
- Contract SHA-256: `e699008656ced7120bf6eacf71129ca416cd98e9c3d8d3e653f97e2e90ef0079`
- Candidate 1: CIC IoT 2022
- Verdict: **`PENDING_MEMBER_INVENTORY_AFTER_DOWNLOAD`**

## 1. Outcome first

The official CIC IoT 2022 page establishes a raw-PCAP corpus, a device-oriented capture
layout, and named Flood and RTSP Brute Force attack scenarios. It does not publish a
pre-open exact mapping from stable device identifiers to benign member files, victim
attack member files, independent sessions, or per-device attack families.

Accordingly, official metadata cannot yet prove even one same-device benign-history /
attack pairing. The frozen protocol explicitly maps this absence to PENDING, not to a
positive pairing and not to a negative scientific conclusion.

Candidate 2 remains sealed. No digest-matched proceed review is applicable because
candidate 1 did not enter a frozen failure state. No bulk download is authorized.

## 2. Official metadata established

- Publisher: Canadian Institute for Cybersecurity, University of New Brunswick.
- Official landing page: `https://www.unb.ca/cic/datasets/iotdataset-2022.html`.
- Data form: raw PCAP capture organized under Power, Idle, Interactions, Scenarios,
  Active, and Attacks.
- Named attacks: Flood and RTSP Brute Force; the page says attacks target some devices
  and describes repeated captures.
- Research access is offered through the publisher's dataset workflow and citation
  instructions. No credentials, cookies, signed links, or personal form data were
  retained.

## 3. What metadata did not establish

- exact member names and checksums;
- exact victim device identity per attack member;
- benign-only member identity per the same device;
- independent benign/attack session counts;
- deterministic commissioning/attack role boundaries before opening a bulk object;
- compressed/extracted byte budgets or published checksums; and
- the hydraulic-style long/high-density descriptor coverage.

Raw PCAP would permit the descriptors to be measured later, but future measurability is
not metadata evidence and is not counted as task-relevance success.

## 4. Split consequence

The paired-device count `N` is unknown, so the frozen `N>=8`,
`N_E=max(2,ceil(N/4))`, and `N_T>=6` gates cannot be evaluated. No Data-E or Data-T
identity was created. Device/file/date fragments were not promoted to independent
devices.

## 5. Boundary audit

All are zero: bulk archives and PCAPs downloaded, form submissions, credential/cookie
files written, candidate-2 accesses, training runs, embedding opens, report opens, and
FINAL opens.

## 6. Verification

- Data-F0 contract tests: **5/5 PASS**.
- Required outputs 1–8 are present in
  `runs/data_f0_candidate1_metadata_audit_20260828/`.
- `SHA256SUMS` independently covers every result and the official-evidence manifest.

## 7. Claim boundary and next action

This PENDING state is not evidence that paired data exist and is not permission to
download them. Advancing candidate 1 would require a separately drafted and frozen bulk-
inventory protocol with a fresh disk/network plan and explicit user authorization. The
current result does not activate candidate 2 and makes no detector-performance claim.
