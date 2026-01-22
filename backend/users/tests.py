# source/apps/users/tests.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from subscriptions.models import SubscriptionPlan

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