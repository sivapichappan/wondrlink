# profile_utils.py
import os
import json
import logging
from typing import Dict, Any, List, Union
from datetime import datetime, date

logger = logging.getLogger("profile_utils")

# In-memory profile cache (for serverless, this resets between invocations)
PATIENT_PROFILE = {}


def calculate_age(dob_str: str) -> int:
    """Calculate age from date of birth string (YYYY-MM-DD format)"""
    try:
        if not dob_str or dob_str == 'unspecified':
            return None
        birth = datetime.strptime(dob_str, "%Y-%m-%d").date()
        today = date.today()
        age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
        return age
    except (ValueError, TypeError):
        return None


def save_and_load_profile(file_storage, upload_folder: str) -> dict:
    """
    Save uploaded JSON profile to disk and load it into memory.
    Returns parsed dict if valid, else raises Exception.
    """
    if not file_storage:
        raise ValueError("No file provided")

    filename = file_storage.filename
    if not filename.lower().endswith(".json"):
        raise ValueError("File must be a JSON")

    os.makedirs(upload_folder, exist_ok=True)
    save_path = os.path.join(upload_folder, filename)
    file_storage.save(save_path)

    try:
        with open(save_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        global PATIENT_PROFILE
        PATIENT_PROFILE = data
        logger.info("Loaded patient profile: %s", filename)
        return data
    except Exception as e:
        logger.exception("Failed to load patient profile")
        raise ValueError(f"Invalid JSON: {e}")


def parse_profile_json(json_content: bytes) -> dict:
    """Parse profile from JSON bytes (for serverless without file system)."""
    try:
        data = json.loads(json_content.decode('utf-8'))
        global PATIENT_PROFILE
        PATIENT_PROFILE = data
        logger.info("Loaded patient profile from JSON content")
        return data
    except Exception as e:
        logger.exception("Failed to parse profile JSON")
        raise ValueError(f"Invalid JSON: {e}")


def get_profile() -> dict:
    """Return current patient profile (dict)."""
    return PATIENT_PROFILE


def set_profile(profile: dict):
    """Set the current patient profile (dict)."""
    global PATIENT_PROFILE
    PATIENT_PROFILE = profile
    logger.info("Patient profile set in memory")


def safe_extract_value(data: Any, path: str, default: str = "unspecified") -> str:
    """Safely extract a value from nested dictionary using dot notation."""
    if not data:
        return default

    try:
        keys = path.split('.')
        current = data

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default

        if isinstance(current, (str, int, float)):
            return str(current)
        elif isinstance(current, bool):
            return "yes" if current else "no"
        elif isinstance(current, list):
            if current:
                return ', '.join(str(item) for item in current[:3]) + ('...' if len(current) > 3 else '')
            else:
                return default
        elif isinstance(current, dict):
            if 'status' in current:
                return str(current['status'])
            elif 'value' in current:
                return str(current['value'])
            else:
                return str(current)
        else:
            return str(current) if current is not None else default

    except Exception:
        return default


def extract_treatments_summary(treatments: List[Dict]) -> List[str]:
    """Extract a summary of treatments from complex treatment data, including cycle info"""
    if not treatments or not isinstance(treatments, list):
        return []

    summaries = []
    for treatment in treatments:
        if not isinstance(treatment, dict):
            continue

        line = treatment.get('line', 'unknown line')
        regimen = treatment.get('regimen', 'unknown regimen')
        status = treatment.get('status', 'completed')
        cycle_number = treatment.get('cycleNumber')  # Extract cycle number

        if status == 'active':
            if cycle_number:
                # Include cycle info: "Currently on FOLFOX (Adjuvant, Cycle 8)"
                summary = f"Currently on {regimen} ({line}, Cycle {cycle_number})"
            else:
                summary = f"Currently on {regimen} ({line})"
        else:
            summary = f"{regimen} ({line})"

        summaries.append(summary)

    return summaries


def extract_biomarkers_summary(biomarkers: Dict) -> str:
    """Extract key biomarkers into readable format"""
    if not biomarkers or not isinstance(biomarkers, dict):
        return "unspecified"

    key_markers = []

    important_markers = ['KRAS', 'NRAS', 'BRAF', 'HER2', 'MSI', 'MMR', 'NTRK', 'PIK3CA']

    for marker in important_markers:
        if marker in biomarkers:
            value = biomarkers[marker]
            if value and str(value).strip():
                key_markers.append(f"{marker}: {value}")

    return ', '.join(key_markers) if key_markers else "pending/unspecified"


# =============================================================================
# BIOMARKER CLINICAL IMPLICATIONS
# =============================================================================

BIOMARKER_IMPLICATIONS = {
    'KRAS': {
        'mutated_keywords': ['mutation', 'mutant', 'mutated', 'g12', 'g13', 'positive'],
        'wildtype_keywords': ['wild-type', 'wildtype', 'wild type', 'negative', 'wt'],
        'mutated_implication': 'KRAS mutation means EGFR-targeted therapies (cetuximab, panitumumab) will NOT be effective for your cancer.',
        'wildtype_implication': 'KRAS wild-type status means you may be eligible for EGFR-targeted therapies (cetuximab, panitumumab) if needed.'
    },
    'NRAS': {
        'mutated_keywords': ['mutation', 'mutant', 'mutated', 'positive'],
        'wildtype_keywords': ['wild-type', 'wildtype', 'wild type', 'negative', 'wt'],
        'mutated_implication': 'NRAS mutation means EGFR-targeted therapies will NOT be effective.',
        'wildtype_implication': None  # Only relevant if mutated
    },
    'BRAF': {
        'mutated_keywords': ['v600e', 'mutation', 'mutant', 'mutated', 'positive'],
        'wildtype_keywords': ['wild-type', 'wildtype', 'wild type', 'negative', 'wt'],
        'mutated_implication': 'BRAF V600E mutation may respond to targeted therapy combinations (encorafenib + cetuximab). This mutation is associated with more aggressive disease but has specific treatment options.',
        'wildtype_implication': None
    },
    'MSI': {
        'favorable_keywords': ['msi-h', 'msi-high', 'high', 'unstable', 'msih'],
        'unfavorable_keywords': ['mss', 'stable', 'msi-l', 'msi-low', 'microsatellite stable'],
        'favorable_implication': 'MSI-High (MSI-H) status is actually good news - these tumors often respond very well to immunotherapy (checkpoint inhibitors like pembrolizumab). This is an important treatment option.',
        'unfavorable_implication': 'MSS (Microsatellite Stable) means immunotherapy/checkpoint inhibitors are unlikely to be effective as a standalone treatment. However, many other effective treatments are available.'
    },
    'HER2': {
        'positive_keywords': ['positive', 'amplified', 'overexpressed', '3+', '2+'],
        'negative_keywords': ['negative', 'not amplified', '0', '1+'],
        'positive_implication': 'HER2-positive status means you may benefit from HER2-targeted therapies (trastuzumab, pertuzumab) which are showing promising results in colorectal cancer.',
        'negative_implication': None
    },
    'MMR': {
        'deficient_keywords': ['deficient', 'dmmr', 'loss'],
        'proficient_keywords': ['proficient', 'pmmr', 'intact'],
        'deficient_implication': 'MMR-deficient tumors (like MSI-H) often respond well to immunotherapy.',
        'proficient_implication': 'MMR-proficient status means the tumor is microsatellite stable and less likely to respond to immunotherapy alone.'
    }
}


# =============================================================================
# COMORBIDITY CLINICAL INTERACTIONS (Item 1 - Clinical Feedback)
# =============================================================================

COMORBIDITY_INTERACTIONS = {
    'Type 2 diabetes': {
        'treatment_interactions': [
            'Corticosteroids (dexamethasone, often given with chemo as anti-nausea) can significantly raise blood sugar. Monitor glucose closely on chemo days and for 2-3 days after.',
            'Neuropathy from oxaliplatin can be harder to distinguish from diabetic neuropathy — report any new numbness or tingling promptly.',
            'Dehydration from diarrhea or vomiting can cause blood sugar fluctuations and kidney strain. Stay well hydrated and contact your care team if unable to keep fluids down.'
        ],
        'monitoring_note': 'Discuss blood sugar monitoring schedule with your oncologist and endocrinologist during chemotherapy.'
    },
    'Hypertension': {
        'treatment_interactions': [
            'Bevacizumab (Avastin) and other anti-VEGF drugs commonly cause or worsen high blood pressure — blood pressure monitoring is essential during treatment.',
            '5-FU and capecitabine carry a small risk of coronary vasospasm. Report any chest tightness immediately.',
            'Some anti-nausea medications can affect cardiac rhythm at high doses — your care team monitors this.'
        ],
        'monitoring_note': 'Monitor blood pressure at home and report readings above your established threshold to your oncology team.'
    },
    'Heart disease': {
        'treatment_interactions': [
            '5-Fluorouracil (5-FU) and capecitabine carry a risk of cardiotoxicity — chest pain, palpitations, or shortness of breath during or after infusion should be reported immediately.',
            'Bevacizumab is typically used cautiously or avoided in patients with recent cardiac events.',
            'Your oncologist should coordinate with your cardiologist before starting or changing chemotherapy regimens.'
        ],
        'monitoring_note': 'Ensure your oncologist has your full cardiac history. A cardio-oncology consultation may be valuable.'
    },
    'Kidney disease': {
        'treatment_interactions': [
            'Many chemotherapy drugs are renally cleared — kidney function (creatinine, GFR) is monitored regularly and doses adjusted accordingly.',
            'Oxaliplatin and other nephrotoxic agents require dose modifications when kidney function is reduced.',
            'Staying well hydrated helps protect kidneys during treatment, but discuss fluid restriction needs with your nephrologist.'
        ],
        'monitoring_note': 'Kidney function labs are typically checked before each cycle. Your oncologist adjusts doses based on these results.'
    },
    'Liver disease': {
        'treatment_interactions': [
            'Many chemotherapy drugs are metabolized by the liver — liver function tests (LFTs) are checked regularly.',
            'Dose reductions may be needed for drugs like irinotecan if liver function is compromised.',
            'Liver metastases (if present) can also affect drug metabolism differently than underlying liver disease.'
        ],
        'monitoring_note': 'Liver function is monitored before each cycle. Dose modifications are common and expected.'
    },
    'COPD/Lung disease': {
        'treatment_interactions': [
            'Fatigue from chemotherapy combined with COPD-related breathlessness can compound. Pulmonary rehab strategies can help.',
            'Some targeted therapies have pulmonary side effects — report any new or worsening shortness of breath.'
        ],
        'monitoring_note': 'Ensure your pulmonologist is aware of your chemotherapy regimen.'
    },
    'Obesity': {
        'treatment_interactions': [
            'Chemotherapy dosing is calculated on actual body weight or adjusted ideal body weight — your oncology team uses established dosing guidelines.',
            'Obesity increases risk of lymphedema and wound complications after surgery.',
            'Weight management and activity are important during and after treatment — an oncology dietitian can help.'
        ],
        'monitoring_note': 'Discuss weight-related treatment considerations with your oncologist.'
    },
    'Arthritis': {
        'treatment_interactions': [
            'Joint pain can be worsened by some targeted therapies.',
            'NSAIDs (ibuprofen) for arthritis pain may interact with some chemo drugs or increase bleeding risk — always check with your oncologist before taking OTC pain medications.',
            'Corticosteroids used in chemo regimens may temporarily relieve arthritis symptoms but can cause flares when tapered.'
        ],
        'monitoring_note': 'Keep your oncologist and rheumatologist informed of any changes in joint symptoms during treatment.'
    }
}


# =============================================================================
# TREATMENT LINE AUTO-DETECTION RULES (Item 2 - Clinical Feedback)
# =============================================================================

TREATMENT_LINE_RULES = {
    # Third-line+ (highest confidence — these are virtually always 3L+)
    'REGORAFENIB': {'line': '3L+', 'display': 'Third-line or later', 'confidence': 'high',
                     'note': 'Regorafenib is approved for third-line or later CRC.'},
    'TAS-102': {'line': '3L+', 'display': 'Third-line or later', 'confidence': 'high',
                 'note': 'TAS-102 (trifluridine/tipiracil) is approved for third-line or later CRC.'},
    'LONSURF': {'line': '3L+', 'display': 'Third-line or later', 'confidence': 'high',
                 'note': 'Lonsurf is approved for third-line or later CRC.'},
    'FRUQUINTINIB': {'line': '3L+', 'display': 'Third-line or later', 'confidence': 'high',
                      'note': 'Fruquintinib is approved for third-line or later CRC.'},
    # Second-line specific agents
    'AFLIBERCEPT': {'line': '2L', 'display': 'Second-line', 'confidence': 'high',
                     'note': 'Aflibercept is used in second-line CRC (with FOLFIRI).'},
    'RAMUCIRUMAB': {'line': '2L', 'display': 'Second-line', 'confidence': 'high',
                     'note': 'Ramucirumab is used in second-line CRC (with FOLFIRI).'},
    # First-line intensive
    'FOLFOXIRI': {'line': '1L', 'display': 'First-line (intensive)', 'confidence': 'high',
                   'note': 'FOLFOXIRI is an intensive first-line regimen typically for fit patients.'},
    # Standard backbone regimens (can span lines)
    'FOLFOX': {'line': '1L_or_adj', 'display': 'First-line or adjuvant', 'confidence': 'medium',
                'note': 'FOLFOX is used in both adjuvant (post-surgery) and first-line metastatic settings.'},
    'CAPOX': {'line': '1L_or_adj', 'display': 'First-line or adjuvant', 'confidence': 'medium',
               'note': 'CAPOX (XELOX) is used in both adjuvant and first-line metastatic settings.'},
    'FOLFIRI': {'line': '1L_or_2L', 'display': 'First or second-line', 'confidence': 'medium',
                'note': 'FOLFIRI is used in both first-line and second-line settings.'},
    # Immunotherapy
    'PEMBROLIZUMAB': {'line': '1L_msi_h', 'display': 'First-line (MSI-H only)', 'confidence': 'high',
                       'note': 'Pembrolizumab is first-line for MSI-H/dMMR metastatic CRC.'},
    'NIVOLUMAB': {'line': '2L+_msi_h', 'display': 'Second-line or later (MSI-H)', 'confidence': 'high',
                   'note': 'Nivolumab is approved for MSI-H/dMMR CRC after prior therapy.'},
    # Targeted therapy
    'ENCORAFENIB': {'line': '2L+_braf', 'display': 'Second-line or later (BRAF V600E)', 'confidence': 'high',
                     'note': 'Encorafenib + cetuximab is for BRAF V600E-mutant CRC after first-line.'},
}


def auto_detect_treatment_line(regimen: str, biomarkers: dict = None) -> dict:
    """
    Attempt to auto-detect treatment line from regimen name.

    Args:
        regimen: The regimen string (e.g., 'FOLFOX + Bevacizumab')
        biomarkers: Optional biomarker dict for MSI/BRAF-aware detection

    Returns:
        Dict with 'detected', 'line', 'display', 'confidence', 'note'
        or {'detected': False} if no match
    """
    if not regimen:
        return {'detected': False}

    regimen_upper = regimen.upper()

    for drug_key, rule in TREATMENT_LINE_RULES.items():
        if drug_key in regimen_upper:
            result = {'detected': True, **rule, 'drug_matched': drug_key}

            # Refine MSI-H specific rules
            if '_msi_h' in rule['line'] and biomarkers:
                msi_val = str(biomarkers.get('MSI', '')).lower()
                if not any(kw in msi_val for kw in ['msi-h', 'msi-high', 'unstable', 'msih']):
                    result['note'] += ' NOTE: This agent is typically only first-line for MSI-H tumors. Verify biomarker status.'
                    result['confidence'] = 'low'

            return result

    return {'detected': False}


def get_comorbidity_interactions(comorbidities: list, query_type: str = None) -> list:
    """
    Get relevant comorbidity-treatment interaction notes.

    Args:
        comorbidities: List of comorbidity strings from patient profile
        query_type: Current query type to filter relevance

    Returns:
        List of interaction strings
    """
    if not comorbidities or not isinstance(comorbidities, list):
        return []

    # Only inject comorbidity context for relevant query types
    relevant_query_types = ['treatment', 'side_effect', 'prognosis', None]
    if query_type not in relevant_query_types:
        return []

    interactions = []
    for comorbidity in comorbidities[:3]:  # Cap at 3 comorbidities to control token budget
        comorbidity_str = str(comorbidity).strip()
        if comorbidity_str in COMORBIDITY_INTERACTIONS:
            entry = COMORBIDITY_INTERACTIONS[comorbidity_str]
            for note in entry['treatment_interactions'][:2]:  # Max 2 notes per comorbidity
                interactions.append(f"[{comorbidity_str}] {note}")
            if entry.get('monitoring_note'):
                interactions.append(f"[{comorbidity_str} monitoring] {entry['monitoring_note']}")

    return interactions


def get_biomarker_implications(biomarkers: Dict) -> List[str]:
    """
    Extract clinical implications from biomarker status.

    Args:
        biomarkers: Dict of biomarker name -> value (e.g., {'KRAS': 'G12D mutation', 'MSI': 'MSS'})

    Returns:
        List of relevant clinical implication strings
    """
    if not biomarkers or not isinstance(biomarkers, dict):
        return []

    implications = []

    for marker_name, marker_info in BIOMARKER_IMPLICATIONS.items():
        if marker_name not in biomarkers:
            continue

        value = str(biomarkers[marker_name]).lower()
        if not value or value in ['unspecified', 'pending', 'unknown', 'n/a']:
            continue

        # Check for MSI (special case with favorable/unfavorable)
        if marker_name == 'MSI':
            if any(kw in value for kw in marker_info.get('favorable_keywords', [])):
                if marker_info.get('favorable_implication'):
                    implications.append(marker_info['favorable_implication'])
            elif any(kw in value for kw in marker_info.get('unfavorable_keywords', [])):
                if marker_info.get('unfavorable_implication'):
                    implications.append(marker_info['unfavorable_implication'])

        # Check for MMR (deficient/proficient)
        elif marker_name == 'MMR':
            if any(kw in value for kw in marker_info.get('deficient_keywords', [])):
                if marker_info.get('deficient_implication'):
                    implications.append(marker_info['deficient_implication'])
            elif any(kw in value for kw in marker_info.get('proficient_keywords', [])):
                if marker_info.get('proficient_implication'):
                    implications.append(marker_info['proficient_implication'])

        # Check for HER2 (positive/negative)
        elif marker_name == 'HER2':
            if any(kw in value for kw in marker_info.get('positive_keywords', [])):
                if marker_info.get('positive_implication'):
                    implications.append(marker_info['positive_implication'])

        # Check for mutation markers (KRAS, NRAS, BRAF)
        else:
            if any(kw in value for kw in marker_info.get('mutated_keywords', [])):
                if marker_info.get('mutated_implication'):
                    implications.append(marker_info['mutated_implication'])
            elif any(kw in value for kw in marker_info.get('wildtype_keywords', [])):
                if marker_info.get('wildtype_implication'):
                    implications.append(marker_info['wildtype_implication'])

    return implications


def format_biomarker_context(biomarkers: Dict, query_type: str = None) -> str:
    """
    Format biomarker information with clinical implications for prompt context.

    Only includes implications when relevant to the query type.
    """
    if not biomarkers:
        return ""

    summary = extract_biomarkers_summary(biomarkers)
    if summary == "pending/unspecified":
        return ""

    # Only add implications for treatment/prognosis queries
    include_implications = query_type in ['treatment', 'prognosis', 'diagnosis', None]

    if include_implications:
        implications = get_biomarker_implications(biomarkers)
        if implications:
            # Limit to top 2 most relevant implications
            impl_text = " | ".join(implications)
            return f"Biomarkers: {summary}\nImplications: {impl_text}"

    return f"Biomarkers: {summary}"


def extract_current_symptoms(profile: Dict) -> List[str]:
    """Extract current symptoms/toxicities from treatment data"""
    symptoms = []

    treatments = profile.get('treatments', [])
    if isinstance(treatments, list):
        for treatment in treatments:
            if isinstance(treatment, dict) and treatment.get('status') == 'active':
                toxicities = treatment.get('toxicities', [])
                if isinstance(toxicities, list):
                    for tox in toxicities:
                        if isinstance(tox, dict):
                            event = tox.get('event', '')
                            grade = tox.get('grade', '')
                            if event:
                                symptom = f"Grade {grade} {event}" if grade else event
                                symptoms.append(symptom)

    direct_symptoms = profile.get('symptoms', [])
    if isinstance(direct_symptoms, list):
        symptoms.extend([str(s) for s in direct_symptoms])

    return symptoms


def extract_current_medications(profile: Dict) -> List[str]:
    """Extract current medications from treatment regimens"""
    medications = []

    treatments = profile.get('treatments', [])
    if isinstance(treatments, list):
        for treatment in treatments:
            if isinstance(treatment, dict) and treatment.get('status') == 'active':
                regimen = treatment.get('regimen', '')
                if regimen:
                    meds = []
                    if 'FOLFOX' in regimen:
                        meds.extend(['5-FU', 'Leucovorin', 'Oxaliplatin'])
                    if 'FOLFIRI' in regimen:
                        meds.extend(['5-FU', 'Leucovorin', 'Irinotecan'])
                    if 'bevacizumab' in regimen:
                        meds.append('Bevacizumab')
                    if 'panitumumab' in regimen:
                        meds.append('Panitumumab')
                    if 'TAS-102' in regimen:
                        meds.append('Trifluridine/Tipiracil')

                    medications.extend(meds)

    seen = set()
    unique_meds = []
    for med in medications:
        if med not in seen:
            seen.add(med)
            unique_meds.append(med)

    return unique_meds


def extract_patient_context_complex(profile: dict) -> Dict[str, Any]:
    """Enhanced patient context extraction that handles complex nested JSON structures."""
    if not profile:
        return {}

    context = {}

    patient_info = profile.get('patient', {})
    if isinstance(patient_info, dict):
        dob = safe_extract_value(patient_info, 'dob', 'unspecified')
        age = safe_extract_value(patient_info, 'age', None)
        
        if age and age != 'None' and age != 'unspecified':
             # Use provided age if available
             try:
                 context['age'] = int(age)
             except (ValueError, TypeError):
                 context['age'] = age
        else:
             # Fallback to calculating from DOB
             calced_age = calculate_age(dob)
             if calced_age is not None:
                context['age'] = calced_age
             else:
                context['age'] = None

        firstName = safe_extract_value(patient_info, 'firstName', None)
        name = safe_extract_value(patient_info, 'name', None)
        
        if firstName and firstName != 'unspecified' and firstName != 'None':
             context['patient_name'] = firstName
        elif name and name != 'unspecified':
             context['patient_name'] = name
             
        context['zip_code'] = safe_extract_value(patient_info, 'zipCode', 'unspecified')
        context['race_ethnicity'] = safe_extract_value(patient_info, 'raceEthnicity', 'unspecified')
        context['height'] = safe_extract_value(patient_info, 'height', 'unspecified')
        context['weight'] = safe_extract_value(patient_info, 'weight', 'unspecified')

        context['gender'] = safe_extract_value(patient_info, 'sex', 'unspecified')
        context['performance_status'] = f"ECOG {safe_extract_value(patient_info, 'ecog', 'unspecified')}"
        context['allergies'] = safe_extract_value(patient_info, 'allergies', 'none reported')

        comorbidities = patient_info.get('comorbidities', [])
        if isinstance(comorbidities, list) and comorbidities:
            context['medical_history'] = comorbidities
        else:
            context['medical_history'] = []

    primary_dx = profile.get('primaryDiagnosis', {})
    if isinstance(primary_dx, dict):
        site = safe_extract_value(primary_dx, 'site', '')
        histology = safe_extract_value(primary_dx, 'histology', '')
        stage = safe_extract_value(primary_dx, 'stage', 'unspecified')

        if site and histology:
            context['cancer_type'] = f"{site} {histology}"
        elif site:
            context['cancer_type'] = f"{site} cancer"
        elif histology:
            context['cancer_type'] = histology
        else:
            context['cancer_type'] = 'unspecified'

        context['stage'] = stage

        biomarkers = primary_dx.get('biomarkers', {})
        if isinstance(biomarkers, dict):
            context['biomarkers'] = extract_biomarkers_summary(biomarkers)
        else:
            context['biomarkers'] = 'unspecified'

    treatments = profile.get('treatments', [])
    if isinstance(treatments, list):
        context['current_treatments'] = extract_treatments_summary(treatments)
        context['medications'] = extract_current_medications(profile)

        # Extract cycle metadata from active treatment
        context['current_cycle_number'] = None
        context['treatment_line'] = None
        context['current_regimen'] = None
        context['completed_regimens'] = []

        for treatment in treatments:
            if not isinstance(treatment, dict):
                continue
            if treatment.get('status') == 'active' and context['current_regimen'] is None:
                context['current_cycle_number'] = treatment.get('cycleNumber')
                context['treatment_line'] = treatment.get('line')
                context['current_regimen'] = treatment.get('regimen')
            elif treatment.get('status') in ('completed', 'discontinued') and treatment.get('regimen'):
                context['completed_regimens'].append(treatment['regimen'])
    else:
        context['current_treatments'] = []
        context['medications'] = []
        context['current_cycle_number'] = None
        context['treatment_line'] = None
        context['current_regimen'] = None
        context['completed_regimens'] = []

    context['symptoms'] = extract_current_symptoms(profile)

    resistance = profile.get('resistance', [])
    if isinstance(resistance, list) and resistance:
        latest_resistance = resistance[-1] if resistance else {}
        if isinstance(latest_resistance, dict):
            mechanism = safe_extract_value(latest_resistance, 'mechanism', '')
            if mechanism:
                context['resistance_mechanism'] = mechanism

    current_options = profile.get('currentOptions', [])
    if isinstance(current_options, list) and current_options:
        context['treatment_options'] = current_options[:3]

    recurrences = profile.get('recurrences', [])
    if isinstance(recurrences, list) and recurrences:
        latest_recurrence = recurrences[-1] if recurrences else {}
        if isinstance(latest_recurrence, dict):
            sites = latest_recurrence.get('sites', [])
            if isinstance(sites, list) and sites:
                context['disease_sites'] = sites

    return context


def format_patient_summary_complex(context: Dict[str, Any]) -> str:
    """Format complex patient context into a readable summary for AI and UI display."""
    if not context:
        return "No patient profile available."

    summary_parts = []

    cancer_type = context.get('cancer_type', 'unspecified cancer')
    stage = context.get('stage', 'unspecified')
    if stage != 'unspecified':
        summary_parts.append(f"Diagnosis: {cancer_type}, stage {stage}")
    else:
        summary_parts.append(f"Diagnosis: {cancer_type}")

    demo_parts = []
    gender = context.get('gender', 'unspecified')
    if gender != 'unspecified':
        demo_parts.append(gender)
        
    age = context.get('age')
    if age:
        demo_parts.append(f"{age} yo")
        
    race = context.get('race_ethnicity', 'unspecified')
    if race != 'unspecified':
        demo_parts.append(race)

    performance_status = context.get('performance_status', 'unspecified')
    if performance_status != 'unspecified':
        demo_parts.append(performance_status)

    if demo_parts:
        summary_parts.append(f"Patient: {', '.join(demo_parts)}")

    treatments = context.get('current_treatments', [])
    if treatments:
        current_tx = [tx for tx in treatments if 'Currently on' in tx]
        if current_tx:
            summary_parts.append(current_tx[0])

    biomarkers = context.get('biomarkers', 'unspecified')
    if biomarkers != 'unspecified' and biomarkers:
        summary_parts.append(f"Key biomarkers: {biomarkers}")

    symptoms = context.get('symptoms', [])
    if symptoms:
        summary_parts.append(f"Current issues: {', '.join(symptoms[:2])}{'...' if len(symptoms) > 2 else ''}")

    resistance = context.get('resistance_mechanism', '')
    if resistance:
        summary_parts.append(f"Resistance: {resistance}")

    return " | ".join(summary_parts)
