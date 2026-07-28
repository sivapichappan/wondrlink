# Connection map Phase 3 — attestation and publication gate probes

Run after applying `2026_07_29_connection_map_attestation.sql` then
`2026_07_29_connection_map_publication.sql`.

Phase 3's gate is **"a human approves an edge end to end"**: an edge with a
verified citation is approved, signed by a physician, and published — and every
way that should fail, fails.

Target: sage-dev (`eizhshntrquvqwfsseeh`). Prod at release.

---

## Setup

A complete fixture is needed, because the gate checks everything at once: two
concepts **with `display_patient` filled in**, a real section, an edge created
through `insert_master_edge_with_evidence` **with `patient_phrasing`**, an
active `reviewer_attesting` physician, and a draft version listing the edge.

## Probes

| # | Probe | Expected |
|---|---|---|
| 1 | `connection_map_publication_blockers(v)` on a draft whose edge is a candidate with no signature | **two rows**: status not approved, and no attestation — the list is itemized, not first-failure |
| 2 | `connection_map_publish(v, actor)` in that state | **ERROR** naming the count and every blocker (acceptance #6) |
| 3 | Approve the edge, `connection_map_attest(...)` as an active MD, then publish | **succeeds**: status published, `published_at` stamped, `frozen_hash` set |
| 4 | Reword `patient_phrasing` after signing, re-check blockers | **"attestation voided: edge or evidence changed after signing"** (acceptance #10) |
| 5 | Restore the exact signed wording, re-check | **zero blockers** — the hash tracks content, it is not a one-way tripwire |
| 6 | Revoke the reviewer, re-check blockers | **zero blockers** — they were active at signing (acceptance #8) |
| 7 | `connection_map_attest(...)` as the now-revoked reviewer | **ERROR** `is not active (status revoked)` (acceptance #7) |
| 8 | `UPDATE attestation SET decision=...` | **ERROR** `attestation is append-only` (acceptance #25) |
| 9 | Set `governance_note` to NULL, re-check blockers | **"governance_note is required to publish"** (acceptance #9) |
| 10 | `UPDATE` any field of a **published** version | **ERROR** `published map versions are immutable` (§4.5) |
| 11 | Set `enabled_relationships` to include `acts_through` | **ERROR** check violation — §4.3 makes it authoring-only, never patient-facing |
| 12 | Change `source_section.text` after the citation was made, re-check blockers | **"evidence no longer matches its source text"** — §5.7 requires evidence to still verify AT PUBLICATION, which the insert-time trigger cannot speak for |

---

## Run log

**2026-07-28, sage-dev — ALL PROBES PASS.** Probes 1 through 12 each behaved
exactly as stated, including the end-to-end publication in probe 3: an edge
carrying a character-verified citation went candidate → approved → signed →
published with a frozen hash.

Two results worth keeping in mind:

- **Probe 5** confirms the hash is content-addressed. Restoring the exact
  wording a physician signed clears the block, rather than requiring a new
  signature for a change that was reverted.
- **Probes 6 and 7 together** are the distinction acceptance #7 and #8 draw:
  revoking a reviewer stops them signing anything new, but does not retroactively
  invalidate what they signed while active. That only works because signing-time
  standing is snapshotted onto the attestation.

**Fixture rows remain on sage-dev by design.** The attestation cannot be
deleted (append-only) and it holds a RESTRICT reference to its edge, so the
gate fixture is permanent. That is the immutability guarantee working, not a
cleanup failure.
