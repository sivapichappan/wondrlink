# llm_utils.py
import os
import re
import logging
import json
from typing import List, Dict, Any, Tuple, Optional, Union

logger = logging.getLogger("llm_utils")

# =============================================================================
# PII DETECTION AND FILTERING (Compliance Feature)
# =============================================================================

# PII patterns to detect and filter from user queries
PII_PATTERNS = {
    'ssn': r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b',  # Social Security Number
    'dob': r'\b(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{4}[/\-]\d{1,2}[/\-]\d{1,2})\b',  # Date patterns
    'phone': r'\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',  # Phone numbers
    'email': r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Z|a-z]{2,}\b',  # Email addresses
    'address': r'\b\d+\s+[A-Za-z]+\s+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Way|Place|Pl)\b',  # Street addresses
    'credit_card': r'\b(?:\d{4}[-\s]?){3}\d{4}\b',  # Credit card numbers
}

# PII instruction to add to system prompt
PII_INSTRUCTION = """
PII HANDLING (CRITICAL):
- Do NOT acknowledge, repeat, or store any personally identifiable information such as:
  * Full names (last names, family names)
  * Dates of birth or specific birth dates
  * Social Security numbers
  * Phone numbers
  * Email addresses
  * Street addresses
  * Credit card numbers
- If the user provides such information, do NOT include it in your response
- Only use the patient's first name if provided in their profile
- Focus on the medical content of the question, ignoring any PII
"""


def detect_pii(text: str) -> Dict[str, List[str]]:
    """
    Detect PII in user input.

    Args:
        text: The text to scan for PII

    Returns:
        Dict of detected PII types and their matched values
    """
    detected = {}

    for pii_type, pattern in PII_PATTERNS.items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            detected[pii_type] = matches

    return detected


def sanitize_query(query: str) -> Tuple[str, List[str]]:
    """
    Remove PII from user query before sending to LLM.

    Args:
        query: The user's query text

    Returns:
        Tuple of (sanitized_query, list_of_warnings)
    """
    sanitized = query
    warnings = []

    # Remove SSN
    if re.search(PII_PATTERNS['ssn'], query):
        sanitized = re.sub(PII_PATTERNS['ssn'], '[REMOVED]', sanitized)
        warnings.append("SSN detected and removed")

    # Remove DOB patterns (but be careful not to remove treatment cycle dates)
    # Only remove if it looks like a birthdate context
    dob_context = re.search(r'\b(?:born|birthday|dob|date of birth)\s*(?:is|:)?\s*' + PII_PATTERNS['dob'], query, re.IGNORECASE)
    if dob_context:
        sanitized = re.sub(r'\b(?:born|birthday|dob|date of birth)\s*(?:is|:)?\s*' + PII_PATTERNS['dob'], '[DOB REMOVED]', sanitized, flags=re.IGNORECASE)
        warnings.append("Date of birth detected and removed")

    # Remove phone numbers
    if re.search(PII_PATTERNS['phone'], query):
        sanitized = re.sub(PII_PATTERNS['phone'], '[PHONE REMOVED]', sanitized)
        warnings.append("Phone number detected and removed")

    # Remove emails
    if re.search(PII_PATTERNS['email'], query):
        sanitized = re.sub(PII_PATTERNS['email'], '[EMAIL REMOVED]', sanitized)
        warnings.append("Email detected and removed")

    # Remove street addresses
    if re.search(PII_PATTERNS['address'], query, re.IGNORECASE):
        sanitized = re.sub(PII_PATTERNS['address'], '[ADDRESS REMOVED]', sanitized, flags=re.IGNORECASE)
        warnings.append("Address detected and removed")

    # Remove credit card numbers
    if re.search(PII_PATTERNS['credit_card'], query):
        sanitized = re.sub(PII_PATTERNS['credit_card'], '[CARD REMOVED]', sanitized)
        warnings.append("Credit card number detected and removed")

    return sanitized, warnings

# Token counting with tiktoken
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
    # Use cl100k_base encoding (same as GPT-4, works well for Llama models)
    TOKEN_ENCODING = tiktoken.get_encoding("cl100k_base")
    logger.info("tiktoken initialized successfully")
except ImportError:
    TIKTOKEN_AVAILABLE = False
    TOKEN_ENCODING = None
    logger.warning("tiktoken not available, using approximate token counting")

# LLM clients - lazy initialization to ensure env vars are loaded first
_groq_client = None
_together_client = None
_groq_initialized = False
_together_initialized = False


def _init_groq():
    """Lazily initialize Groq client on first use."""
    global _groq_client, _groq_initialized
    if _groq_initialized:
        return _groq_client
    _groq_initialized = True
    try:
        from groq import Groq
        api_key = os.environ.get("GROQ_API_KEY")
        if api_key:
            _groq_client = Groq(api_key=api_key)
            logger.info("Groq client initialized successfully")
        else:
            logger.warning("GROQ_API_KEY not set in environment")
    except ImportError:
        logger.warning("groq package not installed")
    except Exception as e:
        logger.warning(f"Groq initialization failed: {e}")
    return _groq_client


def _init_together():
    """Lazily initialize Together client on first use."""
    global _together_client, _together_initialized
    if _together_initialized:
        return _together_client
    _together_initialized = True
    try:
        from together import Together
        api_key = os.environ.get("TOGETHER_API_KEY")
        if api_key:
            _together_client = Together(api_key=api_key)
            logger.info("Together client initialized successfully")
        else:
            logger.warning("TOGETHER_API_KEY not set in environment")
    except ImportError:
        logger.warning("together package not installed")
    except Exception as e:
        logger.warning(f"Together initialization failed: {e}")
    return _together_client


def get_groq_client():
    """Get Groq client, initializing if needed."""
    return _init_groq()


def get_together_client():
    """Get Together client, initializing if needed."""
    return _init_together()


def is_groq_available():
    """Check if Groq is available."""
    return get_groq_client() is not None


def is_together_available():
    """Check if Together is available."""
    return get_together_client() is not None


def get_llm_status() -> Dict[str, Any]:
    """Get the status of LLM providers."""
    together_avail = is_together_available()
    groq_avail = is_groq_available()
    return {
        "together_available": together_avail,
        "groq_available": groq_avail,
        "primary_api": "together" if together_avail else "groq" if groq_avail else None
    }


# Token budget constants
TOKEN_BUDGET = {
    'system': 400,      # System message (increased for enhanced prompts)
    'patient': 400,     # Patient context
    'chunks': 1500,     # Retrieved guideline chunks
    'history': 400,     # Conversation history
    'question': 100,    # User question
    'instructions': 200,# Response instructions
    'response': 1200    # Buffer for response
}


# =============================================================================
# SYSTEM PROMPT — composed from lib/prompts/ (base + per-cancer overlay)
# =============================================================================
#
# As of Phase 1 of the multi-cancer expansion, the system prompt is no longer
# a single hardcoded string. The cancer-agnostic portion lives in
# lib/prompts/base.py and the per-cancer overlay lives in
# config/cancers/<slug>/overlay.md. lib.prompts.assemble_system_prompt(slug)
# composes them.
#
# ENHANCED_SYSTEM_PROMPT is kept as a back-compat export equal to the
# colorectal-composed prompt so existing callers that don't yet pass a
# cancer slug behave identically to pre-refactor.
#
# Prefer calling assemble_system_prompt(cancer_slug) directly in new code.

from lib.prompts import assemble_system_prompt as _assemble_system_prompt

ENHANCED_SYSTEM_PROMPT = _assemble_system_prompt("colorectal")



# =============================================================================
# FOLLOW-UP QUESTION DIVERSITY
# =============================================================================

FOLLOW_UP_INSTRUCTION = """
FOLLOW-UP SUGGESTIONS:
Suggest 2-3 related questions the patient might want to ask next, covering DIFFERENT aspects of their care:
- A question about a different treatment option or drug
- A question about side effect management or quality of life
- A question about practical concerns or emotional support

At the very end of your response, on its own line after a blank line, output exactly this block (the server parses it and renders the questions as interactive chips):

FOLLOWUPS:
- Question 1
- Question 2
- Question 3

Do NOT include any header text like "You might also want to ask about:" — just the FOLLOWUPS: block. Each question on its own line prefixed with "- ".
"""


# Server-side parser for the FOLLOWUPS block. Strips the block out of the
# rendered text and returns the list separately so the frontend can render
# them as interactive chips below the message.
import re as _re_followups


def extract_followups(text: str):
    """
    Pull the trailing FOLLOWUPS: block out of an LLM response.

    Returns (cleaned_text, followups) where followups is a List[str] (0-3 items)
    and cleaned_text has the block removed. Tolerant of minor format drift
    (extra whitespace, the legacy "You might also want to ask about" preamble).
    """
    if not text:
        return text, []
    cleaned = text
    followups = []
    # Strip any legacy preamble line the LLM may emit out of habit.
    legacy_pat = _re_followups.compile(
        r'\s*You might also want to ask about:?\s*',
        _re_followups.IGNORECASE,
    )
    cleaned = legacy_pat.sub('\n', cleaned)

    # Find the FOLLOWUPS: marker (case-insensitive) and consume everything after.
    marker = _re_followups.search(r'\n\s*FOLLOWUPS:\s*\n', cleaned, _re_followups.IGNORECASE)
    if not marker:
        return cleaned.strip(), []

    tail = cleaned[marker.end():]
    cleaned = cleaned[:marker.start()].rstrip()

    # Parse "- item" or "• item" or numbered "1. item" lines from the tail.
    for raw_line in tail.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # Strip leading bullets / numbers
        line = _re_followups.sub(r'^\s*(?:[-•*]|\d+[.)])\s+', '', line)
        line = line.strip().rstrip('?').strip()
        if not line:
            continue
        if not line.endswith('?'):
            line = line + '?'
        # Defensive max length
        if len(line) > 200:
            line = line[:200].rstrip() + '?'
        followups.append(line)
        if len(followups) >= 3:
            break

    return cleaned, followups


# =============================================================================
# LOW CONFIDENCE HEDGING (HALLUCINATION MITIGATION)
# =============================================================================

HEDGE_INSTRUCTION = """LOW CONFIDENCE MODE (the retrieved guideline excerpts may not directly address this question):
1. Begin your response with explicit acknowledgment: "I'm not finding strong guidance specifically about this in our resources, but here's what I can share..."
2. End with: "This is exactly the kind of question your oncology team is best equipped to answer specifically for your situation."
3. Do NOT invent details, statistics, drug names, percentages, or trial numbers to fill gaps.
4. If you genuinely cannot answer from the sources, say so plainly rather than guessing."""

# =============================================================================
# SAFETY VALVE — DISTRESS-TRIGGERED COMFORT MODE
# =============================================================================

SAFETY_VALVE_INSTRUCTION = """SAFETY VALVE ACTIVE — COMFORT-FIRST MODE:
Your FIRST PRIORITY is comfort. The user is in acute distress.
1. Begin with 2 sentences of pure empathetic support — NO medical information yet.
2. Your role shifts from Informer to Companion for this response.
3. After the comfort opening, gently transition to helpful information.
4. Disclaimers should feel like protective gestures, not legal boilerplate.
5. If the distress seems beyond what you can address, offer the WondrLink Foundation
   Personal Navigator: www.wondrlinkfoundation.org"""

# =============================================================================
# PAIN MANAGEMENT GUIDANCE
# =============================================================================

PAIN_MANAGEMENT_GUIDANCE = """
PAIN MANAGEMENT CONTEXT:
When discussing pain relief or over-the-counter medications:
- Frame as: "Some patients find relief with..." — NEVER "Take Tylenol" or "You should take..."
- Always include: "Because your safety is the priority, it's best to check with your
  oncology team before starting anything new — some medications can interact with treatment."
- NSAIDs (ibuprofen, naproxen): may increase bleeding risk, interact with some chemo drugs,
  and affect kidney function. Not recommended without oncologist approval.
- Acetaminophen (Tylenol): generally safer but check liver function (chemo can affect liver).
  Stay within recommended dosage (max 3,000mg/day, less if liver issues).
- For pain 6/10 or higher: this level of pain deserves prompt attention from the care team.
  Encourage reaching out to oncology team today, not just at next appointment."""

# =============================================================================
# SYMPTOM URGENCY DETECTION
# =============================================================================

CONCERNING_SYMPTOM_PATTERNS = {
    'emergency_fever': {
        'keywords': ['fever', '100.4', '101', '102', '103', 'temperature', 'chills'],
        'requires_chemo_context': True,
        'urgency': 'emergency',
        'guidance': '🚨 EMERGENCY: Fever during chemotherapy is a medical emergency due to risk of neutropenic sepsis. Contact your oncologist immediately or go to the ER. Do not wait.'
    },
    'emergency_breathing': {
        'keywords': ['can\'t breathe', 'difficulty breathing', 'short of breath', 'chest pain', 'chest tightness'],
        'requires_chemo_context': False,
        'urgency': 'emergency',
        'guidance': '🚨 EMERGENCY: These symptoms require immediate medical attention. Call 911 or go to the nearest emergency room immediately.'
    },
    'emergency_bleeding': {
        'keywords': ['severe bleeding', 'blood in stool', 'vomiting blood', 'heavy bleeding'],
        'requires_chemo_context': False,
        'urgency': 'emergency',
        'guidance': '🚨 EMERGENCY: Significant bleeding requires immediate medical evaluation. Go to the ER or call 911.'
    },
    'urgent_worsening': {
        'keywords': ['worse', 'worsening', 'getting worse', 'increased', 'more severe', 'progressing'],
        'requires_chemo_context': False,
        'urgency': 'urgent',
        'guidance': '⚠️ URGENT: Worsening symptoms should be reported to your oncology team promptly - typically within 24-48 hours. Dose modifications are common and expected; don\'t hesitate to report changes.'
    },
    'urgent_neuropathy': {
        'keywords': ['tingling worse', 'numbness worse', 'neuropathy worse', 'fingers worse', 'toes worse', 'can\'t feel', 'dropping things'],
        'requires_chemo_context': False,
        'urgency': 'urgent',
        'guidance': '⚠️ URGENT: Worsening neuropathy during oxaliplatin-based therapy requires prompt evaluation. Contact your oncology team within 24-48 hours. Dose modifications are COMMON and can help prevent permanent nerve damage. Call the main clinic line during business hours or the after-hours line if evening/weekend. If you don\'t hear back within a few hours, call again. In the meantime: avoid cold exposure, use warm (not cold) beverages, and wear gloves when handling frozen items.'
    },
    'urgent_dehydration': {
        'keywords': ['can\'t eat', 'can\'t drink', 'not eating', 'not drinking', 'severe nausea', 'severe vomiting', 'can\'t keep anything down'],
        'requires_chemo_context': False,
        'urgency': 'urgent',
        'guidance': '⚠️ URGENT: Inability to eat or drink for more than 24 hours can lead to dehydration and requires medical attention. Contact your oncology team today.'
    },
    'distress_pain_high': {
        'keywords': ['6/10', '7/10', '8/10', '9/10', '10/10', 'pain level 6',
                     'pain level 7', 'pain level 8', 'pain level 9', 'pain level 10',
                     'severe pain', 'excruciating', 'unbearable pain', 'agony'],
        'requires_chemo_context': False,
        'urgency': 'distress',
        'guidance': SAFETY_VALVE_INSTRUCTION
    },
    'distress_emotional': {
        'keywords': ["can't take this anymore", "i'm scared", "i can't do this",
                     "want to give up", "i'm terrified", "i'm losing hope",
                     "what's the point", "i don't want to do this anymore"],
        'requires_chemo_context': False,
        'urgency': 'distress',
        'guidance': SAFETY_VALVE_INSTRUCTION
    }
}


def detect_symptom_urgency(message: str, patient_context: dict = None) -> dict:
    """
    Detect if user message describes concerning symptoms requiring escalation.

    Returns dict with:
    - detected: bool
    - urgency: 'emergency' | 'urgent' | None
    - pattern: str (which pattern matched)
    - guidance: str (specific guidance to prepend to response)
    """
    if patient_context is None:
        patient_context = {}

    message_lower = message.lower()
    on_chemo = bool(patient_context.get('current_treatments'))

    # Check patterns in priority order (emergencies first)
    for pattern_name, pattern in CONCERNING_SYMPTOM_PATTERNS.items():
        # Check if any keywords match
        if any(kw in message_lower for kw in pattern['keywords']):
            # Some patterns only apply during chemo
            if pattern.get('requires_chemo_context') and not on_chemo:
                continue

            return {
                'detected': True,
                'pattern': pattern_name,
                'urgency': pattern['urgency'],
                'guidance': pattern['guidance']
            }

    return {'detected': False, 'urgency': None, 'pattern': None, 'guidance': None}


# =============================================================================
# PATIENT RESOURCES
# =============================================================================

