from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient


User = get_user_model()


class UserAuthAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="charlie",
            email="charlie@example.com",
            password="Pass123!",
        )

    def test_user_can_log_in(self):
        response = self.client.post(
            "/users/login/",
            {"username": "charlie", "password": "Pass123!"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["message"], "Login successful!")

    def test_register_requires_valid_password(self):
        response = self.client.post(
            "/users/register/",
            {"username": "dana", "email": "dana@example.com", "password": "password"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.data)
