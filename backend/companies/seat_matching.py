"""Which register tier a company's address can be placed by, and in what order.

The tiers are tried most precise first and the first one that answers wins, so
the order *is* the policy. It is set by two rules:

- **A PSČ-scoped key before an obec-scoped one.** Both are correct when they
  match; they differ in how they fail. A PSČ is narrow, so its failure mode is
  omission — the key misses and we fall through. A municipality name is not
  unique in Slovakia, so its failure mode is commission — the key matches a
  building in the wrong district. For a pin, omission costs a circle and
  commission costs a lie, so the narrow scope goes first.

- **A street centroid last**, because it is the only tier that draws a circle
  wider than a building on purpose.

`resolve` is written against an injected `fetch`, so the whole decision — every
tier, every rejection, in order — is testable without a database.
"""

from dataclasses import dataclass

from companies.address import (
    MAX_KEY_SPREAD_M,
    MAX_STREET_SPREAD_M,
    MIN_STREET_POINTS,
    centroid,
    is_one_place,
    normalize_obec,
    p90_radius_m,
    parse_street,
    psc_key,
)

BUILDING = 'building'
"""The company's own building. Drawn as a point."""

STREET = 'street'
"""Somewhere on the company's street. Drawn as a circle around the street."""

POSTAL_CODE = 'postal_code'
"""Only the PSČ is known. Drawn as the wide circle, and named in `PostalCodeArea`."""

SEAT_PRECISION_CHOICES = (
    (BUILDING, 'Budova'),
    (STREET, 'Ulica'),
    (POSTAL_CODE, 'PSČ'),
)
"""The three claims a seat position may make, for `Company.seat_precision`.

Defined here and imported by the model rather than written out again there, so
the column's allowed values cannot drift from the values the matcher writes.
"""


@dataclass(frozen=True)
class Tier:
    """One lookup: which register columns it joins on, and what a hit claims."""

    name: str
    columns: tuple
    precision: str


T_PSC_ULICA_ORIENT = Tier('psc_ulica_orient', ('psc', 'ulica', 'orientacne_cislo'), BUILDING)
T_PSC_ULICA_SUPISNE = Tier('psc_ulica_supisne', ('psc', 'ulica', 'supisne_cislo'), BUILDING)
T_OBEC_ULICA_ORIENT = Tier('obec_ulica_orient', ('obec', 'ulica', 'orientacne_cislo'), BUILDING)
T_OBEC_ULICA_SUPISNE = Tier('obec_ulica_supisne', ('obec', 'ulica', 'supisne_cislo'), BUILDING)
T_PSC_ULICA = Tier('psc_ulica', ('psc', 'ulica'), STREET)
T_OBEC_ULICA = Tier('obec_ulica', ('obec', 'ulica'), STREET)

ALL_TIERS = (
    T_PSC_ULICA_ORIENT,
    T_PSC_ULICA_SUPISNE,
    T_OBEC_ULICA_ORIENT,
    T_OBEC_ULICA_SUPISNE,
    T_PSC_ULICA,
    T_OBEC_ULICA,
)
"""The only four column sets that need an index: the three-column pair for
buildings and the two-column pair for streets. A street tier is served by the
building index's leading columns, and a **rural** lookup is the same three
columns with an empty street — so the register's own empty `ULICA` (973 318 of
its 1 739 536 rows, 943 949 of which reach `AddressPoint`) is the rural case,
rather than a second key shape to index.
"""


@dataclass(frozen=True)
class Placement:
    """A place we are willing to draw, and the evidence for it."""

    precision: str
    lat: float
    lon: float
    radius_m: int
    point_count: int
    tier: str


