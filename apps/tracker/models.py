import secrets
from django.db import models


class Broker(models.Model):
    name = models.CharField(max_length=255)
    offer_url = models.URLField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["-created_at"]


class Campaign(models.Model):
    name = models.CharField(max_length=255)
    broker = models.ForeignKey(Broker, on_delete=models.CASCADE, related_name="campaigns")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["-created_at"]


class Click(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="clicks")
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    referrer = models.TextField(blank=True)
    lead_id = models.CharField(max_length=64, unique=True, db_index=True)
    converted = models.BooleanField(default=False)
    conversion_time = models.DateTimeField(null=True, blank=True)
    click_time = models.DateTimeField(auto_now_add=True)
    utm_source = models.CharField(max_length=255, blank=True, null=True)
    utm_medium = models.CharField(max_length=255, blank=True, null=True)
    utm_campaign = models.CharField(max_length=255, blank=True, null=True)
    utm_term = models.CharField(max_length=255, blank=True, null=True)
    utm_content = models.CharField(max_length=255, blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.lead_id:
            self.lead_id = secrets.token_hex(8)
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["-click_time"]
