"""Which `Person` rows are the same human.

`Person.fingerprint` is a **row** key, and it has to stay one. It is what stops
a re-import of the same document from writing a second row for every officer in
it, and every stored value still reproduces from the row's own fields -- which
makes `compute_fingerprint(name, address, person_ico) == fingerprint` the
cheapest corruption check this table has.

What a row key cannot do is recognise one human written twice under different
evidence, and the register does that constantly. Measured 2026-09-13: of 4 238
`(company, name)` duplicate groups, 3 558 (84 %) have every member created
within 60 s of the others, median 7.7 ms apart -- one document, one person,
rendered once under `Predstavenstvo` and again under `Spoločníci`. The two
sections do not carry the same lines, so they do not produce the same address,
and therefore not the same fingerprint:

    id=44903  Matej Vácha  'Dátum narodenia: 20.08.1992'          -> addr:datum narodenia: 20.08.1992
    id=44904  Matej Vácha  ''                                     -> addr:
    id=45335  Matej Vácha  'Beniakova, 3100/12, ..., 841 05'      -> addr:841 05

`id=44903` is history rather than a row: that date line was the whole address,
and a date is not an address -- but because the key reads the address it had
also become the row's identity, so migration `connections/0004` moved its
`konatel` relation to `id=44904` and deleted it. That does not touch the split
the example is about: `44904` and `45335` are still one human under two keys,
and the `Spoločníci` entry that wrote `44904` carries no evidence at all.

No key computed over a single row can join those rows, because the
`Spoločníci` entry carries no evidence at all. So this module does not try. It
resolves them at **read** time and writes nothing.

Why not merge the rows instead -- the obvious fix, and the one this module
deliberately refuses:

* a merge is paid for on a heuristic that already fuses places. A Slovak
  postcode is not unique to a municipality (Hrnčiarska Ves and Hrnčiarske
  Zalužany are both 980 13), and PSČ 040 01 alone holds 1 284 `Person` rows;
* the one signal that could refute a wrong merge -- a birth date -- reached this
  module on 14 rows out of 121 558 (measured 2026-09-15, and no *name group*
  held two dates: each of the three collisions this table had was a dated row
  against an undated one). It is now read from `Person.birth_date` (migration
  `connections/0004`) and used to *refuse* joins, which is all it is good for
  at that prevalence;
* no read path filters a merged marker, so a wrong merge is invisible in the
  product: it shows a role the register never states, permanently.

A wrong *group*, by contrast, is visible and correctable, because every cluster
here is returned with the rows it was built from.

Nothing in this module is stored, so nothing in it can corrupt anything. It is
pure text handling over values already in the database.
"""

import re
from collections import defaultdict

from .models import strip_diacritics

#: A postcode inside one comma-delimited component of an address.
#:
#: Deliberately not anchored to the whole component: the register writes
#: `Bratislava - mestská časť Nové Mesto 831 04` as one component about as often
#: as it writes `841 05` as its own, and 76 live rows are reachable only this
#: way. The `[\d/]` guards keep it off a street number (`3100/12`) and off a
#: rodné číslo (`920820/1234`).
#:
#: Known false positive, accepted: a foreign register number (`HRB 29493`) reads
#: as a postcode. It costs nothing here -- it would only matter if two rows with
#: the same name carried the same foreign number, and those rows already agree
#: on everything else.
_PSC_RE = re.compile(r"(?<![\d/])(\d{3})\s?(\d{2})(?![\d/])")

#: Academic titles the register prefixes to a name. Measured across the live
#: table -- `ing` 16 358, `mgr` 3 079, `mudr` 2 211, `judr` 1 303, `rndr` 354,
#: `phdr` 347, `bc` 335 -- and frequently in sequence (`ing mgr`, `ing arch`,
#: `dipl oec`, `mgr art`). Kept to titles that occurred in the data and that
#: cannot be a first name: a title left on is an under-fix, whereas a first name
#: stripped produces a wrong answer.
_TITLES = frozenset({
    "ing", "arch", "mgr", "art", "mudr", "mddr", "judr", "rndr", "phdr",
    "paeddr", "thdr", "pharmdr", "mvdr", "dr", "doc", "prof", "bc", "dipl",
    "oec", "mga", "pharm", "akad", "drs", "phd", "msc", "bsc", "mim",
})


def base_name(name: str) -> str:
    """The name with its academic titles removed.

    `Ing. Miroslav Trnka` and `Miroslav Trnka` are one person to a reader and
    two groups to `name_normalized`, which folds the title in rather than
    dropping it. Removing it here recovers 566 company groups that a
    title-sensitive grouping leaves apart.

    Only *leading* titles go: a title in the middle of a name is part of it. At
    least one token is always kept, so a row whose whole name is a title does
    not collapse to the empty string and join every other such row.
    """
    tokens = re.sub(r"\s+", " ", strip_diacritics(name or "")).strip().split()
    start = 0
    while start < len(tokens) - 1 and tokens[start].rstrip(".") in _TITLES:
        start += 1
    return " ".join(tokens[start:])


def extract_psc(address: str) -> str:
    """The postcode in an address, as five bare digits, or `''`.

    Scanned right to left over the comma-delimited components, because the
    postcode is the last part of a Slovak address and an earlier component can
    hold a number that looks like one. Within a component the *first* match
    wins, so a foreign address whose postcode precedes a district code reads
    correctly.

    This is the defect #89 was filed against. The old rule in
    `compute_fingerprint` walks back from the end of the address looking for the
    last component that is `not part.isdigit()` -- and a bare Slovak postcode
    (`81103`) *is* a digit string, so the rule skips it and lands on the city
    instead. Bare in 33 424 rows against spaced in only 6 426, which is why the
    identity key had degenerated to "name + city": `bratislava` alone appears in
    3 832 of them.
    """
    text = strip_diacritics(address or "").replace("\n", ",")
    for part in reversed([p.strip() for p in text.split(",") if p.strip()]):
        match = _PSC_RE.search(part)
        if match:
            return match.group(1) + match.group(2)
    return ""


