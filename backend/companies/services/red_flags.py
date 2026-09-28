"""Risk *indicators* for a company -- facts, not a verdict.

See `docs/PLAN.md` §11.22 for the decision record. The short version:

A VAT carousel is a chain -- missing trader, buffer, broker -- and our data hold
*companies*, not the edges between them. Invoices, VAT control statements and
the physical movement of goods are not public, so no amount of work over public
registers can prove a carousel or identify a straw man. What public data *can*
do is show that a company's profile matches one of the shapes those schemes
leave behind. That is what this module computes, and the difference is not
pedantry: it is the difference between a product that says "this looks like
this pattern, here are the numbers, check it" and one that names a person a
criminal.

Three consequences run through every rule below:

* **None of this is summed.** There is no "fraud score". A total would be the
  one number a reader takes away, and it would be an accusation. The flags are
  listed and counted, never added.
* **A rule that could not run says so.** Every rule returns one of three
  states: `fired`, `clear`, or `unassessed` with the reason. A rule that reads
  "clear" and a rule that never ran are different facts -- the same distinction
  `risk_score.compute_risk_score` draws in its `parts`, and for the same reason.
* **Coverage is printed, not implied.** Most of these rules need a filed
  statement, and ~3,5 % of the register has one. A section that showed flags
  without that number would read as if every company had been examined.

Deliberately *not* here: anything that would move `riskScore`. That ladder is
documented as an attention indicator with one home, and folding a dozen new
penalties into it would change every score in the product at once. The flags
sit beside the score, not inside it.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from core.formatting import plural_oblique_sk, plural_sk

from ..address import normalize_obec, parse_street, psc_key
from .velkost import SIZE_UNKNOWN, normalise_size_code

# --------------------------------------------------------------------------
# Thresholds.
#
# Every one of these is a starting value, not a measured one, and the module
# says which is which rather than pretending otherwise: `risk_indicators_report`
# prints the distribution each threshold cuts and how many companies it would
# flag, and the constants are corrected from that output. A threshold invented
# from intuition is a gate that binds for reasons nobody can reconstruct later
# -- the failure mode `docs/PLAN.md` §8.6 records for the 500-filing cutoff.
#
# The shape of the value (a share, a multiple, a count) comes from the
# methodology the task was specified with; the number is the part that must be
# measured.
# --------------------------------------------------------------------------

#: "Tržby v miliónoch eur" -- the smallest revenue the methodology calls large.
REVENUE_LARGE = Decimal('1000000')

#: Size bands that mean 0 or 1 employee (`velkost.SIZE_BANDS`). The methodology
#: says "0 až 1 zamestnancovi"; band `03` (2 employees) is left out on purpose,
#: because widening a specified rule is a decision to take openly rather than
#: to bury in a frozenset.
NO_EMPLOYEE_BANDS = frozenset({'01', '02'})

#: A year-on-year revenue jump of this multiple, from at least `REVENUE_LARGE`.
REVENUE_JUMP_RATIO = Decimal('10')
REVENUE_JUMP_FROM_ZERO = Decimal('1000000')

#: Profit within this share of revenue counts as "almost nothing".
NEAR_ZERO_PROFIT_SHARE = Decimal('0.01')

#: A balance sheet this large is worth asking what it is made of.
BALANCE_MIN_ASSETS = Decimal('1000000')

#: Long-term tangible assets below this share of total assets, while
#: receivables and inventory are at least `WORKING_CAPITAL_SHARE`.
TANGIBLE_ASSET_SHARE_MAX = Decimal('0.01')
WORKING_CAPITAL_SHARE_MIN = Decimal('0.50')

#: Inventory that turns over faster than this, when inventory is material.
INVENTORY_TURNOVER_DAYS_MAX = Decimal('5')

#: Inventory is material at this share of total assets.
INVENTORY_MATERIAL_SHARE = Decimal('0.10')

#: Companies sharing one *building* before the address is called crowded.
#: `address_key` includes the house number, so this is a door and not a street.
ADDRESS_CLUSTER_MIN = 20

#: How many companies one person must hold a function in before the company's
#: page says so. `SERIAL_DIRECTOR_MIN` is the one threshold the methodology
#: states as a count ("desiatky či stovky") rather than as a shape, so it is
#: the one most in need of the measured distribution.
SERIAL_DIRECTOR_MIN = 5

#: Index of tax reliability whose value marks an unreliable VAT payer.
UNRELIABLE_RELIABILITY = 'nespoľahlivý'


def _amount(value) -> Decimal | None:
    """A stored figure, or `None` when the statement did not carry it.

    Never `0`: "the statement has no such line" and "the line reads zero" are
    different facts, and every rule below tests for the presence of its inputs
    rather than for a non-zero value.
    """
    if value is None:
        return None
    return Decimal(value)


def _eur(amount: Decimal | int | float) -> str:
    """An amount as a Slovak reader writes it: space groups, comma decimals.

    The sign is lifted out before the grouping, because `f'{-1234:,}'` is
    `-1,234` -- the minus sits inside the digit run and the cents come out as
    `-56`, printing `-1 234,-56 €`. A loss can be large in this data (a negative
    profit after tax is ordinary), so the negative path is the one that has to
    be right rather than the one that can be forgotten.

    Rounded to cents *before* the split, so a value that rounds up to a whole
    euro does not print a stray `,100`.
    """
    value = abs(Decimal(amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    sign = '-' if Decimal(amount) < 0 else ''
    whole = int(value)
    cents = int((value - whole) * 100)
    text = f'{whole:,}'.replace(',', ' ')
    if cents:
        text += f',{cents:02d}'
    return f'{sign}{text} €'


def _share(part: Decimal, whole: Decimal) -> Decimal | None:
    """`part / whole`, or `None` when the denominator is not a usable number."""
    if whole is None or whole == 0:
        return None
    return part / whole


def _num(value: Decimal, places: int = 1) -> str:
    """A decimal number as a Slovak reader writes it: `1 825,0`.

    Two things are being fixed at once, and both were visible in the first
    version's output. `quantize` keeps the point, so a sentence built from it
    printed `1825.0 dňa` and `10.0×` -- arithmetic notation inside Slovak prose,
    in the text a reader is looking at. And the default rounding is half-to-even,
    so `10.25` printed as `10,2` where the browser prints `10,3`; half-up is the
    house rule (`risk_score._round_half_up` exists for the same reason) and the
    server has to agree with the client about the same number.
    """
    exponent = Decimal(1).scaleb(-places)
    quantized = Decimal(value).quantize(exponent, rounding=ROUND_HALF_UP)
    whole, _, fraction = f'{quantized:,.{places}f}'.partition('.')
    grouped = whole.replace(',', ' ')
    return f'{grouped},{fraction}' if fraction else grouped


def _percent(share: Decimal) -> str:
    """A share as a percentage, formatted by the one function that does this."""
    return f'{_num(share * 100)} %'


def _band_label(code: str | None) -> str | None:
    """The band's words, or `None` when the register did not record one."""
    from .velkost import size_band_label

    return size_band_label(code)


