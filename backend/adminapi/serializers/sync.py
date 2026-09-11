from rest_framework import serializers

from registers.models import (
    AuditLog,
    CompanySyncStatus,
    SyncJob,
)


class SyncJobSerializer(serializers.ModelSerializer):
    progress_percentage = serializers.FloatField(read_only=True)
    items_per_hour = serializers.FloatField(read_only=True)
    duration_seconds = serializers.FloatField(read_only=True, allow_null=True)
    triggered_by_email = serializers.CharField(source="triggered_by.email", read_only=True, default=None)

    class Meta:
        model = SyncJob
        fields = [
            "id",
            "job_type",
            "status",
            "triggered_by",
            "triggered_by_email",
            "triggered_via",
            "parameters",
            "total_items",
            "processed_items",
            "succeeded_items",
            "failed_items",
            "skipped_items",
            "progress_percentage",
            "items_per_hour",
            "duration_seconds",
            "queued_at",
            "started_at",
            "completed_at",
            "last_heartbeat",
            "last_error",
            "notes",
            "celery_task_id",
        ]
        read_only_fields = fields


class SyncJobTriggerSerializer(serializers.Serializer):
    """Body of POST /api/admin/sync/jobs/."""

    job_type = serializers.ChoiceField(choices=[c[0] for c in SyncJob.JOB_TYPE_CHOICES])
    parameters = serializers.JSONField(required=False, default=dict)
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class CompanySyncStatusSerializer(serializers.ModelSerializer):
    company_ico = serializers.CharField(source="company.ico", read_only=True)
    company_name = serializers.CharField(source="company.nazov_UJ", read_only=True)

    class Meta:
        model = CompanySyncStatus
        fields = [
            "id",
            "company",
            "company_ico",
            "company_name",
            "source",
            "last_attempted_at",
            "last_succeeded_at",
            "last_error",
            "last_error_type",
            "consecutive_failures",
            "next_retry_at",
            "is_blocked",
            "blocked_reason",
            "updated_at",
        ]
        read_only_fields = [
            "company_ico",
            "company_name",
            "last_attempted_at",
            "last_succeeded_at",
            "last_error",
            "last_error_type",
            "consecutive_failures",
            "next_retry_at",
            "updated_at",
        ]


class AuditLogSerializer(serializers.ModelSerializer):
    actor_email = serializers.CharField(source="actor.email", read_only=True, default=None)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "actor",
            "actor_email",
            "action",
            "target_type",
            "target_id",
            "payload",
            "method",
            "path",
            "status_code",
            "ip_address",
            "user_agent",
            "created_at",
        ]
        read_only_fields = fields
