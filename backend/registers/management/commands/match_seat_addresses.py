"""Place each company's seat on a real address point, where one can be found.

Reads `Company.ulica`/`mesto`/`psc`, asks `companies.seat_matching` which
register tiers those values could be looked up by, and writes the first tier
that answers honestly into the `seat_*` columns. A company the register cannot
place is **left empty on purpose**: the serializer then falls back to the PSČ
circle, which is a weaker claim but a true one. This command never writes
`postal_code` — copying `PostalCodeArea` onto 400 000 rows would give the circle
a second source that goes stale independently of the first.

Three things keep the *reading* half cheap:

- **One query per tier per chunk, not one per company.** The keys are passed as
  arrays and joined with `unnest`, so 5 000 companies cost six queries instead
  of 30 000. The aggregation is `array_agg`, so a key comes back as one row
  carrying its points rather than as one row per point.
- **Keys are deduplicated before they are sent.** `unnest` over a repeated key
  would emit its points twice and quietly double every count, so the arrays
  hold distinct values by construction.
- **A row is written only when its placement changes.** The current `seat_*`
  values are read alongside the address and compared, so re-running against
  unchanged data writes nothing at all — which matters, because the address
  register is reloaded quarterly and this command is the second half of it.

Where the time actually goes, measured over a 5 000-company chunk: reading the
chunk and matching it is **0.8 s**, of which the six tier queries are 0.73 s and
`resolve` is 0.04 s. Everything else is the write — this table carries 24
indexes, so each updated row costs 24 index entries, and `batch_size` decides
how much the statement itself adds on top of that (see
`BULK_UPDATE_BATCH_SIZE`). A full 449 764-company pass is therefore minutes, not
seconds, and the honest description of this command is "routine but not quick" —
it is idempotent and it makes progress in chunks, so it is safe to interrupt and
re-run.

The distance arithmetic stays in `companies.address`, so the shape of a ring
cannot differ between the importer that measured it and this command that
writes it.
"""

from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.utils import timezone

from companies.models import Company
from companies.seat_matching import ALL_TIERS, BUILDING, STREET, candidates, resolve

# Companies held in memory at once. Bounds the arrays sent in one query and the
# points that come back with them.
CHUNK_SIZE = 5_000

# Rows per `bulk_update` statement, and **not** the chunk size. Django compiles
# `bulk_update` to one `UPDATE ... SET f = CASE WHEN id=.. THEN .. END` per
# field, so a 5 000-row batch is a single statement carrying 35 000 `WHEN`
# clauses and 75 000 bind parameters. Measured on a copy of this table with all
# 24 of its indexes, per 5 000 rows:
#
#   batch_size= 5 000   2.232 s      batch_size=   500   0.457 s
#   batch_size= 1 000   0.530 s      batch_size=   100   0.545 s
#
# 4.9x, and it is the plan cost rather than the writing: the same rows through
# smaller statements do the same index maintenance. 500 is the measured minimum
# and is not a magic number -- anything in the low hundreds lands within 20 % of
# it, and the shape of the curve is what matters: it rises steeply at the top.
BULK_UPDATE_BATCH_SIZE = 500

# The address fields decide the placement; the seat fields are read so an
# unchanged row can be skipped rather than rewritten.
SOURCE_FIELDS = ('id', 'psc', 'mesto', 'ulica')
SEAT_FIELDS = (
    'seat_lat',
    'seat_lon',
    'seat_precision',
    'seat_radius_m',
    'seat_point_count',
    'seat_tier',
)


def _chunks(iterable, size):
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def _fetch_points(tier, keys):
    """The register points behind each of `keys`, keyed by the values tuple.

    `keys` must already be distinct: `unnest` zips the arrays positionally and
    emits a repeated key once per copy, which `array_agg` would then fold into a
    single row with the points counted twice -- inflating `point_count` and
    dragging the centroid.
    """
    columns = tier.columns
    select = ', '.join(f'k.{c}' for c in columns)
    join = ' AND '.join(f'a.{c} = k.{c}' for c in columns)
    placeholders = ', '.join(['%s::text[]'] * len(columns))
    sql = (
        f'SELECT {select}, array_agg(a.lat) AS lats, array_agg(a.lon) AS lons '
        f'FROM unnest({placeholders}) AS k({", ".join(columns)}) '
        f'JOIN companies_addresspoint a ON {join} '
        f'GROUP BY {select}'
    )
    params = [[key[i] for key in keys] for i in range(len(columns))]

    points = {}
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        for *values, lats, lons in cursor.fetchall():
            points[tuple(values)] = list(zip(lats, lons))
    return points