def _rule(code: str, label: str, severity: str):
    """One rule's outcome, in the three states that must stay apart."""

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


# --------------------------------------------------------------------------
# The rules.
#
# Each takes the rows it needs and returns exactly one dict. They are separate
# functions rather than one long ladder so that a rule can be read, tested and
# corrected on its own -- and so that "which rule fired" is answerable from the
# code rather than from a number.
# --------------------------------------------------------------------------


def _flag_revenue_without_employees(company, rows, latest) -> dict:
    """Millions in revenue against a register that records 0-1 employees.

    The register's size band, not a headcount: it is a ŠÚ SR category, and
    63,3 % of active companies carry `00`, which means the register recorded no
    size at all. When it is `00` this rule has not looked -- which is the same
    as never having run, and is reported as such rather than as "no employees".
    """
    fired, clear, unassessed = _rule(
        'trzby_bez_zamestnancov', 'Tržby bez zamestnancov', 'medium'
    )
    code = normalise_size_code(company.velkost_organizacie)
    if code is None or code == SIZE_UNKNOWN:
        return unassessed('register pri firme neuviedol veľkosť')
    band = _band_label(code)
    if band is None:
        return unassessed(f'kód veľkosti {code!r} nie je v číselníku')
    if latest is None or latest.revenue is None:
        return unassessed('nemáme závierku s tržbami')
    revenue = _amount(latest.revenue)
    evidence = {'revenue': str(revenue), 'size_band': code, 'year': latest.year}
    if code not in NO_EMPLOYEE_BANDS:
        return clear(f'tržby {_eur(revenue)} pri {band}', evidence)
    if revenue < REVENUE_LARGE:
        return clear(
            f'tržby {_eur(revenue)} pri {band} — pod hranicou veľkých tržieb',
            evidence,
        )
    return fired(
        f'tržby {_eur(revenue)} pri {band} ({latest.year})', evidence
    )


