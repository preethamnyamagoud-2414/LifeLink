"""
LifeLink - Services Package
Exports domain business logic for matching, eligibility, and authentication.
"""

from app.services.matching_service import (
    get_compatible_donors,
    is_compatible,
    RBC_COMPATIBILITY_MAP,
    UNIVERSAL_DONORS,
    UNIVERSAL_RECIPIENTS,
)
from app.services.donor_service import check_eligibility
from app.services.auth_service import (
    login_required,
    role_required,
    login_user,
    logout_user,
    get_current_user,
)

__all__ = [
    "get_compatible_donors",
    "is_compatible",
    "RBC_COMPATIBILITY_MAP",
    "UNIVERSAL_DONORS",
    "UNIVERSAL_RECIPIENTS",
    "check_eligibility",
    "login_required",
    "role_required",
    "login_user",
    "logout_user",
    "get_current_user",
]
