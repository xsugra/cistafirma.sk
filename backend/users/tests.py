# source/apps/users/tests.py
from django.contrib import admin
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from django.test import TestCase
from django.contrib.auth import get_user_model
from subscriptions.models import SubscriptionPlan

from .admin import CustomUserAdmin
from .forms import CustomUserCreationForm

User = get_user_model()


class UserSubscriptionTest(TestCase):

    def setUp(self):
        # Vytvoríme plán pre testy (testovacia DB je vždy prázdna, migrácie bežia nanovo)
        self.plan = SubscriptionPlan.objects.create(
            name="Test Pro",
            slug="test-pro",
            max_watched_companies=50,
            price_eur=99.00
        )

    def test_user_creation_with_plan(self):
        user = User.objects.create_user(
            email="ceo@cistafirma.sk",
            password="pass",
            subscription_plan=self.plan
        )

        # Overíme, či sa to uložilo
        self.assertEqual(user.subscription_plan, self.plan)
        self.assertEqual(user.subscription_plan.max_watched_companies, 50)

        # Overíme, či frontend dostane správny slug
        self.assertEqual(user.subscription_plan.slug, "test-pro")


class CustomUserAdminFormTest(TestCase):

    def setUp(self):
        self.request = RequestFactory().get('/admin/users/user/add/')
        self.request.user = AnonymousUser()
        self.user_admin = CustomUserAdmin(User, admin.site)

    def test_custom_creation_form_has_no_usable_password(self):
        form = CustomUserCreationForm()
        self.assertNotIn('usable_password', form.fields)

    def test_admin_add_form_has_no_usable_password(self):
        form_class = self.user_admin.get_form(self.request, obj=None)
        form = form_class()
        self.assertNotIn('usable_password', form.fields)
