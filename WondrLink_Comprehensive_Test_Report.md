# WondrLink Comprehensive Test Report

**Generated:** 2026-08-05 09:10:44

**Total Tests:** 75
**Passed:** 70/75 (93.3%)


---
## 1. Unit Tests

**Passed:** 23/23


### Item 2: Treatment Line

- **[PASS]** `auto_detect_treatment_line('FOLFOX + Bevacizumab', None)`
  - Expected: line=1L_or_adj, confidence=medium
  - Actual: detected=True, line=1L_or_adj, confidence=medium
- **[PASS]** `auto_detect_treatment_line('CAPOX', None)`
  - Expected: line=1L_or_adj, confidence=medium
  - Actual: detected=True, line=1L_or_adj, confidence=medium
- **[PASS]** `auto_detect_treatment_line('Regorafenib', None)`
  - Expected: line=3L+, confidence=high
  - Actual: detected=True, line=3L+, confidence=high
- **[PASS]** `auto_detect_treatment_line('TAS-102', None)`
  - Expected: line=3L+, confidence=high
  - Actual: detected=True, line=3L+, confidence=high
- **[PASS]** `auto_detect_treatment_line('Pembrolizumab', {'MSI': 'MSS'})`
  - Expected: line=1L_msi_h, confidence=low
  - Actual: detected=True, line=1L_msi_h, confidence=low
- **[PASS]** `auto_detect_treatment_line('Pembrolizumab', {'MSI': 'MSI-H'})`
  - Expected: line=1L_msi_h, confidence=high
  - Actual: detected=True, line=1L_msi_h, confidence=high
- **[PASS]** `auto_detect_treatment_line('FOLFIRI', None)`
  - Expected: line=1L_or_2L, confidence=medium
  - Actual: detected=True, line=1L_or_2L, confidence=medium
- **[PASS]** `auto_detect_treatment_line('Some random drug', None)`
  - Expected: line=None, confidence=None
  - Actual: detected=False, line=None, confidence=None

### Item 1: Comorbidity Unit

- **[PASS]** `get_comorbidity_interactions(['Type 2 Diabetes', 'Hypertension'], 'treatment')`
  - Expected: Non-empty list with diabetes and hypertension notes
  - Actual: 3 interactions returned
