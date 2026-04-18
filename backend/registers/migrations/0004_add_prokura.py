from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('registers', '0003_orsr_company_profile'),
    ]

    operations = [
        migrations.AddField(
            model_name='orsrcompanyprofile',
            name='prokura',
            field=models.JSONField(default=list, verbose_name='Prokúra'),
        ),
    ]

