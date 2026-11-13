
import json

from django.utils import timezone
from django.core.cache import cache

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from users.models import Profile
from .models import Conversation, Message, MessageRead


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.room_group_name = f"chat_{self.conversation_id}"
        self.joined_group = False
        self.tracked_online = False

        if not self.scope["user"].is_authenticated:
            await self.close()
            return

        if not await self.is_member():
            await self.close()
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        self.joined_group = True

        await self.accept()

        await self.mark_online()
        self.tracked_online = True

    async def disconnect(self, close_code):
        if getattr(self, "joined_group", False):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

        if getattr(self, "tracked_online", False):
            await self.mark_offline()

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, TypeError):
            return

        if not isinstance(data, dict):
            return

        # Verify the user still belongs to this conversation
        if not await self.is_member():
            await self.close()
            return

        # Handle typing indicators
        if data.get("type") == "typing":
            if type(data.get("is_typing")) is not bool:
                return

            await self.typing(data["is_typing"])
            return

        # Handle read receipts
        if data.get("type") == "read":
            message_id = data.get("message_id")

            if type(message_id) is not int:
                return

            success = await self.mark_message_read(message_id)

            if success:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "read_receipt",
                        "message_id": message_id,
                        "username": self.scope["user"].username
                    }
                )

            return

        # Handle regular messages
        message = data.get("message")

        if not isinstance(message, str) or not message.strip():
            return

        saved_message = await self.save_message(message.strip())

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": saved_message["content"],
                "sender": self.scope["user"].username,
                "id": saved_message["id"]
            }
        )

    # Send chat messages to connected users
    async def chat_message(self, event):
        if not await self.is_member():
            await self.close()
            return

        await self.send(
            text_data=json.dumps({
                "id": event["id"],
                "message": event["message"],
                "sender": event["sender"]
            })
        )

    # Broadcast typing status
    async def typing(self, is_typing):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "typing_message",
                "username": self.scope["user"].username,
                "is_typing": is_typing
            }
        )

    # Send typing indicators to connected users
    async def typing_message(self, event):
        if not await self.is_member():
            await self.close()
            return

        await self.send(
            text_data=json.dumps({
                "type": "typing",
                "username": event["username"],
                "is_typing": event["is_typing"]
            })
        )

    # Send read receipts to connected users
    async def read_receipt(self, event):
        if not await self.is_member():
            await self.close()
            return

        await self.send(
            text_data=json.dumps({
                "type": "read",
                "message_id": event["message_id"],
                "user": event["username"]
            })
        )

    # Check whether a user belongs to the conversation
    @database_sync_to_async
    def is_member(self):
        return Conversation.objects.filter(
            id=self.conversation_id,
            participants=self.scope["user"]
        ).exists()

    # Save messages to the database
    @database_sync_to_async
    def save_message(self, content):
        message = Message.objects.create(
            conversation_id=self.conversation_id,
            sender=self.scope["user"],
            content=content
        )

        return {
            "id": message.id,
            "content": message.content
        }

    # Save a read receipt
    @database_sync_to_async
    def mark_message_read(self, message_id):
        message = Message.objects.filter(
            id=message_id,
            conversation_id=self.conversation_id
        ).first()

        if not message:
            return False

        if message.sender_id == self.scope["user"].id:
            return False

        receipt, created = MessageRead.objects.get_or_create(
            message=message,
            user=self.scope["user"]
        )

        return created

    # Increment active connection count
    @database_sync_to_async
    def mark_online(self):
        key = f"online_{self.scope['user'].id}"
        count = cache.get(key, 0)
        cache.set(key, count + 1, timeout=None)

    # Decrement active connection count
    @database_sync_to_async
    def mark_offline(self):
        key = f"online_{self.scope['user'].id}"
        count = cache.get(key, 0)

        if count <= 1:
            cache.delete(key)

            Profile.objects.filter(
                user=self.scope["user"]
            ).update(last_seen=timezone.now())
        else:
            cache.set(key, count - 1, timeout=None)
