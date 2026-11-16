"""
LifeLink - Unit Tests for Donor Eligibility Rules
Tests 90-day cooldown interval, weight, and age validations.
"""

import unittest
from datetime import date, timedelta
from app.services.donor_service import check_eligibility, MIN_DONATION_INTERVAL_DAYS


class TestDonorEligibility(unittest.TestCase):
    """Verifies donor eligibility logic."""

    def test_eligible_donor(self):
        """A healthy adult with no recent donations should be immediately eligible."""
        eligible, msg, details = check_eligibility(
            birth_date=date(1995, 5, 20),
            weight_kg=68.5,
            last_donation=None
        )
        self.assertTrue(eligible)
        self.assertTrue(details["cooldown_complete"])

    def test_cooldown_active(self):
        """A donor who donated 30 days ago must be in cooldown."""
        recent_donation = date.today() - timedelta(days=30)
        eligible, msg, details = check_eligibility(
            birth_date=date(1995, 5, 20),
            weight_kg=68.5,
            last_donation=recent_donation
        )
        self.assertFalse(eligible)
        self.assertFalse(details["cooldown_complete"])
        self.assertEqual(details["days_remaining"], 60)

    def test_cooldown_completed(self):
        """A donor who donated 95 days ago has completed cooldown."""
        past_donation = date.today() - timedelta(days=95)
        eligible, msg, details = check_eligibility(
            birth_date=date(1995, 5, 20),
            weight_kg=68.5,
            last_donation=past_donation
        )
        self.assertTrue(eligible)
        self.assertTrue(details["cooldown_complete"])

    def test_underweight(self):
        """A donor weighing under 45 kg should be marked ineligible."""
        eligible, msg, details = check_eligibility(
            birth_date=date(1995, 5, 20),
            weight_kg=42.0,
            last_donation=None
        )
        self.assertFalse(eligible)
        self.assertFalse(details["weight_valid"])

    def test_underage(self):
        """A donor under 18 should be marked ineligible."""
        underage_birth = date.today() - timedelta(days=365 * 16)
        eligible, msg, details = check_eligibility(
            birth_date=underage_birth,
            weight_kg=60.0,
            last_donation=None
        )
        self.assertFalse(eligible)
        self.assertFalse(details["age_valid"])

    def test_screening_temporary_deferral(self):
        """A donor with recent antibiotic intake should receive a temporary deferral."""
        eligible, msg, details = check_eligibility(
            birth_date=date(1995, 5, 20),
            weight_kg=68.5,
            screening_answers={"antibiotics": True}
        )
        self.assertFalse(eligible)
        self.assertEqual(details["status"], "TEMPORARY_DEFERRAL")
        self.assertFalse(details["screening_valid"])
        self.assertTrue(len(details["reasons"]) > 0)

    def test_screening_permanent_deferral(self):
        """A donor with HIV/Hepatitis/Syphilis or insulin diabetes should receive permanent deferral."""
        eligible, msg, details = check_eligibility(
            birth_date=date(1995, 5, 20),
            weight_kg=68.5,
            screening_answers={"infection": True}
        )
        self.assertFalse(eligible)
        self.assertEqual(details["status"], "PERMANENT_DEFERRAL")
        self.assertIsNone(details["eligible_from"])

    def test_screening_female_only_question(self):
        """Pregnancy question only defers female donors."""
        # Male donor answering pregnant=True should be ignored
        eligible_male, _, _ = check_eligibility(
            birth_date=date(1995, 5, 20),
            weight_kg=68.5,
            gender="male",
            screening_answers={"pregnant": True}
        )
        self.assertTrue(eligible_male)

        # Female donor answering pregnant=True should be deferred
        eligible_female, _, details = check_eligibility(
            birth_date=date(1995, 5, 20),
            weight_kg=68.5,
            gender="female",
            screening_answers={"pregnant": True}
        )
        self.assertFalse(eligible_female)
        self.assertEqual(details["status"], "TEMPORARY_DEFERRAL")


if __name__ == "__main__":
    unittest.main()