# =============================================================================
# CURATED PATIENT RESOURCES - Contextually referenced based on query type
# =============================================================================
PATIENT_RESOURCES = {
    # General Information - staging, treatment overviews, guidelines
    'general': [
        {'name': 'National Cancer Institute', 'url': 'https://www.cancer.gov/types/colorectal', 'desc': 'Comprehensive cancer info'},
        {'name': 'American Cancer Society', 'url': 'https://www.cancer.org/cancer/colon-rectal-cancer.html', 'desc': 'Patient-friendly overviews'},
        {'name': 'NCCN Patient Guidelines', 'url': 'https://www.nccn.org/patients/guidelines/content/PDF/colon-patient.pdf', 'desc': 'Evidence-based treatment guidelines'},
    ],

    # Advocacy Organizations - patient advocacy, resources
    'advocacy': [
        {'name': 'Colorectal Cancer Alliance', 'url': 'https://colorectalcancer.org', 'desc': 'Patient support and resources'},
        {'name': 'Fight Colorectal Cancer', 'url': 'https://fightcolorectalcancer.org', 'desc': 'Advocacy and patient resources'},
        {'name': 'Colon Cancer Coalition', 'url': 'https://coloncancercoalition.org', 'desc': 'Awareness and screening'},
    ],

    # Support Communities - peer support, online communities
    'support': [
        {'name': 'Colontown', 'url': 'https://colontown.org', 'desc': 'Active peer support community (11,000+ members)'},
        {'name': 'Colontown University', 'url': 'https://learn.colontown.org', 'desc': 'Free patient education courses'},
        {'name': 'Blue Hope Nation (CCA)', 'url': 'https://colorectalcancer.org/bluehq', 'desc': 'Online support hub'},
        {'name': 'Smart Patients CRC', 'url': 'https://www.smartpatients.com/communities/colorectal-cancer', 'desc': 'Patient discussion community'},
    ],

    # Clinical Trials - trial search, trial finder
    'clinical_trials': [
        {'name': 'ClinicalTrials.gov', 'url': 'https://clinicaltrials.gov', 'desc': 'NIH database of all trials'},
        {'name': 'NCI Trial Search', 'url': 'https://www.cancer.gov/research/participate/clinical-trials-search', 'desc': 'National Cancer Institute trials'},
        {'name': 'CCA Trial Finder', 'url': 'https://colorectalcancer.org/treatment/types-treatment/clinical-trials/clinical-trial-finder', 'desc': 'Simplified trial search'},
    ],

    # Treatment Information - surgery, chemo, targeted therapy, immunotherapy
    'treatment': [
        {'name': 'ACS Colon Treatment', 'url': 'https://www.cancer.org/cancer/colon-rectal-cancer/treating.html', 'desc': 'Treatment overview'},
        {'name': 'NCI Treatment (PDQ)', 'url': 'https://www.cancer.gov/types/colorectal/patient/colon-treatment-pdq', 'desc': 'Detailed treatment info'},
        {'name': 'Chemocare Drug Info', 'url': 'https://chemocare.com/chemotherapy/drug-info/default.aspx', 'desc': 'Chemotherapy drug details'},
    ],

    # Side Effects (General) - chemo side effects, symptom management
    'side_effects_chemo': [
        {'name': 'Chemocare Side Effects', 'url': 'https://chemocare.com/chemotherapy/side-effects/default.aspx', 'desc': 'Drug-specific side effects'},
        {'name': 'NCI Side Effects', 'url': 'https://www.cancer.gov/about-cancer/treatment/side-effects', 'desc': 'Managing treatment effects'},
        {'name': 'ACS Side Effects', 'url': 'https://www.cancer.org/cancer/managing-cancer/side-effects.html', 'desc': 'Side effect management'},
    ],

    # Neuropathy - tingling, numbness, nerve damage
    'neuropathy': [
        {'name': 'Foundation for PN', 'url': 'https://www.foundationforpn.org', 'desc': 'Neuropathy-specific support'},
        {'name': 'Chemocare Neuropathy', 'url': 'https://chemocare.com/chemotherapy/side-effects/peripheral-neuropathy.aspx', 'desc': 'Management tips'},
    ],

    # Fatigue - tiredness, energy, exhaustion
    'fatigue': [
        {'name': 'Cancer.org Fatigue', 'url': 'https://www.cancer.org/treatment/treatments-and-side-effects/physical-side-effects/fatigue.html', 'desc': 'Fatigue management'},
        {'name': 'NCI Late Effects', 'url': 'https://www.cancer.gov/about-cancer/coping/survivorship/late-effects', 'desc': 'Long-term effects'},
    ],

    # Nausea - vomiting, appetite, anti-nausea
    'nausea': [
        {'name': 'Chemocare Nausea', 'url': 'https://chemocare.com/chemotherapy/side-effects/nausea-and-vomiting.aspx', 'desc': 'Nausea management'},
    ],

    # Emotional & Mental Health - anxiety, depression, coping, family
    'emotional': [
        {'name': 'Cancer Support Community', 'url': 'https://www.cancersupportcommunity.org', 'desc': 'Free support groups'},
        {'name': 'CancerCare Counseling', 'url': 'https://www.cancercare.org', 'desc': 'Free counseling services'},
        {'name': 'Imerman Angels', 'url': 'https://imermanangels.org', 'desc': 'Free 1-on-1 cancer support'},
        {'name': 'Cancer Hope Network', 'url': 'https://www.cancerhopenetwork.org', 'desc': 'Peer support matching'},
    ],

    # Financial Assistance - costs, copays, insurance
    'financial': [
        {'name': 'Patient Advocate Foundation', 'url': 'https://www.patientadvocate.org', 'desc': 'Insurance and financial help'},
        {'name': 'CancerCare Financial', 'url': 'https://www.cancercare.org/financial', 'desc': 'Financial assistance programs'},
        {'name': 'CCA Financial Resources', 'url': 'https://colorectalcancer.org/resources-support/resources/financial-assistance', 'desc': 'CRC-specific financial help'},
        {'name': 'NeedyMeds', 'url': 'https://www.needymeds.org', 'desc': 'Medication assistance finder'},
        {'name': 'PAN Foundation', 'url': 'https://www.panfoundation.org', 'desc': 'Co-pay assistance'},
    ],

    # Survivorship - after treatment, long-term, follow-up
    'survivorship': [
        {'name': 'ACS Survivorship', 'url': 'https://www.cancer.org/cancer/colon-rectal-cancer/after-treatment/follow-up.html', 'desc': 'Follow-up care guide'},
        {'name': 'Cancer Survivors Network', 'url': 'https://csn.cancer.org', 'desc': 'ACS peer support'},
        {'name': 'NCI Follow-Up Care', 'url': 'https://www.cancer.gov/about-cancer/coping/survivorship/follow-up-care', 'desc': 'Survivorship care planning'},
    ],

    # Screening - colonoscopy, FIT test, prevention, early detection
    'screening': [
        {'name': 'ACS Screening Guidelines', 'url': 'https://www.cancer.org/cancer/colon-rectal-cancer/detection-diagnosis-staging/acs-recommendations.html', 'desc': 'Screening recommendations'},
        {'name': 'USPSTF Guidelines', 'url': 'https://www.uspreventiveservicestaskforce.org/uspstf/recommendation/colorectal-cancer-screening', 'desc': 'Federal screening guidelines'},
        {'name': 'CDC Screen for Life', 'url': 'https://www.cdc.gov/colorectal-cancer/screening/index.html', 'desc': 'CDC screening resources'},
    ],

    # Diagnosis - symptoms, staging, biomarker testing
    'diagnosis': [
        {'name': 'ACS Diagnosis', 'url': 'https://www.cancer.org/cancer/colon-rectal-cancer/detection-diagnosis-staging/how-diagnosed.html', 'desc': 'How CRC is diagnosed'},
        {'name': 'ACS Staging', 'url': 'https://www.cancer.org/cancer/colon-rectal-cancer/detection-diagnosis-staging/staged.html', 'desc': 'Cancer staging explained'},
        {'name': 'Biomarker Testing (CCA)', 'url': 'https://colorectalcancer.org/treatment/biomarker-testing', 'desc': 'Biomarker testing guide'},
        {'name': 'NCI Biomarkers', 'url': 'https://www.cancer.gov/about-cancer/treatment/types/biomarker-testing-cancer-treatment', 'desc': 'Testing for treatment'},
    ],

    # Nutrition - diet, eating, weight, dietitian
    'nutrition': [
        {'name': 'Oncology Nutrition (AND)', 'url': 'https://www.oncologynutrition.org', 'desc': 'Dietitian resources'},
        {'name': 'Cancer.org Nutrition', 'url': 'https://www.cancer.org/treatment/survivorship-during-and-after-treatment/staying-active/nutrition.html', 'desc': 'Nutrition during treatment'},
    ],

    # Ostomy - colostomy, ileostomy, stoma care
    'ostomy': [
        {'name': 'UOAA', 'url': 'https://www.ostomy.org', 'desc': 'Ostomy education and support'},
        {'name': 'UOAA Support Groups', 'url': 'https://www.ostomy.org/support-group-finder/', 'desc': 'Find local support'},
        {'name': 'ACS Colostomy Guide', 'url': 'https://www.cancer.org/cancer/managing-cancer/treatment-types/surgery/ostomies/colostomy.html', 'desc': 'Living with colostomy'},
        {'name': 'MSK Ostomy Care', 'url': 'https://www.mskcc.org/cancer-care/patient-education/caring-for-your-ileostomy-colostomy', 'desc': 'Practical ostomy care'},
    ],

    # Hereditary & Genetic - Lynch syndrome, genetic testing, family history
    'hereditary': [
        {'name': 'NCI Genetics (PDQ)', 'url': 'https://www.cancer.gov/types/colorectal/patient/colorectal-genetics-pdq', 'desc': 'Genetics of CRC'},
        {'name': 'Find Genetic Counselor', 'url': 'https://www.findageneticcounselor.com', 'desc': 'NSGC counselor finder'},
        {'name': 'Lynch Syndrome Info', 'url': 'https://www.cancer.net/cancer-types/lynch-syndrome', 'desc': 'Lynch syndrome guide'},
        {'name': 'FORCE', 'url': 'https://www.facingourrisk.org', 'desc': 'Hereditary cancer support'},
    ],

    # Helplines - phone support, crisis lines
    'helplines': [
        {'name': 'American Cancer Society', 'url': 'tel:1-800-227-2345', 'desc': '1-800-227-2345 (24/7)'},
        {'name': 'CCA Helpline', 'url': 'tel:1-877-422-2030', 'desc': '1-877-422-2030 (M-F 9am-9pm ET)'},
        {'name': 'NCI Cancer Info', 'url': 'tel:1-800-422-6237', 'desc': '1-800-422-6237 (M-F 9am-9pm ET)'},
        {'name': 'Cancer Support Helpline', 'url': 'tel:1-888-793-9355', 'desc': '1-888-793-9355 (free, confidential)'},
    ],

    # Caregiver resources (expanded - Item 10)
    'caregiver': [
        {'name': 'ACS Caregiver Guide', 'url': 'https://www.cancer.org/cancer/caregivers.html', 'desc': 'Caregiver resource guide'},
        {'name': 'NCI Caregiver Support', 'url': 'https://www.cancer.gov/about-cancer/coping/caregiver-support', 'desc': 'Support for caregivers'},
        {'name': 'Caregiver Action Network', 'url': 'https://www.caregiveraction.org', 'desc': 'Caregiver advocacy and training'},
        {'name': 'UOAA Ostomy Caregiver Guide', 'url': 'https://www.ostomy.org/caregivers/', 'desc': 'CRC-specific ostomy care'},
        {'name': 'CancerCare for Caregivers', 'url': 'https://www.cancercare.org/tagged/caregivers', 'desc': 'Free counseling for caregivers'},
        {'name': 'Lotsa Helping Hands', 'url': 'https://lotsahelpinghands.com', 'desc': 'Coordinate practical help'},
    ],

    # Surgery specific
    'surgery': [
        {'name': 'ACS Colon Surgery', 'url': 'https://www.cancer.org/cancer/colon-rectal-cancer/treating/surgery.html', 'desc': 'Surgery for colon cancer'},
        {'name': 'ASCRS Patient Info', 'url': 'https://www.fascrs.org/patients', 'desc': 'Colorectal surgery info'},
    ],

    # Prevention - risk reduction, lifestyle
    'prevention': [
        {'name': 'ACS Prevention', 'url': 'https://www.cancer.org/cancer/colon-rectal-cancer/causes-risks-prevention/prevention.html', 'desc': 'CRC prevention'},
        {'name': 'NCI Prevention (PDQ)', 'url': 'https://www.cancer.gov/types/colorectal/patient/colorectal-prevention-pdq', 'desc': 'Prevention strategies'},
        {'name': 'CCA Risk Factors', 'url': 'https://colorectalcancer.org/prevention-screening/risk-factors', 'desc': 'Risk factor info'},
    ],

    # Wellness & Mind-Body (Item 11)
    'wellness': [
        {'name': 'Society for Integrative Oncology', 'url': 'https://integrativeonc.org', 'desc': 'Evidence-based integrative care'},
        {'name': 'MBSR Programs', 'url': 'https://www.mindfulnesscds.com', 'desc': 'Mindfulness for cancer patients'},
        {'name': 'CancerCare Mind-Body', 'url': 'https://www.cancercare.org/tagged/mind-body', 'desc': 'Free mind-body resources'},
        {'name': 'Livestrong at the YMCA', 'url': 'https://www.livestrong.org/what-we-do/program/livestrong-at-the-ymca', 'desc': 'Free cancer fitness program'},
    ],

    # Expanded Access / Compassionate Use (Item 12)
    'expanded_access': [
        {'name': 'FDA Expanded Access', 'url': 'https://www.fda.gov/patients/expanded-access', 'desc': 'FDA expanded access program'},
        {'name': 'Reagan-Udall Navigator', 'url': 'https://navigator.reaganudall.org', 'desc': 'Expanded Access Navigator tool'},
    ],

    # Palliative Care (Item 13)
    'palliative': [
        {'name': 'Get Palliative Care', 'url': 'https://getpalliativecare.org', 'desc': 'Find palliative care providers'},
        {'name': 'PREPARE For Your Care', 'url': 'https://prepareforyourcare.org', 'desc': 'Advance care planning'},
        {'name': 'Five Wishes', 'url': 'https://fivewishes.org', 'desc': 'Advance directive document'},
    ],
}


def get_relevant_resources(query_type: str, include_resources: bool = True, query: str = "") -> List[Dict[str, str]]:
    """
    Return relevant patient-facing resource links as a structured list.

    Args:
        query_type: One of 'treatment', 'side_effect', 'emotional', 'general', 'survivorship', etc.
        include_resources: Whether to include resources (can be disabled for brief responses)
        query: The original user query for symptom-specific resource matching

    Returns:
        List of {"name": str, "url": str} dicts (empty list when not applicable).
        The frontend renders these in a subdued "Trusted resources" row below
        the response rather than inline in the answer text.
    """
    if not include_resources:
        return []

    query_lower = query.lower() if query else ""

    # Keyword-specific resource selection (prioritized matching)
    if 'neuropathy' in query_lower or 'tingling' in query_lower or 'numbness' in query_lower:
        categories = ['neuropathy', 'side_effects_chemo']
    elif 'nausea' in query_lower or 'vomit' in query_lower:
        categories = ['nausea', 'side_effects_chemo']
    elif 'fatigue' in query_lower or 'tired' in query_lower or 'exhausted' in query_lower:
        categories = ['fatigue', 'side_effects_chemo']
    elif 'ostomy' in query_lower or 'colostomy' in query_lower or 'ileostomy' in query_lower or 'stoma' in query_lower:
        categories = ['ostomy', 'support']
    elif 'screening' in query_lower or 'colonoscopy' in query_lower or 'fit test' in query_lower:
        categories = ['screening', 'general']
    elif 'prevention' in query_lower or 'prevent' in query_lower or 'risk factor' in query_lower:
        categories = ['prevention', 'screening']
    elif 'diet' in query_lower or 'nutrition' in query_lower or 'eating' in query_lower or 'food' in query_lower or 'weight' in query_lower:
        categories = ['nutrition', 'support']
    elif 'trial' in query_lower or 'clinical' in query_lower or 'study' in query_lower:
        categories = ['clinical_trials', 'support']
    elif 'financial' in query_lower or 'cost' in query_lower or 'insurance' in query_lower or 'afford' in query_lower or 'pay' in query_lower:
        categories = ['financial', 'support']
    elif 'genetic' in query_lower or 'hereditary' in query_lower or 'lynch' in query_lower or 'family history' in query_lower:
        categories = ['hereditary', 'general']
    elif 'surgery' in query_lower or 'resection' in query_lower or 'operation' in query_lower:
        categories = ['surgery', 'treatment']
    elif 'caregiver' in query_lower or 'family member' in query_lower or 'spouse' in query_lower or 'loved one' in query_lower:
        categories = ['caregiver', 'emotional']
    elif 'helpline' in query_lower or 'call' in query_lower or 'phone' in query_lower or 'talk to someone' in query_lower:
        categories = ['helplines', 'emotional']
    elif 'support group' in query_lower or 'community' in query_lower or 'others' in query_lower or 'connect' in query_lower:
        categories = ['support', 'emotional']
    elif 'biomarker' in query_lower or 'kras' in query_lower or 'msi' in query_lower or 'braf' in query_lower or 'testing' in query_lower:
        categories = ['diagnosis', 'treatment']
    elif 'stage' in query_lower or 'staging' in query_lower or 'diagnosis' in query_lower or 'diagnosed' in query_lower:
        categories = ['diagnosis', 'general']
    elif any(word in query_lower for word in ['anxious', 'anxiety', 'scared', 'fear', 'worried', 'depressed', 'depression', 'cope', 'coping', 'mental']):
        categories = ['emotional', 'helplines']
    elif any(kw in query_lower for kw in ['compassionate use', 'expanded access', 'out of options', 'nothing left', 'no more treatments']):
        categories = ['expanded_access', 'clinical_trials']
    elif any(kw in query_lower for kw in ['yoga', 'exercise', 'mindfulness', 'meditation', 'wellness', 'holistic', 'lifestyle', 'integrative', 'stress management', 'relaxation']):
        categories = ['wellness', 'emotional']
    elif any(kw in query_lower for kw in ['palliative', 'hospice', 'advance directive', 'end of life', 'goals of care']):
        categories = ['palliative', 'emotional']
    else:
        # Fall back to query type mapping
        type_mapping = {
            'emotional': ['emotional', 'helplines'],
            'treatment': ['treatment', 'clinical_trials'],
            'clinical_trial': ['clinical_trials', 'financial'],
            'side_effect': ['side_effects_chemo', 'support'],
            'prognosis': ['support', 'general'],
            'diagnosis': ['diagnosis', 'general'],
            'general': ['general', 'advocacy'],
            'survivorship': ['survivorship', 'support'],
            'screening': ['screening', 'prevention']
        }
        categories = type_mapping.get(query_type, ['general'])

    resources: List[Dict[str, str]] = []
    seen_urls = set()

    for cat in categories:
        if cat not in PATIENT_RESOURCES:
            continue
        for r in PATIENT_RESOURCES[cat][:2]:  # Max 2 per category
            url = r.get("url")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            resources.append({"name": r.get("name", "Resource"), "url": url})
        if len(resources) >= 5:
            break

    return resources[:5]


# =============================================================================
# OXALIPLATIN NEUROPATHY GUIDANCE
# =============================================================================

OXALIPLATIN_NEUROPATHY_GUIDANCE = """
IMPORTANT - For oxaliplatin-related neuropathy:
- ACUTE (cold-triggered): Usually resolves between cycles. Immediate tips: Avoid cold drinks/foods, wear gloves for frozen items, use room-temperature or warm beverages.
- CHRONIC (cumulative tingling/numbness): Dose modifications are COMMON and EXPECTED. Report worsening promptly - this helps prevent permanent damage.
- PROGNOSIS: Acute symptoms typically resolve fully. Chronic sensory neuropathy improves in most patients after stopping oxaliplatin, but can be PERMANENT in approximately 10-15% of patients.
- INTERIM MANAGEMENT: Avoid extreme cold, consider warm compresses for hands/feet, report if symptoms interfere with daily activities (buttoning shirts, writing, walking).
"""


# =============================================================================
# STANDARD CHEMOTHERAPY CYCLE GUIDANCE (Step 2)
# =============================================================================

STANDARD_CYCLE_GUIDANCE = {
    'FOLFOX': {
        'Adjuvant': {
            'expected_cycles': 12,
            'duration': '6 months',
            'note': 'Standard adjuvant FOLFOX is 12 cycles over 6 months. Some centers use 6 cycles of a modified schedule.'
        },
        'Metastatic': {
            'expected_cycles': None,
            'duration': 'ongoing',
            'note': 'Treatment continues until disease progression or intolerance.'
        }
    },
    'FOLFIRI': {
        'Adjuvant': {
            'expected_cycles': 12,
            'duration': '6 months',
            'note': 'Standard adjuvant FOLFIRI is 12 cycles over 6 months.'
        },
        'Metastatic': {
            'expected_cycles': None,
            'duration': 'ongoing',
            'note': 'Treatment continues until disease progression or intolerance.'
        }
    },
    'CAPOX': {
        'Adjuvant': {
            'expected_cycles': 8,
            'duration': '6 months',
            'note': 'Standard adjuvant CAPOX (XELOX) is 8 cycles over 6 months.'
        }
    }
}


