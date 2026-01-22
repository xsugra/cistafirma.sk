# source/apps/subscriptions/migrations/XXXX_create_default_plans.py

from django.db import migrations


def create_plans(apps, schema_editor):
    # Dôležité: V migráciách nepoužívame priamy import modelov,
    # ale apps.get_model, aby sme predišli konfliktom verzií.
    SubscriptionPlan = apps.get_model('subscriptions', 'SubscriptionPlan')

    plans = [
        {
            "name": "Free",
            "slug": "free",
            "max_watched_companies": 2,
            "pdf_reports_per_month": 0,
            "price_eur": 0.00
        },
        {
            "name": "Plus",
            "slug": "plus",
            "max_watched_companies": 10,
            "pdf_reports_per_month": 5,
            "price_eur": 29.00
        },
        {
            "name": "Pro",
            "slug": "pro",
            "max_watched_companies": 50,
            "pdf_reports_per_month": 20,
            "price_eur": 59.00
        },
        {
            "name": "Business",
            "slug": "business",
            "max_watched_companies": 200,
            "pdf_reports_per_month": 100,
            "price_eur": 149.00
        },
    ]

    for plan_data in plans:
        SubscriptionPlan.objects.create(**plan_data)


class Migration(migrations.Migration):
    dependencies = [
        # Závisí od prvej migrácie, ktorá vytvorila tabuľku
        ('subscriptions', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_plans),
    ]
