# CKDB D0-P3 P0-B result (2026-08-20)

## Outcome first

The user successfully submitted the official CIC access form. The resulting
publisher inventory exposes exactly one root object, `Modbus Dataset.zip`.
It exposes neither a benign-only subtree nor an exact benign-member list before
body transfer. Under the FROZEN D0-P3 contract, this is a scientific boundary
failure rather than a network, account, capacity, or implementation failure.

The mechanical verdict is:

```text
status                         = NO_IDENTIFIABLE_THREE_INDUSTRIAL_DOMAINS_CIC_IDENTITY_UNRESOLVED
cic_industrial_domains         = 0
pnnl_maximum_industrial_domains = 2
combined_industrial_maximum    = 2
minimum_required               = 3
route_terminated               = true
replacement_corpus_allowed     = false
third_corpus_search_allowed    = false
```

No download was clicked, no object body was opened, and no personal form value,
credential, cookie, token, or transient post-form URL was recorded.

## Why the whole ZIP is ineligible

The FROZEN protocol requires the CIC contribution to be identifiable as a
benign-only remote object, subtree, or exact member set before transfer. A
single whole-dataset ZIP that may contain both benign and attack material
cannot establish that boundary. Downloading it first and deciding afterwards
would reverse the pre-registered order and is therefore prohibited.

This outcome does not say that the publisher's dataset is defective. It says
that its published transfer interface cannot satisfy this route's pre-body
benign-boundary contract.

## Operational consequence

D0-P3 stops before large transfer. The previously observed D: storage shortfall
does not need remediation for this frozen route, because no UNSW, PNNL, or CIC
large body is now authorized. No cleanup or large download should be started
under D0-P3.

The FROZEN repair budget has already been consumed by PNNL, so this route also
forbids searching for a replacement or third corpus. Continuing research now
requires a separately named and newly pre-registered route; it must not be
presented as continuation of D0-P3.

## Scientific interpretation

CKDB's frozen external-corpus mixture is not identifiable under its declared
three-industrial-domain minimum. This closes only this corpus-mixture route.
It does not retract CKDA D1's strong attack-side signal, and it does not solve
the remaining cross-device benign/OOD failure. The next design discussion
should start from that precise boundary rather than bypassing this result.

Machine-readable evidence:
`runs/mainline_docs/ckdb_d0_p3_p0_b_resolution_20260820.json`