# =============================================================================
# TREATMENT RESPONSE STRUCTURE
# =============================================================================

TREATMENT_RESPONSE_STRUCTURE = """
TREATMENT DISCUSSION FORMAT:
When discussing treatment options for this patient, present ALL guideline-documented options. Do NOT pick a single "best" or "primary" option. The patient and their oncologist decide what's best.

Structure your response as follows:

1. ORGANIZE BY TREATMENT LINE OR BIOMARKER PROFILE:
   - Group options by treatment line (first-line, second-line, etc.) or by biomarker eligibility
   - Present ALL options within each group with EQUAL weight - no ranking

2. FOR EACH OPTION, briefly note:
   - The regimen name and what it includes
   - How it works (in simple terms)
   - Key side effects to expect
   - Biomarker requirements or contraindications for THIS patient

3. DO NOT:
   - Label any option as "primary", "preferred", or "best"
   - Omit options that appear in the guidelines
   - Narrow down to a single recommendation

Remind the patient that treatment selection involves many factors and should be discussed with their oncologist.
"""


# =============================================================================
# CLINICAL TRIAL RESPONSE INSTRUCTIONS
# =============================================================================

CLINICAL_TRIAL_RESPONSE_INSTRUCTIONS = """
CLINICAL TRIAL RESPONSE FORMAT:
When discussing clinical trials, follow these rules strictly:

1. TIMELINESS DISCLAIMER:
   - Include this note in your response: "Clinical trial availability changes frequently. Always verify trial status at ClinicalTrials.gov or with your oncology team before making decisions."
   - Never present trial availability as permanent or guaranteed.

2. NO FABRICATED TRIAL INFORMATION:
   - NEVER invent or guess clinical trial names, NCT numbers, specific institutions, or survival statistics.
   - Only reference specific trials that appear in the structured clinical trials data provided to you.
   - If the patient asks about a specific trial you don't have data for, say: "I don't have verified details on that specific trial. You can look it up at ClinicalTrials.gov."
   - If no structured trial data is provided, discuss clinical trials in general terms only (e.g., "Clinical trials studying immunotherapy for colorectal cancer exist").
   - When uncertain about any fact, state your uncertainty explicitly rather than guessing.

3. TRIAL STATUS DISTINCTION:
   - Clearly distinguish between trial statuses when you discuss them:
     * RECRUITING: Actively seeking new participants — these are the actionable options
     * ACTIVE, NOT RECRUITING: Trial is ongoing but not accepting new patients
     * COMPLETED: Trial has finished — results may be published but enrollment is closed
   - Lead with RECRUITING trials as the actionable options for the patient.

4. MSI-H/dMMR vs MSS IMMUNOTHERAPY DISTINCTION:
   - When discussing immunotherapy trials, ALWAYS clarify the patient's MSI/MMR status and what it means:
   - For MSI-H/dMMR patients: Checkpoint inhibitors (pembrolizumab, nivolumab) are established options and the focus of many clinical trials. Highlight this alignment.
   - For MSS/pMMR patients: Single-agent immunotherapy is generally NOT effective. However, clinical trials are investigating combination approaches (immunotherapy + targeted agents, immunotherapy + radiation) that may benefit MSS patients.
   - If the patient's MSI status is unknown, say: "Immunotherapy eligibility depends on your tumor's microsatellite status (MSI-H vs MSS). Ask your oncologist about testing if you haven't had it done."

5. QUESTIONS FOR YOUR DOCTOR:
   - End every clinical trial discussion with a "Questions to Discuss with Your Oncologist" section:
     * "Am I a good candidate for a clinical trial based on my current health?"
     * "How would this trial affect my current treatment plan?"
     * "What are the potential risks and benefits compared to standard treatment?"
     * "Is there a clinical trial coordinator at your center who can help me explore options?"

6. ELIGIBILITY EDUCATION:
   - Briefly explain common eligibility factors when relevant:
     * Age and overall health (performance status / ECOG score)
     * Specific biomarker requirements (MSI-H, BRAF, KRAS, HER2)
     * Prior treatments and how many lines of therapy you've had
     * Organ function (lab values) and time since last treatment
   - Emphasize: "Many patients qualify for more trials than they expect. Your oncologist or a trial navigator can help assess your eligibility."

7. EMOTIONAL SENSITIVITY:
   - Acknowledge that exploring clinical trials can feel overwhelming.
   - Use empowering framing: "Clinical trials offer access to cutting-edge treatments" rather than "when standard treatments fail."
   - Avoid language implying the patient has "run out of options" — instead say "additional treatment pathways are available."
   - When the patient mentions treatment failure or progression, validate their feelings before providing information.

8. FINANCIAL/INSURANCE INFORMATION:
   - Include a brief note about trial costs when relevant:
     * "Many clinical trials cover the cost of the experimental treatment and related tests."
     * "Standard-of-care costs (routine labs, imaging) are typically billed to your insurance."
     * "Under federal law, most health plans must cover routine patient costs in qualifying clinical trials."
     * "Ask the trial coordinator about any out-of-pocket costs and available financial assistance or travel grants."

9. COLON vs RECTAL CANCER:
   - If the patient has colon cancer, focus on colon-specific trials. Some rectal cancer trials involve different approaches (e.g., neoadjuvant radiation) that may not apply.
   - If a rectal cancer trial appears, note: "This trial may be specific to rectal cancer and could differ from colon cancer approaches."
   - When the cancer type is unspecified, use "colorectal cancer" as the umbrella term.

10. JARGON EDUCATION (Item 7):
   - When mentioning Phase I/II/III, briefly explain in parentheses what the phase means
   - When mentioning "randomized" or "placebo," clarify what this means in a cancer context
   - When mentioning eligibility criteria, emphasize: "Many patients qualify for more trials than they expect"
   - Avoid assuming patients understand terms like "open-label," "crossover," or "NCT number" without brief explanation

TONE: Warm, informative, and empowering. Clinical trials represent hope and progress, not a last resort.
Always include links to: ClinicalTrials.gov, the Colorectal Cancer Alliance Trial Finder, and NCI Trial Search when patients ask about finding trials.
"""


def get_cycle_context(regimen: str, line: str, current_cycle: int) -> str:
    """Generate treatment progress context for prompts."""
    if not regimen or not current_cycle:
        return ""

    # Normalize regimen name (handle "FOLFOX + Bevacizumab")
    base_regimen = regimen.split('+')[0].strip().upper()

    guidance = STANDARD_CYCLE_GUIDANCE.get(base_regimen, {}).get(line)
    if not guidance:
        return f"Currently on cycle {current_cycle}"

    expected = guidance.get('expected_cycles')
    if expected and current_cycle:
        remaining = max(0, expected - current_cycle)
        return f"Cycle {current_cycle} of {expected} ({guidance['duration']}). {remaining} cycles remaining. {guidance.get('note', '')}"
    elif current_cycle:
        return f"Cycle {current_cycle}. {guidance.get('note', '')}"
    return ""


# =============================================================================
# COLONOSCOPY SURVEILLANCE GUIDELINES (Step 4)
# =============================================================================

COLONOSCOPY_SURVEILLANCE_GUIDELINES = """
POST-COLON CANCER COLONOSCOPY SCHEDULE (NCCN/ACS Guidelines):
- First colonoscopy: 1 year after surgery
- If normal at 1 year: Repeat at 3 years
- If normal at 3 years: Every 5 years thereafter
- If polyps found: May need more frequent surveillance (every 1-3 years depending on findings)
- Always discuss your specific schedule with your oncologist based on your individual situation.
"""


# =============================================================================
# FIT TEST GUIDANCE (V4 Step 3)
# =============================================================================

FIT_TEST_GUIDANCE = """
ABOUT FIT (FECAL IMMUNOCHEMICAL TEST):
- FIT detects hidden blood in stool, which can indicate:
  * Cancer
  * Advanced adenomas (precancerous polyps)
  * Other GI bleeding sources
- A positive FIT test requires follow-up colonoscopy to determine the cause
- FIT is an effective screening tool when colonoscopy isn't feasible
- FIT should be done annually for average-risk screening
- FIT is NOT a replacement for colonoscopy after a cancer diagnosis
"""


# =============================================================================
# STAGE PROGNOSIS CONTEXT (V4 Step 7)
# =============================================================================

STAGE_PROGNOSIS_CONTEXT = {
    'IIIA': "Stage IIIA colon cancer has excellent outcomes with appropriate treatment. Five-year survival rates are favorable. Your care team can give you specific numbers based on your pathology.",
    'IIIB': "Stage IIIB colon cancer has meaningful cure rates with surgery and adjuvant chemotherapy. Your care team can discuss your specific prognosis based on your pathology, biomarkers, and treatment response.",
    'IIIC': "Stage IIIC represents more advanced local disease but remains potentially curable. Discuss your specific outlook with your oncology team.",
    'IV': "Stage IV colon cancer is serious, and it's completely understandable to have questions about prognosis. Treatment options continue to expand, and many people live well for years with Stage IV disease. Your oncologist can discuss three kinds of questions: (1) What does the data say about people with a similar situation? (2) What are your own goals for treatment? (3) What does quality of life look like on each path? Palliative care can be involved alongside active treatment — it focuses on living as well as possible, not giving up on treatment."
}

STAGE_IV_PALLIATIVE_CONTEXT = """
STAGE IV / ADVANCED DISEASE GUIDANCE:
- Palliative care is NOT hospice — it is specialized support for symptom management and quality of life, offered alongside active cancer treatment
- Use the SPIKES-adapted approach: Ask what the patient already understands before providing new information
- Offer perception check: "Before I share what I know, can I ask what your oncologist has told you so far?"
- Frame prognosis in three scenarios when asked directly: best-case, expected, and if-disease-progresses
- Validate that asking about prognosis is a sign of strength, not giving up
- Always mention: Advance Care Planning is a gift to family — it ensures YOUR wishes are followed
- Introduce hospice only when contextually appropriate: "Hospice is not about giving up hope — it's about changing what you hope for."
- Resources: palliativecare.org, getpalliativecare.org, prepareforyourcare.org
"""


# =============================================================================
# ER PREPARATION TIPS (V4 Step 4)
# =============================================================================

ER_PREPARATION_TIPS = """
If going to the ER:
• Tell triage immediately that you're on chemotherapy - this often expedites evaluation
• Bring your medication list or take a photo of your pill bottles
• Have your oncologist's after-hours number saved in your phone
• Bring your insurance card and ID
• If possible, have someone accompany you
"""


# =============================================================================
# EMOTIONAL SUPPORT GUIDANCE (V4 Step 2 - Fixed genetic counselor role)
# =============================================================================

EMOTIONAL_SUPPORT_GUIDANCE = """
For emotional support:
- Normalize the emotion: Anxiety, fear, and sadness are completely normal reactions to a cancer diagnosis
- Mention specific resources:
  * Oncology social workers are available at most cancer centers - ask your care team
  * Cancer Support Helpline: 1-888-793-9355 (free, confidential)
  * Calm and Headspace apps have free cancer-specific meditation programs
- For "scanxiety": Anxiety often peaks around scan times - this is very common
- For family communication: Oncology social workers and CancerCare counselors can help with family discussions
- NOTE: Genetic counselors are for hereditary risk discussions (e.g., "Should my children get tested?"), NOT general family communication
"""


# =============================================================================
# ANP TONE CALIBRATION (Item 6 - Clinical Feedback)
# =============================================================================

TONE_SENSITIVITY_LEVELS = {
    'high': ['terminal', 'hospice', 'palliative', 'end of life', 'stage iv', 'stage 4',
             'metastatic', 'prognosis', 'how long', 'dying', 'death', 'going to die',
             'will i die', 'am i dying', 'kill me', 'cure', 'spread',
             'no more options', 'nothing left', 'give up', 'worst case',
             'fatal', 'survive', 'survival rate', 'life expectancy'],
    'medium': ['scared', 'anxious', 'worried', 'overwhelmed', 'stressed', 'depressed',
               'hopeless', "can't cope", 'giving up', 'losing hope', 'family', 'afraid',
               'what if', 'recurrence', 'come back'],
    'low': ['treatment', 'side effect', 'medication', 'diet', 'exercise', 'screening']
}

ANP_TONE_INSTRUCTION = """
TONE CALIBRATION — APPLY ANP FRAMEWORK (Acknowledge → Normalize → Partner):
1. ACKNOWLEDGE: Begin with 1-2 sentences validating the emotional weight of this question.
2. NORMALIZE: Note that this concern is common — "Many people in your situation wonder about this."
3. PARTNER: End with support and a concrete next step — "Your care team can help you with this."

AVOID toxic positivity: "everything happens for a reason", "stay positive", "you'll be fine",
"just think positive", "at least...", "silver lining", "fighting spirit"

INSTEAD use: "This is genuinely hard." / "Your feelings make complete sense." / "Let's look at what might help."
"""


# =============================================================================
# SCREENING SCORE CONTEXT INJECTION (Items 3-5)
# =============================================================================

SCREENING_CONTEXT_TEMPLATES = {
    'PHQ9_high': "MENTAL HEALTH CONTEXT: Patient has elevated depression scores (PHQ-9 moderate-severe). Approach with extra empathy. Validate their experience. Mention oncology social workers and CancerCare counseling (1-800-813-4673).",
    'GAD7_high': "MENTAL HEALTH CONTEXT: Patient has elevated anxiety scores (GAD-7 moderate-severe). Normalize anxiety during cancer treatment. Mention support resources and coping strategies.",
    'PSS10_high': "STRESS CONTEXT: Patient reports high stress (PSS-10). Acknowledge this explicitly. Suggest MBSR, oncology social worker referral, and Cancer Support Community programs. Stress during treatment is extremely common.",
    'ISI_high': "SLEEP CONTEXT: Patient reports significant insomnia (ISI). CRC-specific sleep disruptors include nocturia, dexamethasone, and ostomy concerns. CBT-I is the recommended first-line treatment for cancer-related insomnia."
}

CRC_SLEEP_GUIDANCE = """
SLEEP SUPPORT CONTEXT (ISI triggered):
- CRC-specific sleep disruptors: nocturia (especially after pelvic surgery), dexamethasone (causes insomnia on chemo days), ostomy bag anxiety, pain and neuropathy at night
- Practical tips: Ask about dexamethasone dosing early in day, sleep hygiene basics, CBT-I is evidence-based and preferred over sleep meds during chemo
- Resources: Society of Behavioral Sleep Medicine (behavioralsleep.org)
"""

# =============================================================================
# STRESS-IMMUNE EDUCATION (Item 8)
# =============================================================================

STRESS_IMMUNE_EDUCATION = """
STRESS-IMMUNE PATHWAY EDUCATION:
When discussing stress and its impact, follow these principles:

1. FRAMING (CRITICAL): Never imply or state that stress causes cancer or makes cancer worse.
   USE: "Managing stress supports your overall wellbeing and quality of life during treatment."
   AVOID: "Stress can make your cancer worse" or "reducing stress may help your cancer respond better."

2. SIMPLIFIED EXPLANATION (if patient asks about stress and immune system):
   During stress, the body releases hormones like cortisol and adrenaline. Over time, prolonged
   stress can affect immune function, sleep, and the ability to recover from treatment. Managing
   stress is not about fighting cancer — it is about feeling better, sleeping better, and having
   more energy. These are real, meaningful benefits.

3. EVIDENCE-BASED INTERVENTIONS:
   - Mindfulness-Based Stress Reduction (MBSR) — specifically studied in cancer populations
   - Exercise: Even light walking has documented benefits for mood and fatigue during chemo
   - Social support: Having people to talk to is one of the strongest predictors of wellbeing

4. RESOURCES:
   - Society for Integrative Oncology: integrativeonc.org
   - CancerCare Mind-Body Connection: cancercare.org
"""

# =============================================================================
# COMPASSIONATE USE / EXPANDED ACCESS (Item 12)
# =============================================================================

COMPASSIONATE_USE_GUIDANCE = """
EXPANDED ACCESS / COMPASSIONATE USE EDUCATION:
When a patient appears to have exhausted standard treatment options or asks about accessing
experimental treatments outside of clinical trials, educate them about FDA Expanded Access:

1. WHAT IT IS: FDA Expanded Access allows patients with serious or life-threatening conditions
   to access investigational drugs outside of a clinical trial when no comparable alternative exists.

2. HOW TO ACCESS IT:
   - Your oncologist must identify a drug still in trials that might help
   - The manufacturer must agree to provide it
   - FDA reviews and typically decides within days (>99% approval rate)
   - Resources:
     * FDA Project Facilitate: 1-855-543-3784
     * Reagan-Udall Foundation ExpandedAccessNavigator.org

3. KEY DISCLAIMERS (always include):
   - The product is not FDA-approved
   - Your physician must initiate the request
   - The manufacturer can decline
   - Insurance typically won't cover it
   - Clinical trials remain the preferred path when available

4. EMOTIONAL FRAMING: Frame as "additional treatment pathways" not "last resort."
"""

# =============================================================================
# CAREGIVER GUIDANCE (Item 10)
# =============================================================================

CAREGIVER_GUIDANCE = """
CAREGIVER SUPPORT CONTEXT:
When a user identifies as a caregiver or asks about helping a family member:

1. ACKNOWLEDGE THE CAREGIVER ROLE: Caregiving is one of the most demanding and loving acts.
   Validate their experience: exhaustion, fear, uncertainty, and grief are all normal.

2. CRC-SPECIFIC CAREGIVER TOPICS:
   - Ostomy care: Learning to manage ostomy appliances — UOAA has caregiver guides
   - Diet management: Food restrictions after surgery — ask about dietitian referral
   - Treatment schedule: Helping track chemo cycles, managing side effects at home
   - Emotional labor: Supporting a loved one through cancer takes a toll on caregivers too

3. CARE FOR THE CAREGIVER (always include):
   - Remind caregivers that their own wellbeing matters
   - Suggest respite care resources and peer caregiver support groups
   - Oncology social workers can support caregivers, not just patients

4. RESOURCES: CancerCare caregiver groups (800-813-4673), Lotsa Helping Hands, Caregiver Action Network
"""

# =============================================================================
# HOLISTIC WELLNESS (Item 11)
# =============================================================================

