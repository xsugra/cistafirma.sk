import re

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import NotificationEvent, NotificationPreference
from .serializers import NotificationEventSerializer, NotificationPreferenceSerializer

#: IČO as the register writes it: 8 digits, but historical records carry 6 and
#: the column is `max_length=20`, so this validates the shape rather than a
#: width the data does not actually keep to.
_ICO_RE = re.compile(r'^\d{6,20}$')


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """User's notification events (read-only), optionally for one company.

    `?ico=` narrows the list to a single company, which is what the "Udalosti
    vo firme" section on a company page reads. It is a filter on the existing
    user-scoped resource rather than a company-scoped endpoint on purpose: the
    events are the *requesting user's* mail history, not a property of the
    company, so hanging them off `/api/companies/<ico>/` would put a resource
    that needs an account behind a route that does not.

    Scoping by `self.request.user` is what makes this safe to expose -- an
    unfiltered query would let anyone read every user's notifications for a
    company by guessing an IČO.
    """

    serializer_class = NotificationEventSerializer
    permission_classes = [permissions.IsAuthenticated]

    def ico_filter(self):
        """The `?ico=` value, `''` when absent, or `None` when malformed.

        `None` and `''` are different answers: absent means "the whole
        mailbox", malformed means the caller asked a question we cannot answer
        and must not be handed a different one instead.
        """
        ico = self.request.query_params.get('ico')
        if ico is None:
            return ''
        ico = ico.strip()
        return ico if _ICO_RE.match(ico) else None

    def list(self, request, *args, **kwargs):
        # Validated before `super().list`, because a malformed filter must not
        # fall through to the unfiltered queryset -- that would answer with the
        # user's entire mailbox under a heading that says "for this company".
        if self.ico_filter() is None:
            return Response(
                {'detail': 'Neplatné IČO v parametri "ico". Očakávame 6 až 20 číslic.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        queryset = NotificationEvent.objects.filter(user=self.request.user)

        ico = self.ico_filter()
        if ico:
            queryset = queryset.filter(company_ico=ico)

        return queryset.order_by('-created_at')[:50]


class NotificationPreferenceViewSet(viewsets.GenericViewSet):
    """User's notification preferences (get + update)."""

    serializer_class = NotificationPreferenceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        pref, _ = NotificationPreference.objects.get_or_create(
            user=self.request.user,
            defaults={
                'email_enabled': True,
                'on_debt_change': True,
                'on_status_change': True,
                'on_executive_change': False,
            },
        )
        return pref

    def list(self, request):
        pref = self.get_object()
        return Response(NotificationPreferenceSerializer(pref).data)

    @action(detail=False, methods=['patch'])
    def update_preferences(self, request):
        pref = self.get_object()
        serializer = NotificationPreferenceSerializer(pref, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
