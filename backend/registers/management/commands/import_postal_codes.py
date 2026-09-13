"""Import the MV SR address register into `PostalCodeArea`.

Source: dataset "Adresy podľa krajov (csv)" published by Ministerstvo vnútra SR
(`data.gov.sk/set/b27f57f1-7e76-45e0-8968-631f9176b2e9`, direct download
`data.slovensko.sk/download?id=d22c42f3-82b5-450d-b8fb-4245d50a31ec`), 162 MB,
`accrualPeriodicity` QUARTERLY. Coordinates are WGS84 decimal degrees written
with a **comma**, in `ADRBOD_X` (lon) and `ADRBOD_Y` (lat) — the source needs no
transformation, verified against a known municipality before this was written.

Why the key is PSČ and not `mesto` is argued in `PostalCodeArea`'s docstring.
The short version: 95 municipality names in this source sit in more than one
district, and our own `mesto` spells city parts differently from the register
(`Bratislava - mestská časť Ružinov` vs `Bratislava-Ružinov`), so joining on a
name would be fuzzy matching. PSČ covers 98,09 % of our companies and needs no
name matching at all.

Two traps this command handles rather than inheriting:

- **Rows with no PSČ.** The source has 224 of them, and they carry valid
  coordinates scattered across the country — a naive `GROUP BY PSC` would
  manufacture an "area" whose centroid sits somewhere in central Slovakia and
  would pin our three PSČ-less companies to it. They are skipped and counted.
- **Thin areas.** A PSČ with one address point yields a 0 m radius, i.e. a pin
  claiming the accuracy of a building entrance. Anything below
  `MIN_ADDRESS_POINTS` is not stored, and the UI shows no map for it.
"""

import csv
import math
from array import array
from collections import Counter, defaultdict
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count

from companies.models import MIN_ADDRESS_POINTS, Company, PostalCodeArea

# Metres per degree at the equator; the longitude component is scaled by the
# cosine of the latitude. A flat approximation is enough here: the largest
# radius we store is ~8 km, where the error is far below the approximation's
# whole point -- which is that this is a postcode area, not a doorstep.
METRES_PER_DEGREE = 111_320
COVERAGE = 0.90


def _metres(lon1, lat1, lon2, lat2):
    dx = (lon1 - lon2) * METRES_PER_DEGREE * math.cos(math.radians(lat1))
    dy = (lat1 - lat2) * METRES_PER_DEGREE
    return math.hypot(dx, dy)