HOLISTIC_WELLNESS_GUIDANCE = """
HOLISTIC WELLNESS CONTEXT:
EVIDENCE-BASED WELLNESS INTERVENTIONS for CRC patients:

1. EXERCISE: ASCO and ACS recommend regular activity during and after treatment.
   - Even 30 minutes of walking 3x/week has documented benefits for fatigue and mood
   - Ask oncologist about activity restrictions (especially after surgery)
   - Livestrong at the YMCA: Free cancer-specific fitness programs

2. MIND-BODY PRACTICES:
   - MBSR: 8-week programs with strong evidence in cancer populations
   - Yoga for Cancer: Gentle, modified yoga safe during treatment
   - Progressive muscle relaxation: Can help with procedure anxiety

3. NUTRITION:
   - Ask for referral to oncology-certified dietitian (RD with CSO certification)
   - AICR has CRC-specific nutrition guides

4. SOCIAL CONNECTION:
   - Colontown peer support community (colontown.org): 11,000+ CRC patients
   - In-person support groups via Cancer Support Community
"""

# =============================================================================
# NUTRITION GUIDANCE (Phase 5)
# =============================================================================

CRC_NUTRITION_GUIDANCE = """
CRC-SPECIFIC NUTRITION CONTEXT:
When a user asks about diet, food, nutrition, eating, or weight during/after CRC treatment:

1. PHASE-BASED GUIDANCE (tailor to patient's treatment status):
   - Post-surgery: Low-residue diet, gradual fiber reintroduction over 6-12 weeks
   - During chemo: Small frequent meals, manage nausea with ginger/bland foods, increased protein (1.0-1.5g/kg/day)
   - Survivorship: AICR guidelines (plant-rich diet, limit red/processed meat, maintain healthy weight)

2. COMMON CHEMO SIDE EFFECT DIET TIPS:
   - Nausea: Cold/room-temp foods, ginger, crackers, eat between meals
   - Diarrhea (5-FU, irinotecan): BRAT diet, soluble fiber, replace electrolytes
   - Constipation (ondansetron, opioids): Increase fiber gradually, prune juice, fluids
   - Mouth sores (5-FU, capecitabine): Soft moist foods, avoid acidic/spicy, baking soda rinse
   - Neuropathy (oxaliplatin): Avoid cold foods/drinks during and 3-5 days after infusion
   - Metallic taste: Try cold meats, marinades, plastic utensils

3. STOMA-SPECIFIC (if applicable):
   - Chew thoroughly, drink between meals not during
   - Thickening foods: applesauce, banana, rice, peanut butter
   - Thinning foods: fruit juice, leafy greens, spicy food

4. EVIDENCE-BASED ANTI-RECURRENCE DIET:
   - Higher fiber intake associated with 18% lower CRC-specific mortality per 5g/day increase
   - Western diet pattern linked to 3.25x higher recurrence risk (JAMA Oncology 2018)
   - Cruciferous vegetables, berries, omega-3 fatty acids have supporting evidence
   - Limit: red meat under 18oz/week, avoid processed meat, limit alcohol

5. SUPPLEMENTS (always note: discuss with oncologist first):
   - Vitamin D: 1000-2000 IU daily (observational evidence for CRC outcomes)
   - Calcium: 1000-1200mg daily
   - Avoid high-dose antioxidant supplements during active chemotherapy

6. COMORBIDITY-AWARE NUTRITION:
   - Diabetes + CRC: Complex carbs, pair with protein, monitor glucose on steroids
   - Hypertension + CRC: DASH-compatible, limit sodium <2300mg, important with bevacizumab
   - Obesity + CRC: Moderate calorie focus post-treatment (not during active chemo)

7. REFERRAL: Suggest oncology-certified dietitian (CSO credential) via eatright.org

Always present nutrition information as educational. Do not prescribe specific diets."""

# SCREENING AMBASSADOR (Item 9)
# =============================================================================

SCREENING_AMBASSADOR_GUIDANCE = """
SCREENING AMBASSADOR CONTEXT:
When a user mentions a family member, friend, or asks about cancer prevention/screening for others:

1. KEY MESSAGES:
   - CRC is the #2 cancer killer in the US — but one of the most preventable with early screening
   - People with a first-degree relative with CRC should start screening at age 40, or 10 years
     before the relative's diagnosis, whichever is earlier
   - Screening options (present all equally):
     * Colonoscopy: Every 10 years; gold standard; removes polyps during the test
     * FIT test: Annual stool test; non-invasive; done at home
     * Cologuard: Every 3 years; stool DNA test; FDA-approved
     * CT Colonography: Every 5 years; non-invasive imaging

2. SHAREABLE FRAMING: "Getting screened means your family doesn't have to go through what you're going through."

3. RESOURCES: CDC Screen for Life (cdc.gov/colorectal-cancer/screening), ACS guidelines, Fight CRC
"""


def count_tokens(text: str) -> int:
    """Count tokens in text using tiktoken or approximate fallback."""
    if not text:
        return 0

    if TIKTOKEN_AVAILABLE and TOKEN_ENCODING:
        return len(TOKEN_ENCODING.encode(text))

    # Fallback: approximate 4 chars per token (conservative estimate)
    return len(text) // 4


def truncate_to_tokens(text: str, max_tokens: int, preserve_end: bool = False) -> str:
    """
    Truncate text to fit within token budget.

    Args:
        text: Text to truncate
        max_tokens: Maximum tokens allowed
        preserve_end: If True, keep end of text (for conversation history)
    """
    if not text:
        return text

    current_tokens = count_tokens(text)
    if current_tokens <= max_tokens:
        return text

    if TIKTOKEN_AVAILABLE and TOKEN_ENCODING:
        tokens = TOKEN_ENCODING.encode(text)
        if preserve_end:
            truncated_tokens = tokens[-max_tokens:]
        else:
            truncated_tokens = tokens[:max_tokens]
        return TOKEN_ENCODING.decode(truncated_tokens)

    # Fallback: approximate by character ratio
    char_limit = max_tokens * 4
    if preserve_end:
        return "..." + text[-char_limit:]
    return text[:char_limit] + "..."


def select_chunks_within_budget(chunks: list, max_tokens: int) -> str:
    """Select and format chunks that fit within token budget.
       Accepts List[str] or List[Dict] (with 'content' key).
       Labels each chunk with [Source N: filename §section] where N is 1-indexed
       position. The number N is what the LLM uses for inline citations [1], [2].
    """
    if not chunks:
        return "No specific guideline excerpts found for this query."

    selected = []
    current_tokens = 0
    source_number = 0  # 1-indexed counter for inline-citation alignment

    for i, chunk in enumerate(chunks):
        # Handle dict vs str
        if isinstance(chunk, dict):
            text = chunk.get('content', '') or chunk.get('chunk_text', '') or ""
            filename = chunk.get('filename', '') or 'medical guidelines'
            chunk_idx = chunk.get('chunk_index', '')
            clean_name = filename.replace('.pdf', '').replace('_', ' ')
        else:
            text = str(chunk)
            clean_name = 'medical guidelines'
            chunk_idx = ''

        if not text:
            continue

        # Tentatively assign next source number; only commit if we actually include it
        next_num = source_number + 1
        source_label = f"[Source {next_num}: {clean_name}" + (f" §{chunk_idx}" if chunk_idx != '' else '') + "]"
        labeled_text = f"{source_label}\n{text}"
        chunk_tokens = count_tokens(labeled_text)
        separator_tokens = 8 if i > 0 else 0

        if current_tokens + chunk_tokens + separator_tokens > max_tokens:
            if not selected:
                truncated = truncate_to_tokens(text, max_tokens - 80)
                selected.append(f"{source_label}\n{truncated}")
                source_number = next_num
            break

        selected.append(labeled_text)
        current_tokens += chunk_tokens + separator_tokens
        source_number = next_num

    if selected:
        return "\n\n".join(selected)
    return "No specific guideline excerpts found for this query."


# =============================================================================
# TONE SOFTENER — belt-and-suspenders for the "you should / you must" rule.
# =============================================================================
# The base system prompt forbids "you should" / "you must" / "tell your doctor"
# directed at the patient, and offers substitutions. LLMs still slip — ~5-22%
# of responses in baseline evals contained at least one forbidden phrase.
# This post-processor swaps the phrases in-place before the response reaches
# the user. Idempotent + telemetry-logged so we can track slip rate over time.

import re as _tone_re
import logging as _tone_logging

_tone_logger = _tone_logging.getLogger("llm_utils.tone")

# (regex pattern, replacement, label). Patterns are case-insensitive; word
# boundaries are explicit to avoid touching things like "youshouldbe" (rare
# but possible in raw text).
_TONE_SUBSTITUTIONS = [
    # The strongest violations first
    (r"\byou must\b", "it might help to", "you_must"),
    (r"\byou have to\b", "it might help to", "you_have_to"),
    (r"\byou need to\b", "it might help to", "you_need_to"),
    (r"\byou ought to\b", "it might help to", "you_ought_to"),
    (r"\byou should\b", "it might help to", "you_should"),
    # "Tell your doctor" as a standalone directive
    (r"\btell your (doctor|physician|oncologist|care team)\b",
     r"let your \1 know", "tell_your_doctor"),
]


def soften_tone(text: str) -> tuple[str, dict]:
    """
    Replace forbidden directive phrases with collaborative substitutions.

    Returns (softened_text, metadata) where metadata = {
        'substitutions': int,           # total replacements made
        'by_pattern': {label: count},   # per-pattern counts
    }
    """
    if not text:
        return text, {"substitutions": 0, "by_pattern": {}}
    out = text
    by_pattern: dict = {}
    total = 0
    for pattern, replacement, label in _TONE_SUBSTITUTIONS:
        out, n = _tone_re.subn(pattern, replacement, out, flags=_tone_re.IGNORECASE)
        if n:
            by_pattern[label] = n
            total += n
    if total:
        _tone_logger.info(
            "tone_softened total=%d by_pattern=%s",
            total, by_pattern,
        )
    return out, {"substitutions": total, "by_pattern": by_pattern}


# =============================================================================
# INLINE CITATION POST-PROCESSING (Feature 1)
# =============================================================================

import re as _re_citations


def postprocess_citations(response_text: str, retrieved_chunks: list, max_chunks: int = None):
    """
    Validate and extract inline [N] citation markers from an LLM response.

    Strips invalid markers (citing N higher than available chunks) and returns
    a citation_map keyed by the citation numbers that actually appeared in the
    final response.

    Returns:
        (cleaned_text, citation_map)
        citation_map: {N: {filename, section, preview, content}}

    Edge cases:
      - LLM cited [5] but only 3 chunks available → marker stripped from text
      - LLM produced no markers → returns (text, {}) — frontend falls back to bottom panel
      - Same N cited multiple times → single map entry, all renders point to same source
      - Combined markers like [1, 3] → split into individual [1] and [3] for rendering
    """
    if not response_text:
        return response_text, {}

    if not retrieved_chunks:
        # No chunks → strip ALL citation markers (LLM should not be citing)
        cleaned = _re_citations.sub(r'\s*\[\d+(?:\s*,\s*\d+)*\]', '', response_text)
        return cleaned, {}

    # Cap to the number of chunks we actually surfaced to the LLM in select_chunks_within_budget
    available = max_chunks if max_chunks is not None else len(retrieved_chunks)
    available = min(available, len(retrieved_chunks))

    # Find all [N] or [N, M, ...] patterns
    citation_pattern = _re_citations.compile(r'\[(\d+(?:\s*,\s*\d+)*)\]')

    cited_numbers = set()

    def _replace_marker(match):
        nums_str = match.group(1)
        nums = [int(n.strip()) for n in nums_str.split(',')]
        # Filter to valid numbers only
        valid_nums = [n for n in nums if 1 <= n <= available]
        if not valid_nums:
            # All invalid — strip entire marker
            return ''
        cited_numbers.update(valid_nums)
        # Reconstruct using only valid numbers
        if len(valid_nums) == 1:
            return f'[{valid_nums[0]}]'
        return '[' + ', '.join(str(n) for n in valid_nums) + ']'

    cleaned = citation_pattern.sub(_replace_marker, response_text)

    # Build citation_map for the numbers that actually survived
    citation_map = {}
    for n in cited_numbers:
        idx = n - 1  # convert to 0-indexed
        if idx >= len(retrieved_chunks):
            continue
        chunk = retrieved_chunks[idx]
        if not isinstance(chunk, dict):
            citation_map[n] = {
                'filename': 'medical guidelines',
                'section': None,
                'preview': str(chunk)[:140],
            }
            continue
        filename = chunk.get('filename', 'medical guidelines') or 'medical guidelines'
        content = chunk.get('content', '') or ''
        preview = content[:140].strip()
        if len(content) > 140:
            preview += '...'
        citation_map[n] = {
            'filename': filename.replace('.pdf', '').replace('_', ' '),
            'section': chunk.get('chunk_index'),
            'preview': preview,
        }

    return cleaned, citation_map


# =============================================================================
# FEATURE 2: PRE-VISIT QUESTION GENERATOR
# =============================================================================

PREVISIT_QUESTION_PROMPT = """You are helping a {cancer_kind} patient prepare for their next oncology visit. Generate a focused, profile-aware list of questions they can ask their care team.

PATIENT PROFILE:
{patient_summary}

PATIENT'S CONTEXT FOR THIS VISIT:
{user_context}

Generate 10–12 questions, grouped under 3–4 topical headers. Each question should be:
- Specific to this patient's diagnosis, treatment line, biomarkers, comorbidities, and stated context
- Answerable by an oncology team member in 1–2 minutes
- Phrased the way the patient would speak it (first person, plain language, no jargon)
- Practical — focused on what the patient can act on or understand

Avoid:
- Yes/no questions ("Is FOLFOX safe?") — prefer open-ended ("What side effects from FOLFOX should I expect to feel first?")
- Generic CRC questions that ignore this patient's profile
- Questions that ask the AI to diagnose or predict outcomes

OUTPUT FORMAT — strict JSON, no prose, no markdown:
{{
  "groups": [
    {{"topic": "Treatment plan and timing", "questions": ["...", "..."]}},
    {{"topic": "Side effects to expect", "questions": ["...", "..."]}},
    {{"topic": "Daily life and self-care", "questions": ["...", "..."]}}
  ]
}}

If the patient profile is empty or minimal, fall back to general CRC pre-visit questions but still group them.
Output ONLY the JSON object. No preamble, no explanation."""


# Process-local cache: key = sha256(profile_id + context), value = (timestamp, result_dict)
# Survives within a single serverless invocation; not shared across cold starts.
_PREVISIT_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_PREVISIT_CACHE_TTL_SEC = 300  # 5 minutes


def _previsit_cache_key(profile_id: str, context: str) -> str:
    import hashlib
    return hashlib.sha256(f"{profile_id}|{context}".encode('utf-8')).hexdigest()


def get_cached_previsit(profile_id: str, context: str):
    import time
    key = _previsit_cache_key(profile_id, context)
    entry = _PREVISIT_CACHE.get(key)
    if not entry:
        return None
    ts, result = entry
    if time.time() - ts > _PREVISIT_CACHE_TTL_SEC:
        _PREVISIT_CACHE.pop(key, None)
        return None
    return result


def set_cached_previsit(profile_id: str, context: str, result: Dict[str, Any]) -> None:
    import time
    key = _previsit_cache_key(profile_id, context)
    _PREVISIT_CACHE[key] = (time.time(), result)


def generate_previsit_questions(patient_summary: str, user_context: str, cancer_slug: str = None) -> Dict[str, Any]:
    """
    Run the pre-visit question prompt and parse JSON output.
    Returns: {'groups': [...], 'used_fallback': bool}

    Falls back to a generic question set if LLM call fails or JSON parsing fails.
    """
    from lib import cancer_registry as _registry
    cancer_kind = _registry.display_name(cancer_slug).lower()

    prompt = PREVISIT_QUESTION_PROMPT.format(
        cancer_kind=cancer_kind,
        patient_summary=patient_summary or "No profile information available.",
        user_context=user_context or "No specific context provided. Generate broad pre-visit questions for this patient."
    )

    try:
        answer, _api = call_llm(prompt, response_length="detailed", query_type="general", cancer_slug=cancer_slug)
        if not answer:
            raise RuntimeError("Empty LLM response")

        # Extract JSON object — LLM occasionally wraps in markdown
        match = _re_citations.search(r'\{[\s\S]*\}', answer)
        if not match:
            raise ValueError("No JSON object in response")
        parsed = json.loads(match.group(0))
        groups = parsed.get('groups', [])
        if not isinstance(groups, list) or not groups:
            raise ValueError("Empty or malformed groups")

        # Sanity-cap to 4 groups, 12 questions total
        cleaned = []
        total_q = 0
        for g in groups[:4]:
            if not isinstance(g, dict):
                continue
            topic = str(g.get('topic', 'General questions'))[:80]
            qs = g.get('questions', [])
            if not isinstance(qs, list):
                continue
            qs = [str(q)[:300] for q in qs if isinstance(q, (str, int))][:6]
            if total_q + len(qs) > 12:
                qs = qs[:12 - total_q]
            if qs:
                cleaned.append({'topic': topic, 'questions': qs})
                total_q += len(qs)
            if total_q >= 12:
                break

        if not cleaned:
            raise ValueError("All groups were filtered out")
        return {'groups': cleaned, 'used_fallback': False}
    except Exception as e:
        logger.warning(f"Pre-visit question generation fell back: {e}")
        return {
            'groups': _PREVISIT_FALLBACK_QUESTIONS,
            'used_fallback': True,
        }


_PREVISIT_FALLBACK_QUESTIONS = [
    {
        "topic": "Treatment plan and timing",
        "questions": [
            "What is the goal of this treatment plan — cure, slow progression, or symptom control?",
            "How long will I be on this regimen, and what milestones will tell us it's working?",
            "What scans or labs will we use to track my response?",
        ],
    },
    {
        "topic": "Side effects and what to watch for",
        "questions": [
            "Which side effects are most common, and which ones should I call you immediately for?",
            "What can I do at home to manage fatigue and nausea?",
            "Are there long-term side effects I should be aware of after treatment ends?",
        ],
    },
    {
        "topic": "Daily life and support",
        "questions": [
            "Are there foods or activities I should avoid during treatment?",
            "Who on the care team should I contact for non-urgent questions?",
            "What support services (social work, nutrition, mental health) are available?",
        ],
    },
]


# =============================================================================
# FEATURE 3: APPOINTMENT COMPANION (VISIT RECAP)
# =============================================================================

VISIT_RECAP_PROMPT = """You are helping a {cancer_kind} patient organize what happened at a recent oncology visit. The patient has provided their own notes (which may be informal, incomplete, or paraphrased). Your job is to extract a clean, structured recap.

PATIENT PROFILE (use this to detect contradictions or fill in gaps):
{patient_summary}

PATIENT'S VISIT NOTES:
{transcript}

Extract a structured recap. Be faithful to what the patient said — do NOT invent details, drugs, dose changes, or scan results that are not in their notes.

If the notes mention a treatment change that contradicts the patient's stored profile (e.g. they say "switching to FOLFIRI" but their profile shows FOLFOX), flag it under "flags".

If something is unclear ("doctor mentioned a new medication but I don't remember the name"), include it in "action_items" as a follow-up — do NOT guess.

OUTPUT FORMAT — strict JSON only:
{{
  "discussed": ["bullet 1", "bullet 2", "..."],
  "treatment_changes": ["change 1", "..."],
  "action_items": ["thing the patient should do", "..."],
  "follow_up_questions": ["question to bring next time", "..."],
  "flags": ["potential contradiction or thing worth confirming with the care team", "..."]
}}

Rules:
- Each list can be empty if nothing applies. Use [] not null.
- Each item should be 1 sentence, plain language, first-person where natural.
- "flags" is for things the patient should confirm with their care team (contradictions with profile, ambiguous instructions, missed information).
- Do NOT cite sources or use [N] markers in this output — this is a structured recap, not a generated medical answer.
- Output ONLY the JSON object. No preamble, no markdown."""


