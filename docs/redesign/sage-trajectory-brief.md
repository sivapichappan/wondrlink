# Sage Trajectory Brief

v1.1 — August 24, 2026 — for implementation planning. Approved design spec in section 7; rendered mockups ship alongside this file as `sage-mockups.html`. Thesis, verbatim from the redesign decision: "This is an app made for developers, not an app made for a stressed-out cancer patient." Every change below reverses that.

## 1. Who it's for

Sage is built for a cancer patient with zero clinical vocabulary — scared, tired, on a phone; a caregiver may join second to ease their mind, and wherever the two conflict, the patient wins.

## 2. Communication standard

Rules a writer can check copy against and an engineer can build gates against.

1. **Plain register is the default.** Sixth-grade reading level on every patient-facing string — UI, chat, cards, notifications. Enforced by an automated readability check in CI, not review-time taste. (The standard already exists and shipped in exactly one feature; it is now global.)
2. **Adapt up, never lead up.** Sage may match a patient who writes clinically; it never initiates jargon. Any clinical term that must appear gets a plain explanation inline on first use. Acronyms never appear in titles, buttons, or push notifications.
3. **Never a naked refusal.** Every limited answer makes the same three-part move: answer the answerable part, name the limit in one plain sentence, route to the patient's own care team. Fixed template, not improvisation.
4. **Default-engage.** The gate's only job is detecting contact with enumerated walls: prognosis, diagnosis, dosing and medication changes, and the frozen crisis machinery. Everything else gets a real answer. "Off-topic" is not a wall — food, work, kids, and money are on-topic because cancer lives inside a whole life.
5. **Predictions stay in the back.** Guideline-derived predictions may choose which questions Sage asks and which cards it deals, and when. No output sentence may describe the patient's future course.
6. **Ask-budget.** At most 2–3 questions per check-in, each traceable to a guideline relationship with the patient's actual treatment. Every ask carries an escape hatch ("Not now" / "I don't know"), and every data request says why: "To search trials, I still need two things."
7. **Zero interpretation in compiled outputs.** "Since your last visit" contains only facts the patient already confirmed (scanner "Looks right" taps, chat confirmations, their own recorded words) plus their open questions. Nothing is inferred at compile time.
8. **Every sentence traces to a signed source.** All medical content comes from the versioned, clinician-reviewed library. No live web retrieval at answer time — a reviewer's signature must always cover exactly what the patient reads.
9. **Notifications inherit all of the above:** frequency budget, calm copy, nothing clinical on a lock screen.

## 3. What we're cutting

- The six-step, 27-decision profile builder.
- All six standalone questionnaires. Named cost: no validated scores or severity trends remain, and the Lynch-syndrome risk screen (PREMM5) dies with them.
- The nine-tool home grid.
- Onboarding: the tips screen, the "Just four things" form, the setup pop-up, the duplicate year-of-birth ask, and the oncologist fork (replaced by a small footer link on the welcome screen; the patient app never mentions oncologists again).
- The Personal Navigator promise and its website dead-end. Decision on record (option C): dead ends state the limit plainly and route to the patient's care team.
- "My terms" as a destination tool — explanations go inline everywhere.
- "Surveillance" as a name, unconditionally.
- The patient-facing deep-research toggle — search depth is never a patient decision.
- Acronym titles and raw scores anywhere a patient can see them.
- The off-topic classifier default (replaced by walls-only detection, rule 4).

## 4. What we're keeping, and why

- **The frozen layer, untouched:** consent wording, 18+ gate, state blocks, welcome disclaimer, crisis tiers and interceptor, physician review gate. Not revisited by this redesign.
- **Document scanner + "Looks right / Not right":** promoted to acquisition backbone — it now feeds trials, the patient model, and "Since your last visit."
- **Visit recording:** promoted to a pillar; the recap is its output, not a separate tool.
- **Lifecycle stages (words, never numbers):** they become the card engine's clock, and they are the only global "how well Sage knows you" indicator allowed. No progress bars.
- **The ECOG-style plain card** ("On most days, which sounds most like you?") as the template for any structured ask that ever returns.
- **The recent voice work:** ships as-is; the testers never saw it.
- **Trial matching:** stays in the core promise, retimed — it activates "when Sage knows enough," and is never promised as a day-one deliverable.
- **Insurance appeal and pre-visit questions:** survive as cards dealt in conversation at the relevant moment.

## 5. Five biggest changes, in priority order

