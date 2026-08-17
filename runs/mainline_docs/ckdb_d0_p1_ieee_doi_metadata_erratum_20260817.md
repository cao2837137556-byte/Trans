# CKDB D0-P1 IEEE DOI metadata retrieval erratum

Status: FROZEN_ENGINEERING_ERRATUM

Date: 2026-08-17

## Evidence

The frozen descriptor DOI resolves to IEEE document 11137365, but automated
HTML retrieval returns HTTP 202 and either an empty body or an AWS WAF
JavaScript robot-verification shell.  That shell is not bibliographic evidence
and the executor correctly failed closed.

The same DOI supports standard DOI content negotiation for
`application/vnd.citationstyles.csl+json`.  DOI.org redirects that request to
the exact Crossref API transform endpoint, which returns the publisher-
registered descriptor metadata including DOI and title.

## Mechanical erratum

For the pre-existing `unsw_descriptor_landing` Tier-A object only:

- keep the same DOI request URL and byte ceiling;
- request `application/vnd.citationstyles.csl+json`;
- change the expected representation from HTML to JSON;
- replace the unusable IEEE WAF final host with exact host `api.crossref.org`;
- require a nonempty JSON object and reject HTML/WAF masquerading as metadata.

This remains the same frozen object purpose: descriptor-paper bibliographic
metadata.  No device/corpus candidate, tier gate, domain count, long-TCP rule,
scientific verdict, or claim boundary changes.  The retrieval plan must receive
a new SHA-256 identity before retry.

This erratum authorizes no PCAP, 13.92 GB archive, second industrial corpus,
HPC, training, embedding, threshold, label, or FINAL operation.

Plan identities:

- superseded transport-erratum plan:
  `ca28462274bd0fe2256e8eefaead9bfc6e768b74f2dbc99a89479e34a3d46bfe`
- active:
  `0abf7b61faf4259caefc106c65ea0128a69b0c460ea7a772d72fac53d6fe161b`
