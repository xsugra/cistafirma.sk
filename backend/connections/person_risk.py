"""Observations about a person's company footprint -- never a verdict about them.

See `docs/PLAN.md` §11.22, and §11.22.2 in particular. This is the module where
the difference between the two matters most, so it is worth stating plainly:

*"Konateľ v 14 firmách, z toho 5 zrušených" is an observation with dates.
"Biely kôň" is a claim about a person.* The product may utter the first and must
never utter the second, and not only for legal reasons: a straw man is a person
who is *used*, often without understanding what they signed, and the register
cannot tell that person apart from an entrepreneur who genuinely runs fourteen
companies. Both look identical in this data. Every label below therefore
describes what the register holds and lets the reader draw the conclusion.

Two consequences that shape the code:

* **Nothing here is summed or ranked.** There is no "person risk score", because
  one number beside a person's name is a verdict whatever the caption says.
* **The cluster is the unit, not the row.** A person in this database is more
  than one `Person` row -- the fingerprint is a row key, frozen, and the same
  human appears under several of them (§11.18). So these functions take the
  `member_ids` of a cluster, never a single id, or the counts would be of nodes
  rather than of a life.

One rule is deliberately absent. `is_active is None` means the function's
history was never read for that company, not that the function ended -- so
"unknown functions" is reported as *coverage*, in the counts that qualify every
other number, rather than as an indicator. Making it a flag would turn our own
gap in scraping into a fact about a person.
"""

from __future__ import annotations

from decimal import Decimal

from core.formatting import plural_oblique_sk, plural_sk

# --------------------------------------------------------------------------
# Thresholds. As in `companies.services.red_flags`, these are starting values
# that `risk_indicators_report` measures and corrects -- see the note there.
# --------------------------------------------------------------------------

#: Companies one person must hold a function in before a company's page says so.
SERIAL_DIRECTOR_MIN = 5

#: Distinct NACE divisions across a person's companies.
SECTOR_DIVISIONS_MIN = 4

#: Companies needed before a mortality *share* is a share of anything.
MORTALITY_MIN_COMPANIES = 4

#: Share of a person's companies the register has struck off.
MORTALITY_SHARE_MIN = Decimal('0.5')


def _rule(code: str, label: str, severity: str):
    """One rule's outcome, in the three states that must stay apart.

    Duplicated from `companies.services.red_flags` rather than imported: the two
    modules are owned by different apps, and `connections` importing a private
    helper out of a `companies` service is a coupling that would outlive the
    reason for it. The shape is pinned by tests on both sides.
    """

    def fired(detail: str, evidence: dict) -> dict:
        return {
            'code': code,
            'label': label,
            'severity': severity,
            'state': 'fired',
            'detail': detail,
            'reason': None,
            'evidence': evidence,
        }

    def clear(detail: str, evidence: dict | None = None) -> dict:
        return {
            'code': code,
            'label': label,
            'severity': severity,
            'state': 'clear',
            'detail': detail,
            'reason': None,
            'evidence': evidence or {},
        }

    def unassessed(reason: str) -> dict:
        return {
            'code': code,
            'label': label,
            'severity': severity,
            'state': 'unassessed',
            'detail': None,
            'reason': reason,
            'evidence': {},
        }

    return fired, clear, unassessed


