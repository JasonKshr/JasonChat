from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from chat.models import Conversation


User = get_user_model()


class ChatAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user_one = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="Pass123!",
        )
        self.user_two = User.objects.create_user(
            username="bob",
            email="bob@example.com",
            password="Pass123!",
        )
        self.client.force_authenticate(self.user_one)

    def test_create_private_conversation_and_send_message(self):
        response = self.client.post(
            "/chat/create/",
            {"name": "", "is_group": False, "participants": [self.user_two.id]},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        conversation_id = response.data["id"]

        message_response = self.client.post(
            "/chat/send/",
            {"conversation": conversation_id, "content": "Hello there!"},
            format="json",
        )

        self.assertEqual(message_response.status_code, 201)
        self.assertEqual(message_response.data["content"], "Hello there!")

    def test_blank_message_is_rejected(self):
        conversation = Conversation.objects.create(name="Support", is_group=False)
        conversation.participants.add(self.user_one, self.user_two)

        response = self.client.post(
            "/chat/send/",
            {"conversation": conversation.id, "content": "   "},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("content", response.data)
