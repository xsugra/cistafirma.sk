from rest_framework import serializers
from .models import NotificationEvent, NotificationPreference


class NotificationEventSerializer(serializers.ModelSerializer):
    companyIco = serializers.CharField(source='company_ico', read_only=True)
    companyName = serializers.CharField(source='company_name', read_only=True)
    eventType = serializers.CharField(source='event_type', read_only=True)
    eventTypeDisplay = serializers.CharField(source='get_event_type_display', read_only=True)
    sentEmail = serializers.BooleanField(source='sent_email', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = NotificationEvent
        fields = [
            'id', 'companyIco', 'companyName', 'eventType',
            'eventTypeDisplay', 'title', 'details',
            'sentEmail', 'createdAt',
        ]
        read_only_fields = fields


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    emailEnabled = serializers.BooleanField(source='email_enabled')
    onDebtChange = serializers.BooleanField(source='on_debt_change')
    onStatusChange = serializers.BooleanField(source='on_status_change')
    onExecutiveChange = serializers.BooleanField(source='on_executive_change')

    class Meta:
        model = NotificationPreference
        fields = [
            'emailEnabled', 'onDebtChange', 'onStatusChange',
            'onExecutiveChange',
        ]