def _flag_revenue_jump(company, rows, latest) -> dict:
    """A revenue jump that skips the years in between.

    Two cases, and they are the same fact: a company that had 5 million in its
    second year, and one that had zero and then five. The second cannot be
    expressed as a ratio, so it is a branch rather than a division by zero.
    """
    fired, clear, unassessed = _rule('skok_trzby', 'Skokový rast tržieb', 'medium')
    with_revenue = [r for r in rows if r.revenue is not None]
    if len(with_revenue) < 2:
        return unassessed('menej ako dva roky s tržbami')

    previous, latest = with_revenue[-2], with_revenue[-1]
    before, now = _amount(previous.revenue), _amount(latest.revenue)
    evidence = {
        'from_year': previous.year,
        'to_year': latest.year,
        'from': str(before),
        'to': str(now),
    }

    if before == 0:
        if now >= REVENUE_JUMP_FROM_ZERO:
            return fired(
                f'tržby z 0 € na {_eur(now)} medzi {previous.year} a {latest.year}',
                evidence,
            )
        return clear(f'tržby z 0 € na {_eur(now)} — pod hranicou', evidence)

    if before < 0:
        return unassessed('predchádzajúci rok má záporné tržby, pomer nedáva zmysel')

    ratio = now / before
    if ratio >= REVENUE_JUMP_RATIO and now >= REVENUE_LARGE:
        return fired(
            f'tržby vzrástli {_num(ratio)}× '
            f'({_eur(before)} → {_eur(now)}) medzi {previous.year} a {latest.year}',
            {**evidence, 'ratio': str(ratio.quantize(Decimal('0.01')))},
        )
    return clear(
        f'tržby {_eur(before)} → {_eur(now)} medzi {previous.year} a {latest.year}',
        {**evidence, 'ratio': str(ratio.quantize(Decimal('0.01')))},
    )


def _flag_turnover_without_profit(company, rows, latest) -> dict:
    """Large revenue, almost no profit, and the tax that goes with it.

    The methodology's shape: 10 million in revenue, 2 000 in profit. Reported
    with the tax figure beside it, because "and a minimal income tax" is part
    of the same observation and separating them into two rules would let a
    reader see one without the other.
    """
    fired, clear, unassessed = _rule(
        'zisk_nula_pri_trzboch', 'Veľké tržby, takmer nulový zisk', 'medium'
    )
    if latest is None or latest.revenue is None:
        return unassessed('nemáme závierku s tržbami')
    profit = _amount(latest.profit_after_tax)
    if profit is None:
        return unassessed('závierka neuvádza zisk po zdanení')
    revenue = _amount(latest.revenue)
    threshold = revenue * NEAR_ZERO_PROFIT_SHARE
    tax = _amount(latest.income_tax)
    evidence = {
        'revenue': str(revenue),
        'profit_after_tax': str(profit),
        'income_tax': None if tax is None else str(tax),
        'year': latest.year,
    }
    if revenue < REVENUE_LARGE:
        return clear(f'tržby {_eur(revenue)} — pod hranicou veľkých tržieb', evidence)

    tax_clause = 'daň z príjmu neuvedená' if tax is None else f'daň z príjmu {_eur(tax)}'
    if abs(profit) <= threshold:
        return fired(
            f'tržby {_eur(revenue)}, zisk po zdanení {_eur(profit)}, {tax_clause} '
            f'({latest.year})',
            evidence,
        )
    return clear(f'tržby {_eur(revenue)}, zisk po zdanení {_eur(profit)}', evidence)


