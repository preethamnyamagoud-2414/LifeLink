"""
LifeLink - Donor Eligibility Service
Implements standard clinical guidelines: 90-day donation interval, age/weight verification.
"""

from typing import Dict, Any, Tuple, Optional
from datetime import date, timedelta


"""
LifeLink - Donor Eligibility Service
Implements standard clinical guidelines: 90-day donation interval, age/weight verification,
and 10-point comprehensive health screening questionnaire.
"""

from typing import Dict, Any, Tuple, Optional, List
from datetime import date, timedelta
import json
import logging

logger = logging.getLogger(__name__)

# Clinical guidelines
MIN_DONATION_INTERVAL_DAYS = 90
MIN_DONOR_AGE = 18
MAX_DONOR_AGE = 65
MIN_DONOR_WEIGHT_KG = 45.0

# 10 Clinical Health Screening Questionnaire Definitions
DONOR_SCREENING_QUESTIONS = [
    {
        "key": "unwell",
        "text": "In the last 7 days, have you had fever, cold, flu, or felt unwell?",
        "deferral": "TEMPORARY_DEFERRAL",
        "days": 7,
        "msg": "Currently unwell or recovering from fever/cold/flu in last 7 days"
    },
    {
        "key": "antibiotics",
        "text": "Have you taken antibiotics in the last 7 days?",
        "deferral": "TEMPORARY_DEFERRAL",
        "days": 7,
        "msg": "Recent antibiotic medication course in last 7 days"
    },
    {
        "key": "tattoo",
        "text": "Have you had a tattoo, body piercing or acupuncture in the last 12 months?",
        "deferral": "TEMPORARY_DEFERRAL",
        "days": 180,
        "msg": "Tattoo, body piercing, or acupuncture within last 12 months (infection window)"
    },
    {
        "key": "surgery",
        "text": "Have you had major surgery in the last 6 months?",
        "deferral": "TEMPORARY_DEFERRAL",
        "days": 180,
        "msg": "Major surgical procedure within last 6 months"
    },
    {
        "key": "malaria",
        "text": "Have you had malaria in the last 3 months?",
        "deferral": "TEMPORARY_DEFERRAL",
        "days": 90,
        "msg": "Malaria infection or anti-malarial treatment in last 3 months"
    },
    {
        "key": "pregnant",
        "text": "Are you pregnant, or have you given birth / been breastfeeding in the last 12 months?",
        "female_only": True,
        "deferral": "TEMPORARY_DEFERRAL",
        "days": 365,
        "msg": "Current pregnancy or postpartum / lactation within last 12 months"
    },
    {
        "key": "blood_pressure",
        "text": "Do you have high or low blood pressure that is not under control?",
        "deferral": "TEMPORARY_DEFERRAL",
        "days": 14,
        "msg": "Blood pressure currently not medically stabilized"
    },
    {
        "key": "infection",
        "text": "Have you ever tested positive for HIV, Hepatitis B, Hepatitis C or syphilis?",
        "deferral": "PERMANENT_DEFERRAL",
        "msg": "History of blood-borne viral infection (HIV/Hepatitis/Syphilis)"
    },
    {
        "key": "chronic",
        "text": "Do you have heart disease, cancer, kidney or liver disease, epilepsy, or a bleeding disorder?",
        "deferral": "PERMANENT_DEFERRAL",
        "msg": "Chronic underlying medical condition (cardiac, oncologic, renal, or bleeding disorder)"
    },
    {
        "key": "insulin",
        "text": "Do you have diabetes that is treated with insulin?",
        "deferral": "PERMANENT_DEFERRAL",
        "msg": "Insulin-dependent diabetes mellitus"
    }
]


