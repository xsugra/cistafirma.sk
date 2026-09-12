"""Companies that sit next to a given one.

Four company-page sections ask the same question with a different boundary --
"who else is in this region", "who else is in this industry", "who is largest",
"who is most like this firm". They share one query shape here rather than four
views each spelling out its own ordering, because the interesting part is not
the filter but the *population*: what a reader is being shown the top of.

That population is the honest difficulty. Only companies with a filed RUZ
statement have any revenue at all -- under two thousand of 445 000 in the local
database -- so a "largest companies" list is a ranking of a fraction of a
percent of the register. Returning rows without saying so would read as "these
are the biggest firms in the country" when it means "these are the biggest
firms that have filed". Every scope therefore reports both the count it ranked
(`total_ranked`) and the count it ranked *within* (`total_in_scope`), and the
frontend prints the pair.

Neither count is written down anywhere as a constant, deliberately: the
financials sync is still filling the table, so the ranked population grew by
about a hundred in a single afternoon. A frozen number in a comment or a
section note would go stale and start contradicting the figure the section
prints from the same query.

Two consequences of reading the figure rather than the register:

* Every scope is ordered by revenue and therefore filters to rows that *have*
  one. A company with no filed revenue is not ranked last, it is not ranked --
  it is inside `total_in_scope` and outside `total_ranked`, which is exactly
  what the pair of counts is for.
* Each company is shown at its **own** most recent statement, and those years
  differ. The row carries its year so a reader can see that the largest firm in
  a region is largest on a 2016 filing. Ranking only within one year would be
  tidier and would shrink an already tiny population by an order of magnitude,
  so the year is shown instead.

This is deliberately *not* `adminapi.services.company_filters`. That service
carries lead scores, sync state, confidence floors and a JSON filter builder --
none of which belong on an anonymous endpoint, and all of which would have to
be kept out by a deny-list that a later edit could quietly widen. The
vocabulary here is only what these four sections need.

`reason` and `ranked_by` are codes, not sentences: the frontend owns every
Slovak string it renders, exactly as it does for `financialsState`.
"""

from __future__ import annotations

import logging
import math
from decimal import Decimal

from django.db.models import FloatField, QuerySet, Subquery
from django.db.models.functions import Abs, Cast, Ln

from ..models import Company, CompanyFinancialResult
from .nace import _extract_division, get_nace_division_name

logger = logging.getLogger(__name__)

#: How many rows a section shows. A company page is a summary, not a
#: directory; the count beside it is what tells the reader there are more.
PEER_LIMIT = 10

#: The latest statement for a company, newest year first. Spelled once and
#: used by every scope below -- and matching `adminapi`'s `_listing_queryset`,
#: so the admin panel and a company page cannot disagree about which year is a
#: firm's "latest".
_LATEST_ORDER = ('-year', '-updated_at', '-id')

SCOPE_KRAJ = 'kraj'
SCOPE_ODVETVIE = 'odvetvie'
SCOPE_TRZBY = 'trzby'
SCOPE_PODOBNE = 'podobne'

PEER_SCOPES = (SCOPE_PODOBNE, SCOPE_KRAJ, SCOPE_ODVETVIE, SCOPE_TRZBY)

#: NUTS 3 code -> Slovak region name. Not in the RUZ payload: the register
#: sends `kraj: "1"` and the model stores the derived `SK010`-style code, so
#: without this a section would head itself "Firmy v kraji SK010". The eight
#: codes are the complete set the data uses -- `SKZZZ` (5 rows) and '' (390)
#: are not regions and get no name, which is why the lookup falls back to the
#: raw code rather than guessing.
KRAJ_NAMES = {
    'SK010': 'Bratislavský kraj',
    'SK021': 'Trnavský kraj',
    'SK022': 'Trenčiansky kraj',
    'SK023': 'Nitriansky kraj',
    'SK031': 'Žilinský kraj',
    'SK032': 'Banskobystrický kraj',
    'SK041': 'Prešovský kraj',
    'SK042': 'Košický kraj',
}