def _flag_balance_without_fixed_assets(company, rows, latest) -> dict:
    """A large balance sheet made of receivables and inventory, not equipment.

    The shape is a trading shell: nothing that could produce anything, and a
    great deal that could be invoiced.
    """
    fired, clear, unassessed = _rule(
        'majetok_bez_dhm', 'Majetok bez dlhodobého hmotného majetku', 'medium'
    )
    if latest is None:
        return unassessed('nemáme závierku')
    total = _amount(latest.assets_total)
    tangible = _amount(latest.assets_tangible)
    inventory = _amount(latest.assets_inventory)
    receivables = _amount(latest.assets_receivables_short)
    if total is None or tangible is None:
        return unassessed('závierka neuvádza aktíva alebo dlhodobý hmotný majetok')
    if inventory is None or receivables is None:
        return unassessed('závierka neuvádza zásoby alebo krátkodobé pohľadávky')
    if total < BALANCE_MIN_ASSETS:
        return clear(
            f'aktíva {_eur(total)} — pod hranicou veľkej súvahy',
            {'assets_total': str(total), 'year': latest.year},
        )

    working = inventory + receivables
    tangible_share = _share(tangible, total)
    working_share = _share(working, total)
    if tangible_share is None or working_share is None:
        return unassessed('aktíva sú nulové, podiel sa nedá počítať')

    evidence = {
        'assets_total': str(total),
        'assets_tangible': str(tangible),
        'working_capital': str(working),
        'year': latest.year,
    }
    if tangible_share <= TANGIBLE_ASSET_SHARE_MAX and working_share >= WORKING_CAPITAL_SHARE_MIN:
        return fired(
            f'aktíva {_eur(total)}, z toho dlhodobý hmotný majetok '
            f'{_percent(tangible_share)} a zásoby s pohľadávkami {_percent(working_share)} '
            f'({latest.year})',
            evidence,
        )
    return clear(
        f'dlhodobý hmotný majetok {_percent(tangible_share)} z aktív '
        f'{_eur(total)} ({latest.year})',
        {
            **evidence,
            'tangible_share': str(tangible_share.quantize(Decimal('0.0001'))),
            'working_share': str(working_share.quantize(Decimal('0.0001'))),
        },
    )


def _flag_inventory_turnover(company, rows, latest) -> dict:
    """Inventory that turns over in days, in a company whose inventory is material.

    Material is the guard that keeps this from firing on a service company with
    a token stock figure, where a meaningless ratio would be read as a finding.
    """
    fired, clear, unassessed = _rule(
        'obrat_zasob', 'Neprimerane rýchly obrat zásob', 'medium'
    )
    if latest is None or latest.revenue is None:
        return unassessed('nemáme závierku s tržbami')
    inventory = _amount(latest.assets_inventory)
    total = _amount(latest.assets_total)
    revenue = _amount(latest.revenue)
    if inventory is None or total is None:
        return unassessed('závierka neuvádza zásoby alebo aktíva')
    if inventory <= 0 or revenue <= 0:
        return clear(
            'zásoby alebo tržby sú nulové, obrat sa nedá počítať',
            {'inventory': str(inventory), 'revenue': str(revenue), 'year': latest.year},
        )

    material_share = _share(inventory, total)
    if material_share is None or material_share < INVENTORY_MATERIAL_SHARE:
        return clear(
            f'zásoby {_eur(inventory)} sú {_percent(material_share or Decimal(0))} '
            'aktív — nemateriálne',
            {
                'inventory': str(inventory),
                'revenue': str(revenue),
                'share': None if material_share is None else str(
                    material_share.quantize(Decimal('0.0001'))
                ),
                'year': latest.year,
            },
        )

    days = inventory / revenue * Decimal(365)
    evidence = {
        'inventory': str(inventory),
        'revenue': str(revenue),
        'days': str(days.quantize(Decimal('0.1'))),
        'year': latest.year,
    }
    if days < INVENTORY_TURNOVER_DAYS_MAX:
        return fired(
            f'zásoby {_eur(inventory)} pri tržbách {_eur(revenue)} sa obrátia za '
            f'{_num(days)} dňa ({latest.year})',
            evidence,
        )
    return clear(
        f'zásoby sa obrátia za {_num(days)} dňa ({latest.year})',
        {**evidence, 'share': str(material_share.quantize(Decimal('0.0001')))},
    )


