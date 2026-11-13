from django.db import models
from django.conf import settings

class Conversation(models.Model):
    name = models.CharField(max_length=100, blank=True)
    is_group = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="conversations"
    )
    
class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE
    )

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    content = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    
class ConversationMember(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    is_admin = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "user"],
                name="unique_conversation_member"
            )
        ]
        
class MessageRead(models.Model):
  message = models.ForeignKey(
      Message,
      on_delete=models.CASCADE,
      related_name="read_receipts"
  )

  user = models.ForeignKey(
      settings.AUTH_USER_MODEL,
      on_delete=models.CASCADE
  )

  read_at = models.DateTimeField(auto_now_add=True)

  class Meta:
      constraints = [
          models.UniqueConstraint(
              fields=["message", "user"],
              name="unique_message_read"
          )
      ]