def footprint(member_ids) -> dict:
    """What one person's cluster adds up to, in companies rather than rows.

    A person may hold several functions in the same company (konateľ and
    spoločník), which is one company and two rows, and may appear under several
    `Person` rows, which is one company and two more. Both are folded here,
    because a count of rows would be a count of our own bookkeeping.

    Returns `{'companies': [...], 'relations': n}` where each company carries
    the roles held, the function dates seen, and the register's own status.
    """
    from .models import PersonCompanyRelation

    ids = list(member_ids)
    if not ids:
        return {'companies': [], 'relations': 0}

    rows = (
        PersonCompanyRelation.objects
        .filter(person_id__in=ids)
        .values(
            'company_id',
            'company__ico',
            'company__nazov_UJ',
            'company__datum_zrusenia',
            'company__sk_NACE',
            'role',
            'is_active',
            'vznik_funkcie',
            'zanik_funkcie',
        )
    )

    # The role's own label ('Konateľ'), not the register's raw text. The two are
    # separate fields -- `role_display` holds whatever ORSR wrote, which is
    # unnormalised and often empty -- and a count line built from the raw text
    # would read `4× konatel` for one company and `4× Konateľ` for the next.
    labels = dict(PersonCompanyRelation.RoleType.choices)

    by_company: dict[int, dict] = {}
    relations = 0
    for row in rows:
        relations += 1
        entry = by_company.get(row['company_id'])
        if entry is None:
            entry = by_company[row['company_id']] = {
                'company_id': row['company_id'],
                'ico': row['company__ico'],
                'name': row['company__nazov_UJ'],
                'nace': (row['company__sk_NACE'] or '').strip(),
                'dissolved_on': row['company__datum_zrusenia'],
                'roles': set(),
                'active_states': set(),
                'started': [],
                'ended': [],
            }
        entry['roles'].add(labels.get(row['role'], row['role']))
        entry['active_states'].add(row['is_active'])
        if row['vznik_funkcie']:
            entry['started'].append(row['vznik_funkcie'])
        if row['zanik_funkcie']:
            entry['ended'].append(row['zanik_funkcie'])

    companies = []
    for entry in by_company.values():
        entry['roles'] = sorted(entry['roles'])
        entry['started'] = min(entry['started']) if entry['started'] else None
        entry['ended'] = max(entry['ended']) if entry['ended'] else None
        companies.append(entry)
    companies.sort(key=lambda c: (c['name'] or ''))
    return {'companies': companies, 'relations': relations}


def coverage(companies) -> dict:
    """What the rules below could look at, printed beside their outcomes.

    "Unknown functions" lives here and not among the flags, deliberately. When
    the ORSR history for a company was never read, `is_active` is `None` -- that
    is our gap, and reporting it as an indicator would dress a hole in our own
    scraping up as a fact about a person.
    """
    active_known = 0
    active_unknown = 0
    for company in companies:
        if company['active_states'] == {None}:
            active_unknown += 1
        else:
            active_known += 1
    return {
        'companies': len(companies),
        'companies_active_known': active_known,
        'companies_function_state_unknown': active_unknown,
        'companies_dissolved': sum(1 for c in companies if c['dissolved_on']),
    }


def nace_division(value: str) -> str | None:
    """The two-digit NACE division, or `None` when the code is too short.

    `sk_NACE` is a text code of varying length (`46190`, `46`, sometimes with a
    suffix). The division is the first two digits; anything shorter than that
    is a code we cannot place, and returning `None` keeps it out of a count
    rather than silently counting it as its own division.
    """
    code = (value or '').strip()
    if len(code) < 2 or not code[:2].isdigit():
        return None
    return code[:2]


def _flag_many_companies(companies) -> dict:
    """Functions held across many companies.

    The count, the roles, and how many of those companies are still running --
    because "14 companies, 5 struck off" and "14 companies, all active" are
    different observations and a reader needs both halves to weigh either.
    """
    fired, clear, unassessed = _rule(
        'serialny_statutar', 'Funkcia vo viacerých firmách', 'high'
    )
    total = len(companies)
    if total == 0:
        return unassessed('nemáme prepojenie na žiadnu firmu')
    if total < SERIAL_DIRECTOR_MIN:
        return clear(f'evidovaná v {plural_oblique_sk(total, "firme", "firmách")}')

    dissolved = sum(1 for c in companies if c['dissolved_on'])
    roles: dict[str, int] = {}
    for company in companies:
        for role in company['roles']:
            roles[role] = roles.get(role, 0) + 1
    roles_text = ', '.join(
        f'{count}× {role}' for role, count in
        sorted(roles.items(), key=lambda kv: (-kv[1], kv[0]))
    )
    detail = f'evidovaná v {plural_oblique_sk(total, "firme", "firmách")}'
    if roles_text:
        detail += f' ({roles_text})'
    if dissolved:
        detail += f', z toho {dissolved} zrušených'
    return fired(detail, {
        'companies': total,
        'companies_dissolved': dissolved,
        'roles': roles,
    })


