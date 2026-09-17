from django.db import migrations, models
from django.db.models.functions import Upper


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0012_add_nace_active_index'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='company',
            index=models.Index(Upper('mesto'), name='company_mesto_ci_idx'),
        ),
        migrations.AddIndex(
            model_name='company',
            index=models.Index(Upper('sk_NACE'), name='company_nace_ci_idx'),
        ),
    ]
