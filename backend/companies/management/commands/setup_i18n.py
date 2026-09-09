"""
Management command to setup i18n for CistaFirma.

Usage:
    python manage.py setup_i18n
    python manage.py setup_i18n --extract
    python manage.py setup_i18n --compile
"""

from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.conf import settings
import os


class Command(BaseCommand):
    help = 'Setup and manage i18n (internationalization) for CistaFirma'

    def add_arguments(self, parser):
        parser.add_argument(
            '--extract',
            action='store_true',
            help='Extract translatable strings from source code',
        )
        parser.add_argument(
            '--compile',
            action='store_true',
            help='Compile .po files to .mo files',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Extract and compile (default if no options given)',
        )
        parser.add_argument(
            '--languages',
            nargs='+',
            default=['en', 'sk'],
            help='Languages to extract/compile (default: en sk)',
        )

    def handle(self, *args, **options):
        # If no specific action, do both extract and compile
        extract = options['extract'] or options['all'] or (
            not options['extract'] and not options['compile']
        )
        compile_msgs = options['compile'] or options['all'] or (
            not options['extract'] and not options['compile']
        )
        languages = options['languages']

        self.stdout.write(
            self.style.SUCCESS(
                f'🌍 CistaFirma i18n Setup\n'
                f'   Languages: {", ".join(languages)}\n'
                f'   Extract: {extract}\n'
                f'   Compile: {compile_msgs}'
            )
        )

        try:
            # Check if locale directories exist
            self._ensure_locale_dirs()

            if extract:
                self.stdout.write(self.style.WARNING('\n📝 Extracting translatable strings...'))
                call_command('makemessages', '-a', '--no-wrap', verbosity=1)
                self.stdout.write(
                    self.style.SUCCESS(
                        '✓ Strings extracted to .po files\n'
                        '  Files: backend/*/locale/*/LC_MESSAGES/django.po'
                    )
                )

            if compile_msgs:
                self.stdout.write(self.style.WARNING('\n🔨 Compiling translations...'))
                call_command('compilemessages', verbosity=1)
                self.stdout.write(
                    self.style.SUCCESS(
                        '✓ Translations compiled to .mo files\n'
                        '  Files: backend/*/locale/*/LC_MESSAGES/django.mo'
                    )
                )

            self.stdout.write(
                self.style.SUCCESS(
                    '\n✨ i18n setup complete!\n'
                    '\n📋 Next steps:\n'
                    '   1. Edit .po files to add translations\n'
                    '   2. Run: python manage.py compilemessages\n'
                    '   3. Commit .po files to git (not .mo files)\n'
                    '\n📖 For more info: docs/I18N_IMPLEMENTATION.md'
                )
            )

        except Exception as e:
            raise CommandError(f'i18n setup failed: {str(e)}')

    def _ensure_locale_dirs(self):
        """Ensure locale directories exist."""
        from pathlib import Path

        locale_paths = getattr(settings, 'LOCALE_PATHS', [])

        for path in locale_paths:
            Path(path).mkdir(parents=True, exist_ok=True)
            lc_messages = Path(path) / 'LC_MESSAGES'
            lc_messages.mkdir(parents=True, exist_ok=True)
            self.stdout.write(
                self.style.SUCCESS(f'   Created: {lc_messages}')
            )

        # Also ensure app-level locale dirs
        apps = ['companies', 'registers', 'core']
        for app in apps:
            app_locale = f'backend/{app}/locale'
            Path(app_locale).mkdir(parents=True, exist_ok=True)
            lc_messages = Path(app_locale) / 'LC_MESSAGES'
            lc_messages.mkdir(parents=True, exist_ok=True)
            self.stdout.write(
                self.style.SUCCESS(f'   Created: {lc_messages}')
            )