def _latest_rows() -> QuerySet[CompanyFinancialResult]:
    """One row per company: its most recent statement.

    Postgres `DISTINCT ON`, which is why the ordering has to start with
    `company_id`. The result is a subquery of primary keys rather than a join,
    because a join to this would multiply each company by its history and need
    a `DISTINCT` on the outer query anyway.

    Driven from the financials table and not from `Company`, because the
    population that matters is small (one row per company that has ever filed)
    while `Company` is 445 000 rows wide -- an `Exists` over all of them costs
    a subquery probe per company for an answer this gets by sorting 16 000.
    """
    return (
        CompanyFinancialResult.objects
        .order_by('company_id', *_LATEST_ORDER)
        .distinct('company_id')
        .values('pk')
    )


def _ranked_queryset() -> QuerySet[CompanyFinancialResult]:
    """Every live company's latest statement, ready to be ranked.

    `revenue__isnull=False` is not an optimisation, it is the definition of the
    ranking: a row with no revenue has no place in an order by revenue, and
    letting it sit at the bottom would put it inside a count that claims to be
    "companies we ranked".
    """
    return (
        CompanyFinancialResult.objects
        .filter(pk__in=Subquery(_latest_rows()))
        .filter(company__datum_zrusenia__isnull=True)
        .filter(revenue__isnull=False)
        .select_related('company')
    )


def _row(result: CompanyFinancialResult) -> dict:
    """One row of a section, in the shape the frontend table renders."""
    company = result.company
    return {
        'ico': company.ico,
        'name': company.nazov_UJ,
        'city': company.mesto,
        'nace_code': company.sk_NACE,
        'nace_name': get_nace_division_name(company.sk_NACE),
        'year': result.year,
        # Strings, not Decimals. DRF's `JSONRenderer` would turn a bare
        # `Decimal` into a `float` -- a binary fraction for a euro amount, and
        # a different wire type from every other endpoint in this project,
        # where `COERCE_DECIMAL_TO_STRING` makes the same figure a string. The
        # frontend already parses these with `Number()`. `None` stays null: a
        # statement that did not carry the line is not a zero.
        'revenue': None if result.revenue is None else str(result.revenue),
        'profit': None if result.profit is None else str(result.profit),
    }


def _division_prefix(nace_code: str | None) -> str | None:
    """The 2-digit division of a SK NACE code, as a string to prefix-match.

    `_extract_division` already owns the parsing (codes arrive as `62.01.0`,
    `62010`, or with stray spacing), so this reads it rather than re-slicing
    the string here and disagreeing with the sector benchmarks.
    """
    division = _extract_division(nace_code)
    return f'{division:02d}' if division is not None else None


def _division_label(nace_code: str | None) -> str | None:
    """The division name, or `None` when the taxonomy has none for it."""
    return get_nace_division_name(nace_code)


def _active() -> QuerySet[Company]:
    """Every company that has not been struck off."""
    return Company.objects.filter(datum_zrusenia__isnull=True)


def _empty(scope: str, reason: str) -> dict:
    """The payload for a scope the subject cannot be ranked in.

    Same key set as a filled payload, so the frontend has one shape to read and
    cannot mistake a missing key for a missing value.
    """
    return {
        'scope': scope,
        'subject': None,
        'subject_label': None,
        'reason': reason,
        'ranked_by': 'revenue',
        'total_ranked': 0,
        'total_in_scope': 0,
        'results': [],
    }


def _payload(scope, subject, subject_label, ranked, in_scope, ranked_by='revenue'):
    """Assemble a filled payload, taking the head of `ranked` as the rows.

    The slice happens here rather than at each call site so `total_ranked` is
    always the count of the queryset the rows came from -- a section cannot
    report the size of one ranking and show the top of another.
    """
    return {
        'scope': scope,
        'subject': subject,
        'subject_label': subject_label,
        'reason': None,
        'ranked_by': ranked_by,
        'total_ranked': ranked.count(),
        'total_in_scope': in_scope.count(),
        'results': [_row(r) for r in ranked[:PEER_LIMIT]],
    }


