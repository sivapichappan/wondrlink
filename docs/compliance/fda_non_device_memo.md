# WondrLink — FDA Non-Device Position

> **DRAFT — INTERNAL USE — ATTORNEY + CLINICAL ADVISOR REVIEW REQUIRED.**
> Prepared May 2026. Internal position memo justifying that WondrLink is not a regulated medical device under the FDA Software as a Medical Device (SaMD) framework, leveraging the 21st Century Cures Act Clinical Decision Support (CDS) exemption.

## Summary Position

WondrLink Foundation maintains that WondrLink is **not** a device subject to FDA premarket clearance or approval. WondrLink is positioned as an educational tool for patients and caregivers affected by colon cancer, and it meets the criteria for the Clinical Decision Support exemption in section 520(o)(1)(E) of the Federal Food, Drug, and Cosmetic Act (FFDCA), as added by the 21st Century Cures Act, and as interpreted in FDA's September 2022 final guidance "Clinical Decision Support Software."

## Product Description

WondrLink is a web application that provides patients and caregivers with personalized educational content about colon cancer, including:
- Conversational answers to user questions, drawn from a curated corpus of NCCN, ASCO, ACS, NCI, and other publicly available oncology guidelines.
- Self-administered mental health screening tools (PHQ-9, GAD-7, PSS-10, ISI) with raw scores and standard severity labels.
- Matching against publicly listed clinical trials at ClinicalTrials.gov.
- Symptom check-ins displaying severity bands.
- Surveillance schedule reminders based on NCCN guidelines.

WondrLink does **not**:
- Diagnose, treat, cure, mitigate, or prevent any disease.
- Recommend a specific treatment or dose for a specific patient.
- Replace or substitute for the judgment of a treating clinician.
- Acquire, process, or analyze a medical image or signal from an in vitro diagnostic device or signal acquisition system.

## Application of the CDS Exemption Criteria

Section 520(o)(1)(E) excludes software functions from the "device" definition that meet all four criteria. WondrLink's posture:

1. **Not intended to acquire, process, or analyze a medical image or signal from an in vitro diagnostic device or signal acquisition system.**
   - WondrLink processes only user-typed text and self-reported symptom severity. No imaging, no biosignal, no IVD output.
   - ✅ Met.

2. **Intended for the purpose of displaying, analyzing, or printing medical information about a patient or other medical information (such as peer-reviewed clinical studies and clinical practice guidelines).**
   - WondrLink retrieves and presents information from NCCN, ASCO, ACS, NCI, and other guideline documents; it does not synthesize new diagnostic conclusions.
   - ✅ Met.

3. **Intended for the purpose of supporting or providing recommendations to a healthcare professional about prevention, diagnosis, or treatment of a disease or condition.**
   - WondrLink is patient-facing, not clinician-facing. This criterion is *not* met in the form FDA's CDS guidance contemplates.
   - However, FDA guidance and case law have generally treated patient-facing educational software (without specific treatment recommendations) as non-device when criteria 1, 2, and 4 are met and when no specific diagnostic or treatment determination is delivered to the patient. WondrLink relies on this broader position, not on criterion 3 strictly applied.

4. **Intended for the purpose of enabling such healthcare professional [or patient] to independently review the basis for such recommendations** so that the user does not rely primarily on the software's recommendation.
   - WondrLink shipped (May 2026) the hallucination mitigation system with inline `[N]` citations linking each medical claim to the source guideline. Users can hover any citation to see the actual source text. The persistent AI disclosure banner reinforces that AI responses are not medical advice.
   - ✅ Met. The "independent review" criterion is supported by inline citation infrastructure and source attribution.

## Specific Features Considered

### Mental Health Screening (PHQ-9, GAD-7, PSS-10, ISI, PREMM5)
These are user-administered, well-established public-domain screening instruments. WondrLink displays the standard scoring with standard severity bands. The application explicitly tells users to share results with their care team and does not deliver a diagnosis. Consistent with FDA's longstanding position that patient self-administration of public-domain instruments is not a device function.

### PRO-CTCAE Symptom Tracking
WondrLink presents PRO-CTCAE-aligned severity grading for symptom check-ins. The display is descriptive ("severe"), not directive ("you have X condition"). Users are referred to their care team for action. Treated as patient-facing education, not as a clinical decision tool.

### Surveillance Schedule Display
WondrLink shows NCCN-recommended surveillance intervals based on the user's stated stage and surgery date. The display is an educational reminder, not a prescriptive medical instruction.

### Crisis Detection
PHQ-9 Question 9 triggers a crisis overlay with 988 / Crisis Text Line / 911 resources. This is a safety feature consistent with patient-facing application norms and is not diagnostic.

## Affirmative Steps Beyond Criteria

In addition to meeting (or substantially meeting) the four CDS criteria:
- WondrLink does not make patient-specific treatment recommendations.
- WondrLink does not select dose, interval, or drug for any patient.
- WondrLink does not interpret images, biosignals, or in vitro diagnostic test results.
- WondrLink applies HIPAA-style de-identification before sending user content to LLM providers.
- WondrLink's hallucination mitigation system (off-topic detection, second-pass LLM verification, source-grounded prompts, inline citations) substantially reduces the risk that the AI delivers a recommendation a user would mistakenly rely on without independent review.

## Risks and Open Items

- **PRO-CTCAE Grade 3+ alerts:** if WondrLink ever begins directing users to specific clinical actions ("call your oncologist now"), the position weakens. Current behavior is to recommend talking with the care team — not directive. Maintain this framing.
- **Surveillance schedule:** if it begins generating personalized timing recommendations (vs. displaying generic NCCN intervals), the position weakens.
- **Therapy-adjacent framing:** state AI laws in IL/NV restrict AI-delivered "therapy." Geographic restriction at signup addresses the state-law exposure. The FDA exemption argument is separate from the state-law analysis.

## Documentation Owners

- Position memo owner: Privacy Officer + Engineering Lead
- Annual review by external regulatory counsel
- Next scheduled review: TBD post attorney engagement
