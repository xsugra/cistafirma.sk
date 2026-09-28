"""Measure the risk-indicator thresholds against the data they will cut.

Read-only, and deliberately so: it runs no rule that writes, touches no table,
and starts no container. It may be run against the production database.

Why it exists. Every threshold in `companies.services.red_flags` and
`connections.person_risk` is a *starting value* -- a shape taken from the
methodology the feature was specified with, and a number that has not yet been
measured. This project has already paid for a threshold written from intuition:
`docs/PLAN.md` §8.6 records a 500-filing cutoff that looked like the cause of a
gap for thirteen years and explained exactly one of them. A gate whose number
nobody can reconstruct is a gate that binds for reasons that have to be
rediscovered from scratch.

So the rules carry their measured quantity in `evidence` whether they fired or
not, and this command is a pure aggregation of what they report. It computes no
threshold logic of its own -- if it did, the report and the product could
disagree about the same company, which is the failure this repository keeps
paying for.

Usage (on `dell`, where the data is):

    python manage.py risk_indicators_report
    python manage.py risk_indicators_report --sample 5000
    python manage.py risk_indicators_report --skip-address   # seconds, not minutes
"""

from __future__ import annotations

import hashlib
import heapq
import time
from collections import Counter
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand
from django.db.models import Count

from companies.models import Company, CompanyFinancialResult
from companies.services import red_flags
from connections import person_risk
from connections.models import Person, PersonCompanyRelation


def percentile(values, fraction):
    """The value at `fraction` of a sorted-by-value sample, nearest-rank.

    Nearest-rank and not interpolated: every number this report prints is a
    value some company actually has, and an interpolated threshold would be a
    number no company has -- which is precisely the kind of invented figure the
    command exists to avoid.
    """
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round(fraction * len(ordered))) - 1))
    return ordered[index]


def _decimal(value):
    if value is None:
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError):
        return None