def generate_visit_recap(patient_summary: str, transcript: str, cancer_slug: str = None) -> Dict[str, Any]:
    """
    Run the visit recap prompt and parse JSON output.
    Returns: {'discussed': [...], 'treatment_changes': [...], 'action_items': [...],
              'follow_up_questions': [...], 'flags': [...], 'used_fallback': bool}

    Falls back to a plain-text best-effort structure if JSON parsing fails.
    """
    if not transcript or len(transcript.strip()) < 30:
        return {
            'discussed': [],
            'treatment_changes': [],
            'action_items': [],
            'follow_up_questions': [],
            'flags': ["The notes were too short to produce a meaningful recap. Try adding more detail or use the microphone."],
            'used_fallback': True,
        }

    # Soft cap; LLM doesn't need an essay
    if len(transcript) > 8000:
        transcript = transcript[:8000]

    from lib import cancer_registry as _registry
    cancer_kind = _registry.display_name(cancer_slug).lower()

    prompt = VISIT_RECAP_PROMPT.format(
        cancer_kind=cancer_kind,
        patient_summary=patient_summary or "No profile information available.",
        transcript=transcript,
    )

    try:
        answer, _api = call_llm(prompt, response_length="detailed", query_type="general")
        if not answer:
            raise RuntimeError("Empty LLM response")

        match = _re_citations.search(r'\{[\s\S]*\}', answer)
        if not match:
            raise ValueError("No JSON in response")
        parsed = json.loads(match.group(0))

        def _str_list(key, max_items=10, max_len=300):
            items = parsed.get(key, [])
            if not isinstance(items, list):
                return []
            cleaned = []
            for it in items[:max_items]:
                if isinstance(it, (str, int)):
                    s = str(it).strip()[:max_len]
                    if s:
                        cleaned.append(s)
            return cleaned

        return {
            'discussed': _str_list('discussed'),
            'treatment_changes': _str_list('treatment_changes'),
            'action_items': _str_list('action_items'),
            'follow_up_questions': _str_list('follow_up_questions'),
            'flags': _str_list('flags'),
            'used_fallback': False,
        }
    except Exception as e:
        logger.warning(f"Visit recap generation fell back: {e}")
        # Plain-text fallback: store the raw LLM output as a single discussed bullet
        return {
            'discussed': ["I had trouble parsing your notes into a structured recap, but I saved them. Your care team can review the full text."],
            'treatment_changes': [],
            'action_items': [],
            'follow_up_questions': [],
            'flags': ["Recap parsing failed — please review the transcript with your care team."],
            'used_fallback': True,
        }


# =============================================================================
# FEATURE 4: INSURANCE APPEAL LETTER DRAFTING
# =============================================================================

INSURANCE_APPEAL_PROMPT = """You are helping a {cancer_kind} patient draft a formal appeal letter for an insurance denial. Your draft will be reviewed by the patient and their oncology team before being sent — it is a starting point, not a final document.

PATIENT PROFILE (de-identified):
{patient_summary}

THE INSURANCE DENIAL (extracted from the patient's denial letter — may be incomplete):
{denial_text}

RELEVANT CLINICAL GUIDELINE EXCERPTS:
{guidelines}

Write a formal appeal letter the patient could send to their insurance company. Use this structure:

1. Header: "To: [Insurance Company]", "Re: Appeal of [denial reference, if extracted]", and the date.
2. Opening paragraph: state that the patient is formally appealing the denial, name the requested treatment/service, and reference the denial letter.
3. Clinical rationale (1–2 paragraphs): explain why this treatment is medically appropriate for this patient's diagnosis, stage, biomarkers, and treatment line. Be specific to the profile.
4. Guideline support (1–2 paragraphs): cite the provided guideline excerpts using inline numbered citations [1], [2], etc., per the SOURCE numbers in the guidelines section. Quote brief language from the excerpts where helpful.
5. Closing: request reconsideration, request a peer-to-peer review with the treating oncologist, list any supporting documents the patient can provide.

CRITICAL RULES:
- Use [1], [2] inline citations ONLY for claims drawn from the guideline excerpts above. Source N corresponds to the [Source N: ...] excerpt.
- DO NOT invent guideline language, statistics, or trial numbers not in the provided excerpts.
- If the requested treatment is NOT supported by the guidelines provided, say so directly in the letter rather than fabricating support — e.g., "While the standard NCCN pathway differs from the requested approach, my treating oncologist's clinical judgment supports..."
- Use the patient's de-identified profile only — do NOT include patient name, MRN, or DOB. Use placeholder "[Patient Name]" and "[Member ID]" the patient will fill in.
- Tone: professional, factual, respectful. Avoid emotional appeals; lead with clinical evidence.
- Length: 350–550 words.

Output ONLY the letter text. No preamble, no explanation, no markdown headers — write it in standard business letter form."""


def generate_insurance_appeal(patient_summary: str, denial_text: str, retrieved_chunks: list, guidelines_formatted: str, cancer_slug: str = None) -> Dict[str, Any]:
    """
    Run the insurance appeal prompt and return the draft + citation map.
    Returns: {'draft': str, 'citations': dict, 'used_fallback': bool}
    """
    if not denial_text or len(denial_text.strip()) < 50:
        return {
            'draft': "",
            'citations': {},
            'used_fallback': True,
            'error': 'Could not extract enough text from the denial letter. Try retyping the denial reason in the box below.',
        }

    from lib import cancer_registry as _registry
    cancer_kind = _registry.display_name(cancer_slug).lower()

    prompt = INSURANCE_APPEAL_PROMPT.format(
        cancer_kind=cancer_kind,
        patient_summary=patient_summary or "Profile information unavailable; the patient should fill in personal details before sending.",
        denial_text=denial_text[:4000],
        guidelines=guidelines_formatted or "No specific guideline excerpts available for this denial reason.",
    )

    try:
        answer, _api = call_llm(prompt, response_length="detailed", query_type="general", cancer_slug=cancer_slug)
        if not answer or len(answer.strip()) < 200:
            raise RuntimeError("LLM returned an unusable letter")

        # Run inline citation post-processor (Feature 1 reuse)
        cleaned, citation_map = postprocess_citations(answer, retrieved_chunks)
        return {
            'draft': cleaned,
            'citations': citation_map,
            'used_fallback': False,
        }
    except Exception as e:
        logger.warning(f"Insurance appeal generation fell back: {e}")
        return {
            'draft': "",
            'citations': {},
            'used_fallback': True,
            'error': "I couldn't draft a letter right now. Please try again, or describe the denial reason directly.",
        }


# =============================================================================
# FEATURE 5: DEEP-DIVE RESEARCH MODE
# =============================================================================

DEEP_RESEARCH_PROMPT = """You are producing a deep-dive research report for a {cancer_kind} patient or caregiver. The report should be thorough, structured, and grounded — and should explicitly hedge or refuse where the source excerpts do not support a confident answer.

PATIENT PROFILE (de-identified, may be empty):
{patient_summary}

THE QUESTION:
{query}

RELEVANT SOURCE EXCERPTS (NCCN/NCI/ASCO/CRC-specific):
{guidelines}

Write a structured report with these sections (use the exact section headers, in this order):

## Background
Brief framing of the question and why it matters for this patient (1 short paragraph).

## Current Evidence
What the provided source excerpts say about this question. Use inline numbered citations [1], [2] tied to the [Source N: ...] excerpts above. If sources conflict, present both. If sources are silent, say so explicitly.

## Treatment Options or Approaches
Each distinct approach as a sub-section header (### Option name) with: rationale, who it tends to fit, key trade-offs. Cite sources inline.

## Caveats & Uncertainty
What this report does NOT cover. Specific limitations of the evidence. Where individual factors (comorbidities, age, performance status) materially change the picture.

## Questions for Your Oncology Team
5–8 specific questions the patient should bring to their next visit, tailored to this question and their profile.

CRITICAL RULES:
- Use [N] inline citations ONLY where supported by the source excerpts.
- DO NOT invent statistics, drug names, dose numbers, NCT trial numbers, or guideline language not in the excerpts.
- If a section has insufficient source backing, write "The provided sources don't directly address this — please discuss with your care team."
- Tone: thorough but accessible. Avoid jargon. Use "you" / "your" naturally.
- Length: 800–1500 words.

Output the report directly. No preamble, no meta-commentary."""


SUBQUERY_DERIVATION_PROMPT = """The user asked a complex medical question. Generate 2–3 related sub-queries that would surface different relevant sub-topics from a colorectal cancer guideline corpus. Sub-queries should be different angles on the question — not paraphrases.

USER QUESTION: {query}

Output as a JSON array of 2–3 short search queries:
["sub-query 1", "sub-query 2", "sub-query 3"]

Output ONLY the JSON array. No prose."""


def derive_subqueries(query: str) -> List[str]:
    """
    Use Groq 8B (fast, cheap) to derive 2-3 sub-queries for multi-pass retrieval.
    Falls back to [] (caller treats as no sub-queries) if anything goes wrong.
    """
    try:
        client = get_groq_client()
        if not client:
            return []
        from model_registry import get_model
        prompt = SUBQUERY_DERIVATION_PROMPT.format(query=query[:500])
        completion = client.chat.completions.create(
            model=get_model("verifier"),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.2,
        )
        raw = (completion.choices[0].message.content or "").strip()
        match = _re_citations.search(r'\[[\s\S]*\]', raw)
        if not match:
            return []
        arr = json.loads(match.group(0))
        if not isinstance(arr, list):
            return []
        out = []
        for q in arr[:3]:
            if isinstance(q, str):
                q = q.strip()[:200]
                if q and q.lower() != query.lower():
                    out.append(q)
        return out
    except Exception as e:
        logger.warning(f"Sub-query derivation failed: {e}")
        return []


def parse_deep_research_sections(report_text: str) -> List[Dict[str, str]]:
    """
    Split a deep-research report into [{title, body}] sections by '## ' markers.
    """
    if not report_text:
        return []
    parts = _re_citations.split(r'^## ', report_text, flags=_re_citations.MULTILINE)
    sections = []
    # First part may be pre-amble (no header) — skip if empty
    leading = (parts[0] if parts else '').strip()
    if leading:
        sections.append({'title': 'Overview', 'body': leading})
    for chunk in parts[1:]:
        if not chunk.strip():
            continue
        lines = chunk.split('\n', 1)
        title = lines[0].strip()
        body = lines[1].strip() if len(lines) > 1 else ''
        sections.append({'title': title, 'body': body})
    return sections


def generate_deep_research(query: str, retrieved_chunks: list, patient_summary: str, cancer_slug: str = None) -> Dict[str, Any]:
    """
    Generate a structured deep-research report. Includes:
      - longer LLM call (max_tokens via response_length="detailed")
      - second-pass verification (reuses verify.py)
      - regenerate-once-on-fabrication
      - inline-citation post-processing (Feature 1)
      - section parsing

    Returns {report, sections, citations, verified, fabrication_risk, used_fallback}
    """
    if not query or not retrieved_chunks:
        return {
            'report': '',
            'sections': [],
            'citations': {},
            'verified': False,
            'fabrication_risk': 'unknown',
            'used_fallback': True,
        }

    from lib import cancer_registry as _registry
    cancer_kind = _registry.display_name(cancer_slug).lower()

    guidelines_formatted = select_chunks_within_budget(retrieved_chunks, 3500)
    prompt = DEEP_RESEARCH_PROMPT.format(
        cancer_kind=cancer_kind,
        patient_summary=patient_summary or "Profile information unavailable.",
        query=query,
        guidelines=guidelines_formatted,
    )

    try:
        # Primary report — use detailed length so max_tokens is generous
        report, _api = call_llm(prompt, response_length="detailed", query_type="general", cancer_slug=cancer_slug)
        if not report or len(report.strip()) < 200:
            raise RuntimeError("Empty or unusably short report")

        report = trim_incomplete_sentence(report)

        # Second-pass verification (heavy report → must be source-grounded)
        verified = True
        risk = 'unknown'
        try:
            from verify import verify_response, HEDGED_FALLBACK_RESPONSE
            verdict = verify_response(report, retrieved_chunks, query)
            verified = bool(verdict.get('verified', True))
            risk = verdict.get('fabrication_risk', 'unknown')
            if verdict.get('recommended_action') == 'regenerate':
                hedged_prompt = (
                    "CRITICAL: The previous draft contained unsupported claims. "
                    "You MUST hedge heavily and explicitly say where the sources do not address a question. "
                    "If specific details are not in the source excerpts, write 'The sources don't directly address this' "
                    "rather than fabricating. Do not invent statistics, drug names, dose numbers, or NCT trials.\n\n"
                    + prompt
                )
                retry_report, _ = call_llm(hedged_prompt, response_length="detailed", query_type="general")
                if retry_report and len(retry_report.strip()) > 200:
                    retry_report = trim_incomplete_sentence(retry_report)
                    retry_verdict = verify_response(retry_report, retrieved_chunks, query)
                    if retry_verdict.get('verified'):
                        report = retry_report
                        verified = True
                        risk = retry_verdict.get('fabrication_risk', risk)
                    else:
                        # Both attempts failed — return hedged fallback
                        return {
                            'report': HEDGED_FALLBACK_RESPONSE,
                            'sections': [{'title': "I'm not confident enough to answer this", 'body': HEDGED_FALLBACK_RESPONSE}],
                            'citations': {},
                            'verified': False,
                            'fabrication_risk': retry_verdict.get('fabrication_risk', 'high'),
                            'used_fallback': True,
                        }
        except Exception as e:
            logger.warning(f"Deep research verification failed (continuing): {e}")

        # Inline citation post-processing (Feature 1)
        cleaned_report, citation_map = postprocess_citations(report, retrieved_chunks)
        sections = parse_deep_research_sections(cleaned_report)

        return {
            'report': cleaned_report,
            'sections': sections,
            'citations': citation_map,
            'verified': verified,
            'fabrication_risk': risk,
            'used_fallback': False,
        }
    except Exception as e:
        logger.exception(f"Deep research generation failed: {e}")
        return {
            'report': '',
            'sections': [],
            'citations': {},
            'verified': False,
            'fabrication_risk': 'unknown',
            'used_fallback': True,
        }


def classify_query_type(message: str) -> str:
    """
    Classify the query into categories to determine what context is relevant.
    Returns: clinical_trial | treatment | side_effect | prognosis | diagnosis | general
    """
    message_lower = message.lower()

    clinical_trial_keywords = [
        'clinical trial', 'clinical trials', 'clinical study', 'clinical studies',
        'research study', 'research studies', 'experimental treatment',
        'investigational', 'trial eligibility', 'find trials', 'search trials',
        'trial options', 'trials near me', 'trial for my cancer',
        'phase 1', 'phase 2', 'phase 3', 'phase i', 'phase ii', 'phase iii',
        'nct', 'recruiting', 'enroll in a trial', 'participate in research'
    ]

    treatment_keywords = [
        'treatment', 'therapy', 'chemotherapy', 'chemo', 'radiation', 'surgery',
        'medication', 'drug', 'regimen', 'folfox', 'folfiri', 'immunotherapy',
        'targeted therapy', 'option', 'next step'
    ]

    side_effect_keywords = [
        'side effect', 'symptom', 'pain', 'nausea', 'fatigue', 'tired',
        'neuropathy', 'diarrhea', 'constipation', 'vomit', 'fever', 'rash',
        'toxicity', 'adverse', 'reaction', 'feeling', 'hurt', 'ache'
    ]

    prognosis_keywords = [
        'prognosis', 'survival', 'outcome', 'life expectancy', 'cure',
        'remission', 'progression', 'spread', 'metastasis', 'stage',
        'how long', 'will i', 'chance', 'likely',
        'going to die', 'will i die', 'am i dying', 'die from',
        'hope for', 'any hope'
    ]

    diagnosis_keywords = [
        'diagnosis', 'test', 'scan', 'biopsy', 'ct', 'mri', 'pet',
        'blood work', 'lab', 'marker', 'cea', 'biomarker', 'genetic'
    ]

    profile_keywords = [
        'profile', 'my info', 'about me', 'my data', 'my record',
        'who am i', 'what do you know', 'patient info'
    ]

    # Caregiver queries (Item 10)
    caregiver_keywords = [
        'caregiver', 'caring for', 'taking care of', 'family member', 'loved one',
        'my husband', 'my wife', 'my mother', 'my father',
        'my partner', 'my spouse', 'help my husband', 'help my wife',
        'support my', 'helping my'
    ]

    # Screening ambassador queries (Item 9)
    family_screening_keywords = [
        'my family', 'my children', 'my kids', 'my sister', 'my brother',
        'should they get tested', 'should they get screened', 'genetic risk',
        'family screening', 'screening for my', 'colonoscopy for',
        'should my family', 'family get screened', 'family get tested',
        'hereditary risk', 'risk for my'
    ]

    # Emotional/wellness queries (Items 8, 11)
    emotional_keywords_classify = [
        'stress', 'anxious', 'anxiety', 'scared', 'depressed', 'cope', 'coping',
        'emotional', 'mindfulness', 'meditation', 'wellness', 'yoga', 'exercise',
        'giving up', 'hopeless', 'overwhelmed', 'crying', 'can\'t stop',
        'feeling down', 'losing hope', 'afraid', 'worried', 'immune system'
    ]

    # Nutrition queries (Phase 5)
    nutrition_keywords = [
        'diet', 'food', 'eat', 'eating', 'nutrition', 'meal', 'recipe',
        'fiber', 'protein', 'vitamin', 'supplement', 'weight',
        'stoma', 'colostomy', 'ileostomy', 'low-residue', 'low residue',
        'nausea food', 'what to eat', 'what should i eat', 'appetite',
        'cooking', 'grocery', 'calorie', 'sugar', 'sodium'
    ]

    # Weighted scoring: multi-word phrases get bonus to beat single-word overlaps
    def _weighted_score(keywords, text):
        score = 0
        for kw in keywords:
            if kw in text:
                score += 2 if ' ' in kw else 1  # multi-word phrases count double
        return score

    scores = {
        'clinical_trial': _weighted_score(clinical_trial_keywords, message_lower),
        'treatment': _weighted_score(treatment_keywords, message_lower),
        'side_effect': _weighted_score(side_effect_keywords, message_lower),
        'prognosis': _weighted_score(prognosis_keywords, message_lower),
        'diagnosis': _weighted_score(diagnosis_keywords, message_lower),
        'profile': _weighted_score(profile_keywords, message_lower),
        'caregiver': _weighted_score(caregiver_keywords, message_lower),
        'screening_ambassador': _weighted_score(family_screening_keywords, message_lower),
        'emotional': _weighted_score(emotional_keywords_classify, message_lower),
        'nutrition': _weighted_score(nutrition_keywords, message_lower),
    }

    # Boost: "side effect" phrase or specific symptoms strongly indicate side_effect category
    if 'side effect' in message_lower or 'side effects' in message_lower:
        scores['side_effect'] += 3
    # Symptom words strongly indicate side_effect even when treatment drugs mentioned
    symptom_words = ['nausea', 'diarrhea', 'vomiting', 'fatigue', 'neuropathy', 'pain', 'rash', 'fever',
                     'numbness', 'tingling', 'mouth sores', 'hair loss', 'constipation']
    if any(sw in message_lower for sw in symptom_words):
        scores['side_effect'] += 3

    # Boost: caregiver context overrides side_effect when caring-for language present
    if scores['caregiver'] > 0 and any(kw in message_lower for kw in
            ['help my', 'my wife', 'my husband', 'caring for', 'caregiver', 'my mother', 'my father']):
        scores['caregiver'] += 3

    # Boost: clinical trial context for trial-related questions
    if 'trial' in message_lower or 'randomized' in message_lower or 'placebo' in message_lower:
        scores['clinical_trial'] += 2

    # Boost: treatment when drug names or "safe" + drug mentioned
    treatment_drug_names = ['bevacizumab', 'cetuximab', 'panitumumab', 'regorafenib', 'pembrolizumab',
                            'nivolumab', 'encorafenib', 'capecitabine', 'oxaliplatin', 'irinotecan']
    if any(d in message_lower for d in treatment_drug_names):
        scores['treatment'] += 2

    max_score = max(scores.values())
    if max_score == 0:
        return 'general'

    for category, score in scores.items():
        if score == max_score:
            return category

    return 'general'


