# Model-improvement learning loop — DORMANT (activation checklist)

**Status: built, NOT active.** All plumbing is behind `FEATURE_MODEL_IMPROVEMENT`
(env, default false). With the flag off, behavior is byte-identical to before
Phase 5 (verified by `scripts/test_patient_model.py` consent-parity test).

## What it is

Using **de-identified, cohort-keyed patterns** (never raw patient text) to
improve WondrChat: cold-start priors for new patients, question-policy tuning,
trial-match calibration. This is a **new processing purpose** — the existing
`consent_sharing` covers only sharing de-identified queries with LLM providers
*to answer the user*, not retention/secondary use.

## Privacy design (already enforced in code)

- `consent_model_improvement` is **opt-IN**: no signup baseline, defaults to
  not-granted (`lib/supabase_storage.py` `OPT_IN_CONSENT_KEYS`), recorded via
  a `grant` action, and **never** feeds `chat_disabled` — declining must not
  degrade the product.
- `pattern_records` has **no user_id column by design**; records are
  whitelisted categorical fields only, PII-guarded before insert
  (`lib/learning_loop.py`).
- **k-anonymity (k≥20)** at consumption: a pattern may only influence anything
  once ≥20 distinct contributions exist for its cohort key.
- Right-to-delete: pattern records are unlinkable by design; the user's
  linkable data deletion path (`delete_all_user_data`) is unchanged.

## Activation checklist (in order — do not skip)

1. [ ] **Attorney review** of the opt-in consent copy (new purpose language,
       WA MHMDA "clear affirmative act", CCPA/CPRA secondary-use disclosure)
       + Privacy Policy / Consumer Health Data Notice updates.
2. [ ] **Bump `CURRENT_CONSENT_VERSION`** in `lib/compliance.py` so existing
       users see the updated notice (the opt-in itself stays optional).
3. [ ] Ship the **opt-in UI** (Settings → Consent Management: a fourth,
       clearly-optional toggle; default off).
4. [ ] Apply `supabase_migrations/2026_07_15_model_improvement_dormant.sql`
       (safe to apply early — changes no runtime behavior).
5. [ ] Set `FEATURE_MODEL_IMPROVEMENT=true` in Vercel.
6. [ ] Wire `emit_pattern_record()` call sites (Modeler outputs, question-
       policy outcomes, trial-match calibration events).
7. [ ] Before ANY consumption of patterns: implement the k≥20 export gate and
       have clinical review sign off on how patterns influence the app
       (per the supervisor brief: silent predictions checked against outcomes,
       clinical review before anything user-visible).