def _flag_unreliable_tax_index(company, rows, latest) -> dict:
    """The Financial Directorate's own reliability index, quoted.

    Not a rule we invented: `tax_reliability` is the register's word, and this
    only reads it. 218 143 rows carry no index, which is the register having
    rated nobody -- not a rating of "reliable".
    """
    fired, clear, unassessed = _rule(
        'dph_nespolahlivy', 'Index daňovej spoľahlivosti', 'high'
    )
    index = (company.tax_reliability or '').strip()
    if not index:
        return unassessed('Finančná správa index neuviedla')
    if index.lower() == UNRELIABLE_RELIABILITY:
        return fired(
            f'index daňovej spoľahlivosti: {index}',
            {'tax_reliability': index},
        )
    return clear(f'index daňovej spoľahlivosti: {index}', {'tax_reliability': index})


def _flag_vat_deregistered(company, rows, latest) -> dict:
    """Struck off the VAT register, and not put back on since.

    The order of the two dates is the whole rule, and it is the same rule
    `frontend/utils/vatStatus.ts` applies to draw the VAT chip -- a company
    that was struck off and later re-registered is a current payer, and the
    stored `vat_payer` flag is often the older of the two facts. Measured
    2026-09-17: 384 of the 32 127 rows carrying a removal date were
    re-registered after it.

    This module keeps its own copy rather than importing across the language
    boundary, so the two are pinned by tests on both sides; a divergence would
    mean the chip and the flag disagreeing about the same company.
    """
    fired, clear, unassessed = _rule(
        'dph_vymazany', 'Vymazaný z registra DPH', 'high'
    )
    deleted = company.vat_deleted_date
    if deleted is None:
        return unassessed('register neuvádza dátum výmazu z registra DPH')
    registered = company.datum_reg_dph
    if registered is not None and registered > deleted:
        return clear(
            f'vymazaný {deleted}, ale znovu zaregistrovaný {registered}',
            {
                'vat_deleted_date': str(deleted),
                'datum_reg_dph': str(registered),
                're-registered': True,
            },
        )
    reason = (company.vat_deleted_reason or '').strip()
    detail = f'vymazaný z registra DPH k {deleted}'
    if reason:
        detail += f' ({reason})'
    return fired(detail, {
        'vat_deleted_date': str(deleted),
        'vat_deleted_reason': reason or None,
        'datum_reg_dph': None if registered is None else str(registered),
    })


def _flag_debt_and_dissolution(company, rows, latest) -> dict:
    """Recorded arrears and a company the register has struck off.

    Both halves are needed. Arrears alone are ordinary; a dissolution alone is
    ordinary. The pair is what the methodology describes as the end state of a
    company left to accumulate debt and then abandoned.
    """
    fired, clear, unassessed = _rule(
        'nedoplatky_a_zanik', 'Nedoplatky a zrušená firma', 'high'
    )
    from .risk_score import total_debt

    debt = total_debt(company)
    dissolved = company.datum_zrusenia
    if dissolved is None:
        return clear(
            f'evidované nedoplatky {_eur(debt)}, firma nie je zrušená',
            {'total_debt': str(debt), 'datum_zrusenia': None},
        )
    if debt <= 0:
        return clear(
            f'firma zrušená {dissolved}, bez evidovaných nedoplatkov',
            {'total_debt': str(debt), 'datum_zrusenia': str(dissolved)},
        )
    return fired(
        f'evidované nedoplatky {_eur(debt)} a firma zrušená {dissolved}',
        {'total_debt': str(debt), 'datum_zrusenia': str(dissolved)},
    )


