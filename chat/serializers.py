from rest_framework import serializers
from .models import Conversation

class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = ["id", "name", "is_group", "participants", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_name(self, value):
        if value is not None:
            value = value.strip()
            if not value:
                return value
            if len(value) > 100:
                raise serializers.ValidationError(
                    "Conversation name cannot exceed 100 characters."
                )
        return value

    def validate(self, data):
        participants = data.get("participants") or []
        if isinstance(participants, (str, int)):
            participants = [participants]
        participants = list(participants)
        is_group = data.get("is_group", False)

        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required.")

        participant_ids = {user.id for user in participants}
        participant_ids.add(request.user.id)
        count = len(participant_ids)

        if not is_group and count != 2:
            raise serializers.ValidationError(
                "Private chats must have exactly 2 participants."
            )

        if is_group and count < 2:
            raise serializers.ValidationError(
                "Group chats must have at least 2 participants."
            )

        return data

from .models import Message

class MessageSerializer(serializers.ModelSerializer):
    content = serializers.CharField(trim_whitespace=True, allow_blank=False)

    class Meta:
        model = Message
        fields = ["id", "conversation", "sender", "content", "sent_at"]
        read_only_fields = ["id", "sender", "sent_at"]

    def validate_content(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Message content cannot be empty.")
        return value