1. **Invert the gate.** Before: "Can I still go to my granddaughter's birthday party?" → refused as off-topic, while fluent oncology gets the longest answers. After: a real answer, with limits named only at true walls. Includes the logged classifier bug fix but goes beyond it — default-engage is design, not repair.
2. **Kill the builder; learn from scans and talk.** Before: six steps, 27 decisions, twelve gene checkboxes before any value. After: chat asks your name and cancer type; "snap a photo of any report when you're ready"; Sage names what it still needs only when a goal needs it. Trials unlock when Sage knows enough.
3. **Home becomes the conversation.** Before: a nine-tool grid plus a DUE TODAY strip. After: chat, a "+" in the composer holding exactly Scan a report / Record a visit / Since your last visit, and cards dealt in-stream (trial matches, pre-visit questions, appeal help, scan suggestions). Instrument card engagement from day one: if cards underperform, scanning starves, the model stays ignorant, and trials never unlock.
4. **Check-ins become engine-chosen questions in chat.** Before: "Depression (PHQ-9)," "LATEST PHQ-9: Moderately severe." After: two or three plain questions picked from the patient's regimen ("Any tingling in your fingers, especially when you touch something cold?"), asked in chat, initiated by notifications that obey rule 9.
5. **Onboarding shrinks to three screens plus a conversation.** Before: seven screens, an oncologist fork, "one account cannot be both." After: welcome (oncologist footer link) → one legal screen (date of birth, state, the three frozen checkboxes) → "Who are you here for?" → chat asks everything else, starting with "What should I call you?"

Also in scope, below the top five: the "Since your last visit" compiler (confirmed facts only); the allowlisted ingestion pipeline (NCI patient-version summaries, American Cancer Society, NCCN patient guidelines, MedlinePlus) with scheduled diff-and-re-review, using the refusal log as the monthly acquisition list; appointment-date awareness as a first-class part of the patient model (asked conversationally after each recorded visit).

## 6. Open questions we deliberately postponed

- **Retention and motivation.** On the record, verbatim: until this work happens, the check-in system only detects patients who show up.
- **Caregiver mechanics:** what a linked account can see, consent between accounts, caregiver-view density. Patient-first is decided; the mechanics are not.
- **Calendar sync** and its permissions ask — a simple app does not open by requesting calendar access.
- **Oncologist-side redesign** behind the footer link.
- **Library operations:** review cadence and who at WondrLink owns the queue permanently. The physician gate is now recurring editorial labor, not a one-time signoff.
- **Whether any validated screen returns** as a plain card, if the clinician side ever needs standardized trends.
- **Patients without a reachable care team:** what the dead end routes to for them. This is the cost of cutting the navigator promise — carry it visibly until answered.

## 7. Design spec (approved)

Rendered target: `sage-mockups.html`, twelve screens, approved August 24, 2026. The copy in the mockups is canonical — implement strings as written; they were composed to pass section 2. Names, dates, and places (Maria, Dr. Rivera, University Hospital) are placeholder data, not copy. The mockup file's `:root` CSS block is the token source of truth; lift it directly.

**Tokens.**
- Palette: page `#F6F7F3` (green-tinted paper, deliberately not cream); ink `#24312B`; secondary ink `#5A6A61`; muted `#8A968E`; primary action sage `#4A7862`; deep sage `#2F5443` (text on tints); tint `#E4ECE5`; accent border `#D5DFD6`; card `#FFFFFF`; hairline `#E2E7E0`; patient-bubble warm `#F1E9DC` with ink `#5D4C36` — the only warm element on screen, reserved for the patient's own words.
- Type: **Source Serif 4 is Sage's voice** — every Sage chat message, the wordmark, the italic stage words, document and trial titles. **Instrument Sans is the interface** — buttons, chips, labels, patient bubbles. The rule is semantic: typography tells the patient who is speaking before they read a word. Sage messages 16px serif, line-height 1.55; nothing below 13px.
- Shape and components: cards 18–20px radius; chips full-round with a quiet borderless variant for escape hatches ("Not now," "I'm not sure"); dealt cards carry the sage accent border to distinguish them from plain messages; composer is `+` / text / mic; fact rows confirm with a tick; the "+" sheet holds exactly three rows; the stage renders as italic serif words in the header — never a number, never a bar.

**Screen inventory — screen → what it implements.**

| # | Screen | Implements |
|---|--------|-----------|
| 01 | Welcome | Frozen disclaimer on welcome; oncologist door as footer link |
| 02 | Legal, all of it | The only form in Sage; DOB asked once; frozen consent wording verbatim |
| 03 | Who are you here for | The one surviving onboarding question; re-voices the app |
| 04 | Chat takes over | Change 5; rule 6 escape hatch on the first ask |
| 05 | Home — the conversation | Changes 2–3; stage words; dealt scan card as acquisition path |
| 06 | The "+" open | Change 3; exactly three tools; trials and pre-visit never listed |
| 07 | A check-in | Change 4; rules 5–6; engine-chosen questions, surveys gone |
| 08 | After a scan | Plain-words facts, per-fact confirmation; feeds rule 7 |
| 09 | Trials — the ask | Rule 6 verbatim; trials unlock when Sage knows enough |
| 10 | Trials — the match | Plain titles, one status pill, every path routes to the doctor |
| 11 | Since your last visit | Rule 7; confirmed facts and the patient's words only |
| 12 | At the limit | Rule 3's three-part move at a frozen wall; decision C routing |

**Handoff notes for implementation.** The mockup HTML is a reference rendering, not production code — rebuild components natively, keep the tokens. Instrument card engagement from day one (change 3's stated risk: if cards underperform, scanning starves and trials never unlock). Screens 05–10 assume the walls-only gate (change 1) is in place; build the gate inversion first or the conversation shown here refuses half its own script.
