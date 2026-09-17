"""How a Slovak address becomes a join key — one definition, in one place.

The seat map used to know only a PSČ, and a PSČ centroid sits a median 1 980 m
from its own address points (p90 4 118 m), so the map drew a circle to stay
honest. The MV SR address register we already download carries the street, both
house numbers and the coordinate, so a company can usually be placed on its
actual building instead — but only by parsing `Company.ulica`
(`Bratislava 1458/71`, `Krajné 52`, `Tomášikova 50/E`) into the same shape the
register stores it in.

That parsing is the whole risk, so it lives here alone and both ends call it:
`import_address_points` normalises the register with it and `match_seat_addresses`
normalises our own rows with it, so a test can hold both ends at once. Two
definitions of "the same street" at the two ends of one join is the mistake #90
named for IČO — and it is the mistake this module was still making for PSČ until
`psc_key` moved here: the register import stripped the space inline while the
matcher folded with `normalize_text`, which keeps one, so every company whose
`psc` reads `941 01` had every PSČ-scoped tier silently miss. `PostalCodeArea`
now delegates to `psc_key` rather than owning a second copy.

What is deliberately *not* shared here is the distance formula's callers: the
PSČ importer computes its own radius inline. That is arithmetic, not a key — two
copies of the same formula cannot silently mis-join a row, which is what makes
key normalisation different in kind.
"""

import math
import re
import unicodedata

METRES_PER_DEGREE = 111_320
"""Metres per degree of latitude. Longitude is scaled by the cosine of latitude."""

COVERAGE = 0.90
"""The share of a key's address points its radius must cover."""

MAX_KEY_SPREAD_M = 150.0
"""How far apart the points behind one *building* key may be, in metres.

A key that reaches more than one point is only usable when those points are one
building seen twice — two entrances, or the same house in two register rows.
Beyond this they are two different places, and taking either would be a guess.

Measured over 100 000 companies drawn at random (`md5(ico)`): the keys this rule
rejected spanned **154,5 m to 337 km**, median 4,23 km — a municipality name is
not unique in Slovakia (`Nevidzany` sits in two districts, 62 km apart). The
wider end also locates the limit: the widest key that *passed* spanned 145,1 m,
so 150 m sits in an empty band rather than being rounded to a convenient number.

(That measurement replaces one taken on a 4 000-company slice ordered by
`ruz_id`, which put the rejected maximum at 73 km. The slice is the geographic
head `normalize_obec` names, and it is why the constant survived a re-measure
while the number describing it did not.)
"""

MAX_STREET_SPREAD_M = 5_000.0
"""How far apart the points behind one *street* key may be, in metres.

Many points is the ordinary case for a street, so this cannot be the building
rule. It exists because street names collide too: the widest street key in the
register spans 205 km. A "street" longer than this is two villages sharing a
name, and its centroid would land between them.
"""

MIN_STREET_RADIUS_M = 50
"""The smallest circle a street match may draw.

A street with a single known address point would otherwise get a 0 m radius —
i.e. a pin claiming a building entrance, which is the overclaim this whole
module exists to avoid. 50 m says "on this street" and nothing more.
"""

MIN_STREET_POINTS = 2
"""Below this a street key carries no shape to average, so it is not used."""

# The register's own house-number shapes, measured over all 1 739 536 rows:
# `SUPISNE_CISLO` is **always** pure digits, and `ORIENTACNE_CISLO_CELE` is
# digits with an optional *trailing* letter (`1A`, `2A`, `12A` -- 2 427 rows of
# the most common one). **No row anywhere leads with a letter.** So the number
# is digits first, and that is what this matches.
#
# `Tomášiková 50/E` is our side, not the register's: a letter after a slash. It
# parses as registration 50 with orientation `e`, and an `e` will never match a
# register value -- which is exactly why `parse_street` returns the two columns
# separately rather than picking one, so the registration reading still gets
# its chance against `SUPISNE_CISLO`.
_NUMBER = r'\d+[A-Za-z]?'
_STREET_AND_NUMBER = re.compile(
    rf'^(?P<street>.*?)[\s,]*(?P<a>{_NUMBER})(?:/(?P<b>{_NUMBER}|[A-Za-z]))?$'
)
_TRAILING_UL = re.compile(r'[, ]*\bul\.?$', re.IGNORECASE)
_OBEC_QUALIFIER = re.compile(r'\b(mesto|obec|mestská časť|mestska cast)\b', re.IGNORECASE)
_OBEC_SEPARATOR = re.compile(r'\s*[-–]\s*')

# Matched against an already-folded key, so the words carry no diacritics.
_STREET_TYPE_WORD = re.compile(
    r'\s+(ulica|cesta|trieda|namestie|nabrezie|aleja|sady|ul)\.?$'
)
_DOT_SPACE = re.compile(r'\.\s*')