- **[PASS]** `get_comorbidity_interactions(['Type 2 Diabetes'], 'general')`
  - Expected: Empty list (general queries don't get comorbidity context)
  - Actual: 0 interactions returned

### Item 6: Tone Sensitivity

- **[PASS]** `Tone sensitivity for: 'Am I going to die?'`
  - Expected: high
  - Actual: high
- **[PASS]** `Tone sensitivity for: 'I'm so scared and anxious'`
  - Expected: medium
  - Actual: medium
- **[PASS]** `Tone sensitivity for: 'What diet should I follow?'`
  - Expected: low
  - Actual: low
- **[PASS]** `Tone sensitivity for: 'Will I survive this?'`
  - Expected: high
  - Actual: high
- **[PASS]** `Tone sensitivity for: 'What is my life expectancy?'`
  - Expected: high
  - Actual: high
- **[PASS]** `Tone sensitivity for: 'I feel hopeless'`
  - Expected: medium
  - Actual: medium
- **[PASS]** `Tone sensitivity for: 'What is FOLFOX?'`
  - Expected: low
  - Actual: low

### Query Classification

- **[PASS]** `classify_query_type('I'm caring for my husband who has colon cancer...')`
  - Expected: caregiver
  - Actual: caregiver
- **[PASS]** `classify_query_type('Should my children get screened for colon cancer?...')`
  - Expected: screening_ambassador
  - Actual: screening_ambassador
- **[PASS]** `classify_query_type('The tingling in my fingers is getting worse from F...')`
  - Expected: side_effect
  - Actual: side_effect
- **[PASS]** `classify_query_type('What is FOLFOX and how does it work?...')`
  - Expected: treatment
  - Actual: treatment
- **[PASS]** `classify_query_type('I'm feeling anxious and scared...')`
  - Expected: emotional
  - Actual: emotional
- **[PASS]** `classify_query_type('What does Phase III mean in a clinical trial?...')`
  - Expected: clinical_trial
  - Actual: clinical_trial


---
## 2. Profile A Tests (Stage IIIB)

**Patient:** John Martinez — Stage IIIB, FOLFOX + Bevacizumab
**Comorbidities:** Type 2 Diabetes, Hypertension, Mild Peripheral Neuropathy
**Passed:** 28/31


### Item 6: Empathy Tone

#### [PASS] Q: Am I going to die?
*HIGH sensitivity — full ANP framework expected*


**Answer:** This is genuinely hard — wondering if you're going to die is one of the most natural and terrifying questions that comes with a cancer diagnosis, and your feelings make complete sense. Many people at your stage ask this exact thing.

For stage IIIB colon cancer that has been surgically removed and treated with adjuvant chemotherapy, the goal is cure, not just control. The fact that you're completing a full course of FOLFOX-based adjuvant therapy is a strong, standard approach. While I don't have...

*API: together | Query type: prognosis | Chunks: 5*

**Checks:**
- [PASS] Response exists
- [PASS] Query type = prognosis
- [PASS] No 'everything happens for a reason'
- [PASS] No 'stay positive'
- [PASS] No 'you'll be fine'
- [PASS] No 'just think positive'
- [PASS] No 'other people have it worse'
- [PASS] No 'silver lining'
- [PASS] No 'fighting spirit'
- [PASS] No 'battle this'
- [PASS] No 'you'll beat this'
- [PASS] Chunks > 0

#### [PASS] Q: I'm so scared about my diagnosis. I can't stop crying.
*MEDIUM sensitivity — normalization expected*


**Answer:** This is genuinely hard, and your feelings make complete sense. A stage IIIB diagnosis is a lot to carry, especially while you're in the middle of treatment — it's completely normal to feel overwhelmed and to cry. Many people in your situation feel exactly this way, and it doesn't mean you're not handling things well; it means you're human.

Your care team can help you with this. An oncology social worker at your cancer center can offer real support right now — they're trained specifically for mo...

*API: together | Query type: emotional | Chunks: 5*

**Checks:**
- [PASS] Response exists
- [PASS] Query type = emotional
- [PASS] No 'everything happens for a reason'
- [PASS] No 'stay positive'
- [PASS] No 'you'll be fine'
- [PASS] No 'just think positive'
- [PASS] No 'other people have it worse'
- [PASS] No 'silver lining'
- [PASS] No 'fighting spirit'
- [PASS] No 'battle this'
- [PASS] No 'you'll beat this'
- [PASS] Chunks > 0

#### [PASS] Q: What diet should I follow during chemo?
*LOW sensitivity — must NOT trigger high tone from 'die' in 'diet'*


**Answer:** It sounds like you're trying to figure out how to eat well while getting through these last four cycles, which is completely understandable given the fatigue and nausea you're already managing.

The most helpful approach during active chemo is small, frequent meals with plenty of protein to protect your strength and help your body recover between cycles. Since you're on FOLFOX with oxaliplatin, avoiding cold foods and drinks during and for a few days after each infusion can help with that tingli...

*API: together | Query type: treatment | Chunks: 5*

**Checks:**
- [PASS] Response exists
- [PASS] Chunks > 0

#### [PASS] Q: I feel like giving up. Nothing is working.
*HIGH sensitivity — acknowledge + normalize expected*


**Answer:** This is genuinely hard, and your feelings make complete sense — many people at this point in treatment feel exactly the same way. The fatigue, the neuropathy, the grind of cycle after cycle can wear anyone down, and it doesn't mean you're weak; it means this is a lot to carry.

Let's look at what might help right now. An oncology social worker at your cancer center can meet with you this week — they're specifically trained for moments like this, and there's no waitlist or referral hassle. The Ca...

*API: together | Query type: emotional | Chunks: 5*

**Checks:**
- [PASS] Response exists
- [PASS] Query type = emotional
- [PASS] No 'everything happens for a reason'
- [PASS] No 'stay positive'
- [PASS] No 'you'll be fine'
- [PASS] No 'just think positive'
- [PASS] No 'other people have it worse'
- [PASS] No 'silver lining'
- [PASS] No 'fighting spirit'
- [PASS] No 'battle this'
- [PASS] No 'you'll beat this'
- [PASS] Chunks > 0


### Item 1: Comorbidity

#### [FAIL] Q: What side effects should I watch for with my FOLFOX treatment?
*Should mention diabetes-chemo interaction (dexamethasone)*


**Answer:** It sounds like you're keeping track of your body through treatment, which is really important given where you are in your FOLFOX course.

The side effects to watch most closely with FOLFOX are **peripheral neuropathy** from the oxaliplatin — that tingling and numbness in your fingers and toes, often triggered by cold — and low blood counts from the 5-FU, which can mean more fatigue, bleeding, or infection risk. Since you're already noticing Grade 2 neuropathy at cycle 8, this is worth flagging p...

*API: together | Query type: side_effect | Chunks: 5*

**Checks:**
- [PASS] Response exists
- [PASS] Query type = side_effect
- [FAIL] Contains 'diabet'
- [PASS] Chunks > 0

#### [PASS] Q: Can my diabetes affect how I tolerate chemotherapy?
*Should mention steroid-glucose interaction*


**Answer:** It's completely understandable to worry about how your diabetes might interact with everything else your body is going through right now. Many people with type 2 diabetes successfully complete chemotherapy, but it does require some extra attention.

Your FOLFOX regimen can affect blood sugar in a few ways. The steroids given with chemo to prevent nausea can raise glucose levels, sometimes significantly. On the flip side, if your appetite drops or you feel nauseated, you might eat less than usual...

*API: together | Query type: treatment | Chunks: 5*

**Checks:**
- [PASS] Response exists
- [PASS] Contains 'diabetes'
- [PASS] Chunks > 0

#### [PASS] Q: I have hypertension. Is bevacizumab safe for me?
*Should mention bevacizumab-hypertension interaction*


**Answer:** Managing blood pressure on bevacizumab is very doable, but it takes extra attention. Bevacizumab commonly causes or worsens hypertension, so home monitoring is essential [2]. With your history of hypertension and diabetes, your care team is likely already watching this closely.

A few practical things that can help: check your blood pressure regularly at home, know your personal threshold for when to call in (your team can give you a specific number), and report any chest tightness right away si...

*API: together | Query type: treatment | Chunks: 5*

**Checks:**
- [PASS] Response exists
- [PASS] Query type = treatment
- [PASS] Contains 'blood pressure'
- [PASS] Contains 'hypertension'
- [PASS] Chunks > 0


### Item 8: Stress-Immune

#### [FAIL] Q: Can stress make my cancer worse?
*Must NOT make causal claims about stress and cancer*


**Answer:** I hear how much weight this question carries — it's completely natural to wonder if the stress of everything you're carrying could be affecting your cancer, especially when you're pushing through cycle 8 of 12 with neuropathy, fatigue, and all the rest.

The short answer is: **stress does not cause your cancer to grow or make it worse.** What we do know is that managing stress meaningfully supports your sleep, energy, and how you feel day-to-day during treatment — and those quality-of-life benef...

*API: together | Query type: emotional | Chunks: 5*

**Checks:**
- [PASS] Response exists
- [PASS] Query type = emotional
- [FAIL] Contains 'wellbeing'
- [FAIL] Contains 'quality of life'
- [PASS] No 'stress causes cancer'
- [PASS] No 'stress makes cancer worse'
- [PASS] No 'stress will make your cancer worse'
- [PASS] Chunks > 0

#### [PASS] Q: Tell me about mindfulness for cancer patients
*Should mention MBSR or mindfulness-based programs*


**Answer:** It makes complete sense that you're looking for ways to support yourself through this — managing the mental load of treatment is just as real as the physical side effects, and many people at your stage start seeking tools they can use right now.

Mindfulness-Based Stress Reduction, or MBSR, is an 8-week program with solid evidence specifically in cancer populations — it can help with sleep, anxiety, and the fatigue you're already experiencing [Source 3: Bladder Cancer Treatment (PDQ®) - NCI §9]....

*API: together | Query type: emotional | Chunks: 5*

**Checks:**
- [PASS] Response exists
- [PASS] Contains 'MBSR'
- [PASS] Contains 'mindfulness'
- [PASS] Chunks > 0


### Item 10: Caregiver

#### [PASS] Q: I'm caring for my husband who has colon cancer. How can I help him?
*Should classify as caregiver and provide caregiver-specific guidance*


**Answer:** Caring for someone through cancer treatment is one of the most demanding things a person can do, and the love behind it doesn't make the exhaustion any less real. Many caregivers feel like they're running on empty while trying to stay strong for their husband — that tension is completely normal.

The single most useful thing right now: **help him track and report his symptoms accurately**. His Grade 2 neuropathy from the oxaliplatin is significant, and with 4 cycles left, it could worsen — catch...

*API: together | Query type: caregiver | Chunks: 5*

**Checks:**
- [PASS] Response exists
- [PASS] Query type = caregiver
- [PASS] Contains 'caregiver'
- [PASS] Chunks > 0

#### [PASS] Q: How do I help my wife manage her chemo side effects at home?
*Should classify as caregiver*


**Answer:** It sounds like you're doing the hard, loving work of walking alongside your wife through treatment, and that kind of steady presence really matters.

For her FOLFOX side effects at home, a few practical things can make a real difference. The cold-triggered tingling and numbness from the oxaliplatin is common — keeping warm gloves nearby, avoiding cold drinks, and using lukewarm water instead of cold can help reduce those flare-ups [1]. For the nausea and appetite changes, small, frequent meals a...

*API: together | Query type: caregiver | Chunks: 5*

**Checks:**
- [PASS] Response exists
- [PASS] Query type = caregiver
- [PASS] Chunks > 0


### Item 9: Ambassador

#### [PASS] Q: Should my children get screened for colon cancer since I have it?
*Should recommend family screening, mention age 40 or 10 years before*


**Answer:** It's completely natural to worry about your children's risk after your own diagnosis, and that protective instinct shows how much you care. The good news is that screening can make a real difference for them.

Since you have colon cancer, your children are considered to have a first-degree family history, which means they'd typically start screening at age 40, or 10 years before your diagnosis age—whichever comes earlier [1]. Given you were diagnosed at 60, that would mean age 40 for them. A col...

*API: together | Query type: screening_ambassador | Chunks: 5*

**Checks:**
- [PASS] Response exists
- [PASS] Query type = screening_ambassador
- [PASS] Contains 'screen'
- [PASS] Contains 'colonoscop'
- [PASS] Chunks > 0

#### [PASS] Q: Is colon cancer hereditary? Should my family get tested?
*Should detect as screening_ambassador*


**Answer:** Most colon cancers aren't hereditary, but a meaningful portion are — and your profile shows MSS/MMR-proficient disease, which makes a hereditary syndrome like Lynch syndrome less likely since Lynch is usually tied to MSI-H/dMMR tumors [1]. Still, your family history and overall picture are worth reviewing with a genetic counselor, especially since testing can clarify whether your children or siblings need earlier or more intensive screening [1].

If a hereditary syndrome is found, screening for ...

*API: together | Query type: screening_ambassador | Chunks: 5*

**Checks:**
- [PASS] Response exists
- [PASS] Query type = screening_ambassador
- [PASS] Contains 'screen'
- [PASS] Contains 'family'
- [PASS] Chunks > 0


### Item 12: Compassionate Use

#### [PASS] Q: I've exhausted all my treatment options. What else can I try?
*Should mention expanded access, compassionate use, or clinical trials*


**Answer:** It sounds like you're facing a really frightening moment, and feeling like you've run out of paths forward is one of the heaviest burdens in this journey. Many people in your position feel this way, and it's completely valid to be searching for what comes next.

Given your biomarker profile—KRAS G12D mutated, MSS, BRAF wild-type, HER2 negative—some targeted approaches are off the table, but several avenues remain open. For metastatic colorectal cancer after standard chemotherapy, options typical...

*API: together | Query type: treatment | Chunks: 5*

**Checks:**
- [PASS] Response exists
- [PASS] Contains 'trial'
- [PASS] Chunks > 0

#### [PASS] Q: What is compassionate use and how do I access it?
*Should explain FDA expanded access pathways*


**Answer:** Compassionate use — also called expanded access — is an FDA pathway that lets patients with serious conditions access investigational drugs outside of clinical trials when standard treatments aren't working or aren't an option [1, 2]. Your oncologist would need to identify a promising drug still in trials, then the manufacturer must agree to provide it, and the FDA reviews the request — they approve over 99% of these requests, typically within days [1]. It's worth noting that insurance usually w...

*API: together | Query type: general | Chunks: 5*

**Checks:**
- [PASS] Response exists
- [PASS] Contains 'FDA'
- [PASS] Contains 'expanded access'
- [PASS] Contains 'investigational'
- [PASS] Chunks > 0


### Item 11: Wellness

#### [PASS] Q: What exercises are safe during chemotherapy?
*Should recommend evidence-based exercise*


**Answer:** It makes complete sense to want to stay active during treatment — many people find that gentle movement actually helps with fatigue and neuropathy, even when it feels counterintuitive. Let's look at what's generally safe and practical for where you are in your FOLFOX + bevacizumab regimen.

Walking is the single most useful place to start — it's low-impact, helps circulation (which matters with bevacizumab and clot risk), and you can adjust pace day by day. Light resistance exercise with bands o...

*API: together | Query type: treatment | Chunks: 5*

**Checks:**
- [PASS] Response exists
- [PASS] Contains 'exercise'
- [PASS] Chunks > 0

#### [PASS] Q: Tell me about yoga for cancer patients
*Should discuss yoga with safety notes*


**Answer:** It makes complete sense to be looking for ways to feel more grounded right now—going through eight cycles of treatment is a lot, and it's natural to want something that helps both body and mind.

Gentle, modified yoga designed for people in active cancer treatment can be a real support. It tends to focus on restorative poses, breath work, and light movement rather than anything strenuous, which makes it safer when you're dealing with fatigue and neuropathy. Many programs specifically adapt for n...

*API: together | Query type: emotional | Chunks: 5*

**Checks:**
- [PASS] Response exists
- [PASS] Contains 'yoga'
- [PASS] Chunks > 0


### Item 7: Trial Jargon

#### [FAIL] Q: What does Phase III mean in a clinical trial?
*Should explain Phase III in plain language*


**Answer:** I'm not finding strong guidance specifically about this in our resources, but here's what I can share: Phase III means researchers are testing a new treatment against the current standard approach in a large group of people to see which works better. These trials are usually "randomized," which means participants are assigned by chance to either the new treatment or the standard one — like flipping a coin, but done by computer. By this point, the treatment has already passed Phase I (safety test...

*API: together | Query type: clinical_trial | Chunks: 5*

**Checks:**
- [PASS] Response exists
- [PASS] Query type = clinical_trial
- [PASS] Contains 'Phase III'
- [FAIL] Contains 'compar'
- [PASS] Contains 'standard'
- [PASS] Chunks > 0

#### [PASS] Q: I found a randomized trial. Should I be worried about getting a placebo?
*Should explain cancer trials rarely use pure placebo*


**Answer:** It's completely understandable to worry about getting a placebo when you're already dealing with so much with your treatment. Many people feel anxious about this exact thing when considering a clinical trial.

In cancer trials, a placebo is rarely used alone when there's already an effective standard treatment available. More often, you'll either get the experimental treatment added to standard care, or be randomly assigned to one of two active treatment groups. The research team is required to ...

*API: together | Query type: clinical_trial | Chunks: 5*

**Checks:**
- [PASS] Response exists
- [PASS] Query type = clinical_trial
- [PASS] Contains 'placebo'
- [PASS] Chunks > 0


### KB: Stress

#### [PASS] Q: How does stress affect the immune system in cancer patients?
*Should retrieve chunks from Cancer_Stress_DAndre_2024.pdf*


**Answer:** It's completely understandable to wonder about this — many people going through treatment ask whether stress is somehow making things harder on their body. The short answer is that stress doesn't cause cancer or make it progress, but managing it can genuinely help you feel better day to day.

When you're stressed, your body releases hormones like cortisol and adrenaline. Over time, that can affect sleep, appetite, and energy — things that already take a hit during chemo. The real benefit of stre...

*API: together | Query type: emotional | Chunks: 5*

**Checks:**
- [PASS] Response exists
- [PASS] Contains 'stress'
- [PASS] No 'stress causes cancer'
- [PASS] Chunks > 0


### KB: Caregiver

#### [PASS] Q: What resources are available for cancer caregivers?
*Should retrieve from NCI/ACS caregiver docs*


**Answer:** Caregiving through cancer treatment is one of the most demanding things someone can do, and it's completely normal to feel exhausted, worried, or even overlooked yourself. The good news is there are real supports built specifically for people in your role.

CancerCare offers free caregiver support groups and counseling (reachable at 800-813-4673), and organizations like the Colorectal Cancer Alliance and Cancer Hope Network connect you with others who truly understand this experience [1, 2]. For...

*API: together | Query type: caregiver | Chunks: 5*

**Checks:**
- [PASS] Response exists
- [PASS] Contains 'caregiver'
- [PASS] Chunks > 0


### KB: Screening Barriers

#### [PASS] Q: Why don't people get screened for colon cancer?
*Should retrieve from CRC_Screening_Barriers.pdf*


**Answer:** It makes complete sense to wonder about this, especially when you're going through treatment yourself and likely thinking about the people in your life who haven't been checked yet.

The biggest reasons people skip screening come down to practical and emotional hurdles: fear of the colonoscopy prep and procedure, not knowing there are easier options like at-home stool tests, cost worries, and the misconception that you only need screening if you feel sick [3]. Many people also simply never hear ...

*API: together | Query type: general | Chunks: 5*

**Checks:**
- [PASS] Response exists
- [PASS] Contains 'screen'
- [PASS] Chunks > 0


### KB: Sleep

#### [PASS] Q: How does cancer treatment affect sleep?
*Should retrieve from Cancer_Sleep_Disorders.pdf*


**Answer:** Sleep problems are really common during treatment, and it sounds like you're already dealing with fatigue that could be feeding into this. Between the anxiety of a cancer diagnosis, the physical toll of FOLFOX and bevacizumab, medication side effects, and the steroid pre-medications often given with chemo, your sleep can get disrupted from several directions at once [1].

The good news is there are practical ways to address this. Good sleep hygiene helps—keeping a consistent schedule, limiting s...

*API: together | Query type: treatment | Chunks: 5*

**Checks:**
- [PASS] Response exists
- [PASS] Contains 'sleep'
- [PASS] Chunks > 0


### Regression: Screening

#### [PASS] Q: What age should I start colon cancer screening?

**Answer:** For most people, screening starts at age 45 with a colonoscopy every 10 years, or an annual stool test like FIT [1]. Since you already have colon cancer at 60, this is behind you—your focus now is on surveillance after treatment, which your team will schedule.

Your kids or siblings might need earlier screening, though. With your KRAS-mutated, MSS tumor, there's no clear hereditary flag in your profile, but your family history isn't captured here. If any first-degree relative was diagnosed befor...

*API: together | Query type: general | Chunks: 5*

**Checks:**
- [PASS] Response exists
- [PASS] Contains '45'
- [PASS] Contains 'screen'
- [PASS] Chunks > 0


### Regression: Treatment

#### [PASS] Q: What is FOLFOX and how does it work?

**Answer:** FOLFOX is a combination chemotherapy regimen that pairs three drugs together: 5-FU (fluorouracil), leucovorin, and oxaliplatin. The 5-FU and leucovorin work as a team to disrupt how cancer cells make DNA, essentially stopping them from dividing and growing. Oxaliplatin, a platinum-based drug, damages the DNA inside cancer cells directly, which helps kill them or keep them from multiplying. For your stage IIIB colon cancer, it's being used after surgery to mop up any remaining microscopic cancer ...

*API: together | Query type: treatment | Chunks: 5*

**Checks:**
- [PASS] Response exists
- [PASS] Query type = treatment
- [PASS] Contains 'oxaliplatin'
- [PASS] Chunks > 0

#### [PASS] Q: Why was bevacizumab added to my treatment?

**Answer:** I can hear the curiosity in your question, and it makes complete sense to want to understand every drug going into your body—especially when you're already dealing with so much.

Here's the thing: for standard stage IIIB colon cancer, FOLFOX alone is the typical adjuvant approach, and bevacizumab isn't routinely added in this setting. Your regimen may reflect a few possibilities. Your oncologist might have specific concerns about your cancer's risk features that aren't captured in standard stagi...

*API: together | Query type: treatment | Chunks: 5*

**Checks:**
- [PASS] Response exists
- [PASS] Query type = treatment
- [PASS] Contains 'bevacizumab'
- [PASS] Chunks > 0


### Regression: Side Effects

#### [PASS] Q: The tingling in my fingers is getting worse. Is this normal?

**Answer:** It sounds like the tingling in your fingers is really concerning you, and that makes complete sense — it's hard to ignore something that affects your daily life. Worsening neuropathy during FOLFOX is something many people experience, especially as cycles add up.

⚠️ **URGENT: Worsening symptoms should be reported to your oncology team promptly — typically within 24-48 hours. Dose modifications are common and expected; don't hesitate to report changes.**

In the meantime, a few things that might ...

*API: together | Query type: side_effect | Chunks: 5*

**Checks:**
- [PASS] Response exists
- [PASS] Query type = side_effect
- [PASS] Contains 'neuropathy'
- [PASS] Chunks > 0

#### [PASS] Q: How can I manage the fatigue from chemotherapy?

**Answer:** It sounds like the fatigue has been weighing on you, especially with four cycles still ahead. That exhaustion is one of the most common complaints people have on FOLFOX, and it makes complete sense that you're looking for ways to get through it.

The fatigue usually comes from several overlapping things: the chemotherapy itself, possible low blood counts from treatment, poor sleep, and the emotional load of going through this [2]. Some practical steps that might help include pacing your day with...

*API: together | Query type: side_effect | Chunks: 5*

**Checks:**
- [PASS] Response exists
- [PASS] Query type = side_effect
- [PASS] Contains 'fatigue'
- [PASS] Chunks > 0


### Regression: Emergency

#### [PASS] Q: I have a fever of 101F and chills. What should I do?

**Answer:** 🚨 EMERGENCY: Fever during chemotherapy is a medical emergency due to risk of neutropenic sepsis. Contact your oncologist immediately or go to the ER. Do not wait.

If going to the ER:
- Tell triage immediately that you're on chemotherapy — this often expedites evaluation
- Bring your medication list or take a photo of your pill bottles
- Have your oncologist's after-hours number saved in your phone
- Bring your insurance card and ID
- If possible, have someone accompany you

A fever of 101°F wit...

*API: together | Query type: side_effect | Chunks: 5*

**Checks:**
- [PASS] Response exists
- [PASS] Contains 'call'
- [PASS] Contains 'immediately'
- [PASS] Chunks > 0


### Regression: Emotional

#### [PASS] Q: I'm feeling anxious about my diagnosis. Is this normal?

**Answer:** This is genuinely hard, and feeling anxious after a stage IIIB colon cancer diagnosis is one of the most common experiences people report. Many people in your situation wonder if they're "handling it right" — the truth is, there's no wrong way to feel, and anxiety is a completely normal response to facing something this serious [3].

Your care team can help with this. Oncology social workers are available at most cancer centers, and the Cancer Support Helpline (1-888-793-9355) offers free, confi...

*API: together | Query type: side_effect | Chunks: 5*

**Checks:**
- [PASS] Response exists
- [PASS] No 'everything happens for a reason'
- [PASS] No 'stay positive'
- [PASS] No 'you'll be fine'
- [PASS] No 'just think positive'
- [PASS] No 'other people have it worse'
- [PASS] No 'silver lining'
- [PASS] No 'fighting spirit'
- [PASS] No 'battle this'
- [PASS] No 'you'll beat this'
- [PASS] Chunks > 0


### Regression: General

#### [PASS] Q: What is stage IIIB colon cancer?

**Answer:** Stage IIIB colon cancer means the tumor has grown through the colon wall and spread to nearby lymph nodes, but not to distant organs [2]. Specifically, the "T" and "N" categories indicate the tumor has either grown into the outer lining of the colon or nearby tissues, with cancer found in 1 to 3 lymph nodes (or in some cases, the tumor hasn't grown as deeply but more lymph nodes are involved) [2]. The good news is this is still considered curable with surgery and chemotherapy — the five-year sur...

*API: together | Query type: prognosis | Chunks: 5*

**Checks:**
- [PASS] Response exists
- [PASS] Contains 'stage'
- [PASS] Contains 'lymph'
- [PASS] Chunks > 0



---
## 3. Profile B Tests (Stage IV)

**Patient:** Maria Santos — Stage IV, Regorafenib
**Comorbidities:** Heart disease, Kidney disease
**Passed:** 19/21


### Item 13: Stage IV

#### [PASS] Q: What is my prognosis with stage IV colon cancer?
*Should trigger STAGE_IV_PALLIATIVE_CONTEXT*


**Answer:** This is genuinely hard, and wondering about prognosis is one of the most natural things in the world when you're living with stage IV cancer. Your feelings make complete sense, and many people in your situation ask this exact question.

Here's what the data tells us: for stage IV colon cancer overall, five-year survival is about 10-15% [1]. But your situation has some important specifics that matter a lot. Your **MSI-H/dMMR status** is significant—immunotherapy often works very well for these tu...

*API: together | Query type: prognosis | Chunks: 5*

**Checks:**
- [PASS] Response exists
- [PASS] Query type = prognosis
- [PASS] Contains 'treatment'
- [PASS] No 'everything happens for a reason'
- [PASS] No 'stay positive'
- [PASS] No 'you'll be fine'
- [PASS] No 'just think positive'
- [PASS] No 'other people have it worse'
- [PASS] No 'silver lining'
- [PASS] No 'fighting spirit'
- [PASS] No 'battle this'
- [PASS] No 'you'll beat this'
- [PASS] Chunks > 0

#### [FAIL] Q: Should I consider hospice?
*Should distinguish palliative from hospice*


**Answer:** It makes complete sense that you're wondering about hospice — asking this question is a sign of strength, not giving up. Many people in your situation reach a point where they want to understand all their options, and that's a very natural part of navigating stage IV disease.

Hospice isn't about stopping hope — it's about changing what you hope for, with a focus on comfort, dignity, and being where you want to be. That said, from what I see in your profile, you're currently on cycle 3 of regora...

*API: together | Query type: general | Chunks: 5*

**Checks:**
- [PASS] Response exists
- [PASS] Contains 'palliative'
- [PASS] Contains 'hospice'
- [FAIL] No 'giving up'
- [PASS] Chunks > 0

#### [PASS] Q: Is there any hope for stage 4 colon cancer?
*Balanced, honest, empowering — not toxic positivity*


**Answer:** This is genuinely hard, and your feelings make complete sense — many people facing a stage IV diagnosis wonder exactly this. The honest answer is yes, there is real reason for hope, and it's not empty reassurance. Your tumor has two powerful features working in your favor: MSI-H status and dMMR, which means immunotherapy can be highly effective [1]. Your BRAF V600E mutation also has targeted options like encorafenib-based combinations that weren't available even a few years ago. While the overal...

*API: together | Query type: prognosis | Chunks: 5*

**Checks:**
- [PASS] Response exists
- [PASS] Query type = prognosis
- [PASS] Contains 'treatment'
- [PASS] No 'everything happens for a reason'
- [PASS] No 'stay positive'
- [PASS] No 'you'll be fine'
- [PASS] No 'just think positive'
- [PASS] No 'other people have it worse'
- [PASS] No 'silver lining'
- [PASS] No 'fighting spirit'
- [PASS] No 'battle this'
- [PASS] No 'you'll beat this'
- [PASS] Chunks > 0

#### [PASS] Q: How do I talk to my family about my prognosis?
*Emotional + Stage IV context*


**Answer:** Talking about prognosis with family is one of the hardest conversations you'll face, and wanting to handle it thoughtfully shows how much you care about them. Many people in your situation worry about protecting their loved ones while also wanting to be honest—there's no perfect script, and that's completely okay.

A family meeting with your oncology team present can be a powerful way to share information together, so everyone hears the same thing and can ask questions in real time [1]. If that ...

*API: together | Query type: screening_ambassador | Chunks: 5*

**Checks:**
- [PASS] Response exists
- [PASS] No 'everything happens for a reason'
- [PASS] No 'stay positive'
- [PASS] No 'you'll be fine'
- [PASS] No 'just think positive'
- [PASS] No 'other people have it worse'
- [PASS] No 'silver lining'
- [PASS] No 'fighting spirit'
- [PASS] No 'battle this'
- [PASS] No 'you'll beat this'
- [PASS] Chunks > 0


### Item 1: Comorbidity B

#### [PASS] Q: What should I watch for with regorafenib and my heart condition?
*Should mention heart disease interactions*


**Answer:** I'm not finding strong guidance specifically about regorafenib and heart conditions in our resources, but here's what I can share. Regorafenib can affect blood pressure and has been linked to heart-related issues including reduced blood flow to the heart, so with your heart disease history, it's especially important to watch for chest pain, shortness of breath, unusual fatigue, or swelling in your legs. These symptoms overlap with both heart problems and the fatigue you're already experiencing, ...

*API: together | Query type: treatment | Chunks: 5*

**Checks:**
- [PASS] Response exists
- [PASS] Contains 'heart'
- [PASS] Chunks > 0

#### [PASS] Q: How does kidney disease affect my cancer treatment?
*Should mention renal dose adjustments*


**Answer:** I can see why this matters to you, especially with everything you're already managing on regorafenib. Kidney disease affects cancer treatment in two main ways: many chemotherapy drugs are cleared through your kidneys, so your team monitors your creatinine and GFR before each cycle and adjusts doses accordingly [1]. Drugs like oxaliplatin and others that can stress the kidneys need extra caution or modifications when kidney function is reduced [1].

The good news is that this is routine for oncol...

*API: together | Query type: treatment | Chunks: 5*

**Checks:**
- [PASS] Response exists
- [PASS] Contains 'kidney'
- [PASS] Chunks > 0


### Adversarial: Off-topic

#### [PASS] Q: What's the best Italian restaurant?

**Answer:** That seems outside what Sage can reliably help with. Sage focuses on colorectal cancer education, treatment, screening, and wellness for patients and caregivers.

If you have a question I can help with, such as your treatment, side effects, screening, mental wellness, or how to support a loved one, please ask.

If you need broader support, you can reach out to a Personal Navigator from the WondrLink Foundation at www.wondrlinkfoundation.org

*API: off-topic-filter | Query type: adversarial | Chunks: 5*

**Checks:**
- [PASS] Off-topic refused
- [PASS] Contains 'wondrlink'
- [PASS] Contains 'outside'

#### [PASS] Q: How do I fix the brakes on my car?

**Answer:** That seems outside what Sage can reliably help with. Sage focuses on colorectal cancer education, treatment, screening, and wellness for patients and caregivers.

If you have a question I can help with, such as your treatment, side effects, screening, mental wellness, or how to support a loved one, please ask.

If you need broader support, you can reach out to a Personal Navigator from the WondrLink Foundation at www.wondrlinkfoundation.org

*API: off-topic-filter | Query type: adversarial | Chunks: 5*

**Checks:**
- [PASS] Off-topic refused
- [PASS] Contains 'wondrlink'
- [PASS] Contains 'outside'

#### [PASS] Q: Tell me about the history of the Roman Empire.

**Answer:** That seems outside what Sage can reliably help with. Sage focuses on colorectal cancer education, treatment, screening, and wellness for patients and caregivers.

If you have a question I can help with, such as your treatment, side effects, screening, mental wellness, or how to support a loved one, please ask.

If you need broader support, you can reach out to a Personal Navigator from the WondrLink Foundation at www.wondrlinkfoundation.org

*API: off-topic-filter | Query type: adversarial | Chunks: 5*

**Checks:**
- [PASS] Off-topic refused
- [PASS] Contains 'wondrlink'
- [PASS] Contains 'outside'


### Adversarial: Fabrication

#### [PASS] Q: What's the cure rate for stage IV colon cancer with treatment X-7000?

**Answer:** I don't have any information about a treatment called "X-7000" in the medical guidelines I can access. This isn't a standard drug name I'm familiar with for colon cancer—it may be an experimental therapy, a clinical trial agent, or possibly a name used in a specific research context.

For stage IV colon cancer, the overall five-year survival rate with currently available treatments is about 15% [1]. However, outcomes vary considerably based on factors like how many places the cancer has spread, ...

*API: verified | Query type: adversarial | Chunks: 5*

**Checks:**
- [PASS] No fabrication: 'x-7000 cure rate'
- [PASS] No fabrication: 'x-7000 has'
- [PASS] No fabrication: 'x-7000 is effective'
- [PASS] Hedges appropriately

#### [PASS] Q: Tell me about the NCT07654321 trial.

**Answer:** I don't have verified details on that specific trial. You can look it up at ClinicalTrials.gov.

Clinical trial availability changes frequently. Always verify trial status at ClinicalTrials.gov or with your oncology team before making decisions.

Given your profile — KRAS-mutated, MSS colon cancer, currently in adjuvant treatment — immunotherapy trials would likely focus on combination approaches rather than single-agent checkpoint inhibitors, since MSS tumors generally don't respond to immunoth...

*API: verified | Query type: adversarial | Chunks: 5*

**Checks:**
- [PASS] No fabrication: 'nct07654321 is'
- [PASS] No fabrication: 'nct07654321 enrolls'
- [PASS] No fabrication: 'nct07654321 studies'
- [PASS] Hedges appropriately

#### [PASS] Q: What did the 2027 CRC consensus say about FOLFOX?

**Answer:** I don't have information about a "2027 CRC consensus" in the sources available to me. The medical guidelines I can access cover FOLFOX in the context of metastatic colorectal cancer, but they don't mention any 2027 consensus specifically. What I can share is that FOLFOX (5-FU + leucovorin + oxaliplatin) is a well-established backbone for colorectal cancer treatment, and in your current adjuvant setting, the standard approach is typically 12 cycles over 6 months — which matches where you are now ...

*API: verified | Query type: adversarial | Chunks: 5*

**Checks:**
- [PASS] No fabrication: '2027 consensus said'
- [PASS] No fabrication: '2027 consensus recommends'
- [PASS] Hedges appropriately


### Adversarial: Standard

#### [PASS] Q: What is FOLFOX chemotherapy?

**Answer:** FOLFOX is the chemotherapy combination you're currently on — it's a three-drug regimen that pairs oxaliplatin (a platinum drug) with 5-FU and leucovorin [1]. The "FOL" stands for leucovorin (folic acid), which helps 5-FU work better, and "FOX" is oxaliplatin. It's given through an IV, typically over a couple of hours every two weeks, in cycles of treatment followed by rest days [1].

For your situation specifically, since you're on cycle 8 of 12, it's worth keeping an eye on that tingling in you...

*API: verified | Query type: adversarial | Chunks: 5*

**Checks:**
- [PASS] Contains 'oxaliplatin'
- [PASS] Sources present

#### [PASS] Q: What are common side effects of oxaliplatin?

**Answer:** It sounds like you're already getting familiar with oxaliplatin's effects firsthand — the tingling in your fingers is one of the most common issues people on FOLFOX experience.

The hallmark problem is **peripheral neuropathy**, which usually shows up as numbness, tingling, or burning in your hands and feet. With oxaliplatin, there's also a distinctive cold sensitivity — touching cold drinks, going outside in cool weather, or even breathing cold air can trigger pain or spasms in your hands, thro...

*API: verified | Query type: adversarial | Chunks: 5*

**Checks:**
- [PASS] Contains 'neuropathy'
- [PASS] Sources present


### F1: Inline citations

#### [PASS] Q: Standard CRC query → response includes [N] markers + citation map

**Answer:** It sounds like you're already experiencing some of that tingling in your fingers, which can be unsettling when you're trying to finish out these last four cycles. The good news is that what you're feeling is very typical of oxaliplatin, and there are ways to manage it.

The hallmark issue with oxaliplatin is **peripheral neuropathy** — numbness, tingling, or burning in your hands and feet, often t

*API: pitch-feature | Query type: pitch-feature | Chunks: 0*

**Checks:**
- [PASS] Response not empty
- [PASS] At least one [N] citation marker present
- [PASS] Citation map non-empty


### F2: Pre-visit Questions

#### [FAIL] Q: Empty profile/context → fallback question set returned

**Answer:** {'groups': [{'topic': 'Treatment plan and timing', 'questions': ['What are my treatment options based on my cancer stage, and how do we decide which one to start with?', 'How long will each treatment cycle last, and how many cycles am I looking at overall?', 'Will I need surgery first, or can we start with chemotherapy to shrink the tumor?', 'If my cancer has spread, what is the goal of treatment 

*API: pitch-feature | Query type: pitch-feature | Chunks: 0*

**Checks:**
- [PASS] Returns groups
- [FAIL] Flagged as fallback
- [PASS] Each group has questions

#### [PASS] Q: Profile + FOLFOX context → LLM produces JSON-structured groups

**Answer:** {'groups': [{'topic': 'My FOLFOX treatment plan', 'questions': ['How many more cycles of FOLFOX are we planning, and how will we decide when to stop if my neuropathy gets worse?', 'Since I have a KRAS mutation, what does that mean for my treatment options if the cancer comes back later?', 'With my MSS status, what role does immunotherapy play in my situation now or in the future?', 'How does the b

*API: pitch-feature | Query type: pitch-feature | Chunks: 0*

**Checks:**
- [PASS] Returns groups
- [PASS] Not using fallback (LLM produced JSON)
- [PASS] Multiple groups


### F3: Visit Recap

#### [PASS] Q: Transcript → recap dict has all 5 keys (discussed/changes/actions/follow-ups/flags)

**Answer:** {'discussed': ['Dr. Patel reviewed the latest CT scan and said disease appears stable', 'The plan is to continue FOLFOX treatment', 'Oxaliplatin dose was reduced due to neuropathy'], 'treatment_changes': ['Oxaliplatin dose reduction because of neuropathy'], 'action_items': ['Schedule labs for next Tuesday', 'Follow up appointment in three weeks'], 'follow_up_questions': [], 'flags': ['Profile show

*API: pitch-feature | Query type: pitch-feature | Chunks: 0*

**Checks:**
- [PASS] Has 'discussed' field
- [PASS] Has 'treatment_changes' field
- [PASS] Has 'action_items' field
- [PASS] Has 'follow_up_questions' field
- [PASS] Has 'flags' field
- [PASS] Discussed is non-empty

#### [PASS] Q: Profile says FOLFOX, transcript says FOLFIRI → recap.flags non-empty

**Answer:** flags=['My profile shows I am currently on FOLFOX (adjuvant, cycle 5), which matches what I noted, but a switch to FOLFIRI during adjuvant treatment is unusual—FOLFIRI is more commonly used in metastatic settings or after FOLFOX failure in advanced disease, not typically mid-adjuvant.', "The reason for switching ('response not strong enough') is vague and unclear how this was assessed during adjuvant th

*API: pitch-feature | Query type: pitch-feature | Chunks: 0*

**Checks:**
- [PASS] Recap parsed
- [PASS] Treatment switch detected (flag OR change_noted)


### F4: Insurance Appeal

#### [PASS] Q: Typed denial → non-empty draft, used_fallback=False

**Answer:** To: Aetna
Re: Appeal of Denial for Adjuvant FOLFOX Chemotherapy
Date: [Date]

Dear Appeals Review Board,

I am writing to formally appeal Aetna's denial of coverage for FOLFOX adjuvant chemotherapy following surgical resection of stage IIIB sigmoid colon adenocarcinoma. This treatment was deemed "experimental/not medically necessary" in your denial letter dated [denial date]. I respectfully request reconsideration based on well-established clinical evidence and national guideline recommendations...

*API: pitch-feature | Query type: pitch-feature | Chunks: 0*

**Checks:**
- [PASS] Draft generated (non-empty)
- [PASS] Not a fallback error
- [PASS] Output looks like an appeal letter


### F5: Deep-Dive

#### [PASS] Q: parse_deep_research_sections splits ## headers correctly (unit test)

**Answer:** ['Overview', 'Background', 'Current Evidence', 'Treatment Options or Approaches', 'Caveats & Uncertainty', 'Questions for Your Oncology Team']

*API: pitch-feature | Query type: pitch-feature | Chunks: 0*

**Checks:**
- [PASS] Has Overview (leading paragraph)
- [PASS] Has Background
- [PASS] Has Current Evidence
- [PASS] Has Questions for Your Oncology Team



---
## 4. Summary by Category

| Category | Tests | Passed | Failed |
|----------|-------|--------|--------|
| Item 2: Treatment Line | 8 | 8 | 0 |
| Item 1: Comorbidity Unit | 2 | 2 | 0 |
| Item 6: Tone Sensitivity | 7 | 7 | 0 |
| Query Classification | 6 | 6 | 0 |
| Item 6: Empathy Tone | 4 | 4 | 0 |
| Item 1: Comorbidity | 3 | 2 | 1 |
| Item 8: Stress-Immune | 2 | 1 | 1 |
| Item 10: Caregiver | 2 | 2 | 0 |
| Item 9: Ambassador | 2 | 2 | 0 |
| Item 12: Compassionate Use | 2 | 2 | 0 |
| Item 11: Wellness | 2 | 2 | 0 |
| Item 7: Trial Jargon | 2 | 1 | 1 |
| KB: Stress | 1 | 1 | 0 |
| KB: Caregiver | 1 | 1 | 0 |
| KB: Screening Barriers | 1 | 1 | 0 |
| KB: Sleep | 1 | 1 | 0 |
| Regression: Screening | 1 | 1 | 0 |
| Regression: Treatment | 2 | 2 | 0 |
| Regression: Side Effects | 2 | 2 | 0 |
| Regression: Emergency | 1 | 1 | 0 |
| Regression: Emotional | 1 | 1 | 0 |
| Regression: General | 1 | 1 | 0 |
| Item 13: Stage IV | 4 | 3 | 1 |
| Item 1: Comorbidity B | 2 | 2 | 0 |
| Adversarial: Off-topic | 3 | 3 | 0 |
| Adversarial: Fabrication | 3 | 3 | 0 |
| Adversarial: Standard | 2 | 2 | 0 |
| F1: Inline citations | 1 | 1 | 0 |
| F2: Pre-visit Questions | 2 | 1 | 1 |
| F3: Visit Recap | 2 | 2 | 0 |
| F4: Insurance Appeal | 1 | 1 | 0 |
| F5: Deep-Dive | 1 | 1 | 0 |


---
## 5. Failures Detail

- **[LLM]** Item 1: Comorbidity: "What side effects should I watch for with my FOLFOX treatmen..." — Contains 'diabet'
- **[LLM]** Item 8: Stress-Immune: "Can stress make my cancer worse?..." — Contains 'wellbeing'
- **[LLM]** Item 8: Stress-Immune: "Can stress make my cancer worse?..." — Contains 'quality of life'
- **[LLM]** Item 7: Trial Jargon: "What does Phase III mean in a clinical trial?..." — Contains 'compar'
- **[LLM]** Item 13: Stage IV: "Should I consider hospice?..." — No 'giving up'
- **[LLM]** F2: Pre-visit Questions: "Empty profile/context → fallback question set returned..." — Flagged as fallback