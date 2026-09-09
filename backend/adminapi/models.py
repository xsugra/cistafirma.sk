"""Persisted admin-side helper models."""

from django.conf import settings
from django.db import models


class SavedCompanyFilter(models.Model):
    """A saved filter definition for the admin companies table."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_company_filters",
        verbose_name="Používateľ",
    )
    name = models.CharField(max_length=160, verbose_name="Názov filtra")
    description = models.TextField(blank=True, default="", verbose_name="Popis")
    filters = models.JSONField(default=dict, verbose_name="Parametre filtra")
    is_favorite = models.BooleanField(default=False, verbose_name="Obľúbený")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Vytvorené")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aktualizované")

    class Meta:
        verbose_name = "Uložený filter firiem"
        verbose_name_plural = "Uložené filtre firiem"
        ordering = ["-is_favorite", "name"]
        unique_together = [("user", "name")]

    def __str__(self):
        return f"{self.user} → {self.name}"

