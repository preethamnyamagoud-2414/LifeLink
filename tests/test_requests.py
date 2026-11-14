"""
LifeLink - Unit Tests for Blood Requests Module & Request Tracking
"""

import unittest
from datetime import date
from app import create_app


class TestRequestsModule(unittest.TestCase):
    """Verifies emergency transfusion request submission, validation, tracking, and privacy safeguards."""

    def setUp(self):
        self.app = create_app("testing")
        self.client = self.app.test_client()

    def test_request_form_renders(self):
        """Emergency request form renders with HTTP 200 and required fields."""
        response = self.client.get("/requests/new")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"patient_name", response.data)
        self.assertIn(b"preferred_contact_method", response.data)
        self.assertIn(b"required_date", response.data)

    def test_emergency_request_redirect_alias(self):
        """Visiting /emergency-request redirects to /requests/new."""
        response = self.client.get("/emergency-request", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/requests/new", response.location)

    def test_request_submission_validation_error(self):
        """Submitting invalid request payload returns HTTP 400 with validation message."""
        with self.client:
            with self.client.session_transaction() as sess:
                sess["_csrf_token"] = "token123"

            # Submit without patient name or valid units
            response = self.client.post(
                "/requests/new",
                data={
                    "csrf_token": "token123",
                    "patient_name": "",
                    "blood_group": "INVALID",
                    "units_needed": "0",
                }
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn(b"Patient name is required", response.data)

    def test_successful_request_submission_and_redirect_to_tracker(self):
        """Valid submission saves request and redirects to tracking page."""
        with self.client:
            with self.client.session_transaction() as sess:
                sess["_csrf_token"] = "token123"
                sess["user_id"] = 10

            response = self.client.post(
                "/requests/new",
                data={
                    "csrf_token": "token123",
                    "patient_name": "Test Patient",
                    "blood_group": "O-",
                    "units_needed": "2",
                    "urgency_level": "CRITICAL",
                    "hospital_name": "City General Hospital",
                    "hospital_address": "ICU Room 101",
                    "hospital_area": "District 1",
                    "city": "Central Metro",
                    "state": "Metro State",
                    "contact_person": "Dr. Sterling",
                    "contact_phone": "+1-555-019-0010",
                    "preferred_contact_method": "phone",
                    "required_date": str(date.today()),
                    "additional_notes": "Urgent trauma surgery"
                },
                follow_redirects=False
            )
            self.assertEqual(response.status_code, 302)
            self.assertIn("/requests/track/", response.location)

    def test_request_tracking_page_renders_with_privacy_protections(self):
        """Tracking page renders Request #1, masks donor identity, and suppresses private phone numbers."""
        response = self.client.get("/requests/track/1")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Robert Sterling", response.data)
        self.assertIn(b"O-", response.data)
        self.assertIn(b"City General Trauma Center", response.data)

        # Privacy protection test: Sarah Jenkins must be masked as 'Sarah J.'
        self.assertIn(b"Sarah J.", response.data)
        # Private phone number '+1 (555) 019-0002' must NOT be rendered in public tracking view
        self.assertNotIn(b"+1 (555) 019-0002", response.data)

    def test_medical_advisory_notice_displayed_on_tracker(self):
        """Tracking page contains the mandatory disclaimer regarding unverified donor responses."""
        response = self.client.get("/requests/track/1")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"DOES NOT represent verified biological cross-match", response.data)
        self.assertIn(b"contact an authorized hospital blood bank", response.data)

    def test_track_lookup_page(self):
        """Lookup page renders and redirects to specific request when ID is provided."""
        response = self.client.get("/requests/lookup")
        self.assertEqual(response.status_code, 200)

        redirect_response = self.client.get("/requests/lookup?id=2", follow_redirects=False)
        self.assertEqual(redirect_response.status_code, 302)
        self.assertIn("/requests/track/2", redirect_response.location)


if __name__ == "__main__":
    unittest.main()
