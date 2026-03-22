import uuid

from django.conf import settings
from django.db import models


class TrainingPlan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="training_plan",
    )
    name = models.CharField(max_length=255)
    achievability = models.CharField(max_length=20, blank=True, default="")
    coach_message = models.TextField(blank=True, default="")
    sessions = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} — {self.name}"