def normalize_text(value):
    """Fold a value to the key both ends of the join agree on.

    Diacritics are stripped, case is dropped and every run of whitespace becomes
    one space, because the register and our own rows disagree on all three
    (`ALLENDEHO` vs `Allendeho`, `Námestie SNP` vs `Námestie  SNP`).
    """
    folded = unicodedata.normalize('NFKD', value or '')
    folded = ''.join(c for c in folded if not unicodedata.combining(c))
    return ' '.join(folded.lower().split())


def psc_key(value):
    """A PSČ as a join key: the five digits, and nothing between them.

    Deliberately **not** `normalize_text`, which collapses a run of whitespace to
    one space and therefore keeps it. `Company.psc` carries three values written
    with a space (`602 00`, `024 01`, `941 01`) and both registers write them
    without, so folding with `normalize_text` sends the key `941 01` at a column
    that holds `94101` — a key that cannot match anything, on the tiers the
    matcher's own policy says to ask first. That is why the join has one function
    here rather than one at each end.

    Missing digits are neither guessed nor padded: a value that is not the five
    characters is simply not found, and the company falls back to a wider claim.
    """
    if not value:
        return ''
    return ''.join(str(value).split())


def normalize_obec(value):
    """The municipality, without the city-part qualifier the two sources differ on.

    Our `mesto` reads `Bratislava - mestská časť Ružinov` where the register
    writes `Bratislava-Ružinov`; both have to become `bratislava` or no municipal
    key ever matches.

    Splitting on the hyphen can in principle collide two genuinely different
    hyphenated municipalities, and the spread rule downstream does **not** catch
    all of them. It catches a collision that leaves two or more register points,
    because those points are far apart and `is_one_place` refuses them. It cannot
    catch one that leaves exactly **one**, because a single point is always one
    place — so the key is accepted, and the pin is drawn at building precision
    with the point count to confirm it and nothing on screen to query it.

    That is not hypothetical, and it is why the fold is worth stating plainly
    rather than claiming a guarantee it does not have. The register keeps a
    city's parts apart (`Bratislava-Ružinov` is its own OBEC value, 25 300 rows)
    and this function folds 17 of them onto `bratislava`; **40,1 % of the placed
    companies name a part in `mesto`**, and of the 34 901 companies the
    municipal building tiers place, **7 415 sit on a single register point in a
    municipality the register splits** — where a lone point cannot be checked
    against the part the company named. The fold is still the right default
    (without it no municipal key matches at all, and the PSČ-scoped tiers that
    would have answered precisely are asked first), but the residue is real and
    is tracked in `docs/PLAN.md` rather than assumed away here.

    Measured against the finished `match_seat_addresses` run (384 440 placed of
    449 764) with *this function*, not a copy of its rule.
    """
    without_part = _OBEC_SEPARATOR.split(value or '')[0]
    return normalize_text(_OBEC_QUALIFIER.sub(' ', without_part))


def street_key(value):
    """The street name as a key: the same street, however it happens to be written.

    Every difference folded away here was found by measuring which rows fail to
    join, and each is typographic rather than semantic:

    | our rows                     | the register               |
    |------------------------------|----------------------------|
    | `Bratislavská`               | `bratislavska ulica`       |
    | `17. novembra`               | `17.novembra`              |
    | `J.L.Bellu`                  | `j. l. bellu`              |
    | `M. Schneidra-Trnavského`    | `m. schneidra trnavskeho`  |

    so the generic street-type word is dropped, a space after a full stop is
    dropped, and a hyphen is treated as the same break as a space. Folding on
    *both* ends is what lets those rows join at all; leaving any one of them in
    loses every company behind it to a PSČ circle.

    Folding can in principle merge two streets that a town keeps apart. A merge
    that leaves two or more register points is caught by the spread rule — the
    points are far apart and the key is refused. A merge that leaves exactly
    **one** point is not caught by anything, for the reason `normalize_obec`
    sets out: one point is one place. So the guard bounds this fold rather than
    sealing it, and the residue is the same one named there.

    Measured over 20 000 companies drawn at random (`md5(ico)`), folding on both
    ends is worth a great deal more than it costs: **17 106 companies placed
    against 15 333 without the folds — 85,5 % against 76,7 %** — for 20 more
    keys rejected by the spread rule. It is not a marginal tidy-up; without it
    nearly one company in eleven falls back to a PSČ circle it did not have to.

    (The same measurement was once read off a 4 000-company slice taken as
    `order_by("ruz_id")[:4000]`, which put the gain at 72 companies. That slice
    is the geographic head #98 exposed, and it understated this by a factor of
    twenty-five — a reminder that a *rate* measured on an ordered slice is not a
    rate, however carefully it is computed.)

    The trade is the point of having the spread rule at all: a merge shows up as
    a rejection to fall back from, not as a pin on the wrong building.
    """
    folded = normalize_text(value)
    folded = _DOT_SPACE.sub('.', folded)
    folded = ' '.join(folded.replace('-', ' ').split())
    return _STREET_TYPE_WORD.sub('', folded) or folded


