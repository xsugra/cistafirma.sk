from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()


class EmailOrUsernameModelBackend:
    """
    Umožňuje prihlásenie pomocou emailu alebo username.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            # Hľadáme užívateľa, ktorého email ALEBO username sa zhoduje so vstupom
            user = User.objects.get(Q(username=username) | Q(email=username))
        except User.DoesNotExist:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def user_can_authenticate(self, user):
        is_active = getattr(
            user,
            'is_active',
            None
        )
        return is_active or is_active is None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
