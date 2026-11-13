
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Conversation, ConversationMember, Message
from .serializers import ConversationSerializer, MessageSerializer


User = get_user_model()


# Create a conversation
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_conversation(request):
    serializer = ConversationSerializer(
        data=request.data,
        context={"request": request}
    )

    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    with transaction.atomic():
        conversation = serializer.save()

        # Add the creator automatically
        conversation.participants.add(request.user)

        # Create membership records for group chats
        if conversation.is_group:
            for user in conversation.participants.all():
                ConversationMember.objects.get_or_create(
                    conversation=conversation,
                    user=user,
                    defaults={
                        "is_admin": user.id == request.user.id
                    }
                )

    return Response(
        ConversationSerializer(conversation).data,
        status=201
    )


# List conversations for the logged-in user
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_conversations(request):
    conversations = Conversation.objects.filter(
        participants=request.user
    )

    serializer = ConversationSerializer(
        conversations,
        many=True
    )

    return Response(serializer.data)


# Send a message
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def send_message(request):
    serializer = MessageSerializer(data=request.data)

    if serializer.is_valid():
        conversation = serializer.validated_data["conversation"]

        if not conversation.participants.filter(
            id=request.user.id
        ).exists():
            return Response(
                {"error": "You are not part of this conversation"},
                status=403
            )

        serializer.save(sender=request.user)

        return Response(serializer.data, status=201)

    return Response(serializer.errors, status=400)


# Retrieve messages in a conversation
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_messages(request, conversation_id):
    conversation = get_object_or_404(
        Conversation,
        id=conversation_id,
        participants=request.user
    )

    messages = Message.objects.filter(
        conversation=conversation
    ).order_by("sent_at")

    serializer = MessageSerializer(messages, many=True)

    return Response(serializer.data)


# Edit a message
@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def edit_message(request, message_id):
    message = get_object_or_404(
        Message,
        id=message_id,
        conversation__participants=request.user
    )

    if message.sender_id != request.user.id:
        return Response(
            {"error": "You can only edit your own messages"},
            status=403
        )

    content = request.data.get("content")

    if not isinstance(content, str) or not content.strip():
        return Response(
            {"error": "Message cannot be empty"},
            status=400
        )

    message.content = content.strip()
    message.save(update_fields=["content"])

    return Response(MessageSerializer(message).data)


# Delete a message
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_message(request, message_id):
    message = get_object_or_404(
        Message,
        id=message_id,
        conversation__participants=request.user
    )

    if message.sender_id != request.user.id:
        return Response(
            {"error": "You can only delete your own messages"},
            status=403
        )

    message.delete()

    return Response(status=204)


# Add a participant to a group
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_participant(request, conversation_id):
    conversation = get_object_or_404(
        Conversation,
        id=conversation_id,
        participants=request.user
    )

    if not conversation.is_group:
        return Response(
            {"error": "Cannot add users to private chats"},
            status=400
        )

    # Only group admins can add members
    if not ConversationMember.objects.filter(
        conversation=conversation,
        user=request.user,
        is_admin=True
    ).exists():
        return Response(
            {"error": "Only group admins can add participants"},
            status=403
        )

    user_id = request.data.get("user_id")
    user = get_object_or_404(User, id=user_id)

    if conversation.participants.filter(id=user.id).exists():
        return Response(
            {"error": "User is already in the group"},
            status=400
        )

    with transaction.atomic():
        conversation.participants.add(user)

        ConversationMember.objects.get_or_create(
            conversation=conversation,
            user=user,
            defaults={"is_admin": False}
        )

    return Response(
        {"message": "User added successfully!"},
        status=200
    )


