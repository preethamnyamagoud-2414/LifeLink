"""
LifeLink - Unit Tests for Application Factory & Blueprint Registration
"""

import unittest
from app import create_app


class TestAppFactory(unittest.TestCase):
    """Verifies that the Flask application factory correctly initializes."""

    def setUp(self):
        self.app = create_app("testing")
        self.client = self.app.test_client()

    def test_app_is_testing(self):
        """Testing configuration should set TESTING=True."""
        self.assertTrue(self.app.config["TESTING"])

    def test_blueprints_registered(self):
        """All 6 core modular blueprints must be registered."""
        expected_blueprints = {"public", "auth", "donor", "patient", "requests", "admin"}
        registered_blueprints = set(self.app.blueprints.keys())
        self.assertTrue(expected_blueprints.issubset(registered_blueprints))

    def test_health_check_endpoint(self):
        """The /health endpoint must return JSON containing app and blueprint status."""
        response = self.client.get("/health")
        # May return 200 or 503 depending on whether MySQL is running locally
        self.assertIn(response.status_code, [200, 503])
        self.assertTrue(response.is_json)
        data = response.get_json()
        self.assertEqual(data["app"], "LifeLink")
        self.assertIn("blueprints", data)

    def test_public_routes(self):
        """Public homepage and search routes should respond with HTTP 200."""
        res_home = self.client.get("/")
        self.assertEqual(res_home.status_code, 200)

        res_find = self.client.get("/find-donors")
        self.assertEqual(res_find.status_code, 200)

        res_about = self.client.get("/about")
        self.assertEqual(res_about.status_code, 200)


if __name__ == "__main__":
    unittest.main()
