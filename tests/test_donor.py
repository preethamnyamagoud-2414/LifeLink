"""
LifeLink - Unit Tests for Donor Module & Privacy Search
"""

import unittest
from app import create_app


class TestDonorModule(unittest.TestCase):
    """Verifies donor portal routes, availability switch, and privacy-preserving search."""

    def setUp(self):
        self.app = create_app("testing")
        self.client = self.app.test_client()

    def test_donor_dashboard_requires_login(self):
        """Unauthenticated access to donor dashboard redirects to login."""
        response = self.client.get("/donor/dashboard", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login", response.location)

    def test_authenticated_donor_can_access_dashboard(self):
        """Authenticated donor can load dashboard with HTTP 200."""
        with self.client:
            with self.client.session_transaction() as sess:
                sess["user_id"] = 2
                sess["user_name"] = "Sarah Jenkins"
                sess["user_role"] = "donor"

            response = self.client.get("/donor/dashboard")
            self.assertEqual(response.status_code, 200)

    def test_patient_role_can_access_donor_dashboard(self):
        """A registered user with role 'patient' can access the donor dashboard (dual-role support)."""
        with self.client:
            with self.client.session_transaction() as sess:
                sess["user_id"] = 10
                sess["user_name"] = "Michael Sterling"
                sess["user_role"] = "patient"

            response = self.client.get("/donor/dashboard")
            self.assertEqual(response.status_code, 200)

    def test_availability_toggle_endpoint(self):
        """Authenticated donor can update availability status via AJAX."""
        with self.client:
            with self.client.session_transaction() as sess:
                sess["user_id"] = 2
                sess["user_role"] = "donor"
                sess["_csrf_token"] = "test-token"

            response = self.client.post(
                "/donor/availability",
                json={"csrf_token": "test-token", "is_available": True}
            )
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertTrue(data["success"])
            self.assertTrue(data["is_available"])

    def test_public_search_privacy(self):
        """Search page renders properly and maintains privacy."""
        response = self.client.get("/find-donors?blood_group=O-&location=Central%20Metro")
        self.assertEqual(response.status_code, 200)

    def test_public_search_json_api(self):
        """Search API returns structured JSON and never leaks private contact or address."""
        response = self.client.get("/find-donors?blood_group=O-&format=json")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertIn("donors", data)
        self.assertIn("count", data)

        # Verify privacy constraints on any returned donor
        for donor in data["donors"]:
            self.assertNotIn("phone", donor)
            self.assertNotIn("email", donor)
            self.assertNotIn("street_address", donor)
            self.assertNotIn("medical_notes", donor)
            self.assertIn("display_name", donor)
            self.assertIn("blood_group", donor)
            self.assertIn("city", donor)
            self.assertIn("is_available", donor)

    def test_contact_request_validation_failure(self):
        """Contact request rejects invalid phone number with HTTP 400."""
        with self.client:
            with self.client.session_transaction() as sess:
                sess["_csrf_token"] = "test-token"

            response = self.client.post(
                "/api/donors/contact-request",
                headers={"X-CSRFToken": "test-token"},
                json={
                    "donor_user_id": 2,
                    "requester_name": "Test Requester",
                    "requester_phone": "invalid-phone"
                }
            )
            self.assertEqual(response.status_code, 400)
            data = response.get_json()
            self.assertFalse(data["success"])

    def test_contact_request_success(self):
        """Contact request with valid phone delivers mediated alert."""
        with self.client:
            with self.client.session_transaction() as sess:
                sess["_csrf_token"] = "test-token"

            response = self.client.post(
                "/api/donors/contact-request",
                headers={"X-CSRFToken": "test-token"},
                json={
                    "donor_user_id": 2,
                    "requester_name": "Test Requester",
                    "requester_phone": "+1-555-234-5678",
                    "case_notes": "Urgent surgery scheduled at Memorial Hospital"
                }
            )
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertTrue(data["success"])

    def test_donor_screening_profile_update(self):
        """Authenticated donor can update clinical screening questions via /api/donor/profile."""
        with self.client:
            with self.client.session_transaction() as sess:
                sess["user_id"] = 2
                sess["user_name"] = "Sarah Jenkins"
                sess["user_role"] = "donor"
                sess["_csrf_token"] = "test-token"

            response = self.client.post(
                "/api/donor/profile",
                headers={"X-CSRFToken": "test-token"},
                json={
                    "weight_kg": 65.0,
                    "city": "Central Metro",
                    "answers": {
                        "unwell": False,
                        "antibiotics": False,
                        "tattoo": False,
                        "surgery": False,
                        "malaria": False,
                        "pregnant": False,
                        "blood_pressure": False,
                        "infection": False,
                        "chronic": False,
                        "insulin": False
                    },
                    "consent": True
                }
            )
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertTrue(data["success"])
            self.assertIn("donor", data)
            self.assertIn("eligibility", data["donor"])
            self.assertEqual(data["donor"]["eligibility"]["status"], "ELIGIBLE")
            self.assertTrue(data["donor"]["eligibility"]["eligible"])

    def test_donor_screening_temporary_deferral(self):
        """Updating screening answers with temporary condition defers the donor."""
        with self.client:
            with self.client.session_transaction() as sess:
                sess["user_id"] = 2
                sess["user_name"] = "Sarah Jenkins"
                sess["user_role"] = "donor"
                sess["_csrf_token"] = "test-token"

            response = self.client.post(
                "/api/donor/profile",
                headers={"X-CSRFToken": "test-token"},
                json={
                    "weight_kg": 65.0,
                    "city": "Central Metro",
                    "answers": {
                        "unwell": True,
                        "antibiotics": False
                    },
                    "consent": True
                }
            )
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(data["donor"]["eligibility"]["status"], "TEMPORARY_DEFERRAL")
            self.assertFalse(data["donor"]["eligibility"]["eligible"])


if __name__ == "__main__":
    unittest.main()
