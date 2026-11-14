"""
LifeLink - Unit Tests for Donor, Patient, and Admin Dashboards
Verifies data retrieval, statistics, role-based authorization, and UI components.
"""

import unittest
from app import create_app


class TestDashboards(unittest.TestCase):
    """Verifies all 3 dedicated dashboards and their server-side authorization."""

    def setUp(self):
        self.app = create_app("testing")
        self.client = self.app.test_client()

    # --------------------------------------------------------------------------
    # 1. DONOR DASHBOARD TESTS
    # --------------------------------------------------------------------------
    def test_donor_dashboard_requires_login(self):
        """Unauthenticated access to /donor/dashboard redirects to login."""
        response = self.client.get("/donor/dashboard", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login", response.location)

    def test_donor_dashboard_renders_all_six_components(self):
        """Donor dashboard renders profile completion, blood group, availability, requests, responses, and notifications."""
        with self.client:
            with self.client.session_transaction() as sess:
                sess["user_id"] = 2
                sess["user_name"] = "Sarah Jenkins"
                sess["user_role"] = "donor"

            response = self.client.get("/donor/dashboard")
            self.assertEqual(response.status_code, 200)

            # Component 1: Profile completion
            self.assertIn(b"Profile Completion", response.data)

            # Component 2: Blood group
            self.assertIn(b"O-", response.data)

            # Component 3: Availability setting
            self.assertIn(b"Emergency Availability Setting", response.data)

            # Component 4: Recent blood requests
            self.assertIn(b"Recent Blood Requests Near You", response.data)

            # Component 5: Requests responded to
            self.assertIn(b"Requests You Have Responded To", response.data)

            # Component 6: Notifications
            self.assertIn(b"Recent Alerts &amp; Notifications", response.data)

    # --------------------------------------------------------------------------
    # 2. PATIENT DASHBOARD TESTS
    # --------------------------------------------------------------------------
    def test_patient_dashboard_requires_login(self):
        """Unauthenticated access to /patient/dashboard redirects to login."""
        response = self.client.get("/patient/dashboard", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login", response.location)

    def test_patient_dashboard_renders_all_components(self):
        """Patient dashboard renders new request CTA, active requests, previous requests, donor responses, and tracking."""
        with self.client:
            with self.client.session_transaction() as sess:
                sess["user_id"] = 10
                sess["user_name"] = "Michael Sterling"
                sess["user_role"] = "patient"

            response = self.client.get("/patient/dashboard")
            self.assertEqual(response.status_code, 200)

            # Component 1: Submit new request CTA
            self.assertIn(b"Submit New Blood Request", response.data)

            # Component 2: Active requests
            self.assertIn(b"Your Active Blood Requests", response.data)

            # Component 3: Previous requests
            self.assertIn(b"Previous &amp; Completed Requisitions", response.data)

            # Component 4: Donor responses
            self.assertIn(b"Incoming Donor Responses", response.data)

            # Component 5: Request tracking
            self.assertIn(b"Track Live Status", response.data)

    # --------------------------------------------------------------------------
    # 3. ADMIN DASHBOARD & AUTHORIZATION TESTS
    # --------------------------------------------------------------------------
    def test_admin_dashboard_unauthenticated_blocked(self):
        """Unauthenticated access to /admin/ is blocked and redirected to login."""
        response = self.client.get("/admin/", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login", response.location)

    def test_admin_dashboard_forbidden_for_patient(self):
        """Patients accessing /admin/ are rejected with HTTP 403 Forbidden."""
        with self.client:
            with self.client.session_transaction() as sess:
                sess["user_id"] = 10
                sess["user_name"] = "Michael Sterling"
                sess["user_role"] = "patient"

            response = self.client.get("/admin/")
            self.assertEqual(response.status_code, 403)

    def test_admin_dashboard_forbidden_for_donor(self):
        """Donors accessing /admin/ are rejected with HTTP 403 Forbidden."""
        with self.client:
            with self.client.session_transaction() as sess:
                sess["user_id"] = 2
                sess["user_name"] = "Sarah Jenkins"
                sess["user_role"] = "donor"

            response = self.client.get("/admin/")
            self.assertEqual(response.status_code, 403)

    def test_admin_dashboard_renders_for_authorized_admin(self):
        """Authorized admin loads /admin/ with HTTP 200 and all system KPIs."""
        with self.client:
            with self.client.session_transaction() as sess:
                sess["user_id"] = 1
                sess["user_name"] = "System Administrator"
                sess["user_role"] = "admin"

            response = self.client.get("/admin/")
            self.assertEqual(response.status_code, 200)

            # KPI metrics verification
            self.assertIn(b"Registered Accounts", response.data)
            self.assertIn(b"Donor Profiles", response.data)
            self.assertIn(b"Active Blood Requests", response.data)
            self.assertIn(b"Completed &amp; Cancelled", response.data)

            # Inventory distribution chart
            self.assertIn(b"Donor Registry ABO &amp; Rh Distribution", response.data)

    def test_admin_manage_users_endpoint(self):
        """Admin can access /admin/users to manage registered accounts."""
        with self.client:
            with self.client.session_transaction() as sess:
                sess["user_id"] = 1
                sess["user_role"] = "admin"

            response = self.client.get("/admin/users")
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"User Accounts Administration", response.data)

    def test_admin_manage_requests_endpoint(self):
        """Admin can access /admin/requests to moderate requisitions."""
        with self.client:
            with self.client.session_transaction() as sess:
                sess["user_id"] = 1
                sess["user_role"] = "admin"

            response = self.client.get("/admin/requests")
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Blood Transfusion Requisitions Moderation", response.data)

    def test_admin_audit_logs_endpoint(self):
        """Admin can review audit logs and suspicious activity."""
        with self.client:
            with self.client.session_transaction() as sess:
                sess["user_id"] = 1
                sess["user_role"] = "admin"

            response = self.client.get("/admin/audit-logs")
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Cryptographic Audit &amp; Security Activity Logs", response.data)


if __name__ == "__main__":
    unittest.main()
