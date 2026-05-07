from django.conf import settings
from django.db import models


class Conversation(models.Model):
    LANG_ASM = "asm"
    LANG_C   = "c"
    LANGUAGE_CHOICES = [
        (LANG_ASM, "Assembly"),
        (LANG_C,   "C"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversations",
    )
    title = models.CharField(max_length=255, default="New chat")
    is_pinned = models.BooleanField(default=False)
    language  = models.CharField(
        max_length=8,
        choices=LANGUAGE_CHOICES,
        default=LANG_ASM,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.user.username} – {self.title}"


class Message(models.Model):
    USER = "user"
    ASSISTANT = "assistant"
    ROLE_CHOICES = [
        (USER, "User"),
        (ASSISTANT, "Assistant"),
    ]

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    content = models.TextField()
    temperature = models.FloatField(null=True, blank=True)
    max_tokens = models.IntegerField(null=True, blank=True)
    prompt_tokens     = models.IntegerField(null=True, blank=True)
    completion_tokens = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
