from rest_framework import serializers
from .models import Conversation

class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = ["id", "name", "is_group", "participants", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate(self, data):
        participants = data.get("participants", [])
        is_group = data.get("is_group", False)

        request = self.context.get("request")
        if request and request.user.is_authenticated:
            participant_ids = {user.id for user in participants}
            participant_ids.add(request.user.id)
            count = len(participant_ids)
        else:
            raise serializers.ValidationError("Authentication required.")

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
    class Meta:
        model = Message
        fields = ["id", "conversation", "sender", "content", "sent_at"]
        read_only_fields = ["id", "sender", "sent_at"]