def check_eligibility(
    birth_date: Optional[date] = None,
    weight_kg: Optional[float] = None,
    last_donation: Optional[date] = None,
    gender: Optional[str] = None,
    screening_answers: Optional[Dict[str, Any]] = None,
    medical_notes: Optional[str] = None
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Evaluates clinical criteria for voluntary whole blood donation.
    Checks 90-day cooldown interval, age, weight, and the 10-point screening questions.
    
    :return: (is_eligible: bool, message: str, details: dict)
    """
    today = date.today()
    reasons: List[Dict[str, Any]] = []
    has_permanent_deferral = False
    max_deferral_date: Optional[date] = None

    details: Dict[str, Any] = {
        "cooldown_complete": True,
        "days_remaining": 0,
        "eligible_date": today.isoformat(),
        "age_valid": True,
        "weight_valid": True,
        "screening_valid": True,
        "eligible": True,
        "status": "ELIGIBLE",
        "reasons": reasons,
        "answers": {},
        "eligible_from": None
    }

    # Extract screening answers from medical_notes if not passed directly
    answers: Dict[str, bool] = {}
    if screening_answers:
        for k, v in screening_answers.items():
            answers[k] = v in (True, "true", "yes", 1, "1")
    elif medical_notes:
        try:
            parsed = json.loads(medical_notes)
            if isinstance(parsed, dict) and "answers" in parsed:
                answers = parsed["answers"]
        except Exception:
            pass

    details["answers"] = answers

    # 1. Evaluate Screening Questionnaire Answers
    normalized_gender = (gender or "").strip().lower()
    for q in DONOR_SCREENING_QUESTIONS:
        k = q["key"]
        if q.get("female_only") and normalized_gender != "female":
            continue

        if answers.get(k) is True:
            details["screening_valid"] = False
            if q["deferral"] == "PERMANENT_DEFERRAL":
                has_permanent_deferral = True
                reasons.append({"message": q["msg"], "until": None})
            else:
                days = q.get("days", 30)
                until_date = today + timedelta(days=days)
                if max_deferral_date is None or until_date > max_deferral_date:
                    max_deferral_date = until_date
                reasons.append({"message": q["msg"], "until": until_date.isoformat()})

    # 2. Cooldown Interval Check (90 days for whole blood)
    if last_donation:
        if isinstance(last_donation, str):
            from datetime import datetime
            try:
                last_donation = datetime.strptime(last_donation, "%Y-%m-%d").date()
            except ValueError:
                last_donation = None

        if last_donation:
            days_since = (today - last_donation).days
            if days_since < MIN_DONATION_INTERVAL_DAYS:
                days_left = MIN_DONATION_INTERVAL_DAYS - days_since
                next_date = last_donation + timedelta(days=MIN_DONATION_INTERVAL_DAYS)
                details["cooldown_complete"] = False
                details["days_remaining"] = days_left
                details["eligible_date"] = next_date.isoformat()
                if max_deferral_date is None or next_date > max_deferral_date:
                    max_deferral_date = next_date
                reasons.append({
                    "message": f"Standard 90-day cooldown interval between blood donations ({days_left} days remaining)",
                    "until": next_date.isoformat()
                })

    # 3. Weight Check (clinical minimum: 45 kg)
    if weight_kg is not None and weight_kg < MIN_DONOR_WEIGHT_KG:
        details["weight_valid"] = False
        reasons.append({
            "message": f"Minimum body weight requirement is {MIN_DONOR_WEIGHT_KG} kg (current: {weight_kg} kg)",
            "until": None
        })

    # 4. Age Check (18 to 65)
    if birth_date:
        if isinstance(birth_date, str):
            from datetime import datetime
            try:
                birth_date = datetime.strptime(birth_date, "%Y-%m-%d").date()
            except ValueError:
                birth_date = None

        if birth_date:
            age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
            if age < MIN_DONOR_AGE or age > MAX_DONOR_AGE:
                details["age_valid"] = False
                if age < MIN_DONOR_AGE:
                    reasons.append({
                        "message": f"Donor must be at least {MIN_DONOR_AGE} years of age (current: {age})",
                        "until": None
                    })
                else:
                    has_permanent_deferral = True
                    reasons.append({
                        "message": f"Donor age exceeds maximum clinical threshold of {MAX_DONOR_AGE} years",
                        "until": None
                    })

    # Determine final verdict
    if has_permanent_deferral:
        details["status"] = "PERMANENT_DEFERRAL"
        details["eligible"] = False
        details["eligible_from"] = None
        first_msg = reasons[0]["message"] if reasons else "Permanent deferral"
        return False, f"Donor is not eligible: {first_msg}.", details

    if reasons:
        details["status"] = "TEMPORARY_DEFERRAL"
        details["eligible"] = False
        if max_deferral_date:
            details["eligible_from"] = max_deferral_date.isoformat()
            details["eligible_date"] = max_deferral_date.isoformat()
        first_msg = reasons[0]["message"]
        return False, f"Temporary deferral: {first_msg}.", details

    details["status"] = "ELIGIBLE"
    details["eligible"] = True
    return True, "Donor satisfies baseline clinical eligibility criteria.", details

