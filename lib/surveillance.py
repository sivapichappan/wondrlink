"""
NCCN Survivorship Surveillance Schedule Engine for WondrLink

Generates personalized surveillance schedules based on NCCN guidelines
for colorectal cancer. Uses patient stage, surgery date, and last
colonoscopy date to calculate upcoming recommended appointments.

NCCN Guidelines (Colon Cancer, Version 2.2025):
- Stage I:
  - Colonoscopy at 1 year post-resection, then every 3 years if normal
  - History/physical every 6 months for 2 years, then annually for 3 years
  - CEA every 6 months for 2 years (if T2 or greater)

- Stage II-III:
  - Colonoscopy at 1 year, then every 3-5 years
  - CEA every 3-6 months for 2 years, then every 6 months for 3 years
  - CT chest/abdomen/pelvis annually for up to 5 years (stage II-III)
  - History/physical every 3-6 months for 2 years, then every 6 months for 3 years

- Stage IV (post-resection of metastases):
  - Per oncologist; more frequent imaging
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def generate_surveillance_schedule(stage: str, surgery_date: str,
                                    last_colonoscopy_date: str = None,
                                    diagnosis_date: str = None,
                                    cancer_slug: str = None) -> Dict[str, Any]:
    """
    Generate a personalized surveillance schedule based on guidelines for
    the patient's cancer.

    Phase 1 dispatch behavior:
      - cancer_slug in (None, 'colorectal')  → run the colon-specific
        procedural logic below. Unchanged from pre-refactor (preserves
        eval parity).
      - cancer_slug = any other slug         → return a "coming soon"
        stub. Other cancers ship their own deterministic rubric (read
        from config/cancers/<slug>/surveillance.yaml) when they flip
        ready: true; until then the user is asked to defer to their
        oncology team.

    Args:
        stage: Cancer stage (I, II, IIA, IIB, III, IIIA, IIIB, IIIC, IV)
        surgery_date: Date of primary surgery (YYYY-MM-DD or relative)
        last_colonoscopy_date: Date of last colonoscopy (colorectal only)
        diagnosis_date: Date of diagnosis (optional)
        cancer_slug: Per-cancer dispatch. None = colorectal.

    Returns:
        Dict with 'schedule' (list of items), 'overdue' (list), 'stage_group'
    """
    # Multi-cancer dispatch — Phase 1 keeps colorectal as the only
    # implemented surveillance rubric. Other slugs return a stub so the
    # frontend can render "coming soon" gracefully.
    if cancer_slug and cancer_slug != 'colorectal':
        try:
            from lib.cancer_registry import display_name
            label = display_name(cancer_slug)
        except Exception:
            label = "this cancer"
        return {
            'schedule': [],
            'overdue': [],
            'stage_group': 'unknown',
            'cancer_slug': cancer_slug,
            'message': (
                f"A personalized surveillance schedule for {label} is coming soon. "
                f"In the meantime, please follow the plan your oncology team has set "
                f"for you — surveillance protocols differ meaningfully between cancers, "
                f"and your team's recommendation is the one to trust."
            ),
        }

    now = datetime.now()

    # Parse surgery date
    surgery_dt = _parse_date(surgery_date)
    if not surgery_dt:
        return {
            'schedule': [],
            'overdue': [],
            'stage_group': 'unknown',
            'message': 'Surgery date needed to generate surveillance schedule.'
        }

    # Parse last colonoscopy
    last_colonoscopy_dt = _parse_date(last_colonoscopy_date) if last_colonoscopy_date else None

    # Determine stage group
    stage_upper = str(stage).upper().replace(' ', '')
    if any(s in stage_upper for s in ['IV', '4']):
        stage_group = 'IV'
    elif any(s in stage_upper for s in ['III', '3']):
        stage_group = 'II-III'
    elif any(s in stage_upper for s in ['II', '2']):
        stage_group = 'II-III'
    elif any(s in stage_upper for s in ['I', '1']):
        stage_group = 'I'
    else:
        stage_group = 'II-III'  # Default to more conservative

    months_since_surgery = (now - surgery_dt).days / 30.44

    schedule = []
    overdue = []

    if stage_group == 'IV':
        schedule.append({
            'type': 'Oncologist Visit',
            'recommendation': 'Follow your oncologist\'s individualized surveillance plan',
            'frequency': 'As directed by your oncology team',
            'next_due': None,
            'status': 'ongoing'
        })
        return {
            'schedule': schedule,
            'overdue': [],
            'stage_group': stage_group,
            'months_since_surgery': round(months_since_surgery)
        }

    # === Colonoscopy Schedule ===
    if last_colonoscopy_dt:
        months_since_scope = (now - last_colonoscopy_dt).days / 30.44
        if stage_group == 'I':
            next_scope_months = 36  # Every 3 years after first
        else:
            next_scope_months = 36  # Every 3 years (can extend to 5 if normal)
        next_scope_date = last_colonoscopy_dt + timedelta(days=next_scope_months * 30.44)
    else:
        # First colonoscopy at 1 year post-surgery
        next_scope_date = surgery_dt + timedelta(days=365)

    scope_item = {
        'type': 'Colonoscopy',
        'recommendation': 'At 1 year post-surgery, then every 3 years if normal',
        'frequency': 'Every 1-3 years',
        'next_due': next_scope_date.strftime('%B %Y'),
        'status': 'overdue' if next_scope_date < now else 'upcoming'
    }
    schedule.append(scope_item)
    if scope_item['status'] == 'overdue':
        overdue.append(scope_item)

    # === CEA Testing ===
    if months_since_surgery <= 24:
        cea_freq = 3 if stage_group == 'II-III' else 6
        cea_label = f'Every {cea_freq} months for first 2 years'
    elif months_since_surgery <= 60:
        cea_freq = 6
        cea_label = 'Every 6 months (years 2-5)'
    else:
        cea_freq = None
        cea_label = 'Completed (past 5 years)'

    if cea_freq:
        last_cea_approx = now - timedelta(days=cea_freq * 30.44)
        next_cea = last_cea_approx + timedelta(days=cea_freq * 30.44)
        schedule.append({
            'type': 'CEA Blood Test',
            'recommendation': cea_label,
            'frequency': f'Every {cea_freq} months',
            'next_due': next_cea.strftime('%B %Y') if next_cea > now else 'Due now',
            'status': 'upcoming' if next_cea > now else 'due'
        })

    # === CT Imaging (Stage II-III only) ===
    if stage_group == 'II-III' and months_since_surgery <= 60:
        next_ct = surgery_dt + timedelta(days=365 * (int(months_since_surgery / 12) + 1))
        if next_ct < now:
            next_ct = now + timedelta(days=30)  # Suggest soon
        ct_item = {
            'type': 'CT Scan (Chest/Abdomen/Pelvis)',
            'recommendation': 'Annually for up to 5 years post-surgery',
            'frequency': 'Every 12 months',
            'next_due': next_ct.strftime('%B %Y'),
            'status': 'upcoming'
        }
        schedule.append(ct_item)

    # === Office Visits ===
    if months_since_surgery <= 24:
        visit_freq = 3 if stage_group == 'II-III' else 6
        visit_label = f'Every {visit_freq} months for first 2 years'
    elif months_since_surgery <= 60:
        visit_freq = 6
        visit_label = 'Every 6 months (years 3-5)'
    else:
        visit_freq = 12
        visit_label = 'Annually after 5 years'

    schedule.append({
        'type': 'Office Visit (History & Physical)',
        'recommendation': visit_label,
        'frequency': f'Every {visit_freq} months',
        'next_due': (now + timedelta(days=visit_freq * 15)).strftime('%B %Y'),
        'status': 'upcoming'
    })

    return {
        'schedule': schedule,
        'overdue': overdue,
        'stage_group': stage_group,
        'months_since_surgery': round(months_since_surgery)
    }


def format_surveillance_for_chat(schedule_data: Dict[str, Any]) -> str:
    """Format surveillance schedule for inclusion in LLM context."""
    if not schedule_data or not schedule_data.get('schedule'):
        return ""

    parts = [f"SURVEILLANCE SCHEDULE (Stage {schedule_data['stage_group']}, "
             f"{schedule_data.get('months_since_surgery', '?')} months post-surgery):"]

    for item in schedule_data['schedule']:
        status_icon = '!' if item['status'] == 'overdue' else '-'
        due = item.get('next_due', 'TBD')
        parts.append(f"  {status_icon} {item['type']}: {item['recommendation']} (Next: {due})")

    if schedule_data.get('overdue'):
        parts.append("  OVERDUE items require prompt scheduling.")

    return "\n".join(parts)


def _parse_date(date_str: str) -> Optional[datetime]:
    """Parse a date string, handling both absolute and relative formats."""
    if not date_str or date_str in ('unspecified', 'None', '', 'date not specified'):
        return None

    # Try absolute format
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y'):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    # Try relative format ("approximately X months ago")
    import re
    match = re.search(r'(\d+)\s*month', date_str)
    if match:
        months = int(match.group(1))
        return datetime.now() - timedelta(days=months * 30.44)

    match = re.search(r'(\d+)\s*year', date_str)
    if match:
        years = int(match.group(1))
        return datetime.now() - timedelta(days=years * 365.25)

    return None