class Command(BaseCommand):
    help = (
        'Zmeria distribúcie, z ktorých sú odvodené prahy rizikových '
        'indikátorov. Len číta, nič nezapisuje.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--sample',
            type=int,
            default=2000,
            help='Koľko firiem náhodne prejsť pravidlami (default 2000).',
        )
        parser.add_argument(
            '--address-sample',
            type=int,
            default=200,
            help='Koľko firiem použiť na meranie pravidla o adrese (default 200).',
        )
        parser.add_argument(
            '--skip-address',
            action='store_true',
            help='Vynechať pravidlo o adrese — je to najdrahšie pravidlo.',
        )

    # ------------------------------------------------------------------
    # Sections. Each prints its own heading so a partial run is readable.
    # ------------------------------------------------------------------

    def _section(self, title):
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING(title))
        self.stdout.write('-' * len(title))

    def _cov_scope(self):
        """What the rules have to work with at all.

        Printed first and on purpose: a firing rate read without it would look
        like a claim about the register rather than about the slice of it we
        hold.
        """
        self._section('1. Rozsah dát')
        total = Company.objects.count()
        rows = [
            ('firiem spolu', total),
            ('so závierkou', Company.objects.filter(
                financial_results__isnull=False).distinct().count()),
            ('s prepojenou osobou', Company.objects.filter(
                person_relations__isnull=False).distinct().count()),
            ('so dátumom zrušenia', Company.objects.filter(
                datum_zrusenia__isnull=False).count()),
            ('s dátumom výmazu z DPH', Company.objects.filter(
                vat_deleted_date__isnull=False).count()),
            ('s dátumom registrácie DPH', Company.objects.filter(
                datum_reg_dph__isnull=False).count()),
            ('s indexom spoľahlivosti', Company.objects.exclude(
                tax_reliability__isnull=True).exclude(
                tax_reliability='').count()),
            ('s kódom veľkosti iným než 00', Company.objects.exclude(
                velkost_organizacie__in=[None, '', '00']).count()),
            ('s kódom SK NACE', Company.objects.exclude(
                sk_NACE__in=[None, '']).count()),
            ('závierok spolu', CompanyFinancialResult.objects.count()),
            ('osôb spolu', Person.objects.count()),
            ('prepojení osoba–firma', PersonCompanyRelation.objects.count()),
        ]
        for label, value in rows:
            self.stdout.write(f'  {label:<32} {value:>10,}'.replace(',', ' '))

    def _person_counts(self):
        """How many companies a person holds a function in.

        The `≥ N` column is the measurement `SERIAL_DIRECTOR_MIN` needs: it says
        how many people each candidate threshold would put on a company page.
        """
        self._section('2. Koľko firiem má jedna osoba')
        counts = Counter(
            PersonCompanyRelation.objects
            .values('person_id')
            .annotate(n=Count('company', distinct=True))
            .values_list('n', flat=True)
        )
        people = sum(counts.values())
        self.stdout.write(f'  osôb s aspoň jednou firmou: {people:,}'.replace(',', ' '))
        for size in sorted(counts)[:12]:
            self.stdout.write(f'    {size:>3} firiem: {counts[size]:>8,}'.replace(',', ' '))

        self.stdout.write('')
        self.stdout.write('  kumulatívne (koľko osôb by prah zachytil):')
        for threshold in (2, 3, 4, 5, 8, 10, 15, 20, 30, 50):
            hit = sum(n for size, n in counts.items() if size >= threshold)
            self.stdout.write(
                f'    ≥ {threshold:>3} firiem: {hit:>8,}'.replace(',', ' ')
            )

    def _person_sectors(self):
        """Distinct NACE divisions per person, for `SECTOR_DIVISIONS_MIN`."""
        self._section('3. Oddiely SK NACE na osobu')
        pairs = (
            PersonCompanyRelation.objects
            .values_list('person_id', 'company__sk_NACE')
            .distinct()
        )
        per_person: dict[int, set] = {}
        for person_id, nace in pairs.iterator():
            division = person_risk.nace_division(nace)
            if division is None:
                continue
            per_person.setdefault(person_id, set()).add(division)

        histogram = Counter(len(v) for v in per_person.values())
        self.stdout.write(f'  osôb s aspoň jedným oddielom: {len(per_person):,}'.replace(',', ' '))
        self.stdout.write('  kumulatívne:')
        for threshold in (2, 3, 4, 5, 6, 8, 10):
            hit = sum(n for size, n in histogram.items() if size >= threshold)
            self.stdout.write(
                f'    ≥ {threshold:>3} oddielov: {hit:>8,}'.replace(',', ' ')
            )

    def _person_mortality(self):
        """The dissolved share, over people who have enough companies to have one."""
        self._section('4. Podiel zrušených firiem na osobu')
        rows = (
            PersonCompanyRelation.objects
            .values('person_id', 'company_id', 'company__datum_zrusenia')
            .distinct()
        )
        per_person: dict[int, list] = {}
        for row in rows.iterator():
            per_person.setdefault(row['person_id'], []).append(
                row['company__datum_zrusenia'] is not None
            )

        buckets = Counter()
        eligible = 0
        for dissolved_flags in per_person.values():
            total = len(dissolved_flags)
            if total < person_risk.MORTALITY_MIN_COMPANIES:
                continue
            eligible += 1
            share = sum(dissolved_flags) / total
            buckets[min(10, int(share * 10 + 0.5))] += 1

        self.stdout.write(
            f'  osôb s aspoň {person_risk.MORTALITY_MIN_COMPANIES} firmami: '
            f'{eligible:,}'.replace(',', ' ')
        )
        if not eligible:
            self.stdout.write('  (nikto — prah sa nedá zmerať na tejto vzorke)')
            return
        self.stdout.write('  podiel zrušených (decily):')
        for decile in range(11):
            hit = buckets.get(decile, 0)
            self.stdout.write(
                f'    {decile * 10:>3} %: {hit:>8,}'.replace(',', ' ')
            )

    def _sample_companies(self, size, with_financials=True):
        """A random sample of companies, drawn by `md5(ico)`.

        By hash rather than by `ORDER BY ?`, which the database answers by
        sorting every row; and by hash of the IČO rather than of the primary
        key, so the sample stays the same set of *companies* if the table is
        ever reloaded. Sized in Python rather than in SQL because the same
        command has to run on SQLite, where `md5()` does not exist.
        """
        keyed = (
            (hashlib.md5((ico or '').encode('utf-8')).hexdigest(), pk)
            for pk, ico in Company.objects.values_list('pk', 'ico').iterator()
        )
        chosen = [pk for _, pk in heapq.nsmallest(size, keyed)]

        queryset = Company.objects.filter(pk__in=chosen)
        if with_financials:
            queryset = queryset.prefetch_related('financial_results')
        return list(queryset)

    def _company_rules(self, sample_size):
        """Run the real engine over a random sample and report what it says.

        Not a re-implementation of the rules: `red_flags.company_red_flags` is
        called directly, and the numbers below are read out of the `evidence` it
        returns. A report that recomputed the thresholds could disagree with the
        product about the same company, which is the failure this repository
        keeps paying for.
        """
        self._section('5. Pravidlá na náhodnej vzorke firiem')
        started = time.monotonic()
        companies = self._sample_companies(sample_size)
        drawn = time.monotonic() - started
        self.stdout.write(
            f'  vzorka {len(companies):,} firiem (md5(ico)), vybraná za '
            f'{drawn:.1f} s'.replace(',', ' ')
        )
        if not companies:
            return

        states: dict[str, Counter] = {}
        quantities: dict[str, list] = {}
        # The address rule is excluded here and measured on its own, smaller
        # sample in section 6: at ~a hundred milliseconds each it would dominate
        # this pass and the table below would be a table about that one rule.
        rules = tuple(
            r for r in red_flags.COMPANY_RULES
            if r.__name__ != '_flag_crowded_address'
        )
        started = time.monotonic()
        for company in companies:
            rows = sorted(company.financial_results.all(), key=lambda r: r.year)
            latest = rows[-1] if rows else None
            for rule in rules:
                outcome = rule(company, rows, latest)
                states.setdefault(outcome['code'], Counter())[outcome['state']] += 1
                self._collect(quantities, outcome)
        elapsed = time.monotonic() - started

        self.stdout.write(
            f'  prezreté za {elapsed:.1f} s '
            f'({elapsed / len(companies) * 1000:.2f} ms/firma)'
        )
        self.stdout.write('')
        self.stdout.write(
            f'  {"kód":<26} {"zhoda":>7} {"bez":>7} {"nemerané":>9}'
        )
        for code, counter in states.items():
            self.stdout.write(
                f'  {code:<26} {counter["fired"]:>7} {counter["clear"]:>7} '
                f'{counter["unassessed"]:>9}'
            )

        self.stdout.write('')
        self.stdout.write('  distribúcie meraných veličín (z evidence pravidiel):')
        self._print_quantities(quantities)

    #: Which key in a rule's `evidence` carries the quantity its threshold cuts,
    #: and how to read it. A reporting concern, kept here rather than pushed
    #: into the rules, which should not know they are being plotted.
    QUANTITIES = {
        'trzby_bez_zamestnancov': ('revenue', 'eur'),
        'skok_trzby': ('ratio', 'x'),
        'zisk_nula_pri_trzboch': ('revenue', 'eur'),
        'majetok_bez_dhm': ('tangible_share', 'share'),
        'obrat_zasob': ('days', 'days'),
        'statutar_vo_vela_firmach': ('max_companies_per_person', 'count'),
        'sidlo_so_zhlukom': ('matching_companies', 'count'),
    }

    def _collect(self, quantities, outcome):
        spec = self.QUANTITIES.get(outcome['code'])
        if spec is None:
            return
        key, _kind = spec
        value = _decimal(outcome['evidence'].get(key))
        if value is not None:
            quantities.setdefault(outcome['code'], []).append(value)

    def _print_quantities(self, quantities):
        for code, spec in self.QUANTITIES.items():
            key, kind = spec
            values = quantities.get(code)
            if not values:
                self.stdout.write(f'    {code}: (nemerateľné na vzorke)')
                continue
            marks = ', '.join(
                f'p{int(f * 100)}={self._fmt(percentile(values, f), kind)}'
                for f in (0.05, 0.25, 0.5, 0.75, 0.95, 0.99)
            )
            self.stdout.write(
                f'    {code} [{key}, n={len(values)}]: {marks}'
            )

    @staticmethod
    def _fmt(value, kind):
        if value is None:
            return '-'
        if kind == 'eur':
            return f'{value:,.0f}'.replace(',', ' ')
        if kind == 'share':
            return f'{value * 100:.2f} %'.replace('.', ',')
        if kind == 'days':
            return f'{value:.1f} d'
        if kind == 'x':
            return f'{value:.2f}×'
        return f'{value:.0f}'

    def _address_cost(self, sample_size):
        """What the address rule costs, and what it would find.

        Measured rather than assumed, because it is the one rule whose price is
        not obviously bounded: it folds addresses in Python over the PSČ window,
        so it reads every company in a postal code to answer for one building.
        If that turns out to be too slow for a page view, the number here is
        what says so -- and the rule's own wording already reports the count it
        found rather than hiding the cost in a timeout.
        """
        self._section('6. Pravidlo o adrese — cena a distribúcia')
        companies = self._sample_companies(sample_size, with_financials=False)
        if not companies:
            self.stdout.write('  (žiadna vzorka)')
            return

        counts = []
        unassessed = 0
        started = time.monotonic()
        for company in companies:
            value = red_flags._companies_at_address(company)
            if value is None:
                unassessed += 1
            else:
                counts.append(value)
        elapsed = time.monotonic() - started

        self.stdout.write(
            f'  vzorka {len(companies)} firiem za {elapsed:.1f} s '
            f'({elapsed / len(companies) * 1000:.0f} ms/firma)'
        )
        self.stdout.write(f'  bez adresy (nedá sa porovnať): {unassessed}')
        if not counts:
            return
        self.stdout.write('  firiem na tej istej adrese (budova):')
        for fraction in (0.5, 0.75, 0.9, 0.95, 0.99):
            self.stdout.write(
                f'    p{int(fraction * 100)} = '
                f'{percentile(counts, fraction)}'
            )
        self.stdout.write(f'    max = {max(counts)}')
        for threshold in (5, 10, 20, 50, 100):
            hit = sum(1 for c in counts if c >= threshold)
            self.stdout.write(
                f'    ≥ {threshold:>3} firiem: {hit} z {len(counts)}'
            )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING(
            'Rizikové indikátory — meranie prahov (len čítanie)'
        ))
        self._cov_scope()
        self._person_counts()
        self._person_sectors()
        self._person_mortality()
        self._company_rules(options['sample'])
        if options['skip_address']:
            self.stdout.write('')
            self.stdout.write('  (pravidlo o adrese preskočené cez --skip-address)')
        else:
            self._address_cost(options['address_sample'])
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Hotovo — nič sa nezapísalo.'))
