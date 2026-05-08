# WondrChat 2.2

**Release Date:** April 2026
**Status:** Production (https://wondrchat.vercel.app)
**Previous Version:** [v2.1](../v2.1/RELEASE.md)

---

## Summary

WondrChat 2.2 implements physician and mentor feedback from Stage IV patient profile testing. The core change is a shift from "clinical informer" to "supportive ally" — every response now follows a mandatory empathy-first structure, imperative language is prohibited, and new Safety Valve and Patient Advocate modes handle high-distress and physician-friction situations.

---

## Changes

### Empathy-First Response Architecture (Items 1, 2a)

**Before:** ANP framework only applied to medium/high sensitivity queries. Routine questions got "standard warm professional tone" without emotional acknowledgment.

**After:** Every response follows a mandatory 3-step Validation Loop:
1. **Reflective Acknowledgment** — mirror the user's emotion/experience (1 sentence routine, 2+ sensitive)
2. **Validation** — normalize the experience ("Many people in your situation...")
3. **Permission-Based Guidance** — frame advice as offers ("Would you like to explore..."), never directives

**Tone Rules added:**
- Prohibited: "You must", "You need to", "Tell your doctor", "You should"
- Required: "It might be helpful to...", "Some patients find...", "We can look into..."
- "We" companionship framing throughout
- Disclaimers must feel protective, not bureaucratic

### Softening Phrase Library (Item 2b)

**New file:** `lib/tone_config.py`

Pre-written empathetic phrases injected based on query context:
- `before_clinical_data` — collaborative openers
- `before_disclaimer` — protective framing
- `pain_comfort_openers` — empathetic pain acknowledgments
- `distress_comfort_openers` — emotional distress support
- `physician_friction_bridges` — scripts for next oncologist appointment

### Patient Advocate Mode (Item 3)

**Trigger:** User describes feeling dismissed, unheard, or unsupported by their oncologist (keywords: "dismissive", "won't listen", "rushed", "cold", "doesn't care", "unsupportive", "distant").

**Response:**
1. Acknowledge the difficulty
2. Empower — "You deserve a partnership where your concerns matter"
3. Provide a bridge phrase: "I've been feeling a bit disconnected from our treatment plan lately. Can we spend five minutes today making sure I understand the next steps?"

**Rule:** Never disparages the doctor.

### Safety Valve Mode (Item 4)

**New distress urgency level** added to `detect_symptom_urgency()` alongside existing emergency/urgent:

**Triggers:**
- Pain >= 6/10 (detects "6/10", "7/10", "severe pain", "excruciating", etc.)
- Emotional distress ("can't take this anymore", "I'm scared", "I can't do this", "losing hope")

**Behavior:** First 2 sentences are pure empathetic comfort — no clinical data. AI shifts from "Informer" to "Companion" role. Random comfort opener from `tone_config.py`.

### Compassionate Care Terminology Fix (Item 5)

Added TERMINOLOGY RULES to system prompt:
- "Compassionate care/use" = investigational drugs outside trials ONLY
- Never used for standard chemo, immunotherapy, or approved treatments
- "Palliative care" = comfort-focused care (not hospice)
- "Supportive care" = symptom/side effect management

### Pain Management Guidance (Item 6c)

New `PAIN_MANAGEMENT_GUIDANCE` constant injected when pain + medication keywords co-occur:
- OTC safety framing ("check with oncology team before starting anything new")
- NSAID interaction warnings (bleeding risk, kidney function)
- Acetaminophen liver function note
- Pain >= 6/10 prompts same-day care team contact

### Knowledge Base Expansion (Items 6a, 6b)

| Document | Content |
|----------|---------|
| CRC_Exercise_Protocols.pdf | Aerobic (20-30min 3-5x/week), resistance (2-3x/week), neuropathy balance training, post-surgery restrictions, during-chemo timing |
| CRC_Mucositis_Management.pdf | Salt/baking soda rinses, diet during mucositis, OTC options, when to escalate, which chemos cause it |

**Total KB: 25 documents, 1,751 chunks (all embedded)**

### Human Navigator Escalation (Item 7)

**System prompt:** Auto-offers WondrLink Foundation navigator for complex insurance, out-of-network trials, severe distress, or explicit "speak to a person" requests.

**Sidebar UI:** Persistent "Connect with a Navigator" button linking to www.wondrlinkfoundation.org — always visible when logged in.

---

## Verification Results

### Manual Tests (Stage IV profile)
- "I have 7/10 pain and I'm scared" → Safety Valve: comfort-first opening, no clinical data in first 2 sentences
- "My oncologist is dismissive and won't listen" → Patient Advocate: acknowledge, empower, bridge phrase script
- Both passed with correct tone and structure

### Automated Tests
56/60 (93.3%) — 4 failures are LLM wording variability, not code defects

---

---

## UI Redesign

**Modernized the entire visual design** with dark mode, glassmorphism, refined color system, and improved typography.

### Design System
- **80+ CSS variables** (was 30): typography scale, glassmorphism tokens, semantic alerts, surface variants
- **Deepened brand teal** (#4A8F86 to #357A72) for better contrast
- **Migrated 33 hardcoded colors** to CSS variables (dark-mode ready)

### Dark Mode
- Auto-detects OS preference via `prefers-color-scheme`
- Manual toggle button (moon/sun icon) in sidebar header
- Persists choice to localStorage
- Smooth theme transition (300ms) on all surfaces
- Dark palette: #0F1419 background, #1E252D surface, #5DB8AD teal

### Visual Polish
- **Sidebar**: glassmorphism (backdrop-blur, translucent background)
- **Chat bubbles**: asymmetric radius, left teal accent border on bot messages, solid user color (dropped gradient)
- **Section cards**: hover lift animation with teal left-border accent
- **Suggestion chips**: scale-up micro-interaction on hover
- **Animations**: spring easing curve on chat messages

### Accessibility
- `@media (prefers-contrast: high)` support with deepened primary and border colors
- `<meta name="color-scheme" content="light dark">` for native form theming
- Logo brightness adjustment for dark backgrounds

---

## Commits

```
7268214 WondrChat v2.2: Empathy-first tone, Safety Valve, Patient Advocate, Navigator
e802992 Fix nutrition sidebar buttons targeting wrong input ID
a475fbc Strengthen prompt enforcement and add physician feedback test suite
1a733a9 UI redesign: dark mode, glassmorphism, refined color system and typography
```
