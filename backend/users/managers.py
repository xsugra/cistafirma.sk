from django.contrib.auth.base_user import BaseUserManager
from django.utils.translation import gettext_lazy as _
import uuid


class CustomUserManager(BaseUserManager):
    """
    Custom manager, kde email je unikátny identifikátor pre autentifikáciu
    namiesto username, ale username stále existuje.
    """

    def create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError(_('Emailová adresa musí byť zadaná.'))

        email = self.normalize_email(email)

        # LOGIKA: Ak username nie je zadané, vygenerujeme ho z emailu + UUID
        if not extra_fields.get('username'):
            username_base = email.split('@')[0]
            # Pridáme krátky hash, aby sme zaručili unikátnosť
            extra_fields['username'] = f"{username_base}_{uuid.uuid4().hex[:8]}"

        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser musí mať is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser musí mať is_superuser=True.'))

        # Superuser si zvyčajne zadá username, ale ak nie, logika vyššie to pokryje
        return self.create_user(email, password, **extra_fields)