def _flag_sector_spread(companies) -> dict:
    """Companies spread across unrelated NACE divisions.

    Read as an observation, never as a conclusion: a holding company, an
    accountant's client list and a straw man all look like this. The rule says
    how wide the spread is and leaves the reader the judgement.
    """
    fired, clear, unassessed = _rule(
        'odvetvova_rozptylenost', 'Firmy naprieč odvetviami', 'low'
    )
    if len(companies) < SERIAL_DIRECTOR_MIN:
        return unassessed(
            f'menej ako {SERIAL_DIRECTOR_MIN} firiem — rozptyl nemá z čoho vzniknúť'
        )

    divisions = {nace_division(c['nace']) for c in companies}
    divisions.discard(None)
    without_code = sum(1 for c in companies if nace_division(c['nace']) is None)
    if not divisions:
        return unassessed('ani jedna firma nemá kód SK NACE')

    evidence = {
        'divisions': sorted(divisions),
        'divisions_count': len(divisions),
        'companies_without_nace': without_code,
    }
    # The qualifying clause is not decoration: a company with no NACE code is
    # left out of the count, and a reader is entitled to know how many.
    caveat = (
        f' ({plural_sk(without_code, "firma", "firmy", "firiem")} bez kódu NACE)'
        if without_code else ''
    )
    divisions_text = plural_oblique_sk(len(divisions), 'oddieli', 'oddieloch')
    detail = f'firmy v {divisions_text} SK NACE{caveat}'
    if len(divisions) >= SECTOR_DIVISIONS_MIN:
        return fired(detail, evidence)
    return clear(detail, evidence)


def _flag_company_mortality(companies) -> dict:
    """How many of a person's companies the register has struck off.

    Only companies with a recorded dissolution date count as dissolved. A
    company with no such date is *not* counted as surviving -- it is counted as
    nothing, because absence of the date can mean either that the company runs
    or that we never read that field for it. A share computed over a sample of
    two would be a number pretending to be a rate, so below
    `MORTALITY_MIN_COMPANIES` this rule reports that it has not looked.
    """
    fired, clear, unassessed = _rule(
        'umrtnost_firiem', 'Zrušené firmy', 'medium'
    )
    total = len(companies)
    if total < MORTALITY_MIN_COMPANIES:
        return unassessed(
            f'menej ako {MORTALITY_MIN_COMPANIES} firmy — podiel by nebol podiel'
        )

    dissolved = sum(1 for c in companies if c['dissolved_on'])
    share = Decimal(dissolved) / Decimal(total)
    evidence = {
        'companies': total,
        'companies_dissolved': dissolved,
        'share': str(share.quantize(Decimal('0.001'))),
    }
    detail = f'v registri je zrušených {dissolved} z {total} firiem'
    if share >= MORTALITY_SHARE_MIN:
        return fired(detail, evidence)
    return clear(detail, evidence)


#: Every person rule, in the order a reader sees them.
PERSON_RULES = (
    _flag_many_companies,
    _flag_sector_spread,
    _flag_company_mortality,
)


def person_red_flags(member_ids) -> dict:
    """Every person rule's outcome, with the coverage that qualifies it.

    `member_ids` is the cluster's `Person` rows -- see the module docstring for
    why it is the cluster and not one row.
    """
    data = footprint(member_ids)
    companies = data['companies']
    flags = [rule(companies) for rule in PERSON_RULES]
    return {
        'flags': flags,
        'counts': {
            'fired': sum(1 for f in flags if f['state'] == 'fired'),
            'clear': sum(1 for f in flags if f['state'] == 'clear'),
            'unassessed': sum(1 for f in flags if f['state'] == 'unassessed'),
        },
        'coverage': {
            **coverage(companies),
            'relations': data['relations'],
        },
    }
