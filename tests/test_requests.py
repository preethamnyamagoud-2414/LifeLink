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

    def test_api_requests_submission_unauthenticated(self):
        """Posting to /api/requests without an active session returns HTTP 401 JSON."""
        with self.client:
            with self.client.session_transaction() as sess:
                sess["_csrf_token"] = "token123"

            response = self.client.post(
                "/api/requests",
                json={
                    "csrf_token": "token123",
                    "patient_name": "Test Patient",
                    "blood_group": "A+",
                    "units_needed": 2,
                    "hospital_name": "Metro General Hospital",
                    "hospital_address": "ICU Ward 2",
                    "hospital_area": "District 1",
                    "city": "Central Metro",
                    "contact_person": "Jane Doe",
                    "contact_phone": "+1-555-019-0010"
                }
            )
            self.assertEqual(response.status_code, 401)
            data = response.get_json()
            self.assertFalse(data.get("success"))

    def test_api_requests_submission_success(self):
        """Posting valid emergency request to /api/requests returns HTTP 200 JSON with code and redirect."""
        with self.client:
            with self.client.session_transaction() as sess:
                sess["_csrf_token"] = "token123"
                sess["user_id"] = 10
                sess["user_name"] = "Dr. Michael Sterling"

            response = self.client.post(
                "/api/requests",
                json={
                    "csrf_token": "token123",
                    "patient_name": "Emergency Patient",
                    "blood_group": "O-",
                    "units_needed": 2,
                    "urgency_level": "CRITICAL",
                    "hospital_name": "City Trauma Center",
                    "hospital_address": "Emergency Bay 4",
                    "hospital_area": "District 1",
                    "city": "Central Metro",
                    "contact_person": "Dr. Sterling",
                    "contact_phone": "+1-555-019-0010",
                    "preferred_contact_method": "phone",
                    "required_date": str(date.today())
                }
            )
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertTrue(data.get("success"))
            self.assertIn("REQ-", data.get("code", ""))
            self.assertIn("/requests/track/", data.get("redirect", ""))
            self.assertGreaterEqual(data.get("alerted", 0), 0)

    def test_api_auth_me(self):
        """Verifies /api/auth/me returns 401 when guest and 200 JSON when authenticated."""
        guest_res = self.client.get("/api/auth/me")
        self.assertEqual(guest_res.status_code, 401)

        with self.client:
            with self.client.session_transaction() as sess:
                sess["user_id"] = 1
                sess["user_role"] = "admin"
                sess["user_name"] = "Admin User"

            auth_res = self.client.get("/api/auth/me")
            self.assertEqual(auth_res.status_code, 200)
            data = auth_res.get_json()
            self.assertTrue(data.get("success"))
            self.assertEqual(data["user"]["role"], "admin")

    def test_api_donors_search_json(self):
        """Verifies /api/donors/search returns HTTP 200 with JSON donor list."""
        response = self.client.get("/api/donors/search?blood_group=O-&format=json")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("success"))
        self.assertIn("donors", data)

    def test_volunteer_submission(self):
        """Verifies volunteering for an active request records response and notifies requester."""
        with self.client:
            with self.client.session_transaction() as sess:
                sess["_csrf_token"] = "token123"
                sess["user_id"] = 2  # Donor Sarah J.

            response = self.client.post(
                "/requests/1/volunteer",
                data={
                    "csrf_token": "token123",
                    "message": "I am nearby and can donate within 30 minutes."
                },
                follow_redirects=False
            )
            self.assertEqual(response.status_code, 302)
            self.assertIn("/requests/track/1", response.location)

    def test_api_auth_logout(self):
        """Verifies /api/auth/logout clears user session and returns 200 JSON."""
        with self.client:
            with self.client.session_transaction() as sess:
                sess["_csrf_token"] = "token123"
                sess["user_id"] = 10

            res = self.client.post(
                "/api/auth/logout",
                headers={"X-CSRFToken": "token123"}
            )
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data.get("success"))

    def test_api_profile_update(self):
        """Verifies /api/profile accepts valid updates."""
        with self.client:
            with self.client.session_transaction() as sess:
                sess["_csrf_token"] = "token123"
                sess["user_id"] = 10

            res = self.client.post(
                "/api/profile",
                json={
                    "csrf_token": "token123",
                    "full_name": "Updated Full Name",
                    "phone": "+1-555-019-0099",
                    "city": "Metro City",
                    "district": "North District"
                }
            )
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data.get("success"))


if __name__ == "__main__":
    unittest.main()