class PersonEvidence:
    """One `Person` row, reduced to what identity resolution reads.

    `companies` is the set of company ids the row has a relation to. It is what
    lets two rows be joined inside one company without also joining every
    same-named person in the country: outside a shared company, a name and a
    postcode have to agree before anything is joined.

    `base` and `psc` are computed once on construction because resolution reads
    each of them several times.

    `birth_date` is the only piece of evidence here that can *refute* a join
    rather than merely fail to support one, so it is carried on every row even
    though almost none has it.
    """

    __slots__ = (
        "id", "name", "address", "person_ico", "companies", "base", "psc", "birth_date",
    )

    def __init__(self, id, name, address="", person_ico="", companies=(), birth_date=None):
        self.id = id
        self.name = name
        self.address = address or ""
        self.person_ico = (person_ico or "").strip()
        self.companies = frozenset(companies)
        self.base = base_name(name)
        self.psc = extract_psc(self.address)
        self.birth_date = birth_date


def cluster_evidence(rows):
    """Partition rows into the groups that are plausibly one human.

    Exactly two kinds of evidence join rows, and nothing else does:

    1. **One company, one name.** A single register document that lists the same
       name under two sections is one person, however differently it wrote the
       address -- or whether it wrote one at all. This is where 84 % of the
       duplication comes from. It is refused when the rows contradict each other
       with two different postcodes, because then they may genuinely be two
       people; a row with no postcode at all could belong to either, which is
       not evidence that it belongs to both, so it is joined only to its own
       kind.
    2. **One name, one postcode, any company.** The same human read through two
       registers and formatted differently.

    Two rows carrying two different non-empty IČOs are never joined, whatever
    else agrees: an IČO names an organisation, not a person. Measured, exactly
    one company group in the live data would otherwise be joined this way.

    Two rows that both state a birth date and disagree are never joined either,
    and that guard is a different kind of thing from the rest of this function.
    Every other rule here offers *support* for a join and can be wrong in the
    direction of joining two people; this one can only ever refuse, so a wrong
    answer from it is a visible split rather than an invisible fusion. It was
    written when the register's date line was being stored as an address and so
    was unreadable as evidence (14 rows, no name group holding two dates);
    it is here because the column now holds it and because this is the one
    signal that can contradict a merge instead of merely failing to confirm it.

    Returns a list of clusters, each a list of `PersonEvidence` sorted by row
    id; the clusters themselves are ordered by their lowest row id, so a
    caller's ordering is stable across calls.
    """
    rows = list(rows)
    parent = {row.id: row.id for row in rows}
    #: The distinct non-empty IČOs each cluster holds. Kept per root so the
    #: guard can refuse a join that would put two organisations in one cluster.
    icos = {row.id: ({row.person_ico} if row.person_ico else set()) for row in rows}
    #: The distinct known birth dates each cluster holds, for the same reason.
    dates = {row.id: ({row.birth_date} if row.birth_date else set()) for row in rows}

    def find(row_id):
        root = row_id
        while parent[root] != root:
            root = parent[root]
        while parent[row_id] != root:
            parent[row_id], row_id = root, parent[row_id]
        return root

    def union(a, b):
        root_a, root_b = find(a), find(b)
        if root_a == root_b:
            return
        merged = icos[root_a] | icos[root_b]
        if len(merged) > 1:
            return
        merged_dates = dates[root_a] | dates[root_b]
        if len(merged_dates) > 1:
            return
        parent[root_b] = root_a
        icos[root_a] = merged
        dates[root_a] = merged_dates

    def join(members):
        """Join rows offered as the same human, never across two IČOs.

        A row with no IČO is compatible with either side of a clash, so it is
        offered to each and the guard refuses the second. That is what keeps two
        organisations apart while still letting the unlabelled row join the one
        it actually belongs to.
        """
        first_plain = None
        by_ico = {}
        for row in members:
            if row.person_ico:
                if row.person_ico in by_ico:
                    union(by_ico[row.person_ico].id, row.id)
                else:
                    by_ico[row.person_ico] = row
            elif first_plain is None:
                first_plain = row
            else:
                union(first_plain.id, row.id)
        if first_plain is not None:
            for row in by_ico.values():
                union(first_plain.id, row.id)

    # Rule 1 -- inside one company.
    scoped = defaultdict(list)
    for row in rows:
        for company_id in row.companies:
            scoped[(company_id, row.base)].append(row)

    for members in scoped.values():
        if len(members) < 2:
            continue
        if len({m.psc for m in members if m.psc}) <= 1:
            join(members)
            continue
        by_psc = defaultdict(list)
        plain = []
        for member in members:
            (by_psc[member.psc] if member.psc else plain).append(member)
        for same in by_psc.values():
            join(same)
        join(plain)

    # Rule 2 -- the same name and postcode anywhere. Rows without a postcode
    # are not in this index at all, so they can never be joined by it.
    named = defaultdict(list)
    for row in rows:
        if row.psc:
            named[(row.base, row.psc)].append(row)
    for members in named.values():
        if len(members) > 1:
            join(members)

    clusters = defaultdict(list)
    for row in rows:
        clusters[find(row.id)].append(row)

    return sorted(
        (sorted(members, key=lambda row: row.id) for members in clusters.values()),
        key=lambda members: members[0].id,
    )
