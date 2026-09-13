"""Import the MV SR address register into `AddressPoint` — one row per building.

The **same file** `import_postal_codes` reads, read a second time for the layer
that command throws away: the street, both house numbers and the coordinate of
each individual address point. 1 739 536 rows, QUARTERLY, free, no registration
and no third party — the fine layer costs a second pass, not a second source.

Two differences from the PSČ import, both deliberate:

- **A row with no PSČ is kept.** That import drops them, because a PSČ-keyed
  table has nothing to file them under. Here the municipal scope still uses
  them, so they are imported with an empty `psc` and counted separately.
- **The table is replaced whole, not reconciled row by row.** It is reference
  data with no local mutations and no foreign keys pointing at it, so 1,7 M
  `update_or_create` calls would spend minutes to reach the state a truncate and
  reload reaches in one. The delete and the reload share one transaction, so a
  reader sees the old snapshot until the commit and never a half-loaded table.

**The 35 190 rows that do not arrive are all one thing.** The source holds
1 739 536 rows; the table holds 1 704 346. That gap is not a loss to be
tolerated, so it was reconciled against the file rather than assumed: replaying
this command's own skip order over all 1 739 536 rows derives 1 704 346 and a
residue of **zero** — every missing row has `ADRBOD_X`/`ADRBOD_Y` empty or
unparseable. Nothing is dropped silently, and `no_coordinate` below is the whole
of the difference (0 rows lack a municipality, 0 lack both house numbers).

**A short read is refused, not committed.** The table is replaced whole, so a
truncated download — header intact, body cut anywhere — would otherwise delete
1,7 M rows and load the fraction it managed to read, exit 0, and report a count
nobody compares with anything. The header check cannot catch that (a cut body
still has its header), and neither can any per-row check, because every accessor
here tolerates a short row by design. So the count is compared with what the
table held: more than `MAX_SHRINK` smaller and the command raises, which rolls
the delete back and leaves the previous layer in place. `--allow-shrink` is the
way past it when the register really did get smaller.

The normalisation is not repeated here. `companies.address` owns it and this
command calls it — `street_key`/`normalize_obec` for the keys and `psc_key` for
the PSČ — so the key written on this side is the key `match_seat_addresses`
builds on the other. That is the failure #90 named for IČO, and this command was
still making it for PSČ until `psc_key` replaced the inline `.replace(' ', '')`
that disagreed with the matcher's `normalize_text` on the three `Company.psc`
values written with a space.
"""

import csv

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from companies.address import normalize_number, normalize_obec, psc_key, street_key
from companies.models import AddressPoint

# Objects held in memory at once. Small enough that the peak stays flat on a
# 1,7 M-row file, large enough that the inserts are not one round trip each.
BATCH_SIZE = 20_000

MAX_SHRINK = 0.05
"""How much smaller than the stored layer a load may be before it is refused.

The register grows by well under a percent a quarter, so a load this much
smaller than what is already stored is not a new release of the dataset — it is
a partial read of one. Generous on purpose: it is a guard against a truncated
file, not a check that the source is unchanged.
"""


