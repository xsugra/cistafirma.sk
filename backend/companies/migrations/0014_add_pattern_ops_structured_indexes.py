from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0013_add_case_insensitive_structured_indexes'),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                'CREATE INDEX company_mesto_ci_like_idx ON "Companies and SZCO" ((UPPER("Mesto")) text_pattern_ops);',
                'CREATE INDEX company_psc_ci_like_idx ON "Companies and SZCO" ((UPPER("PSČ")) text_pattern_ops);',
                'CREATE INDEX company_nace_ci_like_idx ON "Companies and SZCO" ((UPPER("NACE")) text_pattern_ops);',
            ],
            reverse_sql=[
                'DROP INDEX IF EXISTS company_mesto_ci_like_idx;',
                'DROP INDEX IF EXISTS company_psc_ci_like_idx;',
                'DROP INDEX IF EXISTS company_nace_ci_like_idx;',
            ],
        ),
    ]