def should_suggest_clinical_trials(query_type: str, patient_context: Dict[str, Any], message: str) -> bool:
    """
    Determine if we should proactively mention clinical trials availability.

    Triggers when:
    - Query is about treatment AND patient is metastatic (Stage IV)
    - Query suggests treatment resistance or progression
    - Patient is asking about next options or alternatives

    Args:
        query_type: The classified query type ('treatment', 'side_effect', etc.)
        patient_context: Patient profile data
        message: The user's question

    Returns:
        True if clinical trials should be proactively suggested
    """
    # Don't suggest trials if the query is already about clinical trials
    if query_type not in ('treatment',):
        return False

    if not patient_context:
        return False

    message_lower = message.lower()

    # Check for metastatic/Stage IV disease
    stage = str(patient_context.get('stage', '')).upper()
    is_metastatic = 'IV' in stage or '4' in stage or 'METASTATIC' in stage.upper()

    # Check for treatment resistance/progression language
    resistance_indicators = [
        'not working', 'stopped working', 'progressed', 'spread',
        'failed', 'resistant', 'progression', 'growing', 'worse'
    ]
    has_resistance_context = any(ind in message_lower for ind in resistance_indicators)

    # Check for "next options" language
    next_options_indicators = [
        'next step', 'other option', 'alternative', 'what else',
        'if this fails', 'after this', 'what\'s next', 'backup',
        'second line', 'third line', 'more options'
    ]
    asking_about_options = any(ind in message_lower for ind in next_options_indicators)

    return is_metastatic or has_resistance_context or asking_about_options


def filter_relevant_context(patient_context: Dict[str, Any], query_type: str, message: str) -> str:
    """Provides full patient context without selective filtering for richer AI understanding."""
    if not patient_context:
        return "No patient profile available."

    full_context = []

    # Demographics (de-identified: no name, no zip code)
    age = patient_context.get('age')
    if age:
        full_context.append(f"Patient: {age} years old")
        
    race = patient_context.get('race_ethnicity', 'unspecified')
    if race != 'unspecified':
        full_context.append(f"Race/Ethnicity: {race}")

    # Diagnosis & Stage (with colon vs rectal distinction for CT-14)
    cancer_type = patient_context.get('cancer_type', 'unspecified cancer')
    cancer_label = cancer_type
    cancer_lower = cancer_type.lower() if cancer_type else ''
    if 'rectal' in cancer_lower and 'colon' not in cancer_lower:
        cancer_label = f"{cancer_type} (rectal cancer — treatment may differ from colon cancer)"
    elif 'colon' in cancer_lower and 'rectal' not in cancer_lower:
        cancer_label = f"{cancer_type} (colon cancer — not rectal)"

    stage = patient_context.get('stage', 'unspecified')
    if stage != 'unspecified':
        full_context.append(f"Diagnosis: {cancer_label}, stage {stage}")
        # Advanced disease flag for Stage IV (Item 13)
        stage_check = str(stage).upper()
        if any(x in stage_check for x in ['IV', '4']) or 'METASTATIC' in stage_check:
            full_context.append("ADVANCED DISEASE FLAG: Stage IV — apply palliative care awareness, SPIKES protocol, tone sensitivity")
    else:
        full_context.append(f"Diagnosis: {cancer_label}")

    # Treatment Info
    treatments = patient_context.get('current_treatments', [])
    if treatments:
        full_context.append(f"Treatments: {', '.join(treatments)}")

    current_cycle = patient_context.get('current_cycle_number')
    treatment_line = patient_context.get('treatment_line')
    current_regimen = patient_context.get('current_regimen')
    if current_cycle and current_regimen:
        cycle_info = get_cycle_context(current_regimen, treatment_line, current_cycle)
        if cycle_info:
            full_context.append(f"Treatment status: {cycle_info}")

    # Auto-detect treatment line if not set but regimen is known (Item 2)
    treatment_line_val = patient_context.get('treatment_line')
    current_regimen_val = patient_context.get('current_regimen')
    if not treatment_line_val and current_regimen_val:
        try:
            from profile_utils import auto_detect_treatment_line
            detection = auto_detect_treatment_line(current_regimen_val)
            if detection.get('detected') and detection.get('confidence') in ('high', 'medium'):
                confidence_word = "" if detection['confidence'] == 'high' else " (likely)"
                full_context.append(
                    f"Treatment line{confidence_word}: {detection['display']} — {detection['note']}"
                )
        except ImportError:
            pass

    # Biomarkers
    biomarkers = patient_context.get('biomarkers', 'unspecified')
    if biomarkers != 'unspecified' and biomarkers:
        full_context.append(f"Biomarkers: {biomarkers}")
        # Explicit warnings for AI
        if 'MSS' in biomarkers or 'Microsatellite Stable' in biomarkers:
            full_context.append("⚠️ MSI Status: MSS - immunotherapy/checkpoint inhibitors likely ineffective")
        elif 'MSI-H' in biomarkers or 'MSI-High' in biomarkers or 'Unstable' in biomarkers:
            full_context.append("✓ MSI Status: MSI-H - may respond to immunotherapy")

    # Medications & History
    meds = patient_context.get('medications', [])
    if meds:
        full_context.append(f"Medications: {', '.join(meds)}")

    history = patient_context.get('medical_history', [])
    if history:
        full_context.append(f"History: {', '.join(history)}")

    allergies = patient_context.get('allergies', 'none reported')
    if allergies != 'none reported':
        full_context.append(f"Allergies: {allergies}")

    # Status & Sites
    status = patient_context.get('performance_status', 'unspecified')
    if status != 'unspecified':
        full_context.append(f"Performance: {status}")

    sites = patient_context.get('disease_sites', [])
    if sites:
        full_context.append(f"Disease sites: {', '.join(sites)}")

    # Symptoms
    symptoms = patient_context.get('symptoms', [])
    if symptoms:
        full_context.append(f"Recent symptoms: {', '.join(symptoms)}")

    # Patient-reported symptom check-in (from dashboard)
    symptom_report = patient_context.get('recent_symptom_report', [])
    if symptom_report:
        report_date = patient_context.get('symptom_report_date', '')
        full_context.append(f"Patient-reported symptoms: {', '.join(symptom_report)}")

    return " | ".join(full_context)


def get_response_settings(response_length: str, query_type: str = None, cancer_slug: str = None) -> Dict[str, Any]:
    """Get max_tokens, temperature, and system message based on response length setting.

    When query_type is 'treatment', token budgets are boosted to accommodate
    presenting ALL guideline options without truncation.

    cancer_slug selects the per-cancer prompt overlay. None falls back to
    colorectal (the registry default) so legacy callers behave identically.
    """
    base_system = _assemble_system_prompt(cancer_slug)
    is_treatment = query_type == 'treatment'
    is_clinical_trial = query_type == 'clinical_trial'
    needs_boost = is_treatment or is_clinical_trial

    if response_length == "brief":
        return {
            "max_tokens": 200 if needs_boost else 150,
            "temperature": 0.2 if is_clinical_trial else 0.3,
            "system_message": base_system + "\n\nRESPONSE LENGTH: Brief (1-2 sentences). Be concise but still warm and helpful.",
            "prompt_instruction": "Answer in 1-2 sentences using simple words. Be concise but complete.",
            "include_resources": False  # Don't add resources for brief responses
        }
    elif response_length == "detailed":
        return {
            "max_tokens": 600 if needs_boost else 400,
            "temperature": 0.2 if is_clinical_trial else 0.4,
            "system_message": base_system + "\n\nRESPONSE LENGTH: Detailed (4-6 sentences). Be thorough. Explain medical terms. Include relevant context.",
            "prompt_instruction": "Answer in 4-6 sentences. Explain any medical terms in plain language. Be thorough.",
            "include_resources": True
        }
    else:  # normal (default)
        return {
            "max_tokens": 400 if needs_boost else 250,
            "temperature": 0.2 if is_clinical_trial else 0.35,
            "system_message": base_system + "\n\nRESPONSE LENGTH: Normal (2-4 sentences). Balance conciseness with helpfulness.",
            "prompt_instruction": "Answer in 2-4 sentences using simple words. Be clear and helpful.",
            "include_resources": True
        }


def format_conversation_context(history: List[Dict[str, str]], max_tokens: int = None) -> str:
    """
    Format conversation history for inclusion in prompt with token budgeting.

    Uses sliding window to include most recent messages within token budget.
    """
    if not history:
        return ""

    if max_tokens is None:
        max_tokens = TOKEN_BUDGET['history']

    # Start from most recent and work backwards
    formatted_parts = []
    current_tokens = 20  # Reserve for header

    for entry in reversed(history):
        question = entry.get('question', '')
        answer = entry.get('answer', '')

        # Truncate long answers
        if count_tokens(answer) > 100:
            answer = truncate_to_tokens(answer, 100)

        entry_text = f"Q: {question}\nA: {answer}"
        entry_tokens = count_tokens(entry_text)

        if current_tokens + entry_tokens > max_tokens:
            break

        formatted_parts.insert(0, entry_text)
        current_tokens += entry_tokens

    if not formatted_parts:
        return ""

    return "PREVIOUS CONVERSATION:\n" + "\n\n".join(formatted_parts)


