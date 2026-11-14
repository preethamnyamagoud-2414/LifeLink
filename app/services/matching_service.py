"""
LifeLink - Blood Compatibility Engine
Implements biological ABO and Rh(D) factor transfusion rules.
"""

from typing import List, Dict

# Red Blood Cell (RBC) Compatibility Matrix
# Maps recipient blood group -> list of compatible donor blood groups
RBC_COMPATIBILITY_MAP: Dict[str, List[str]] = {
    "O-": ["O-"],
    "O+": ["O-", "O+"],
    "A-": ["O-", "A-"],
    "A+": ["O-", "O+", "A-", "A+"],
    "B-": ["O-", "B-"],
    "B+": ["O-", "O+", "B-", "B+"],
    "AB-": ["O-", "A-", "B-", "AB-"],
    "AB+": ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"],  # Universal Recipient
}

# Universal Donor / Recipient Classifications
UNIVERSAL_DONORS = ["O-"]
UNIVERSAL_RECIPIENTS = ["AB+"]


def get_compatible_donors(recipient_blood_group: str) -> List[str]:
    """
    Returns a list of donor blood groups compatible with the given recipient blood group.
    
    :param recipient_blood_group: e.g. 'A+', 'O-'
    :return: List of compatible donor blood groups.
    """
    cleaned_group = recipient_blood_group.strip().upper()
    return RBC_COMPATIBILITY_MAP.get(cleaned_group, [cleaned_group])


def is_compatible(donor_blood_group: str, recipient_blood_group: str) -> bool:
    """
    Checks if a donor's blood can be safely transfused into a recipient.
    
    :param donor_blood_group: e.g. 'O-'
    :param recipient_blood_group: e.g. 'B+'
    :return: True if compatible, False otherwise.
    """
    d_group = donor_blood_group.strip().upper()
    r_group = recipient_blood_group.strip().upper()
    compatible_list = get_compatible_donors(r_group)
    return d_group in compatible_list