def normalize_number(value):
    """A house number as a key. `12A` and `12a` are the same door."""
    return normalize_text(value)


def parse_street(value):
    """Split a `Company.ulica` value into the four things the register stores.

    Returns `(street, lone, orientation, registration)`, where exactly one of
    `lone` or the `orientation`/`registration` pair carries a number:

    | input                  | street        | lone | orientation | registration |
    |------------------------|---------------|------|-------------|--------------|
    | `Bratislavská 1458/71` | `bratislavska`| —    | `71`        | `1458`       |
    | `Starohájska 3`        | `starohajska` | `3`  | —           | —            |
    | `Krajné 52`            | `krajne`      | `52` | —           | —            |
    | `Golianova ul.`        | `golianova`   | —    | —           | —            |

    Slovak addresses write the registration number first and the orientation
    number second, so `1458/71` is registration 1458 at orientation 71.

    A **lone** number is kept apart rather than guessed into one of the two
    columns, because the address field genuinely does not say which it is: in a
    town `Starohájska 3` is an orientation number, and in a village
    `Krajné 52` is a registration number. The caller tries it as both, and the
    register decides.
    """
    stripped = _TRAILING_UL.sub('', (value or '').strip())
    match = _STREET_AND_NUMBER.match(stripped)
    if not match:
        return street_key(stripped), None, None, None

    street = street_key(match.group('street'))
    first = normalize_number(match.group('a'))
    second = normalize_number(match.group('b') or '')
    if second:
        return street, None, second, first
    return street, first, None, None


def metres_between(lon1, lat1, lon2, lat2):
    """Flat-earth distance in metres. Exact enough at the scale of one street."""
    dx = (lon1 - lon2) * METRES_PER_DEGREE * math.cos(math.radians(lat1))
    dy = (lat1 - lat2) * METRES_PER_DEGREE
    return math.hypot(dx, dy)


def centroid(points):
    """The average of `(lat, lon)` pairs, returned as `(lat, lon)`."""
    n = len(points)
    return sum(p[0] for p in points) / n, sum(p[1] for p in points) / n


def spread_m(points):
    """The largest distance between any two of `points`, in metres."""
    if len(points) < 2:
        return 0.0
    widest = 0.0
    for i, (lat1, lon1) in enumerate(points):
        for lat2, lon2 in points[i + 1:]:
            widest = max(widest, metres_between(lon1, lat1, lon2, lat2))
    return widest


def is_one_place(points, max_spread=MAX_KEY_SPREAD_M):
    """Whether `points` are close enough together to be treated as one location.

    **Fewer than two points is `True` by definition**, and that is a property of
    the question rather than a shortcut: one point has no spread, so there is
    nothing here to refuse. The consequence is worth stating where the callers
    can see it — this is a *spread* guard and never a *scope* guard. It answers
    "are these points in the same place as each other", not "was the key that
    produced them narrow enough to trust". A single point returned by a
    municipality-wide key passes here, which is the case `normalize_obec`
    describes.

    Guarded so that a pathological key — a municipality name shared across the
    country, which the register does contain — cannot turn into a quadratic
    comparison. The bounding box is free and bounds the true spread from above,
    so a box inside the limit settles it outright; past the limit, a key with
    more than `_EXACT_SPREAD_LIMIT` points is rejected without the exact number,
    because a key reaching that many points is not one building under any reading.
    """
    if len(points) < 2:
        return True

    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    box = metres_between(min(lons), min(lats), max(lons), max(lats))
    if box <= max_spread:
        return True
    if len(points) > _EXACT_SPREAD_LIMIT:
        return False
    return spread_m(points) <= max_spread


_EXACT_SPREAD_LIMIT = 400
"""Above this many points a key is never one place, so it is not worth measuring."""


def p90_radius_m(points):
    """The radius around the centroid that covers `COVERAGE` of `points`.

    Never below `MIN_STREET_RADIUS_M`: a street with one known point would
    otherwise be drawn as a bare pin.
    """
    centre_lat, centre_lon = centroid(points)
    distances = sorted(
        metres_between(lon, lat, centre_lon, centre_lat) for lat, lon in points
    )
    index = min(len(distances) - 1, max(0, math.ceil(COVERAGE * len(distances)) - 1))
    return max(MIN_STREET_RADIUS_M, int(round(distances[index])))
