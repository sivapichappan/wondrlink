# Supervisor email — edge functions vs live Flask backend (SENT 2026-07-21)

Record of the architecture question raised after receiving
`docs/sage-implementation-guidelines.html` + `config/safety/sage-safety-rules-v0.9.json`.
Decision pending; all guideline work proceeds stack-portable meanwhile (rules as data,
prompts as files, provider-neutral contracts) so either answer is cheap.

---

**Subject: Edge functions or our live backend?**

Hi [Name],

Got the guidelines and the safety rules file. I'm building the safety classifier now,
and everything else in the doc is in flight.

One question before I commit further: the doc assumes Supabase Edge Functions for server
logic. Our backend already runs live as a Flask API on Vercel with the RAG, profile
extraction, trial matching, and eval harness working in production, and it satisfies all
the hard rules (client never calls third parties, keys server-side, one safety choke
point). Porting it to edge functions would mean rewriting and revalidating all of that
in TypeScript.

Can I keep the Flask API as the server boundary, or are edge functions a firm
requirement? My recommendation is to keep Flask.

Best,
Siva

---

Context notes (not in the email):
- His edge-function table maps to live routes: chat ↔ `POST /api/chat`; safety-check ↔
  the new pre-chat classifier inside it; match-trials ↔ `lib/clinical_trials.py`;
  extract-document / summarize-visit / transcribe ↔ planned (Workstreams D/E).
- His AI-config example lists `claude-sonnet-4-6` for chat — treated as illustrative
  (the registry makes model choice pure config; the Kimi-K2.6 decision stands, the
  Anthropic path is built + dormant behind one env var).
- Physician review of the safety rules (v0.9 draft) is tracked as a LAUNCH BLOCKER;
  reviewer suggestion: Dr. Csiki.