def _flag_serial_director(company, rows, latest) -> dict:
    """The company's own officer holds functions across many companies.

    The company-shaped half of the person signal: this is the fact a reader
    looking at *this* company can act on. It says how many companies, and names
    the officer only because the company itself publishes its statutory body.

    Companies with no person relations -- 95,5 % of them -- have not been
    examined, and are reported as such.
    """
    fired, clear, unassessed = _rule(
        'statutar_vo_vela_firmach', 'Štatutár vo viacerých firmách', 'high'
    )
    from django.db.models import Count

    from connections.models import Person, PersonCompanyRelation

    person_ids = list(
        company.person_relations.values_list('person_id', flat=True).distinct()
    )
    if not person_ids:
        return unassessed('firmu nemáme prepojenú so žiadnou osobou')

    counts = (
        PersonCompanyRelation.objects
        .filter(person_id__in=person_ids)
        .values('person_id')
        .annotate(companies=Count('company', distinct=True))
        .order_by('-companies')
    )
    top = counts.first()
    if top is None:
        return unassessed('firmu nemáme prepojenú so žiadnou osobou')

    total = top['companies']
    evidence = {'max_companies_per_person': total, 'persons_examined': len(person_ids)}
    officers = plural_oblique_sk(len(person_ids), 'osoby', 'osôb')
    if total < SERIAL_DIRECTOR_MIN:
        return clear(f'najviac firiem na jednu z {officers}: {total}', evidence)

    name = Person.objects.filter(pk=top['person_id']).values_list('name', flat=True).first()
    evidence['person_id'] = top['person_id']
    held = plural_oblique_sk(total, 'firme', 'firmách')
    return fired(f'{name or "osoba"} je evidovaná v {held}', evidence)


def address_key(company) -> tuple | None:
    """The building a seat names, as a key -- or `None` when it names none.

    `Company.ulica` and `Company.mesto` hold the register's own spelling, so
    they are folded here through the project's address grammar rather than
    compared as strings. That grammar is measured, not guessed: `street_key`
    alone is worth 17 106 companies placed against 15 333 without it, over
    20 000 companies drawn at random (2026-09-11).

    The house number is part of the key, and that is the difference between this
    rule and a useless one. Two hundred companies **in one building** is the
    pattern the methodology describes; two hundred along one street is a street.
    A rural row has no street name -- the register writes the number where the
    street would go, for 973 318 of its 1 739 536 rows -- so the key is
    `('', '52', ...)` rather than a refusal: house 52 in that village is still a
    building two companies can share.
    """
    if not (company.ulica or '').strip():
        return None
    obec = normalize_obec(company.mesto)
    psc = psc_key(company.psc)
    if not obec or not psc:
        return None
    street, lone, orientation, registration = parse_street(company.ulica)
    return (psc, obec, street, lone, orientation, registration)


def _companies_at_address(company) -> int | None:
    """How many companies share this building, or `None` if the seat names none.

    Bounded by PSČ and folded in Python, because the fold cannot be expressed
    in SQL: there is no normalised address column on `Company` (the keys live on
    `AddressPoint`, which is the register's side of the join, not ours), and a
    sequential scan of 445 000 rows on every company page is not a trade worth
    making. The PSČ window is what that costs -- the index on `psc` narrows the
    candidates to one postal code before any folding happens.

    The residue is the fold's own, and `address.street_key` documents it: a fold
    can in principle merge two streets a town keeps apart. For a count that is
    reported as an observation to check, that is liveable -- it is named in the
    flag's wording, and it is why this is an indicator rather than a verdict.
    """
    key = address_key(company)
    if key is None:
        return None
    psc, obec, street, lone, orientation, registration = key

    from companies.models import Company

    # Both spellings of the PSČ: three rows in the table carry a space in it,
    # and querying only the digits would drop exactly those three from the count.
    candidates = (
        Company.objects
        .filter(psc__in={company.psc, psc})
        .values_list('ulica', 'mesto', 'psc')
    )
    count = 0
    for ulica, mesto, row_psc in candidates.iterator():
        if psc_key(row_psc) != psc or normalize_obec(mesto) != obec:
            continue
        if parse_street(ulica) == (street, lone, orientation, registration):
            count += 1
    return count


