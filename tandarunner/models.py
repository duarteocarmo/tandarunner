from django.db import models


class TrainingInsight(models.Model):
    insight_id = models.CharField(max_length=32, unique=True)
    source_id = models.CharField(max_length=32)
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Insight {self.insight_id}; Data: {self.data}"
