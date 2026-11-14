"""
LifeLink - Unit Tests for Security & Validation Layer
Tests CSRF protection, input validators, and rate limiting.
"""

import unittest
from app import create_app
from app.services.security import (
    validate_email,
    validate_phone,
    validate_blood_group,
    validate_password_strength,
    validate_donor_profile_payload,
    validate_blood_request_payload,
)


class TestSecurityAndValidation(unittest.TestCase):
    """Verifies security controls and server-side validation rules."""

    def setUp(self):
        self.app = create_app("testing")
        self.client = self.app.test_client()

    def test_email_validation(self):
        """Valid emails must pass; invalid emails must fail."""
        valid_emails = ["donor@example.com", "patient.help@hospital.org", "first+last@sub.domain.co"]
        for email in valid_emails:
            ok, err = validate_email(email)
            self.assertTrue(ok, f"Expected '{email}' to be valid. Error: {err}")

        invalid_emails = ["notanemail", "@missinguser.com", "user@.com", "spaces in@email.com", ""]
        for email in invalid_emails:
            ok, _ = validate_email(email)
            self.assertFalse(ok, f"Expected '{email}' to be invalid.")

    def test_phone_validation(self):
        """Valid phone numbers must pass; invalid characters must fail."""
        valid_phones = ["+1 (555) 019-0002", "1234567890", "+91 9876543210"]
        for phone in valid_phones:
            ok, err = validate_phone(phone)
            self.assertTrue(ok, f"Expected '{phone}' to be valid. Error: {err}")

        invalid_phones = ["123", "call-me-now", "abc", ""]
        for phone in invalid_phones:
            ok, _ = validate_phone(phone)
            self.assertFalse(ok, f"Expected '{phone}' to be invalid.")

    def test_blood_group_validation(self):
        """Only the 8 standard ABO/Rh blood groups are allowed."""
        for bg in ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]:
            ok, _ = validate_blood_group(bg)
            self.assertTrue(ok, f"Blood group {bg} must be accepted.")

        for invalid_bg in ["C+", "O", "AB", "XYZ", "", "A++"]:
            ok, _ = validate_blood_group(invalid_bg)
            self.assertFalse(ok, f"Blood group {invalid_bg} must be rejected.")

    def test_password_strength_validation(self):
        """Enforces minimum 8 chars, at least one letter, and at least one number."""
        self.assertTrue(validate_password_strength("Secret123")[0])
        self.assertTrue(validate_password_strength("StrongPass99!")[0])

        # Too short
        self.assertFalse(validate_password_strength("Short1")[0])
        # Letters only
        self.assertFalse(validate_password_strength("NoNumbersHere")[0])
        # Numbers only
        self.assertFalse(validate_password_strength("123456789")[0])

    def test_donor_profile_payload_validation(self):
        """Validates donor onboarding payload."""
        valid_payload = {
            "blood_group": "O-",
            "weight_kg": 65.0,
            "city": "Central Metro",
            "state": "Metro State",
            "district": "District 1",
            "date_of_birth": "1995-05-15",
        }
        ok, errors = validate_donor_profile_payload(valid_payload)
        self.assertTrue(ok, f"Expected valid payload, got errors: {errors}")

        # Ineligible weight (< 40 kg)
        underweight_payload = valid_payload.copy()
        underweight_payload["weight_kg"] = 35.0
        ok, errors = validate_donor_profile_payload(underweight_payload)
        self.assertFalse(ok)
        self.assertIn("weight_kg", errors)

    def test_blood_request_payload_validation(self):
        """Validates emergency transfusion request payload."""
        valid_request = {
            "patient_name": "Robert Sterling",
            "blood_group": "O-",
            "units_needed": 2,
            "urgency_level": "CRITICAL",
            "hospital_name": "City General",
            "hospital_address": "ICU Room 12",
            "city": "Central Metro",
            "contact_person": "Dr. Sterling",
            "contact_phone": "+1 (555) 019-0010",
        }
        ok, errors = validate_blood_request_payload(valid_request)
        self.assertTrue(ok, f"Expected valid request, got errors: {errors}")

        # Invalid units (0 units)
        invalid_units = valid_request.copy()
        invalid_units["units_needed"] = 0
        ok, errors = validate_blood_request_payload(invalid_units)
        self.assertFalse(ok)
        self.assertIn("units_needed", errors)

    def test_csrf_protection_on_post(self):
        """Unauthenticated POST request without CSRF token must be rejected with HTTP 400."""
        # Establish session first
        with self.client:
            self.client.get("/")
            # POST without CSRF token
            response = self.client.post("/auth/login", data={"email": "test@example.com", "password": "pass"})
            self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