# Remove a participant from a group
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def remove_participant(request, conversation_id):
    conversation = get_object_or_404(
        Conversation,
        id=conversation_id,
        participants=request.user
    )

    if not conversation.is_group:
        return Response(
            {"error": "Cannot remove users from private chats"},
            status=400
        )

    user_id = request.data.get("user_id")
    user = get_object_or_404(User, id=user_id)

    # Members can leave; admins can remove others
    if user.id != request.user.id:
        if not ConversationMember.objects.filter(
            conversation=conversation,
            user=request.user,
            is_admin=True
        ).exists():
            return Response(
                {"error": "Only group admins can remove other members"},
                status=403
            )

    if not conversation.participants.filter(id=user.id).exists():
        return Response(
            {"error": "User is not in this group"},
            status=400
        )

    # Prevent removing the group's last admin
    if ConversationMember.objects.filter(
        conversation=conversation,
        user=user,
        is_admin=True
    ).exists():
        admin_count = ConversationMember.objects.filter(
            conversation=conversation,
            is_admin=True
        ).count()

        if admin_count <= 1:
            return Response(
                {"error": "Assign another admin before removing the last admin"},
                status=400
            )

    with transaction.atomic():
        conversation.participants.remove(user)

        ConversationMember.objects.filter(
            conversation=conversation,
            user=user
        ).delete()

    return Response(
        {"message": "Participant removed successfully!"},
        status=200
    )
    
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def promote_admin(request, conversation_id):
    conversation = get_object_or_404(
        Conversation,
        id=conversation_id,
        participants=request.user,
        is_group=True
    )

    if not ConversationMember.objects.filter(
        conversation=conversation,
        user=request.user,
        is_admin=True
    ).exists():
        return Response(
            {"error": "Only admins can promote members"},
            status=403
        )

    user_id = request.data.get("user_id")

    member = get_object_or_404(
        ConversationMember,
        conversation=conversation,
        user_id=user_id
    )

    member.is_admin = True
    member.save(update_fields=["is_admin"])

    return Response(
        {"message": "Member promoted to admin successfully"},
        status=200
    )

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def demote_admin(request, conversation_id):
    conversation = get_object_or_404(
        Conversation,
        id=conversation_id,
        participants=request.user,
        is_group=True
    )

    if not ConversationMember.objects.filter(
        conversation=conversation,
        user=request.user,
        is_admin=True
    ).exists():
        return Response(
            {"error": "Only admins can demote members"},
            status=403
        )

    member = get_object_or_404(
        ConversationMember,
        conversation=conversation,
        user_id=request.data.get("user_id")
    )

    if not member.is_admin:
        return Response(
            {"error": "User is not an admin"},
            status=400
        )

    with transaction.atomic():
        admins = ConversationMember.objects.select_for_update().filter(
            conversation=conversation,
            is_admin=True
        )

        if admins.count() <= 1:
            return Response(
                {"error": "Cannot demote the last admin"},
                status=400
            )

        member.is_admin = False
        member.save(update_fields=["is_admin"])

    return Response(
        {"message": "Admin demoted successfully"},
        status=200
    )
    
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_participants(request, conversation_id):
    conversation = get_object_or_404(
        Conversation,
        id=conversation_id,
        participants=request.user
    )

    members = []

    for user in conversation.participants.all():
        membership = ConversationMember.objects.filter(
            conversation=conversation,
            user=user
        ).first()

        members.append({
            "id": user.id,
            "username": user.username,
            "is_admin": membership.is_admin if membership else False
        })

    return Response(members)
  
@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def rename_group(request, conversation_id):
    conversation = get_object_or_404(
        Conversation,
        id=conversation_id,
        participants=request.user,
        is_group=True
    )

    if not ConversationMember.objects.filter(
        conversation=conversation,
        user=request.user,
        is_admin=True
    ).exists():
        return Response(
            {"error": "Only admins can rename groups"},
            status=403
        )

    name = request.data.get("name")

    if not isinstance(name, str) or not name.strip():
        return Response(
            {"error": "Group name cannot be empty"},
            status=400
        )

    if len(name.strip()) > 100:
        return Response(
            {"error": "Group name cannot exceed 100 characters"},
            status=400
        )

    conversation.name = name.strip()
    conversation.save(update_fields=["name"])

    return Response(
        {"message": "Group renamed successfully", "name": conversation.name}
    )
    
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_group(request, conversation_id):
    conversation = get_object_or_404(
        Conversation,
        id=conversation_id,
        participants=request.user,
        is_group=True
    )

    if not ConversationMember.objects.filter(
        conversation=conversation,
        user=request.user,
        is_admin=True
    ).exists():
        return Response(
            {"error": "Only admins can delete groups"},
            status=403
        )

    conversation.delete()

    return Response(status=204)