def _rural(psc, obec, numbers):
    """Building keys for an address that carries no street name.

    A **rural** address — the municipality written where the street goes, which
    is 56 % of the register's rows — has no street to key on, so the number
    carries it alone. Both scopes are tried, narrow first: a PSČ-scoped rural
    key is usable whenever it reaches one point, and it is a stronger statement
    than the municipal one, because the company is known to sit in that PSČ.
    What the PSČ cannot do is *disambiguate* — a rural PSČ spans several
    villages, so number 52 exists in each (measured: those keys reached points
    2.6–5.6 km apart), and the spread rule rejects exactly those.

    The empty street is the whole of the rural case: it is how the register
    itself distinguishes those rows, so the same three-column key serves both
    and the index does not have to be told which kind of address it holds.

    A number with *no* street at all reaches here too: `35` in `Drňa`. In a
    village that number is the registration number and the municipal key places
    it exactly. In a city the same lookup finds nothing, because a city has no
    street-less register rows — so trying it costs a query and cannot mislead.
    """
    found = []
    for scope in (psc, obec):
        if not scope:
            continue
        orient_tier = T_PSC_ULICA_ORIENT if scope == psc else T_OBEC_ULICA_ORIENT
        supisne_tier = T_PSC_ULICA_SUPISNE if scope == psc else T_OBEC_ULICA_SUPISNE
        for number in numbers:
            found.append((orient_tier, (scope, '', number)))
            found.append((supisne_tier, (scope, '', number)))
    return found


def candidates(psc, obec, ulica):
    """Every `(tier, values)` this address could be looked up by, best first.

    `values` lines up with `tier.columns`. The order is the whole policy, so it
    is built here in one pass rather than derived from `ALL_TIERS`, where a
    reordering would silently change which claim the map makes.

    An address with no street name — rural, or only a number — goes to
    `_rural`; everything else is keyed on the street, narrow scope first.

    Both scopes are folded here, and the PSČ one is folded with `psc_key` rather
    than `normalize_text`, which would keep the space in `941 01` and send a key
    the register column cannot hold.
    """
    psc = psc_key(psc)
    obec = normalize_obec(obec)
    street, lone, orientation, registration = parse_street(ulica)
    numbers = [n for n in (orientation, registration, lone) if n]

    if not street or street == obec:
        return _rural(psc, obec, numbers)

    found = []
    for scope in (psc, obec):
        if not scope:
            continue
        orient_tier = T_PSC_ULICA_ORIENT if scope == psc else T_OBEC_ULICA_ORIENT
        supisne_tier = T_PSC_ULICA_SUPISNE if scope == psc else T_OBEC_ULICA_SUPISNE
        if orientation:
            found.append((orient_tier, (scope, street, orientation)))
        if registration:
            found.append((supisne_tier, (scope, street, registration)))
        if lone:
            # The field does not say which number this is, so both are tried and
            # the register decides — orientation first, because in a town that
            # is what a lone number names.
            found.append((orient_tier, (scope, street, lone)))
            found.append((supisne_tier, (scope, street, lone)))

    for scope, tier in ((psc, T_PSC_ULICA), (obec, T_OBEC_ULICA)):
        if scope:
            found.append((tier, (scope, street)))

    return found


def resolve(candidate_list, fetch):
    """The first candidate that answers honestly, or `None`.

    `fetch(tier, values)` returns the register points that key reaches, as
    `(lat, lon)` pairs. A tier that matches but fails its guard is skipped
    rather than used, which is why the guards live here and not in the fetch:
    "there are points" and "those points place this company" are different
    claims, and only the second one may reach the map.

    The guards are re-derived for every company, even when a key repeats within
    a chunk. That looked like the command's bottleneck and is not: measured over
    a 5 000-company chunk, this function is 0.04 s of a 0.82 s pass, and
    memoising the verdict per key moved the total by nothing (the query is 90 %
    of it). The cost is in the SQL and in the write, so nothing is cached here.
    """
    for tier, values in candidate_list:
        points = fetch(tier, values)
        if not points:
            continue

        if tier.precision == BUILDING:
            if not is_one_place(points, MAX_KEY_SPREAD_M):
                continue
            lat, lon = centroid(points)
            return Placement(BUILDING, lat, lon, 0, len(points), tier.name)

        if len(points) < MIN_STREET_POINTS:
            continue
        if not is_one_place(points, MAX_STREET_SPREAD_M):
            continue
        lat, lon = centroid(points)
        return Placement(STREET, lat, lon, p90_radius_m(points), len(points), tier.name)

    return None
