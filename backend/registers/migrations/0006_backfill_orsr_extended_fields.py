from django.db import migrations


def backfill_extended_fields(apps, schema_editor):
    OrsrCompanyProfile = apps.get_model('registers', 'OrsrCompanyProfile')
    OrsrCompanyProfile.objects.filter(oddiel_type__isnull=True).update(oddiel_type='')
    OrsrCompanyProfile.objects.filter(konanie__isnull=True).update(konanie='')
    OrsrCompanyProfile.objects.filter(zakladny_clensky_vklad__isnull=True).update(zakladny_clensky_vklad='')
    OrsrCompanyProfile.objects.filter(zapisovane_zakladne_imanie__isnull=True).update(zapisovane_zakladne_imanie='')
    OrsrCompanyProfile.objects.filter(dalske_pravne_skutocnosti__isnull=True).update(dalske_pravne_skutocnosti='')


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('registers', '0005_orsr_drustva_fields'),
    ]

    operations = [
        migrations.RunPython(backfill_extended_fields, noop_reverse),
    ]