class Command(BaseCommand):
    help = 'Import PSČ areas (centroid + honest radius) from the MV SR address register CSV.'

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
            help='Read, compute and report, but write nothing.',
        )

    def handle(self, *args, **options):
        path = options['path']
        dry_run = options['dry_run']

        if not options['source_version']:
            self.stdout.write(self.style.WARNING(
                'No --source-version given: the stored version stays empty and '
                'these areas cannot be traced to a release of the dataset.'
            ))

        lon = defaultdict(lambda: array('d'))
        lat = defaultdict(lambda: array('d'))
        obec = defaultdict(Counter)
        okres = defaultdict(Counter)
        kraj = defaultdict(Counter)
        # PSČ the source lists but for which no row carried a usable
        # coordinate. Tracked as a set because the coverage report has to tell
        # them apart from PSČ the source does not list at all.
        no_point = set()
        rows = 0
        skipped_no_psc = 0
        skipped_no_psc_no_point = 0
        skipped_no_point = 0

        try:
            handle = open(path, encoding='utf-8', newline='')
        except OSError as e:
            raise CommandError(f'Cannot read {path}: {e}')

        with handle:
            reader = csv.DictReader(handle, delimiter=';')
            missing = {'PSC', 'ADRBOD_X', 'ADRBOD_Y', 'OBEC', 'OKRES', 'KRAJ'} - set(
                reader.fieldnames or []
            )
            if missing:
                raise CommandError(
                    f'{path} is not the MV SR address CSV: missing {sorted(missing)}. '
                    f'Header found: {reader.fieldnames}'
                )

            for row in reader:
                rows += 1
                try:
                    x = float((row['ADRBOD_X'] or '').replace(',', '.'))
                    y = float((row['ADRBOD_Y'] or '').replace(',', '.'))
                except ValueError:
                    x = y = None
                if x is not None and (not x or not y):
                    x = y = None
                psc = PostalCodeArea.normalize_psc(row['PSC'])
                if not psc:
                    # Counted apart, because the two groups fail for different
                    # reasons and only one of them is the trap this guards.
                    if x is None:
                        skipped_no_psc_no_point += 1
                    else:
                        skipped_no_psc += 1
                    continue
                if x is None:
                    no_point.add(psc)
                    skipped_no_point += 1
                    continue
                lon[psc].append(x)
                lat[psc].append(y)
                # Kept as counters, not single values: a PSČ spanning several
                # municipalities has no single one, and the count is the evidence.
                obec[psc][(row['OBEC'] or '').strip()] += 1
                okres[psc][(row['OKRES'] or '').strip()] += 1
                kraj[psc][(row['KRAJ'] or '').strip()] += 1

        self.stdout.write(f'Read {rows:,} rows; {len(lon):,} distinct PSČ with a point.')
        if skipped_no_psc:
            self.stdout.write(
                f'  skipped {skipped_no_psc:,} rows with no PSČ but valid coordinates — '
                f'they are scattered across the country, so their centroid would be a lie'
            )
        if skipped_no_psc_no_point:
            self.stdout.write(
                f'  skipped {skipped_no_psc_no_point:,} rows with neither a PSČ nor usable coordinates'
            )
        if skipped_no_point:
            self.stdout.write(f'  skipped {skipped_no_point:,} rows with unusable coordinates')

        areas = []
        thin = []
        for psc, xs in lon.items():
            n = len(xs)
            if n < MIN_ADDRESS_POINTS:
                thin.append((psc, n))
                continue
            cx = sum(xs) / n
            cy = sum(lat[psc]) / n
            distances = sorted(
                _metres(xs[i], lat[psc][i], cx, cy) for i in range(n)
            )
            # The radius that covers COVERAGE of this PSČ's address points.
            idx = min(n - 1, max(0, math.ceil(COVERAGE * n) - 1))
            areas.append({
                'psc': psc,
                'lat': cy,
                'lon': cx,
                'radius_m': int(round(distances[idx])),
                'point_count': n,
                'dominant_obec': obec[psc].most_common(1)[0][0] if obec[psc] else '',
                'obec_count': len(obec[psc]),
                'okres': okres[psc].most_common(1)[0][0] if okres[psc] else '',
                'kraj': kraj[psc].most_common(1)[0][0] if kraj[psc] else '',
                'source_version': options['source_version'],
            })

        if thin:
            listed = ', '.join(f'{p}({n})' for p, n in sorted(thin)[:20])
            self.stdout.write(self.style.WARNING(
                f'  {len(thin)} PSČ below {MIN_ADDRESS_POINTS} address points — not stored, '
                f'so no pin is claimed for them: {listed}'
            ))

        stale = []
        if not dry_run:
            with transaction.atomic():
                for area in areas:
                    PostalCodeArea.objects.update_or_create(
                        psc=area['psc'], defaults=area
                    )
                # The table is entirely derived from this source, so a PSČ that
                # left the register must leave the table -- otherwise a stale
                # area keeps putting a pin on a place the source no longer
                # supports. Nothing references these by foreign key.
                keep = {a['psc'] for a in areas}
                stale = list(
                    PostalCodeArea.objects.exclude(psc__in=keep).values_list('psc', flat=True)
                )
                if stale:
                    PostalCodeArea.objects.filter(psc__in=stale).delete()

        self._report_coverage(areas, dry_run, stale, {p for p, _ in thin}, no_point)

    def _report_coverage(self, areas, dry_run, stale, thin_psc, no_point):
        """What this actually buys the product, measured against our own rows.

        Reported every run, including a dry one, because the number that matters
        is not how many areas were imported but how many companies can now be
        placed -- and those two move independently.
        """
        stored = {a['psc'] for a in areas}
        if not dry_run:
            stored = set(PostalCodeArea.objects.values_list('psc', flat=True))

        # Normalised in Python with the same function the join uses, not with a
        # SQL expression that would be a second definition of "the same PSČ".
        counts = (
            Company.objects.exclude(psc__isnull=True)
            .exclude(psc='')
            .values('psc')
            .annotate(n=Count('id'))
        )
        total = covered = 0
        unmatched = Counter()
        for row in counts:
            n = row['n']
            total += n
            if PostalCodeArea.normalize_psc(row['psc']) in stored:
                covered += n
            else:
                unmatched[PostalCodeArea.normalize_psc(row['psc'])] += n

        no_psc = Company.objects.filter(psc__isnull=True).count() + Company.objects.filter(
            psc=''
        ).count()
        total += no_psc

        pct = (100.0 * covered / total) if total else 0.0
        verb = 'would cover' if dry_run else 'covers'
        stored_verb = 'would be stored' if dry_run else 'stored'
        self.stdout.write(self.style.SUCCESS(
            f'{len(areas):,} PSČ areas {stored_verb}; this {verb} {covered:,} of '
            f'{total:,} companies ({pct:.2f}%).'
        ))
        if no_psc:
            self.stdout.write(f'  {no_psc:,} companies have no PSČ at all')

        # The reason matters more than the count. "The register has no such PSČ"
        # is a dead end, while "we dropped it under the point floor" is a choice
        # this command made and could make differently -- and lumping the two
        # together would state something false about the source while hiding the
        # one case an operator can act on.
        reasons = Counter()
        reason_rows = Counter()
        for psc, n in unmatched.items():
            if psc in thin_psc:
                reason = 'floor'
            elif psc in no_point:
                reason = 'no_point'
            else:
                reason = 'not_listed'
            reasons[reason] += 1
            reason_rows[reason] += n

        self.stdout.write(
            f'  {len(unmatched):,} distinct PSČ unplaced, {sum(unmatched.values()):,} rows:'
        )
        for reason, note in (
            (
                'not_listed',
                'the register does not list it at all — a post-office PSČ with no '
                'address point, so nothing here can place it',
            ),
            (
                'floor',
                f'listed, but under the {MIN_ADDRESS_POINTS}-point floor, so we chose '
                f'not to claim a pin for it',
            ),
            ('no_point', 'listed, but no row for it carried a usable coordinate'),
        ):
            if reasons[reason]:
                self.stdout.write(
                    f'    {reasons[reason]:,} PSČ · {reason_rows[reason]:,} rows — {note}'
                )
        if stale:
            listed = ', '.join(sorted(stale)[:20])
            self.stdout.write(self.style.WARNING(
                f'  removed {len(stale)} areas that left the source: {listed}'
            ))

        newest = max((a['source_version'] for a in areas if a['source_version']), default='')
        if not newest and not dry_run:
            self.stdout.write(self.style.WARNING(
                'Stored areas carry no source version — re-run with --source-version '
                f'({date.today().isoformat()} would at least date the import).'
            ))