class Command(BaseCommand):
    help = 'Import per-building address points from the MV SR address register CSV.'

    def add_arguments(self, parser):
        parser.add_argument(
            'path',
            help='Path to the MV SR "Adresy podľa krajov" CSV.',
        )
        parser.add_argument(
            '--source-version',
            default='',
            help=(
                "The dataset's dct:modified from the catalogue (YYYY-MM-DD). It "
                "cannot be derived from the CSV, so pass it or the stored version "
                "stays empty and the data cannot be traced to a release."
            ),
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Read, normalise and report, but write nothing.',
        )
        parser.add_argument(
            '--allow-shrink',
            action='store_true',
            help=(
                f'Load even if the file yields more than {MAX_SHRINK:.0%} fewer '
                f'points than the table already holds. Only for a genuine '
                f'release of the dataset that is smaller; a truncated download '
                f'is what the default refusal exists to catch.'
            ),
        )

    def handle(self, *args, **options):
        path = options['path']
        dry_run = options['dry_run']
        version = options['source_version']
        allow_shrink = options['allow_shrink']

        if not version:
            self.stdout.write(self.style.WARNING(
                'No --source-version given: the stored version stays empty and '
                'these points cannot be traced to a release of the dataset.'
            ))

        try:
            handle = open(path, encoding='utf-8', newline='')
        except OSError as e:
            raise CommandError(f'Cannot read {path}: {e}')

        counts = {
            'rows': 0,
            'stored': 0,
            'no_obec': 0,
            'no_coordinate': 0,
            'no_number': 0,
            'rural': 0,
            'no_psc': 0,
        }
        psces = set()
        obecs = set()
        streets = set()

        with handle:
            reader = csv.DictReader(handle, delimiter=';')
            required = {
                'PSC', 'OBEC', 'ULICA', 'SUPISNE_CISLO',
                'ORIENTACNE_CISLO_CELE', 'ADRBOD_X', 'ADRBOD_Y',
            }
            missing = required - set(reader.fieldnames or [])
            if missing:
                raise CommandError(
                    f'{path} is not the MV SR address CSV: missing {sorted(missing)}. '
                    f'Header found: {reader.fieldnames}'
                )

            # Read before the delete, so the gate below has something to compare
            # against. One `count(*)` against a multi-minute load.
            before = AddressPoint.objects.count()

            with transaction.atomic():
                if not dry_run:
                    # Raw delete, not `objects.all().delete()`: the ORM's delete
                    # collects primary keys first, which on 1,7 M rows means
                    # reading them all back to throw them away. This is also not
                    # a TRUNCATE -- that takes an ACCESS EXCLUSIVE lock and would
                    # block the live API, whereas a DELETE leaves readers on the
                    # old snapshot until the commit.
                    with connection.cursor() as cursor:
                        cursor.execute('DELETE FROM companies_addresspoint')

                batch = []
                for row in reader:
                    counts['rows'] += 1

                    obec = normalize_obec(row['OBEC'])
                    if not obec:
                        counts['no_obec'] += 1
                        continue

                    try:
                        lon = float((row['ADRBOD_X'] or '').replace(',', '.'))
                        lat = float((row['ADRBOD_Y'] or '').replace(',', '.'))
                    except ValueError:
                        counts['no_coordinate'] += 1
                        continue
                    if not lon or not lat:
                        counts['no_coordinate'] += 1
                        continue

                    supisne = normalize_number(row['SUPISNE_CISLO'])
                    orient = normalize_number(row['ORIENTACNE_CISLO_CELE'])
                    if not supisne and not orient:
                        # No number at all: the row can key nothing, because a
                        # street centroid is built from every point on the
                        # street and one anonymous point adds only noise.
                        counts['no_number'] += 1
                        continue

                    # Empty when the source leaves ULICA empty, which is the
                    # rural case -- 973 318 of the source's rows, of which
                    # 943 949 reach this table (the rest have no coordinate).
                    # This is the same key shape as a street address, so one
                    # index serves both.
                    ulica = street_key(row['ULICA'])
                    psc = psc_key(row['PSC'])
                    if not psc:
                        counts['no_psc'] += 1
                    if not ulica:
                        counts['rural'] += 1

                    counts['stored'] += 1
                    psces.add(psc)
                    obecs.add(obec)
                    if ulica:
                        streets.add(ulica)

                    if dry_run:
                        continue
                    batch.append(AddressPoint(
                        psc=psc,
                        obec=obec,
                        ulica=ulica,
                        supisne_cislo=supisne,
                        orientacne_cislo=orient,
                        lat=lat,
                        lon=lon,
                        source_version=version,
                    ))
                    if len(batch) >= BATCH_SIZE:
                        AddressPoint.objects.bulk_create(batch, batch_size=BATCH_SIZE)
                        batch.clear()

                if batch:
                    AddressPoint.objects.bulk_create(batch, batch_size=BATCH_SIZE)

                self._refuse_a_short_read(counts, before, allow_shrink)

        self._report(counts, before, psces, obecs, streets, dry_run, version)

    def _refuse_a_short_read(self, counts, before, allow_shrink):
        """Refuse a load that is mostly a *deletion* of the layer already stored.

        Raised inside the transaction on purpose: the delete and the batches it
        already wrote are rolled back, so the previous snapshot survives intact
        and the operator gets an error instead of a half-empty reference layer
        that the next `match_seat_addresses` would read as "the register does not
        know these addresses" — and clear their placements over.
        """
        if allow_shrink or not before:
            return
        kept = counts['stored'] / before
        if kept >= 1 - MAX_SHRINK:
            return
        raise CommandError(
            f'Refusing to replace the address layer: this file yields '
            f'{counts["stored"]:,} points against {before:,} already stored '
            f'({kept:.1%}, more than the {MAX_SHRINK:.0%} this command tolerates). '
            f'A truncated or partial download looks exactly like this. Re-download '
            f'the dataset, or pass --allow-shrink if the register really did shrink.'
        )

    def _report(self, counts, before, psces, obecs, streets, dry_run, version):
        verb = 'would be stored' if dry_run else 'stored'
        self.stdout.write(f'Read {counts["rows"]:,} rows.')
        self.stdout.write(self.style.SUCCESS(
            f'{counts["stored"]:,} address points {verb} across {len(obecs):,} '
            f'municipalities and {len(psces):,} PSČ.'
        ))
        self.stdout.write(
            f'  {len(streets):,} distinct street keys; '
            f'{counts["rural"]:,} rural rows carry the number alone'
        )
        if before:
            # The one number that makes a short read visible after the fact: the
            # count alone says nothing about whether it is complete.
            self.stdout.write(
                f'  the layer held {before:,} points; this is {counts["stored"] - before:+,}'
            )

        # Every skip is a row that can never place a company, so each is named
        # rather than folded into a total: they fail for different reasons and
        # only some are choices this command made.
        for key, note in (
            ('no_obec', 'no municipality, so neither scope can key them'),
            ('no_coordinate', 'no usable coordinate'),
            ('no_number', 'neither house number, so nothing to key on'),
        ):
            if counts[key]:
                self.stdout.write(f'  skipped {counts[key]:,} — {note}')
        if counts['no_psc']:
            self.stdout.write(
                f'  {counts["no_psc"]:,} of the stored rows have no PSČ; they are kept '
                f'because the municipal scope still places companies with them'
            )

        if not version and not dry_run:
            self.stdout.write(self.style.WARNING(
                'Stored points carry no source version — re-run with --source-version '
                'so the layer can be traced to a release of the dataset.'
            ))

        self.stdout.write(
            'Run `manage.py match_seat_addresses` to turn these points into '
            'placements on Company.'
        )