def assemble_prompt(message: str, retrieved: list, patient: dict,
                    response_length: str = "normal", conversation_context: str = "",
                    patient_context: Dict[str, Any] = None) -> Tuple[str, dict]:
    """
    Enhanced prompt assembly with:
    - Query-relevant context filtering
    - Symptom urgency detection
    - Biomarker implications
    - Neuropathy-specific guidance
    - Token budgeting

    Returns:
        Tuple of (prompt_string, metadata_dict)
        metadata_dict includes urgency info, query_type, etc.
    """
    query_type = classify_query_type(message)
    cancer_slug = (patient_context or {}).get('cancer_slug') if patient_context else None
    settings = get_response_settings(response_length, query_type=query_type, cancer_slug=cancer_slug)

    if patient_context is None:
        patient_context = {}

    # ==========================================================================
    # STEP 0: De-identify patient data before sending to external LLM APIs
    # ==========================================================================
    from deidentify import deidentify_patient_context, deidentify_raw_profile, deidentify_conversation_context
    patient_context = deidentify_patient_context(patient_context)
    patient = deidentify_raw_profile(patient)
    conversation_context = deidentify_conversation_context(conversation_context)

    # ==========================================================================
    # STEP 1: Detect symptom urgency FIRST
    # ==========================================================================
    urgency_info = detect_symptom_urgency(message, patient_context)

    # ==========================================================================
    # STEP 2: Get filtered patient context (concise, query-relevant)
    # ==========================================================================
    filtered_context = filter_relevant_context(patient_context, query_type, message)
    filtered_context = truncate_to_tokens(filtered_context, TOKEN_BUDGET['patient'])

    # ==========================================================================
    # STEP 3: Add biomarker implications for treatment/prognosis queries
    # ==========================================================================
    biomarker_context = ""
    if query_type in ['treatment', 'prognosis', 'diagnosis']:
        # Get raw biomarkers from patient profile
        raw_biomarkers = patient.get('primaryDiagnosis', {}).get('biomarkers', {}) if patient else {}
        if raw_biomarkers:
            try:
                from profile_utils import get_biomarker_implications, extract_biomarkers_summary
                implications = get_biomarker_implications(raw_biomarkers)
                if implications:
                    biomarker_context = "\n\nBIOMARKER IMPLICATIONS (use these to inform your answer):\n"
                    for impl in implications:
                        biomarker_context += f"• {impl}\n"
            except ImportError:
                pass  # profile_utils not available

    # ==========================================================================
    # STEP 3b: Add comorbidity interaction context (Item 1)
    # ==========================================================================
    comorbidity_context = ""
    if query_type in ['treatment', 'side_effect', 'prognosis']:
        comorbidities = patient_context.get('medical_history', [])
        if comorbidities:
            try:
                from profile_utils import get_comorbidity_interactions
                interactions = get_comorbidity_interactions(comorbidities, query_type)
                if interactions:
                    comorbidity_context = "\n\nCOMORBIDITY INTERACTIONS (personalize your answer with these):\n"
                    for interaction in interactions:
                        comorbidity_context += f"• {interaction}\n"
            except ImportError:
                pass

    # ==========================================================================
    # STEP 4: Add neuropathy guidance if relevant
    # ==========================================================================
    neuropathy_context = ""
    message_lower = message.lower()
    neuropathy_keywords = ['neuropathy', 'tingling', 'numbness', 'fingers', 'toes', 'nerve', 'peripheral']
    is_neuropathy_question = any(kw in message_lower for kw in neuropathy_keywords)

    # Check if patient is on oxaliplatin-based regimen
    current_treatments = patient_context.get('current_treatments', [])
    on_oxaliplatin = any('folfox' in str(tx).lower() or 'oxaliplatin' in str(tx).lower()
                         for tx in current_treatments)

    if is_neuropathy_question and on_oxaliplatin:
        neuropathy_context = "\n\n" + OXALIPLATIN_NEUROPATHY_GUIDANCE

    # ==========================================================================
    # STEP 4b: Add colonoscopy surveillance guidelines if relevant (V3 Step 4)
    # ==========================================================================
    colonoscopy_context = ""
    colonoscopy_keywords = ['colonoscopy', 'surveillance', 'follow-up', 'follow up', 'after treatment']
    is_colonoscopy_question = any(kw in message_lower for kw in colonoscopy_keywords)

    if is_colonoscopy_question or query_type == 'survivorship':
        colonoscopy_context = "\n\n" + COLONOSCOPY_SURVEILLANCE_GUIDELINES

    # ==========================================================================
    # STEP 4c: Add emotional support guidance if relevant (V3 Step 6)
    # ==========================================================================
    emotional_context = ""
    emotional_keywords = ['anxious', 'anxiety', 'scared', 'fear', 'worried', 'depressed', 'sad', 'emotional', 'cope', 'coping', 'family', 'tell']
    is_emotional_question = any(kw in message_lower for kw in emotional_keywords)

    if is_emotional_question or query_type == 'emotional':
        emotional_context = "\n\n" + EMOTIONAL_SUPPORT_GUIDANCE

    # ==========================================================================
    # STEP 4h: Tone calibration based on ANP framework (Item 6)
    # ==========================================================================
    tone_context = ""
    tone_sensitivity = 'low'
    if any(kw in message_lower for kw in TONE_SENSITIVITY_LEVELS['high']):
        tone_sensitivity = 'high'
    elif any(kw in message_lower for kw in TONE_SENSITIVITY_LEVELS['medium']):
        tone_sensitivity = 'medium'

    if tone_sensitivity in ('high', 'medium'):
        tone_context = f"\n\n{ANP_TONE_INSTRUCTION}\nSENSITIVITY LEVEL: {tone_sensitivity.upper()} — Apply full ANP framework."

    # ==========================================================================
    # STEP 4d: Detect bevacizumab in adjuvant setting (V3 Step 7)
    # ==========================================================================
    treatment_warning = ""
    treatment_line = patient_context.get('treatment_line', '')
    current_regimen = patient_context.get('current_regimen', '')

    if treatment_line == 'Adjuvant' and current_regimen and 'bevacizumab' in current_regimen.lower():
        treatment_warning = """
NOTE: Patient is receiving bevacizumab in the adjuvant setting. Bevacizumab is NOT typically recommended for standard adjuvant treatment in stage II/III colon cancer (per NCCN guidelines). This may indicate:
- Enrollment in a clinical trial
- Physician decision based on specific patient factors
This is a reasonable question to bring to their next appointment. It doesn't mean anything is wrong—treatment plans are sometimes individualized based on factors not captured in general guidelines."""

    # ==========================================================================
    # STEP 4e: Detect immunotherapy questions and add MSI context (V4 Step 1)
    # ==========================================================================
    msi_context = ""
    immunotherapy_keywords = ['immunotherapy', 'checkpoint', 'pembrolizumab', 'keytruda', 'nivolumab', 'opdivo']
    is_immunotherapy_question = any(kw in message_lower for kw in immunotherapy_keywords)

    if is_immunotherapy_question:
        biomarkers = patient_context.get('biomarkers', '')
        if 'MSS' in biomarkers or 'Microsatellite Stable' in biomarkers:
            msi_context = "\n\n⚠️ IMPORTANT MSI STATUS: Patient is MSS (Microsatellite Stable). Checkpoint inhibitors/immunotherapy are unlikely to be effective as standalone treatment for MSS colorectal cancer. Other treatment options remain available."
        elif 'MSI-H' in biomarkers or 'MSI-High' in biomarkers:
            msi_context = "\n\n✓ MSI STATUS: Patient is MSI-H (Microsatellite Instability-High). May respond well to immunotherapy/checkpoint inhibitors."

    # ==========================================================================
    # STEP 4f: Add FIT test guidance if relevant (V4 Step 3)
    # ==========================================================================
    fit_test_context = ""
    fit_keywords = ['fit test', 'fecal', 'stool test', 'fit vs', 'colonoscopy vs']
    is_fit_question = any(kw in message_lower for kw in fit_keywords)

    if is_fit_question:
        fit_test_context = "\n\n" + FIT_TEST_GUIDANCE

    # ==========================================================================
    # STEP 4g: Add prognosis context for stage questions (V4 Step 7 + Item 13)
    # ==========================================================================
    prognosis_context = ""
    stage_keywords = ['stage iii', 'stage 3', 'what stage', 'my stage', 'stage iiib', 'stage 3b',
                      'stage iv', 'stage 4', 'prognosis', 'how long', 'survival', 'cure',
                      'palliative', 'hospice', 'end of life', 'advanced']
    is_stage_question = any(kw in message_lower for kw in stage_keywords)
    stage = patient_context.get('stage', '')
    stage_upper = str(stage).upper()

    # Detect Stage IV
    is_stage_iv = any(x in stage_upper for x in ['IV', '4']) or 'METASTATIC' in stage_upper

    if is_stage_iv and (is_stage_question or query_type == 'prognosis'):
        prognosis_context = f"\n\n{STAGE_IV_PALLIATIVE_CONTEXT}"
        if 'IV' in STAGE_PROGNOSIS_CONTEXT:
            prognosis_context += f"\n\nPROGNOSIS CONTEXT:\n{STAGE_PROGNOSIS_CONTEXT['IV']}"
    elif is_stage_question and stage:
        if stage_upper in STAGE_PROGNOSIS_CONTEXT:
            prognosis_context = f"\n\nPROGNOSIS CONTEXT:\n{STAGE_PROGNOSIS_CONTEXT[stage_upper]}"

    # ==========================================================================
    # STEP 4i: Stress-immune education (Item 8)
    # ==========================================================================
    stress_education_context = ""
    stress_immune_keywords = ['stress', 'immune', 'cortisol', 'mind-body', 'meditation', 'mindfulness', 'relaxation']
    if any(kw in message_lower for kw in stress_immune_keywords) and query_type in ('emotional', 'general'):
        stress_education_context = f"\n\n{STRESS_IMMUNE_EDUCATION}"

    # ==========================================================================
    # STEP 4j: Compassionate use context (Item 12)
    # ==========================================================================
    compassionate_use_context = ""
    exhausted_keywords = ['out of options', 'nothing else', 'no more treatments',
                           'compassionate use', 'expanded access', 'everything failed',
                           'third line', 'fourth line', 'last option', 'nothing left']
    if any(kw in message_lower for kw in exhausted_keywords):
        compassionate_use_context = f"\n\n{COMPASSIONATE_USE_GUIDANCE}"

    # ==========================================================================
    # STEP 4k: Caregiver-specific context (Item 10)
    # ==========================================================================
    caregiver_context = ""
    if query_type == 'caregiver':
        caregiver_context = f"\n\n{CAREGIVER_GUIDANCE}"

    # ==========================================================================
    # STEP 4l: Screening ambassador context (Item 9)
    # ==========================================================================
    ambassador_context = ""
    if query_type == 'screening_ambassador':
        ambassador_context = f"\n\n{SCREENING_AMBASSADOR_GUIDANCE}"

    # ==========================================================================
    # STEP 4m: Holistic wellness context (Item 11)
    # ==========================================================================
    wellness_context = ""
    wellness_keywords = ['yoga', 'exercise', 'mindfulness', 'wellness', 'holistic', 'integrative', 'lifestyle']
    if any(kw in message_lower for kw in wellness_keywords) and query_type in ('emotional', 'general'):
        wellness_context = f"\n\n{HOLISTIC_WELLNESS_GUIDANCE}"

    # ==========================================================================
    # STEP 4i: Nutrition guidance (Phase 5)
    # ==========================================================================
    nutrition_context = ""
    nutrition_kws = ['diet', 'food', 'eat', 'nutrition', 'meal', 'fiber', 'stoma',
                     'colostomy', 'ileostomy', 'weight', 'supplement', 'vitamin']
    if query_type == 'nutrition' or any(kw in message_lower for kw in nutrition_kws):
        nutrition_context = f"\n\n{CRC_NUTRITION_GUIDANCE}"

    # ==========================================================================
    # STEP 4j: Surveillance schedule context for follow-up questions
    # ==========================================================================
    surveillance_context = ""
    surveillance_keywords = ['follow-up', 'follow up', 'next appointment', 'next colonoscopy',
                              'surveillance', 'how often', 'when should i', 'after treatment',
                              'monitoring', 'cea test', 'ct scan']
    if any(kw in message_lower for kw in surveillance_keywords):
        try:
            from surveillance import generate_surveillance_schedule, format_surveillance_for_chat
            stage = patient_context.get('stage', '')
            # Try to get surgery date from raw profile
            surgery_date = None
            if patient:
                for s in patient.get('surgicalHistory', []):
                    if isinstance(s, dict) and s.get('date'):
                        surgery_date = s['date']
                        break
            if stage and surgery_date:
                sched = generate_surveillance_schedule(stage, surgery_date)
                surveillance_context = "\n\n" + format_surveillance_for_chat(sched)
        except Exception:
            pass  # Surveillance not available

    # ==========================================================================
    # STEP 5: Format retrieved guidelines with token budget
    # ==========================================================================
    if retrieved:
        chunk_budget = 2500 if query_type in ('treatment', 'clinical_trial') else TOKEN_BUDGET['chunks']
        guideline_context = select_chunks_within_budget(retrieved, chunk_budget)
        chunks_used = guideline_context.count('---GUIDELINE EXCERPT---') + 1 if guideline_context else 0
        guideline_note = f"Based on {chunks_used} relevant guideline section(s):"
        logger.info(f"Prompt using {chunks_used} chunks, {count_tokens(guideline_context)} tokens for guidelines")
    else:
        guideline_context = "No specific guideline excerpts found for this query."
        guideline_note = "Based on general cancer care knowledge:"

    # ==========================================================================
    # STEP 6: Build urgency-aware instructions
    # ==========================================================================
    urgency_instruction = ""
    if urgency_info['detected']:
        if urgency_info['urgency'] == 'emergency':
            urgency_instruction = f"""
CRITICAL - EMERGENCY DETECTED: Start your response with this exact guidance:
"{urgency_info['guidance']}"
Then include these ER preparation tips:
{ER_PREPARATION_TIPS}
Then provide additional context."""
        elif urgency_info['urgency'] == 'urgent':
            urgency_instruction = f"""
IMPORTANT - URGENT SYMPTOM DETECTED: Include this guidance prominently in your response:
"{urgency_info['guidance']}"
Provide interim management tips while they await medical consultation."""
        elif urgency_info['urgency'] == 'distress':
            import random
            from tone_config import SOFTENING_PHRASES
            comfort = random.choice(SOFTENING_PHRASES['pain_comfort_openers']
                                     if 'pain' in message_lower
                                     else SOFTENING_PHRASES['distress_comfort_openers'])
            urgency_instruction = f"""
{SAFETY_VALVE_INSTRUCTION}
SUGGESTED OPENING: "{comfort}"
After your comfort opening, gently provide helpful information."""

    # ==========================================================================
    # STEP 6b: Pain management context (when OTC/medication discussed with pain)
    # ==========================================================================
    pain_mgmt_context = ""
    pain_keywords = ['pain', 'hurt', 'ache', 'sore', 'tylenol', 'ibuprofen', 'advil',
                     'motrin', 'acetaminophen', 'naproxen', 'aleve', 'painkiller',
                     'pain medication', 'pain relief', 'otc', 'over the counter']
    if sum(1 for pk in pain_keywords if pk in message_lower) >= 2:
        pain_mgmt_context = PAIN_MANAGEMENT_GUIDANCE

    # ==========================================================================
    # STEP 7: Build the prompt
    # ==========================================================================
    prompt_parts = []

    if conversation_context:
        prompt_parts.append(conversation_context)
        prompt_parts.append("")

    # Patient context (concise - don't repeat unnecessarily)
    prompt_parts.extend([
        f"PATIENT CONTEXT (Query Type: {query_type}):",
        filtered_context
    ])

    # Add biomarker implications if relevant
    if biomarker_context:
        prompt_parts.append(biomarker_context)

    # Add comorbidity interactions if relevant (Item 1)
    if comorbidity_context:
        prompt_parts.append(comorbidity_context)

    # Add neuropathy guidance if relevant
    if neuropathy_context:
        prompt_parts.append(neuropathy_context)

    # Add colonoscopy surveillance guidelines if relevant (V3 Step 4)
    if colonoscopy_context:
        prompt_parts.append(colonoscopy_context)

    # Add emotional support guidance if relevant (V3 Step 6)
    if emotional_context:
        prompt_parts.append(emotional_context)

    # Add ANP tone calibration if relevant (Item 6)
    if tone_context:
        prompt_parts.append(tone_context)

    # Add treatment warning if relevant (V3 Step 7)
    if treatment_warning:
        prompt_parts.append(treatment_warning)

    # Add MSI context if relevant (V4 Step 1)
    if msi_context:
        prompt_parts.append(msi_context)

    # Add FIT test guidance if relevant (V4 Step 3)
    if fit_test_context:
        prompt_parts.append(fit_test_context)

    # Add prognosis context if relevant (V4 Step 7)
    if prognosis_context:
        prompt_parts.append(prognosis_context)

    # Add Phase 3 contexts (Items 8, 10, 12, 9, 11)
    if stress_education_context:
        prompt_parts.append(stress_education_context)
    if compassionate_use_context:
        prompt_parts.append(compassionate_use_context)
    if caregiver_context:
        prompt_parts.append(caregiver_context)
    if ambassador_context:
        prompt_parts.append(ambassador_context)
    if wellness_context:
        prompt_parts.append(wellness_context)
    if surveillance_context:
        prompt_parts.append(surveillance_context)
    if nutrition_context:
        prompt_parts.append(nutrition_context)
    if pain_mgmt_context:
        prompt_parts.append(pain_mgmt_context)

    # Conditional hedging based on retrieval confidence
    try:
        from confidence import compute_retrieval_confidence
        retrieval_conf = compute_retrieval_confidence(retrieved or [])
        if retrieval_conf['level'] in ('low', 'medium'):
            prompt_parts.append("\n\n" + HEDGE_INSTRUCTION)
    except Exception as _e:
        retrieval_conf = {'level': 'unknown', 'max_similarity': 0, 'avg_similarity': 0, 'chunk_count': len(retrieved or [])}

    prompt_parts.extend([
        "",
        "MEDICAL GUIDELINES:",
        guideline_note,
        guideline_context,
        "",
        f"USER'S QUESTION: {message}",
        ""
    ])

    # Instructions section
    prompt_parts.append("INSTRUCTIONS:")
    prompt_parts.append(f"• {settings['prompt_instruction']}")
    prompt_parts.append("• Use simple, everyday language - explain medical terms if you must use them")
    prompt_parts.append("• Lead with actionable information, not disclaimers")
    prompt_parts.append("• Be specific and practical")

    if urgency_instruction:
        prompt_parts.append(urgency_instruction)

    # Query-specific instructions
    if query_type == 'side_effect':
        prompt_parts.append("• For side effects: provide interim management tips, mention when to contact the care team")
        prompt_parts.append("• If guidelines mention multiple causes or management approaches for this side effect, list ALL of them - do not narrow to one")
    elif query_type == 'emotional':
        prompt_parts.append("• For emotional concerns: validate feelings, mention oncology social workers and support groups")
    elif query_type == 'prognosis':
        prompt_parts.append("• If guidelines mention multiple prognostic factors or outcomes, present ALL of them rather than a single estimate")
    elif query_type == 'diagnosis':
        prompt_parts.append("• If guidelines mention multiple diagnostic approaches or tests, list ALL of them - do not pick just one")
    elif query_type == 'treatment':
        prompt_parts.append(TREATMENT_RESPONSE_STRUCTURE)
        prompt_parts.append("• Reference the patient's specific biomarkers when discussing treatment eligibility")
    elif query_type == 'clinical_trial':
        prompt_parts.append(CLINICAL_TRIAL_RESPONSE_INSTRUCTIONS)
        prompt_parts.append("• Reference the patient's specific biomarkers and MSI status when discussing trial relevance")
        prompt_parts.append("• If structured trial data is provided below, reference those specific trials. If not, discuss trials in general terms only.")

    # Add follow-up question suggestions for non-brief responses
    if response_length != "brief":
        prompt_parts.append(FOLLOW_UP_INSTRUCTION)

    # Check if clinical trials should be proactively suggested
    if should_suggest_clinical_trials(query_type, patient_context, message):
        prompt_parts.append("• Given the patient's situation, include a brief mention that clinical trials may be worth exploring. Phrase naturally: 'There may also be clinical trials available for your situation - just ask if you'd like me to search for trials near you.'")

    prompt_parts.extend([
        "",
        "RESPONSE:"
    ])

    # Prepare metadata for post-processing
    metadata = {
        'query_type': query_type,
        'urgency_detected': urgency_info['detected'],
        'urgency_level': urgency_info.get('urgency'),
        'urgency_pattern': urgency_info.get('pattern'),
        'urgency_guidance': urgency_info.get('guidance', ''),
        'is_neuropathy_question': is_neuropathy_question,
        'on_oxaliplatin': on_oxaliplatin,
        'include_resources': settings.get('include_resources', True),
        'retrieval_confidence': retrieval_conf,
        # De-identified PHI-bearing components for the route's PII leak guard.
        # The guard must scan ONLY patient-sourced text, never the full prompt:
        # retrieved guideline chunks legitimately contain publication dates and
        # clinic addresses that false-positive the date/address detectors.
        # patient_context / patient / conversation_context here are the
        # post-STEP-0 de-identified values. The route pops this key before the
        # metadata is used anywhere else.
        'pii_guard_payload': {
            'message': message,
            'patient_context': patient_context,
            'patient_profile': patient,
            'conversation_context': conversation_context,
        },
    }

    return "\n".join(prompt_parts), metadata


def trim_incomplete_sentence(response: str) -> str:
    """Trim any incomplete sentence at the end of a response."""
    if not response:
        return response
    response = response.strip()
    if response and response[-1] in '.!?"':
        return response
    last_period = response.rfind('.')
    last_exclaim = response.rfind('!')
    last_question = response.rfind('?')
    last_punct = max(last_period, last_exclaim, last_question)
    if last_punct > 0:
        return response[:last_punct + 1]
    return response


# Disclaimer templates - context-aware
# =============================================================================
# GREETING SHORT-CIRCUIT
# =============================================================================
# Trivial conversational openings should NOT trigger the full LLM + retrieval +
# resource scaffolding. They get a fast canned reply that names the patient
# (if we know them) and invites the next message.

_GREETING_TOKENS = {
    "hi", "hello", "hey", "yo", "hiya", "howdy",
    "good morning", "good afternoon", "good evening",
    "morning", "evening",
    "thanks", "thank you", "thx", "ty", "appreciate it",
    "goodbye", "bye", "see ya", "later",
}


def is_greeting(message: str) -> bool:
    """True if the message is a trivial greeting / thanks / goodbye."""
    if not message:
        return False
    cleaned = message.strip().lower()
    # Strip trailing punctuation
    cleaned = cleaned.rstrip(".!?,;: ")
    if not cleaned or len(cleaned) > 30:
        return False
    if cleaned in _GREETING_TOKENS:
        return True
    # Handle "hi there", "hello again", "thanks so much" — first word match
    first_word = cleaned.split()[0] if cleaned.split() else ""
    if first_word in {"hi", "hello", "hey", "thanks", "thank"} and len(cleaned) <= 30:
        return True
    return False


def greeting_response(first_name: str = "") -> str:
    """Return a short, warm greeting tailored to the patient (if we have a name)."""
    name = (first_name or "").strip()
    if name:
        return f"Hi {name} — what would you like to talk through today?"
    return "Hi — what would you like to talk through today?"


# =============================================================================
# FRIENDLY SOURCE NAMES
# =============================================================================
# Maps raw PDF filenames in data/ to clean display names shown in the
# "Sources used in this response" panel. Anything not mapped falls back to
# a cleaned-up version of the filename (Title Case, underscores -> spaces).

FRIENDLY_SOURCE_NAMES = {
    "acs_caregiver_support.pdf": "ACS Caregiver Support",
    "crc_exercise_protocols.pdf": "CRC Exercise Protocols",
    "crc_mucositis_management.pdf": "Mucositis Management",
    "crc_nutrition_during_chemo.pdf": "Nutrition During Chemo",
    "crc_post_colectomy_diet.pdf": "Post-Colectomy Diet",
    "crc_screening_barriers.pdf": "Screening Barriers Reference",
    "crc_survivorship_nutrition.pdf": "Survivorship Nutrition",
    "crc_treatment_line_reference.pdf": "Treatment Line Reference",
    "cancer_sleep_disorders.pdf": "Cancer Sleep Disorders",
    "cancer_stress_dandre_2024.pdf": "Cancer & Stress (D'Andre 2024)",
    "colon cancer_emergency_urgent_symptoms.docx.pdf": "Emergency & Urgent Symptoms",
    "comprehensive_colon_cancer_guide_441_qa.pdf": "Comprehensive Colon Cancer Guide",
    "nci_caring_for_caregiver_2024.pdf": "NCI Caring for the Caregiver",
    "nci_stress_cancer_fact_sheet.pdf": "NCI Stress & Cancer Fact Sheet",
    "pss10_clinical_reference.pdf": "PSS-10 Clinical Reference",
    "perceived_stress_scale_reference.pdf": "Perceived Stress Scale Reference",
    "prevention and screening strategies for colon cancer.pdf": "Prevention & Screening Strategies",
    "colon cancer review 1.pdf": "Colon Cancer Clinical Review (Part 1)",
    "colon cancer review 2.pdf": "Colon Cancer Clinical Review (Part 2)",
    "colon cancer review 3.pdf": "Colon Cancer Clinical Review (Part 3)",
    "colon cancer screening.pdf": "Colon Cancer Screening Guide",
    "colon cancer survivorship.pdf": "Colon Cancer Survivorship",
    "colon-patient.pdf": "Colon Cancer Patient Guide",
    "colon.pdf": "Colon Cancer Reference",
    "the_american_society_of_colon_and_rectal_surgeons.7.pdf": "ASCRS Reference",
}


def get_friendly_source_name(filename: str) -> str:
    """Return a clean display name for a source PDF. Falls back to filename."""
    if not filename:
        return "Medical guideline"
    key = filename.strip().lower()
    if key in FRIENDLY_SOURCE_NAMES:
        return FRIENDLY_SOURCE_NAMES[key]
    # Fallback: strip extension, replace underscores, title-case
    base = key.rsplit(".pdf", 1)[0].rsplit(".docx", 1)[0]
    base = base.replace("_", " ").strip()
    # Title-case but preserve all-caps acronyms (NCI, ACS, CRC)
    parts = base.split()
    out = []
    for p in parts:
        if p.upper() in {"NCI", "ACS", "CRC", "QA", "MSI", "KRAS", "NRAS", "BRAF"}:
            out.append(p.upper())
        elif p.isupper() and len(p) <= 4:
            out.append(p)
        else:
            out.append(p.capitalize())
    return " ".join(out) or filename