def _wanted(placement):
    """The `seat_*` values a placement implies, in `SEAT_FIELDS` order."""
    if placement is None:
        return (None, None, '', None, None, '')
    return (
        placement.lat,
        placement.lon,
        placement.precision,
        placement.radius_m,
        placement.point_count,
        placement.tier,
    )


class Command(BaseCommand):
    help = "Place companies' seats on register address points (building/street tiers)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report what would change, but write nothing.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help=(
                'Only consider the first N companies. For checking the command '
                'against a slice; the companies it does not see are left exactly '
                'as they are, so a limited run never clears anything outside it. '
                'N=0 considers nothing at all, which is a way to load and report '
                'without touching a row -- and is why the test below is `is not '
                'None` rather than a truth test.'
            ),
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limit = options['limit']

        queryset = Company.objects.values_list(*SOURCE_FIELDS, *SEAT_FIELDS).order_by('id')
        # `is not None`, not truth: `--limit 0` slices to nothing, and a truth
        # test would silently drop the slice and walk the whole table instead.
        if limit is not None:
            queryset = queryset[:limit]

        now = timezone.now()
        seen = 0
        changed = 0
        by_precision = {BUILDING: 0, STREET: 0}
        by_tier = {}
        unplaced = 0

        for chunk in _chunks(queryset.iterator(chunk_size=CHUNK_SIZE), CHUNK_SIZE):
            # Ask each tier once for the whole chunk. `candidates` is called on
            # every row because the tiers a row can use depend on its own values.
            keys_by_tier = {tier.name: set() for tier in ALL_TIERS}
            parsed = []
            for row in chunk:
                found = candidates(row[1], row[2], row[3])
                parsed.append(found)
                for tier, values in found:
                    keys_by_tier[tier.name].add(values)

            points_by_key = {}
            for tier in ALL_TIERS:
                keys = keys_by_tier[tier.name]
                if keys:
                    for values, points in _fetch_points(tier, keys).items():
                        points_by_key[(tier.name, values)] = points

            def fetch(tier, values, _points=points_by_key):
                return _points.get((tier.name, values), ())

            updates = []
            for row, found in zip(chunk, parsed):
                seen += 1
                placement = resolve(found, fetch)
                if placement is None:
                    unplaced += 1
                else:
                    by_precision[placement.precision] += 1
                    by_tier[placement.tier] = by_tier.get(placement.tier, 0) + 1

                wanted = _wanted(placement)
                if wanted == tuple(row[4:]):
                    continue
                changed += 1
                if dry_run:
                    continue
                updates.append(Company(
                    id=row[0],
                    seat_lat=wanted[0],
                    seat_lon=wanted[1],
                    seat_precision=wanted[2],
                    seat_radius_m=wanted[3],
                    seat_point_count=wanted[4],
                    seat_tier=wanted[5],
                    seat_matched_at=now,
                ))

            if updates:
                with transaction.atomic():
                    Company.objects.bulk_update(
                        updates,
                        list(SEAT_FIELDS) + ['seat_matched_at'],
                        batch_size=BULK_UPDATE_BATCH_SIZE,
                    )

            self.stdout.write(f'  {seen:,} companies considered…', ending='\r')

        self.stdout.write(' ' * 40, ending='\r')
        self._report(seen, changed, by_precision, by_tier, unplaced, dry_run)

    def _report(self, seen, changed, by_precision, by_tier, unplaced, dry_run):
        verb = 'would change' if dry_run else 'changed'
        self.stdout.write(f'Considered {seen:,} companies; {changed:,} {verb}.')

        placed = by_precision[BUILDING] + by_precision[STREET]
        if seen:
            self.stdout.write(self.style.SUCCESS(
                f'  {placed:,} placed ({100.0 * placed / seen:.1f} %) — '
                f'{by_precision[BUILDING]:,} on a building, {by_precision[STREET]:,} on a street'
            ))
            self.stdout.write(
                f'  {unplaced:,} ({100.0 * unplaced / seen:.1f} %) the register cannot place; '
                f'they keep the PSČ circle'
            )

        if by_tier:
            self.stdout.write('  which tier answered:')
            for name in sorted(by_tier, key=lambda k: -by_tier[k]):
                self.stdout.write(f'    {name:22s} {by_tier[name]:,}')

        if changed == 0 and not dry_run:
            self.stdout.write(
                'Nothing changed — the stored placements already match the register.'
            )