def peers_for(company: Company, scope: str) -> dict:
    """The ranked neighbours of `company` in one `scope`.

    `podobne` is the only scope that reads the subject's own figures, and it
    degrades rather than fails: with no revenue of its own there is no size to
    be similar to, so it shows the same industry ordered by size and says so
    through `ranked_by`.
    """
    if scope not in PEER_SCOPES:
        raise ValueError(f'unknown scope: {scope!r}')

    active = _active()

    if scope == SCOPE_TRZBY:
        # The population is every company that ever filed, so counting it is
        # the count of rows in the ranking -- not a scan of all 445 000.
        return _payload(
            scope,
            # No narrowing value, so no `subject` -- the frontend falls back to
            # the label, and an empty string would make it print a blank.
            subject=None,
            subject_label='aktívne firmy v registri',
            # The subject is left out of its own peer list in all four scopes.
            # A section headed "firms near this one" that can contain the firm
            # is a different sentence, and the four would then not share one.
            ranked=_ranked_queryset().exclude(
                company_id=company.pk
            ).order_by('-revenue', 'company__nazov_UJ'),
            in_scope=active,
        )

    if scope == SCOPE_KRAJ:
        if not company.kraj:
            return _empty(scope, 'no_region')
        # Exact, not `iexact`: the value comes from the same column as the rows
        # being matched, so it matches itself whatever case the register used --
        # and `iexact` would cost the `company_kraj_active_idx` index for a
        # case-folding the data does not need (all 445 000 rows are `SK0xx`).
        return _payload(
            scope,
            subject=company.kraj,
            subject_label=KRAJ_NAMES.get(company.kraj),
            ranked=_ranked_queryset().filter(company__kraj=company.kraj).exclude(
                company_id=company.pk
            ).order_by('-revenue', 'company__nazov_UJ'),
            in_scope=active.filter(kraj=company.kraj),
        )

    prefix = _division_prefix(company.sk_NACE)
    if not prefix:
        return _empty(scope, 'no_nace')

    # `istartswith` rather than `startswith`: the case-folded prefix is what
    # `company_nace_ci_like_idx` indexes (a `text_pattern_ops` btree), so this
    # is the spelling that reads the index instead of scanning 445 000 rows.
    in_division = _ranked_queryset().filter(
        company__sk_NACE__istartswith=prefix
    ).exclude(company_id=company.pk)
    division_label = f'{prefix} — {_division_label(company.sk_NACE) or "nezaradené"}'

    if scope == SCOPE_ODVETVIE:
        return _payload(
            scope,
            subject=prefix,
            subject_label=division_label,
            ranked=in_division.order_by('-revenue', 'company__nazov_UJ'),
            in_scope=active.filter(sk_NACE__istartswith=prefix),
        )

    # SCOPE_PODOBNE
    own = (
        CompanyFinancialResult.objects
        .filter(company_id=company.pk)
        .order_by(*_LATEST_ORDER)
        .values_list('revenue', flat=True)
        .first()
    )

    # `revenue > 0` and not merely `is not null`: the metric below is a
    # logarithm, and Postgres raises on `ln(0)` rather than returning null --
    # one zero-revenue company in the division would take the whole section
    # down with a 500 instead of dropping one row.
    if own is None or own <= 0:
        # No size of its own, so there is no size to be close to. The section
        # shows the industry by size and `ranked_by` says which order it used.
        return _payload(
            scope,
            subject=prefix,
            subject_label=division_label,
            ranked=in_division.order_by('-revenue', 'company__nazov_UJ'),
            in_scope=active.filter(sk_NACE__istartswith=prefix),
        )

    # Closeness in *ratio*, not in euro: 10 000 EUR away from a firm turning
    # over 50 000 is a different company, and from one turning over 50 000 000
    # it is the same company. `Abs(Ln(a) - Ln(b))` is the log of the ratio
    # without a division by the subject's own revenue, so nothing here depends
    # on the subject being the denominator.
    #
    # `Cast` is not decoration: `Ln` inherits its output type from its source,
    # so `Ln` of the `DecimalField` is a `Decimal` and subtracting the Python
    # float below is a Decimal-minus-Float expression Django refuses to type
    # ("Cannot infer type of '-' expression involving these types"). Casting to
    # `double precision` first makes both sides floats, which is also the type
    # Postgres' `ln` is cheapest on.
    return _payload(
        scope,
        subject=prefix,
        subject_label=division_label,
        ranked=in_division.filter(revenue__gt=0).annotate(
            distance=Abs(Ln(Cast('revenue', FloatField())) - math.log(float(own)))
        ).order_by('distance', 'company__nazov_UJ'),
        in_scope=active.filter(sk_NACE__istartswith=prefix),
        ranked_by='similarity',
    )