def _flag_crowded_address(company, rows, latest) -> dict:
    """Many companies registered at one building.

    What this is *not*: a finding that the address is fictitious. A registered
    office can be shared for ordinary reasons -- an accountant, a virtual office
    a company pays for, an office building -- and the number alone cannot tell
    those apart. What the number does is point at a building worth looking at,
    which is what the flag says.
    """
    fired, clear, unassessed = _rule(
        'sidlo_so_zhlukom', 'Sídlo na adrese s mnohými firmami', 'medium'
    )
    key = address_key(company)
    if key is None:
        return unassessed(
            'register neuvádza ulicu, obec alebo PSČ sídla — adresa sa nedá porovnať'
        )

    count = _companies_at_address(company)
    if count is None:
        return unassessed('adresa sídla sa nedá zostaviť')

    psc, obec, street, lone, orientation, registration = key
    number = orientation or registration or lone
    label = ' '.join(part for part in (street, number) if part) or f'č. {number}'
    evidence = {
        'matching_companies': count,
        'street': street,
        'number': number,
        'obec': obec,
        'psc': psc,
    }
    # Written as a label and a count rather than as a sentence, so that the
    # wording holds for one firm as well as for twenty: "je evidovaných 1
    # firiem" is what the sentence form costs, and a reader who sees it stops
    # trusting the number.
    detail = (
        f'na adrese {label}, {obec}: '
        f'{plural_sk(count, "firma", "firmy", "firiem")} v registri'
    )
    if count >= ADDRESS_CLUSTER_MIN:
        return fired(detail, evidence)
    return clear(detail, evidence)


#: Every company rule, in the order a reader sees them: the ones that speak
#: about the accounts first, then the register's own records, then the network.
COMPANY_RULES = (
    _flag_revenue_without_employees,
    _flag_revenue_jump,
    _flag_turnover_without_profit,
    _flag_balance_without_fixed_assets,
    _flag_inventory_turnover,
    _flag_unreliable_tax_index,
    _flag_vat_deregistered,
    _flag_debt_and_dissolution,
    _flag_serial_director,
    _flag_crowded_address,
)


def coverage(company, rows) -> dict:
    """What the rules above were able to look at for this company.

    Printed with the flags rather than kept in the code, because the honest
    reading of "no flags" depends entirely on it: a company with a filed
    statement and a person graph has been examined by ten rules, and one with
    neither has been examined by almost none.
    """
    return {
        'financial_years': len(rows),
        'has_financials': bool(rows),
        'persons_linked': company.person_relations.values('person_id').distinct().count(),
        'size_band_known': bool(_band_label(normalise_size_code(company.velkost_organizacie))),
        'vat_register_dated': company.vat_deleted_date is not None
        or company.datum_reg_dph is not None,
    }


def company_red_flags(company, rows=None) -> dict:
    """Every company rule's outcome, with the coverage that qualifies it.

    `rows` is the company's `CompanyFinancialResult` ordered by year; pass it
    when the caller already has it, so the rules read one queryset rather than
    each fetching its own. Order matters -- `rows[-1]` is the latest year.
    """
    if rows is None:
        rows = list(company.financial_results.all().order_by('year'))
    else:
        rows = sorted(rows, key=lambda r: r.year)

    latest = rows[-1] if rows else None
    flags = [rule(company, rows, latest) for rule in COMPANY_RULES]

    return {
        'flags': flags,
        'counts': {
            'fired': sum(1 for f in flags if f['state'] == 'fired'),
            'clear': sum(1 for f in flags if f['state'] == 'clear'),
            'unassessed': sum(1 for f in flags if f['state'] == 'unassessed'),
        },
        'coverage': coverage(company, rows),
    }
