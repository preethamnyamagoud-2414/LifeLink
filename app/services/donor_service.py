"""
LifeLink - Donor Eligibility Service
Implements standard clinical guidelines: 90-day donation interval, age/weight verification.
"""

from typing import Dict, Any, Tuple, Optional
from datetime import date, timedelta


# Clinical guidelines
MIN_DONATION_INTERVAL_DAYS = 90
MIN_DONOR_AGE = 18
MAX_DONOR_AGE = 65
MIN_DONOR_WEIGHT_KG = 45.0


def check_eligibility(
    birth_date: Optional[date] = None,
    weight_kg: Optional[float] = None,
    last_donation: Optional[date] = None
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Evaluates clinical criteria for voluntary whole blood donation.
    
    :return: (is_eligible: bool, message: str, details: dict)
    """
    today = date.today()
    details: Dict[str, Any] = {
        "cooldown_complete": True,
        "days_remaining": 0,
        "eligible_date": today.isoformat(),
        "age_valid": True,
        "weight_valid": True
    }

    # 1. Cooldown Interval Check (90 days for whole blood)
    if last_donation:
        if isinstance(last_donation, str):
            from datetime import datetime
            last_donation = datetime.strptime(last_donation, "%Y-%m-%d").date()

        days_since = (today - last_donation).days
        if days_since < MIN_DONATION_INTERVAL_DAYS:
            days_left = MIN_DONATION_INTERVAL_DAYS - days_since
            next_date = last_donation + timedelta(days=MIN_DONATION_INTERVAL_DAYS)
            details["cooldown_complete"] = False
            details["days_remaining"] = days_left
            details["eligible_date"] = next_date.isoformat()
            return False, f"Donor is in standard 90-day cooldown. Eligible in {days_left} days ({next_date}).", details

    # 2. Weight Check
    if weight_kg is not None and weight_kg < MIN_DONOR_WEIGHT_KG:
        details["weight_valid"] = False
        return False, f"Minimum required body weight is {MIN_DONOR_WEIGHT_KG} kg (current: {weight_kg} kg).", details

    # 3. Age Check
    if birth_date:
        if isinstance(birth_date, str):
            from datetime import datetime
            birth_date = datetime.strptime(birth_date, "%Y-%m-%d").date()

        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        if age < MIN_DONOR_AGE or age > MAX_DONOR_AGE:
            details["age_valid"] = False
            return False, f"Donor age must be between {MIN_DONOR_AGE} and {MAX_DONOR_AGE} years (current: {age}).", details

    return True, "Donor satisfies baseline clinical eligibility criteria.", details
