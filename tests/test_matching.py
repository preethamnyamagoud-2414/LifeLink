"""
LifeLink - Unit Tests for Blood Compatibility Engine
Tests ABO and Rh(D) compatibility rules.
"""

import unittest
from app.services.matching_service import (
    get_compatible_donors,
    is_compatible,
    UNIVERSAL_DONORS,
    UNIVERSAL_RECIPIENTS,
)


class TestBloodCompatibility(unittest.TestCase):
    """Verifies that all ABO/Rh blood compatibility rules adhere to clinical standards."""

    def test_universal_donor_o_negative(self):
        """O- should be able to give red blood cells to all 8 blood groups."""
        all_groups = ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"]
        for recipient in all_groups:
            self.assertTrue(
                is_compatible("O-", recipient),
                f"O- must be compatible with recipient {recipient}"
            )

    def test_universal_recipient_ab_positive(self):
        """AB+ should be able to receive red blood cells from all 8 blood groups."""
        all_groups = ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"]
        for donor in all_groups:
            self.assertTrue(
                is_compatible(donor, "AB+"),
                f"Recipient AB+ must accept blood from donor {donor}"
            )

    def test_incompatible_transfusions(self):
        """Incompatible transfusions must return False."""
        # A+ cannot give to O-
        self.assertFalse(is_compatible("A+", "O-"))
        # B+ cannot give to A+
        self.assertFalse(is_compatible("B+", "A+"))
        # AB+ cannot give to anyone other than AB+
        self.assertFalse(is_compatible("AB+", "O+"))
        self.assertFalse(is_compatible("AB+", "A-"))
        # Rh+ cannot give to Rh-
        self.assertFalse(is_compatible("O+", "O-"))
        self.assertFalse(is_compatible("B+", "B-"))

    def test_compatible_donor_list(self):
        """Validates exact list of compatible donors for specific blood types."""
        # O- can only receive from O-
        self.assertEqual(get_compatible_donors("O-"), ["O-"])
        # A- can receive from O- and A-
        self.assertEqual(set(get_compatible_donors("A-")), {"O-", "A-"})
        # B+ can receive from O-, O+, B-, B+
        self.assertEqual(set(get_compatible_donors("B+")), {"O-", "O+", "B-", "B+"})


if __name__ == "__main__":
    unittest.main()
