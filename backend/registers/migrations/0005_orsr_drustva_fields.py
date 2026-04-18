"""
Migrácia: Pridať polia pre poľnohospodárske družstvá a iné typy ORSR

Podľa štruktúry ORSR výpisov (Sr vs Dr) potrebujeme rozšíriť model:
- Typ ORSR (Sr/Dr/...)
- Predstavenstvo (pre družstvá)
- Kontrolná komisia (pre družstvá)
- Základný členský vklad (pre družstvá)
- Zapisované základné imanie (pre družstvá)
- Ďalšie právne skutočnosti
- Konanie (kto koná menom subjektu)
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('registers', '0004_add_prokura'),
    ]

    operations = [
        # Pridať typ ORSR sekcie (Sr, Dr, atď.)
        migrations.AddField(
            model_name='orsrcompanyprofile',
            name='oddiel_type',
            field=models.CharField(
                max_length=10,
                blank=True,
                default='',
                help_text='Typ ORSR sekcie: Sr (obchodná), Dr (družstvo), atď.',
                verbose_name='Typ ORSR'
            ),
        ),

        # Pre družstvá: predstavenstvo
        migrations.AddField(
            model_name='orsrcompanyprofile',
            name='predstavenstvo',
            field=models.JSONField(
                default=list,
                help_text='Členovia predstavenstva (pre družstvá)',
                verbose_name='Predstavenstvo'
            ),
        ),

        # Pre družstvá: kontrolná komisia
        migrations.AddField(
            model_name='orsrcompanyprofile',
            name='kontrolna_komisia',
            field=models.JSONField(
                default=list,
                help_text='Členovia kontrolnej komisie (pre družstvá)',
                verbose_name='Kontrolná komisia'
            ),
        ),

        # Pre družstvá: základný členský vklad
        migrations.AddField(
            model_name='orsrcompanyprofile',
            name='zakladny_clensky_vklad',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Základný členský vklad (pre družstvá)',
                verbose_name='Základný členský vklad'
            ),
        ),

        # Pre družstvá: zapisované základné imanie
        migrations.AddField(
            model_name='orsrcompanyprofile',
            name='zapisovane_zakladne_imanie',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Zapisované základné imanie (pre družstvá)',
                verbose_name='Zapisované základné imanie'
            ),
        ),

        # Ďalšie právne skutočnosti
        migrations.AddField(
            model_name='orsrcompanyprofile',
            name='dalske_pravne_skutocnosti',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Historické a ďalšie právne informácie',
                verbose_name='Ďalšie právne skutočnosti'
            ),
        ),

        # Konanie (kto koná menom subjektu)
        migrations.AddField(
            model_name='orsrcompanyprofile',
            name='konanie',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Konanie menom subjektu (kto je oprávnený)',
                verbose_name='Konanie'
            ),
        ),
    ]