DISCLAIMERS = {
    "action": "\n\n⚠️ Before making any changes to your treatment, please consult your healthcare team.",
    "general": "\n\n💡 This is general information. Your doctor can provide personalized guidance.",
    "emergency": "\n\n🚨 If you're experiencing these symptoms, please contact your healthcare provider or emergency services immediately.",
    "dosage": "\n\nNote: Dosages should be confirmed with your prescribing physician."
}


def should_add_disclaimer(query: str, response: str) -> Tuple[bool, Optional[str]]:
    """
    Determine if a disclaimer is needed and which type.

    Returns (needs_disclaimer, disclaimer_type) where disclaimer_type is one of:
    - "action": Response gives actionable medical advice
    - "general": General treatment discussion
    - "emergency": Emergency symptoms detected
    - "dosage": Specific dosage mentioned
    - None: No disclaimer needed
    """
    query_lower = query.lower()
    response_lower = response.lower()

    # Skip disclaimer for purely informational queries
    info_only_patterns = [
        r"what (is|are|does)",
        r"explain",
        r"tell me about",
        r"how does .* work",
        r"what happens",
        r"why (is|does|do)"
    ]
    is_info_query = any(re.search(p, query_lower) for p in info_only_patterns)

    # Check if response gives actionable advice
    action_patterns = [
        r"you should",
        r"you need to",
        r"take \d+",
        r"stop taking",
        r"start taking",
        r"recommended dose",
        r"increase your",
        r"decrease your"
    ]
    gives_action = any(re.search(p, response_lower) for p in action_patterns)

    # Check for dosage mentions
    dosage_pattern = r'\b(\d+\s*(mg|ml|mcg|units?|tablets?|pills?|capsules?))\b'
    has_dosage = bool(re.search(dosage_pattern, response, re.IGNORECASE))
    defers_to_doctor = any(phrase in response_lower for phrase in ['doctor', 'physician', 'prescrib', 'healthcare'])

    if has_dosage and not defers_to_doctor:
        return True, "dosage"

    if gives_action:
        return True, "action"

    # Don't add disclaimer for pure informational responses
    if is_info_query:
        return False, None

    # Add general disclaimer only if discussing treatments without being purely informational
    treatment_words = ['treatment', 'therapy', 'medication', 'drug', 'chemo']
    if any(word in response_lower for word in treatment_words):
        return True, "general"

    return False, None


def enhanced_medical_validation(response: str, query: str) -> dict:
    """Comprehensive medical-specific validation for safety concerns."""
    safety_flags = []
    modified_response = response

    response_lower = response.lower()
    query_lower = query.lower()

    # 1. Check for dangerous absolute claims (expanded list)
    absolute_patterns = [
        (r'\b(will cure|will definitely|100%|guaranteed to)\b', "absolute_claim"),
        (r'\b(never causes?|always works?|completely safe)\b', "absolute_claim"),
        (r'\b(no side effects?|risk-free|cannot fail)\b', "absolute_claim"),
    ]

    for pattern, flag_type in absolute_patterns:
        if re.search(pattern, response, re.IGNORECASE):
            safety_flags.append(f"Contains {flag_type}: pattern '{pattern}'")

    # 2. Check for emergency symptoms not addressed
    emergency_symptoms = [
        'chest pain', 'difficulty breathing', 'severe bleeding',
        'high fever', 'severe headache', 'confusion', 'seizure',
        'can\'t breathe', 'unconscious', 'stroke symptoms'
    ]
    query_has_emergency = any(s in query_lower for s in emergency_symptoms)
    response_addresses_emergency = any(
        phrase in response_lower
        for phrase in ['seek medical', 'call 911', 'emergency', 'immediately', 'urgent', 'hospital']
    )

    if query_has_emergency and not response_addresses_emergency:
        modified_response = DISCLAIMERS['emergency'] + "\n\n" + modified_response
        safety_flags.append("Added emergency warning")

    # 3. Check response completeness - trim incomplete sentences
    if response and not response.rstrip().endswith(('.', '!', '?', '"', ')')):
        last_period = response.rfind('.')
        if last_period > len(response) * 0.5:  # Keep if >50% of response
            modified_response = response[:last_period + 1]
            safety_flags.append("Trimmed incomplete sentence")

    return {
        "safe": len([f for f in safety_flags if 'absolute_claim' in f]) == 0,
        "flags": safety_flags,
        "severity": "high" if query_has_emergency else "low",
        "modified_response": modified_response
    }


def validate_response(response: str, user_question: str, patient_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate AI response for safety, relevance, and quality.

    Uses context-aware disclaimer logic to avoid over-disclaiming on informational queries.
    """
    validation_result = {
        'is_valid': True,
        'warnings': [],
        'enhanced_response': response,
        'needs_disclaimer': False,
        'disclaimer_type': None
    }

    if not response or len(response.strip()) < 10:
        validation_result['is_valid'] = False
        validation_result['warnings'].append("Response too short or empty")
        return validation_result

    # Run enhanced medical validation first
    medical_validation = enhanced_medical_validation(response, user_question)

    # Use the potentially modified response (e.g., with emergency warning or trimmed)
    current_response = medical_validation.get('modified_response', response)
    validation_result['warnings'].extend(medical_validation.get('flags', []))

    # Check if this is a high-severity situation
    if medical_validation.get('severity') == 'high':
        validation_result['enhanced_response'] = current_response
        # Emergency disclaimer already added by enhanced_medical_validation
        return validation_result

    # CT-02: Check for potentially hallucinated NCT numbers in LLM-generated text
    import re
    nct_matches = re.findall(r'NCT\d{7,8}', current_response)
    if nct_matches:
        logger.warning(f"LLM response contains NCT numbers: {nct_matches} — verify these are from API data, not hallucinated")
        validation_result['warnings'].append(f"Contains NCT numbers: {nct_matches}")

    # Use smart disclaimer logic. The "general" disclaimer ("This is general
    # information. Your doctor can provide personalized guidance.") is now
    # covered by the persistent AI banner above the chat, so we skip appending
    # it per-response. The specific disclaimers (emergency, dosage, action)
    # carry context the banner cannot, so they still apply.
    needs_disclaimer, disclaimer_type = should_add_disclaimer(user_question, current_response)

    if needs_disclaimer and disclaimer_type and disclaimer_type != 'general':
        validation_result['needs_disclaimer'] = True
        validation_result['disclaimer_type'] = disclaimer_type
        current_response += DISCLAIMERS.get(disclaimer_type, '')
        logger.info(f"Added {disclaimer_type} disclaimer")

    validation_result['enhanced_response'] = current_response

    return validation_result


def select_model_for_query(query: str, query_type: str, response_length: str) -> str:
    """
    Select the appropriate model based on query complexity.

    Returns: "together" for complex queries (70B model), "groq" for simple queries (8B model)
    """
    query_lower = query.lower()
    word_count = len(query.split())

    # Simple query indicators -> use faster Groq model
    simple_indicators = [
        word_count < 8,                          # Very short questions
        query_type == 'general',                 # General questions
        '?' not in query,                        # Statements, not questions
        response_length == 'brief',              # Brief responses requested
    ]

    # Complex query indicators -> use larger Together model
    complex_indicators = [
        query_type in ['treatment', 'prognosis', 'clinical_trial'],  # Medical decision topics
        'why' in query_lower,                      # Explanatory questions
        'should i' in query_lower,                 # Decision-making questions
        'compare' in query_lower,                  # Comparative analysis
        response_length == 'detailed',             # Detailed responses requested
        word_count > 20,                           # Long complex questions
    ]

    # Count indicators
    simple_count = sum(1 for x in simple_indicators if x)
    complex_count = sum(1 for x in complex_indicators if x)

    # Default to Together for medical safety, but use Groq for clearly simple queries
    if simple_count >= 3 and complex_count == 0:
        return "groq"

    return "together"


def call_llm(prompt: str, response_length: str = "normal", temperature: float = None,
             query: str = None, query_type: str = None,
             cancer_slug: str = None) -> Tuple[str, str]:
    """
    Call LLM API with smart model routing.

    Uses Together AI (70B) for complex queries and Groq (8B) for simple queries.
    Falls back between providers if one fails.

    Args:
        prompt: The prompt to send to the LLM
        response_length: "brief", "normal", or "detailed" - controls token limits and temperature
        temperature: Optional override for temperature (uses settings default if None)
        query: Original user query (for smart routing)
        query_type: Classified query type (for smart routing)
        cancer_slug: Per-cancer overlay slug; None falls back to colorectal

    Returns: (response_text, api_used)
    """
    settings = get_response_settings(response_length, query_type=query_type, cancer_slug=cancer_slug)

    # Use settings temperature unless explicitly overridden
    effective_temperature = temperature if temperature is not None else settings["temperature"]

    # Always use Together AI (70B) as primary for consistent quality
    preferred_model = "together"
    logger.info(f"Using Together AI (70B) for query type: {query_type or 'unknown'}")

    together_error = None
    groq_error = None

    def try_together():
        """Try Together AI (70B model)."""
        nonlocal together_error
        client = get_together_client()
        if not client:
            together_error = "Together client not available (API key may be invalid)"
            logger.warning(together_error)
            return None
        try:
            from model_registry import get_model
            logger.info(f"Calling Together AI (chat), response_length: {response_length}, temp: {effective_temperature}")
            response = client.chat.completions.create(
                model=get_model("chat"),
                messages=[
                    {"role": "system", "content": settings["system_message"]},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=settings["max_tokens"],
                temperature=effective_temperature,
                top_p=0.9,
            )
            if response and response.choices and len(response.choices) > 0:
                content = response.choices[0].message.content
                if content:
                    logger.info(f"Together AI response success - length: {len(content)}")
                    return content.strip(), "together"
            together_error = "Together AI returned empty response"
            logger.warning(together_error)
        except Exception as e:
            together_error = f"Together AI API error: {str(e)}"
            logger.warning(together_error)
        return None

    def try_groq():
        """Try Groq (8B model - faster)."""
        nonlocal groq_error
        client = get_groq_client()
        if not client:
            groq_error = "Groq client not available (API key may be invalid)"
            logger.warning(groq_error)
            return None
        try:
            from model_registry import get_model
            logger.info(f"Calling Groq (fallback), response_length: {response_length}, temp: {effective_temperature}")
            response = client.chat.completions.create(
                model=get_model("fallback"),
                messages=[
                    {"role": "system", "content": settings["system_message"]},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=settings["max_tokens"],
                temperature=effective_temperature,
                top_p=0.9,
            )
            if response and response.choices and len(response.choices) > 0:
                content = response.choices[0].message.content
                if content:
                    logger.info(f"Groq response success - length: {len(content)}")
                    return content.strip(), "groq"
            groq_error = "Groq returned empty response"
            logger.warning(groq_error)
        except Exception as e:
            groq_error = f"Groq API error: {str(e)}"
            logger.warning(groq_error)
        return None

    # Try preferred model first, then fallback
    if preferred_model == "groq":
        result = try_groq()
        if result:
            return result
        # Fallback to Together
        result = try_together()
        if result:
            return result
    else:
        result = try_together()
        if result:
            return result
        # Fallback to Groq
        result = try_groq()
        if result:
            return result

    # Both failed - include detailed error messages
    error_details = []
    if together_error:
        error_details.append(f"Together: {together_error}")
    if groq_error:
        error_details.append(f"Groq: {groq_error}")
    
    error_msg = "No LLM API available or both failed"
    if error_details:
        error_msg += f" - Details: {'; '.join(error_details)}"
    
    raise RuntimeError(error_msg)


def _quick_extract_profile_updates(message: str) -> dict:
    """
    Quick regex-based extraction for common profile field updates.
    This runs before the LLM call for faster response on simple updates.
    """
    import re
    updates = {}
    msg_lower = message.lower()

    # Zip code patterns
    zip_patterns = [
        r"(?:my\s+)?(?:new\s+)?zip\s*(?:code)?\s*(?:is|:)?\s*(\d{5}(?:-\d{4})?)",
        r"(?:i\s+)?(?:live|moved)\s+(?:in|to)\s+(?:zip\s*(?:code)?\s*)?(\d{5}(?:-\d{4})?)",
        r"zip\s*(?:code)?[:\s]+(\d{5}(?:-\d{4})?)",
    ]
    for pattern in zip_patterns:
        match = re.search(pattern, msg_lower)
        if match:
            if "patient" not in updates:
                updates["patient"] = {}
            updates["patient"]["zipCode"] = match.group(1)
            break

    # Age patterns
    age_patterns = [
        r"(?:i\s+am|i'm|my\s+age\s+is)\s+(\d{1,3})\s*(?:years?\s*old)?",
        r"(?:my\s+)?age[:\s]+(\d{1,3})",
        r"(\d{1,3})\s*(?:years?\s*old|yo|y\.?o\.?)",
    ]
    for pattern in age_patterns:
        match = re.search(pattern, msg_lower)
        if match:
            age = int(match.group(1))
            if 1 <= age <= 120:  # Reasonable age range
                if "patient" not in updates:
                    updates["patient"] = {}
                updates["patient"]["age"] = str(age)
                break

    # Weight patterns (lbs)
    weight_patterns = [
        r"(?:i\s+)?weigh\s+(\d{2,3})\s*(?:lbs?|pounds?)?",
        r"(?:my\s+)?weight\s*(?:is|:)?\s*(\d{2,3})\s*(?:lbs?|pounds?)?",
        r"(\d{2,3})\s*(?:lbs?|pounds?)",
    ]
    for pattern in weight_patterns:
        match = re.search(pattern, msg_lower)
        if match:
            weight = int(match.group(1))
            if 50 <= weight <= 500:  # Reasonable weight range
                if "patient" not in updates:
                    updates["patient"] = {}
                updates["patient"]["weight"] = str(weight)
                break

    # Stage patterns
    stage_patterns = [
        r"(?:i\s+am|i'm|i\s+have|diagnosed\s+with)\s+stage\s+(i{1,3}v?|[1-4])",
        r"(?:my\s+)?(?:cancer\s+)?stage\s*(?:is|:)?\s*(i{1,3}v?|[1-4])",
    ]
    for pattern in stage_patterns:
        match = re.search(pattern, msg_lower)
        if match:
            stage_raw = match.group(1).upper()
            stage_map = {"1": "Stage I", "2": "Stage II", "3": "Stage III", "4": "Stage IV",
                         "I": "Stage I", "II": "Stage II", "III": "Stage III", "IV": "Stage IV"}
            if stage_raw in stage_map:
                if "primaryDiagnosis" not in updates:
                    updates["primaryDiagnosis"] = {}
                updates["primaryDiagnosis"]["stage"] = stage_map[stage_raw]
                break

    # Name patterns
    name_patterns = [
        r"(?:my\s+name\s+is|i'm|call\s+me)\s+([A-Z][a-z]+)",
    ]
    for pattern in name_patterns:
        match = re.search(pattern, message)  # Case-sensitive for names
        if match:
            if "patient" not in updates:
                updates["patient"] = {}
            updates["patient"]["firstName"] = match.group(1)
            break

    return updates


def _extraction_profile_context(current_profile: dict) -> str:
    """
    Build the LLM-safe profile-context JSON for the extractor call.

    De-identify-before-LLM rule (.claude/rules/backend-python.md): the raw
    profile must never reach Together/Groq. This strips identifiers + app
    bookkeeping via deidentify_raw_profile (which also drops _sources /
    beliefs / model_state / visit_recaps etc.), then runs the leak guard as
    belt-and-suspenders. On a detected leak the profile context is omitted
    entirely (extraction still works from the message alone).
    """
    from deidentify import deidentify_raw_profile, detect_pii_leaks
    safe_profile = deidentify_raw_profile(current_profile or {})
    leaks = detect_pii_leaks({"profile_context": safe_profile})
    if leaks:
        # Log leak TYPES only — never values.
        leak_types = ",".join(sorted({name for name, _snippet in leaks}))
        logger.warning(
            "Extractor profile context failed PII guard (%s); omitting profile context",
            leak_types,
        )
        return "{}"
    return json.dumps(safe_profile, indent=2)


def extract_profile_updates_from_query(message: str, current_profile: dict) -> dict:
    """
    Scan user query for profile-relevant updates using LLM.

    Returns: Dict of updates found.
    """
    # First, try quick regex-based extraction for common simple updates
    quick_updates = _quick_extract_profile_updates(message)
    if quick_updates:
        # Log field paths only — extracted values are PII (name, zip, ...).
        logger.info(f"Quick extraction found update fields: {sorted(quick_updates.keys())}")
        return quick_updates

    client = get_together_client() or get_groq_client()
    if not client:
        logger.warning("No LLM client available for profile extraction")
        return {}

    system_prompt = """
    You are a medical data extraction assistant. Analyze the user's message and identify any NEW or UPDATED information
    relevant to their patient profile. Use the CURRENT profile as context to only extract CHANGED or NEW information.

    IMPORTANT: Look for ANY mention of personal or medical information updates, including:
    - "my zip code is...", "I live in...", "my new address..."
    - "I am X years old", "my age is...", "I'm..."
    - "my name is...", "call me..."
    - "I weigh...", "my weight is..."
    - "I'm X feet X inches", "my height is..."
    - "I started...", "I'm now on...", "my new treatment is..."
    - "I have...", "I was diagnosed with..."
    - "my biomarker is...", "my KRAS is...", "I'm MSI-high"
    - "I'm experiencing...", "I have side effects like..."

    Extract fields like:
    - Age (or date of birth)
    - Symptoms (toxicities)
    - Treatments (regimens, cycle numbers, status)
    - Biomarkers (KRAS, NRAS, BRAF, MSI, MMR, HER2, etc.)
    - Comorbidities
    - Basic info (name, zip code, race/ethnicity, height, weight)

    CURRENT PROFILE:
    {current_profile_json}

    Return ONLY a JSON object with the updates. If no updates are found, return {{}}.
    The JSON structure should follow the patient profile format:
    {{
      "patient": {{ "age": ..., "firstName": ..., "zipCode": ..., "weight": ..., "heightFt": ..., "heightIn": ... }},
      "primaryDiagnosis": {{ "biomarkers": {{ ... }}, "stage": ..., "histology": ... }},
      "treatments": [ {{ "category": ..., "regimen": ..., "status": ... }} ],
      "symptoms": [ ... ]
    }}
    Include ONLY the fields that have changed.
    """
    
    # De-identified profile context only — never the raw profile (PII rule).
    current_profile_json = _extraction_profile_context(current_profile)

    try:
        from model_registry import get_model
        model = get_model("extractor") if get_together_client() else get_model("fallback")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt.format(current_profile_json=current_profile_json)},
                {"role": "user", "content": message}
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        if response and response.choices:
            content = response.choices[0].message.content
            return json.loads(content)
    except Exception as e:
        logger.error(f"Profile extraction failed: {e}")

    return {}

