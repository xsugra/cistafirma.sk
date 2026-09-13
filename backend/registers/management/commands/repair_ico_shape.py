"""Repair IČO values the register stores in a shape our pipeline cannot match.

Two jobs, both consequences of the same mistake — treating IČO as a fixed
eight-character digit string:

1. **Whitespace.** The register pads an old 6- or 7-digit IČO to eight
   characters with trailing spaces (`'177474  '`). Every *lookup* path does
   `.strip().zfill(8)`, so a stored padded value never matches: the company is
   in our database and unfindable by its own IČO. Measured 2026-09-13: three
   rows — `'177474  '` (DHZ Sološnica), `'9155139 '` (Fecenková Miroslava),
   `'630021  '` (TJ VATRA).

2. **Records the walk could not store.** RUZ gives organisational units a
   twelve-character IČO, which `varchar(8)` refused; the record was counted as a
   failure and the window moved past it. Those ids are not recorded anywhere we
   can enumerate, because the run that skipped them predates the code that
   writes them to `SyncProgress.notes`. So they are passed in by hand:
   `--ruz-id 1520199`.

Both are idempotent, and both are reported before they are written, because the
only honest way to run a repair against a database that cannot be recreated is
to be able to see what it would do.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import DataError, IntegrityError, transaction

from companies.models import Company
from registers.integrations.ruz_api import RuzApi
from registers.models import IndividualEntity, OrsrCompanyProfile

# Every column that holds an IČO. `SearchHistory` and `person_ico` are excluded:
# they are not identities, and they are already width-20.
ICO_MODELS = (
    (Company, 'Company'),
    (IndividualEntity, 'IndividualEntity'),
    (OrsrCompanyProfile, 'OrsrCompanyProfile'),
)


class Command(BaseCommand):
    help = (
        'Strip whitespace from stored IČO values and re-read named RUZ records '
        'that the walk could not store.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--ruz-id',
            action='append',
            type=int,
            default=None,
            metavar='ID',
            help=(
                'A RUZ id to re-read and store. Repeatable. Use this for a '
                'record the walk skipped as unstorable — the only way to name '
                'one is from the worker log, because the run that skipped it '
                'predates the code that records them in `notes`.'
            ),
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report what would change and write nothing.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        self._report_strip(dry_run)
        for ruz_id in options['ruz_id'] or []:
            self._reimport(ruz_id, dry_run)

    def _report_strip(self, dry_run):
        """Whitespace in a stored IČO, and the conflict that would block it.

        The uniqueness check is not defensive noise: `Company.ico` is `unique`,
        and stripping `'177474  '` to `'177474'` only succeeds while no other row
        already holds `'177474'`. Checked before writing rather than caught
        afterwards, so a conflict is a named row and not a traceback halfway
        through a repair.
        """
        changes = []
        conflicts = []

        for model, label in ICO_MODELS:
            for row in model.objects.all().only('pk', 'ico'):
                stored = row.ico or ''
                stripped = stored.strip()
                if stored == stripped:
                    continue
                if model is not OrsrCompanyProfile:
                    taken = (
                        model.objects.filter(ico=stripped)
                        .exclude(pk=row.pk)
                        .exists()
                    )
                    if taken:
                        conflicts.append((label, row.pk, stored, stripped))
                        continue
                changes.append((model, label, row.pk, stored, stripped))

        for model, label, pk, stored, stripped in changes:
            self.stdout.write(
                f"  {label} pk={pk}: ico {stored!r} -> {stripped!r}"
            )
        for label, pk, stored, stripped in conflicts:
            self.stdout.write(self.style.ERROR(
                f"  {label} pk={pk}: {stored!r} -> {stripped!r} skipped — "
                f"another row already holds {stripped!r}, and `ico` is unique"
            ))

        if not changes:
            self.stdout.write('No stored IČO carries whitespace.')

        if dry_run:
            self.stdout.write(
                f'{len(changes)} IČO value(s) would be stripped, '
                f'{len(conflicts)} skipped.'
            )
            return

        with transaction.atomic():
            for model, _label, pk, _stored, stripped in changes:
                model.objects.filter(pk=pk).update(ico=stripped)

        self.stdout.write(self.style.SUCCESS(
            f'Stripped {len(changes)} IČO value(s); {len(conflicts)} skipped.'
        ))

    def _reimport(self, ruz_id, dry_run):
        """Re-read one RUZ record and store it through the walk's own mapping.

        Deliberately reuses `fetch_ruz_data.Command.update_or_create_company`
        rather than re-implementing the field mapping: a second copy would drift,
        and the whole point of this repair is that the record should now be
        stored exactly as the walk would have stored it.
        """
        if dry_run:
            self.stdout.write(
                f'Would re-read RUZ id {ruz_id} from the register.'
            )
            return

        from registers.management.commands.fetch_ruz_data import Command as Walk

        api = RuzApi()
        details = api.get_company_details(ruz_id)
        if not details:
            raise CommandError(
                f'RUZ returned no record for id {ruz_id} — nothing to store. '
                f'The id may be wrong, or the register may be unreachable.'
            )

        walk = Walk()
        walk.stdout = self.stdout
        walk.stderr = self.stderr
        try:
            created, updated = walk.update_or_create_company(details, 'both')
        except (DataError, IntegrityError) as e:
            # The walk's own mapping does not swallow this -- the *walk* catches
            # it one level up and files it as `unstorable`. Called directly there
            # is no such handler, so a re-read that lands on an IČO another row
            # now holds would end this repair in a traceback, after whatever it
            # had already written. Named here instead, and deliberately not
            # resolved by overwriting the incumbent: the register does answer one
            # IČO with more than one entity, so the two rows may be two different
            # units and forcing the write would destroy one of them.
            self.stdout.write(self.style.ERROR(
                f'RUZ id {ruz_id} ({details.get("ico")!r}) was read but not '
                f'stored — the database refused it: {e}'
            ))
            return

        if not created and not updated:
            self.stdout.write(self.style.WARNING(
                f'RUZ id {ruz_id} was read but not stored — see the message '
                f'above for which field refused it.'
            ))
            return

        company = Company.objects.filter(ruz_id=ruz_id).first()
        stored = getattr(company, 'ico', None) or (
            IndividualEntity.objects.filter(ruz_id=ruz_id).values_list('ico', flat=True).first()
        )
        self.stdout.write(self.style.SUCCESS(
            f"RUZ id {ruz_id} {'created' if created else 'updated'} "
            f"as IČO {stored!r}."
        ))
