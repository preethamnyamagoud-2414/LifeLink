"""
LifeLink - Unit Tests for Authentication & Session Management
"""

import unittest
from app import create_app
from app.services.security import generate_csrf_token


class TestAuthModule(unittest.TestCase):
    """Verifies user login, registration, session roles, and logout."""

    def setUp(self):
        self.app = create_app("testing")
        self.client = self.app.test_client()

    def test_login_page_renders(self):
        """Login page must render with HTTP 200."""
        response = self.client.get("/auth/login")
        self.assertEqual(response.status_code, 200)

    def test_register_page_renders(self):
        """Register choices and forms must render with HTTP 200."""
        res_choice = self.client.get("/auth/register")
        self.assertEqual(res_choice.status_code, 200)

        res_donor = self.client.get("/auth/register/donor")
        self.assertEqual(res_donor.status_code, 200)

        res_patient = self.client.get("/auth/register/patient")
        self.assertEqual(res_patient.status_code, 200)

    def test_login_invalid_email_format(self):
        """Login attempt with malformed email format returns HTTP 400 and error message."""
        with self.client:
            self.client.get("/")
            with self.client.session_transaction() as sess:
                sess["_csrf_token"] = "test-csrf-token"

            response = self.client.post(
                "/auth/login",
                data={
                    "csrf_token": "test-csrf-token",
                    "email": "invalid-email-address",
                    "password": "Password123"
                }
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn(b"Please provide a valid email address", response.data)

    def test_login_invalid_credentials_with_db(self):
        """Testing login with bad password against authenticated DB returns failure message."""
        from unittest.mock import patch

        with self.client:
            self.client.get("/")
            with self.client.session_transaction() as sess:
                sess["_csrf_token"] = "test-csrf-token"

            # Mock DB connection returning True and User returning a record
            with patch("app.routes.auth.test_db_connection", return_value=(True, "Connected", "1.0")):
                with patch("app.routes.auth.User.find_by_email") as mock_find:
                    # Provide a user with hash for "CorrectPassword123"
                    from app.models.user import User
                    mock_find.return_value = {
                        "id": 5,
                        "full_name": "Test User",
                        "email": "test@demo.lifelink.local",
                        "password_hash": User.hash_password("CorrectPassword123"),
                        "role": "donor",
                        "is_active": True
                    }

                    # Attempt with wrong password
                    response = self.client.post(
                        "/auth/login",
                        data={
                            "csrf_token": "test-csrf-token",
                            "email": "test@demo.lifelink.local",
                            "password": "WrongPassword999"
                        }
                    )
                    self.assertEqual(response.status_code, 200)
                    self.assertIn(b"Invalid email or password", response.data)

    def test_donor_registration_validation_errors(self):
        """Donor registration with weak password or invalid phone returns HTTP 400."""
        with self.client:
            self.client.get("/")
            with self.client.session_transaction() as sess:
                sess["_csrf_token"] = "test-csrf-token"

            # 1. Weak password
            response_weak_pw = self.client.post(
                "/auth/register/donor",
                data={
                    "csrf_token": "test-csrf-token",
                    "full_name": "John Doe",
                    "email": "john.doe@example.com",
                    "phone": "+1-555-123-4567",
                    "password": "weak",
                    "blood_group": "O+",
                    "city": "Metro City",
                    "state": "State",
                    "district": "North",
                    "date_of_birth": "1990-01-01",
                    "weight_kg": "70"
                }
            )
            self.assertEqual(response_weak_pw.status_code, 400)
            self.assertIn(b"Password must be at least 8 characters", response_weak_pw.data)

            # 2. Invalid blood group
            response_bad_bg = self.client.post(
                "/auth/register/donor",
                data={
                    "csrf_token": "test-csrf-token",
                    "full_name": "John Doe",
                    "email": "john.doe@example.com",
                    "phone": "+1-555-123-4567",
                    "password": "ValidPassword123",
                    "blood_group": "XYZ-INVALID",
                    "city": "Metro City",
                    "state": "State",
                    "district": "North",
                    "date_of_birth": "1990-01-01",
                    "weight_kg": "70"
                }
            )
            self.assertEqual(response_bad_bg.status_code, 400)

    def test_demo_login_fallback_and_session(self):
        """Testing login with valid credentials establishes authenticated session."""
        from unittest.mock import patch
        from app.models.user import User

        with self.client:
            self.client.get("/")
            with self.client.session_transaction() as sess:
                sess["_csrf_token"] = "test-csrf-token-12345"

            with patch("app.routes.auth.test_db_connection", return_value=(True, "Connected", "1.0")):
                with patch("app.routes.auth.User.find_by_email") as mock_find:
                    mock_find.return_value = {
                        "id": 2,
                        "full_name": "Test Donor",
                        "email": "sarah.jenkins@demo.lifelink.local",
                        "password_hash": User.hash_password("DemoPass@123"),
                        "role": "donor",
                        "is_active": True
                    }

                    response = self.client.post(
                        "/auth/login",
                        data={
                            "csrf_token": "test-csrf-token-12345",
                            "email": "sarah.jenkins@demo.lifelink.local",
                            "password": "DemoPass@123"
                        },
                        follow_redirects=False
                    )
                    # Should redirect to donor dashboard
                    self.assertEqual(response.status_code, 302)

                    with self.client.session_transaction() as sess:
                        self.assertIn("user_id", sess)
                        self.assertEqual(sess.get("user_role"), "donor")

    def test_logout(self):
        """Logout clears the authenticated session."""
        with self.client:
            with self.client.session_transaction() as sess:
                sess["user_id"] = 2
                sess["user_role"] = "donor"

            response = self.client.get("/auth/logout", follow_redirects=False)
            self.assertEqual(response.status_code, 302)

            with self.client.session_transaction() as sess:
                self.assertNotIn("user_id", sess)

    # --------------------------------------------------------------------------
    # PASSWORD RESET TESTS
    # --------------------------------------------------------------------------
    def test_password_reset_token_generation_and_verification(self):
        """Token generator produces cryptographic signed tokens that correctly decode email."""
        from app.models.user import User
        with self.app.app_context():
            test_email = "donor.sarah@example.com"
            token = User.generate_reset_token(test_email)
            self.assertIsInstance(token, str)
            self.assertTrue(len(token) > 20)

            # Verification succeeds
            verified_email = User.verify_reset_token(token, max_age=3600)
            self.assertEqual(verified_email, test_email)

            # Tampered token fails
            bad_token = token + "tampered"
            self.assertIsNone(User.verify_reset_token(bad_token))

    def test_forgot_password_page_renders_and_dispatches(self):
        """Forgot password route renders form and accepts email submission."""
        res_get = self.client.get("/auth/forgot-password")
        self.assertEqual(res_get.status_code, 200)
        self.assertIn(b"Forgot Password", res_get.data)

        # POST with CSRF
        with self.client:
            self.client.get("/")
            with self.client.session_transaction() as sess:
                sess["_csrf_token"] = "token123"

            res_post = self.client.post(
                "/auth/forgot-password",
                data={
                    "csrf_token": "token123",
                    "email": "sarah.jenkins@demo.lifelink.local"
                }
            )
            self.assertEqual(res_post.status_code, 200)
            self.assertIn(b"password reset link", res_post.data)

    def test_reset_password_with_invalid_token(self):
        """Accessing reset-password with bad token redirects to forgot-password."""
        response = self.client.get("/auth/reset-password/completely-bogus-token", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/forgot-password", response.location)

    def test_reset_password_with_valid_token_and_update(self):
        """Valid token allows user to set new password."""
        from app.models.user import User
        with self.app.app_context():
            token = User.generate_reset_token("sarah.jenkins@demo.lifelink.local")

        # GET form
        res_form = self.client.get(f"/auth/reset-password/{token}")
        self.assertEqual(res_form.status_code, 200)
        self.assertIn(b"Set New Password", res_form.data)

        # POST new password
        with self.client:
            self.client.get("/")
            with self.client.session_transaction() as sess:
                sess["_csrf_token"] = "token123"

            res_update = self.client.post(
                f"/auth/reset-password/{token}",
                data={
                    "csrf_token": "token123",
                    "password": "BrandNewPassword123",
                    "confirm_password": "BrandNewPassword123"
                },
                follow_redirects=False
            )
            self.assertEqual(res_update.status_code, 302)
            self.assertIn("/auth/login", res_update.location)

    # --------------------------------------------------------------------------
    # DUAL-ROLE & ADMIN CREATION TESTS
    # --------------------------------------------------------------------------
    def test_admin_account_cannot_be_created_publicly(self):
        """Public registration cannot assign the 'admin' role."""
        with self.client:
            self.client.get("/")
            with self.client.session_transaction() as sess:
                sess["_csrf_token"] = "token123"

            from unittest.mock import patch
            with patch("app.routes.auth.test_db_connection", return_value=(True, "Connected", {})):
                with patch("app.routes.auth.User.find_by_email", return_value=None):
                    with patch("app.routes.auth.User.find_by_phone", return_value=None):
                        with patch("app.routes.auth.User.create") as mock_create:
                            mock_create.return_value = 99
                            response = self.client.post(
                                "/auth/register",
                                data={
                                    "csrf_token": "token123",
                                    "full_name": "Sneaky Admin",
                                    "email": "sneaky@example.com",
                                    "phone": "+1-555-999-0001",
                                    "password": "Password123",
                                    "confirm_password": "Password123",
                                    "role": "admin"
                                },
                                follow_redirects=False
                            )
                            # User.create must be called with role 'patient' or 'donor', NEVER 'admin'
                            called_role = mock_create.call_args[1].get("role") or mock_create.call_args[0][4]
                            self.assertNotEqual(called_role, "admin")

    def test_dual_role_donor_and_requester_access(self):
        """A registered user can access both the Donor dashboard and the Patient dashboard."""
        # 1. Donor can access Patient dashboard
        with self.client:
            with self.client.session_transaction() as sess:
                sess["user_id"] = 2
                sess["user_role"] = "donor"
                sess["user_name"] = "Sarah Jenkins"

            res_patient_dash = self.client.get("/patient/dashboard")
            self.assertEqual(res_patient_dash.status_code, 200)

        # 2. Patient can access Donor dashboard
        with self.client:
            with self.client.session_transaction() as sess:
                sess["user_id"] = 10
                sess["user_role"] = "patient"
                sess["user_name"] = "Michael Sterling"

            res_donor_dash = self.client.get("/donor/dashboard")
            self.assertEqual(res_donor_dash.status_code, 200)

    def test_admin_dashboard_still_strictly_protected(self):
        """Admin dashboard strictly blocks non-admin users with HTTP 403."""
        with self.client:
            with self.client.session_transaction() as sess:
                sess["user_id"] = 2
                sess["user_role"] = "donor"

            res_admin_blocked = self.client.get("/admin/")
            self.assertEqual(res_admin_blocked.status_code, 403)

            res_admin_dash_blocked = self.client.get("/admin/dashboard")
            self.assertEqual(res_admin_dash_blocked.status_code, 403)

    def test_registration_page_contains_screening_questions(self):
        """The registration page must render all 10 donor screening questions."""
        response = self.client.get("/auth/register")
        self.assertEqual(response.status_code, 200)
        content = response.data.decode("utf-8")

        # Verify screening elements
        self.assertIn("Clinical Health Screening Questionnaire", content)
        self.assertIn("screening_unwell", content)
        self.assertIn("screening_antibiotics", content)
        self.assertIn("screening_tattoo", content)
        self.assertIn("screening_surgery", content)
        self.assertIn("screening_malaria", content)
        self.assertIn("screening_pregnant", content)
        self.assertIn("screening_blood_pressure", content)
        self.assertIn("screening_infection", content)
        self.assertIn("screening_chronic", content)
        self.assertIn("screening_insulin", content)
        self.assertIn("screening_consent", content)

    def test_api_auth_register_with_donor_screening(self):
        """POST /api/auth/register processes registration and donor screening."""
        with self.client:
            with self.client.session_transaction() as sess:
                sess["_csrf_token"] = "test-token"

            response = self.client.post(
                "/api/auth/register",
                headers={"X-CSRFToken": "test-token"},
                json={
                    "full_name": "Screening Test User",
                    "email": "screening.donor@example.com",
                    "phone": "+1-555-987-6543",
                    "password": "SecurePassword123",
                    "become_donor": True,
                    "donor": {
                        "blood_group": "A+",
                        "gender": "male",
                        "dob": "1997-04-12",
                        "weight_kg": 72.0,
                        "city": "Central Metro",
                        "district": "District 1",
                        "answers": {
                            "unwell": False,
                            "antibiotics": False,
                            "tattoo": False,
                            "surgery": False,
                            "malaria": False,
                            "blood_pressure": False,
                            "infection": False,
                            "chronic": False,
                            "insulin": False
                        },
                        "consent": True
                    }
                }
            )
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertTrue(data["success"])
            self.assertIn("user", data)
            self.assertEqual(data["user"]["role"], "donor")

    def test_member_register_without_donor_box_succeeds(self):
        """Unified /auth/register POST without enable_donor succeeds as patient without donor validation."""
        from unittest.mock import patch
        with self.client:
            self.client.get("/")
            with self.client.session_transaction() as sess:
                sess["_csrf_token"] = "test-token"

            with patch("app.routes.auth.test_db_connection", return_value=(True, "Connected", {})):
                with patch("app.routes.auth.User.find_by_email", return_value=None):
                    with patch("app.routes.auth.User.find_by_phone", return_value=None):
                        with patch("app.routes.auth.User.create", return_value=123) as mock_u_create:
                            with patch("app.routes.auth.Donor.create") as mock_d_create:
                                response = self.client.post(
                                    "/auth/register",
                                    data={
                                        "csrf_token": "test-token",
                                        "full_name": "Standard User",
                                        "email": "standard.user@example.com",
                                        "phone": "+1-555-888-7777",
                                        "password": "Password123!",
                                        "confirm_password": "Password123!"
                                        # Note: enable_donor is omitted
                                    },
                                    follow_redirects=False
                                )
                                self.assertEqual(response.status_code, 302)
                                self.assertIn("/auth/login", response.location)
                                mock_u_create.assert_called_once()
                                mock_d_create.assert_not_called()

    def test_member_register_with_donor_profile_succeeds(self):
        """Unified /auth/register POST with enable_donor=1 and screening answers creates donor."""
        from unittest.mock import patch
        with self.client:
            self.client.get("/")
            with self.client.session_transaction() as sess:
                sess["_csrf_token"] = "test-token"

            with patch("app.routes.auth.test_db_connection", return_value=(True, "Connected", {})):
                with patch("app.routes.auth.User.find_by_email", return_value=None):
                    with patch("app.routes.auth.User.find_by_phone", return_value=None):
                        with patch("app.routes.auth.User.create", return_value=124) as mock_u_create:
                            with patch("app.routes.auth.Donor.create") as mock_d_create:
                                response = self.client.post(
                                    "/auth/register",
                                    data={
                                        "csrf_token": "test-token",
                                        "full_name": "Donor User",
                                        "email": "donor.user@example.com",
                                        "phone": "+1-555-888-6666",
                                        "password": "Password123!",
                                        "confirm_password": "Password123!",
                                        "enable_donor": "1",
                                        "blood_group": "A+",
                                        "gender": "male",
                                        "date_of_birth": "1995-05-10",
                                        "weight_kg": "70",
                                        "city": "Metro City",
                                        "district": "Metro District",
                                        "state": "Metro State",
                                        "screening_consent": "1",
                                        "screening_unwell": "no",
                                        "screening_antibiotics": "no",
                                        "screening_tattoo": "no",
                                        "screening_surgery": "no",
                                        "screening_malaria": "no",
                                        "screening_blood_pressure": "no",
                                        "screening_infection": "no",
                                        "screening_chronic": "no",
                                        "screening_insulin": "no"
                                    },
                                    follow_redirects=False
                                )
                                self.assertEqual(response.status_code, 302)
                                self.assertIn("/auth/login", response.location)
                                mock_u_create.assert_called_once()
                                mock_d_create.assert_called_once()


if __name__ == "__main__":
    unittest.main()
