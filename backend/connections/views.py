import logging
from collections import defaultdict
from datetime import date

from django.conf import settings
from django.core.cache import cache
from django.db.models import F, Q
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from companies.models import Company
from companies.throttles import OrsrPersonThrottle
from .identity import PersonEvidence, base_name, cluster_evidence
from .models import Person, PersonCompanyRelation, normalize_name
from .person_risk import person_red_flags

logger = logging.getLogger(__name__)

#: Enough to see the shape of an answer without becoming a way to enumerate
#: the graph. A common surname matches thousands of people in this database.
MAX_PERSON_RESULTS = 50
MIN_QUERY_LENGTH = 2

#: Rows read to find at most `MAX_PERSON_RESULTS` people.
#:
#: A person costs one row in the common case, so this is generous -- but it is
#: not unbounded, because clustering does not belong in the path of a keystroke
#: and a two-letter query matches 20 050 rows. When the window is short of the
#: match count, the answer says how many *people* it found is unknown rather
#: than reporting the count it saw (see `total_people`).
CLUSTER_SCAN_LIMIT = 300


def _coverage() -> dict:
    """What our own data does and does not cover.

    Returned with every search rather than printed in the interface as a fixed
    sentence, because it is a moving number: the person graph covers 19 906 of
    445 626 companies today and grows with each ORSR sync. A hardcoded claim
    would drift into a lie the first time it stopped being true.
    """
    return {
        "companies_with_persons": Company.objects.filter(
            person_relations__isnull=False
        ).distinct().count(),
        "companies_total": Company.objects.count(),
    }


def _relation_payload(rel) -> dict:
    """One company, as seen from a person.

    `role` is the enum code and `role_display` the words, which is the opposite
    way round from the graph's edges -- deliberately. An edge is drawn and
    labelled, so it carries the label in `role` and the frontend colours it by
    that string; a row in a list is filtered and round-tripped, so it carries
    the code in `role`, matching both the `role=` query parameter and the column
    the code came from. `role_display` falls back to the enum's own label
    because the register's free text is often absent (it is a separate field
    there too), and a client should not need the mapping table to render one.
    """
    return {
        "ico": rel.company.ico,
        "name": rel.company.nazov_UJ,
        "role": rel.role,
        "role_display": rel.role_display or rel.get_role_display(),
        "is_active": rel.is_active,
        "vznik_funkcie": rel.vznik_funkcie,
        "zanik_funkcie": rel.zanik_funkcie,
        # How many stored relations this one row stands for. One in the common
        # case. More once `_joined_periods` has folded a chain of them into the
        # single office they describe -- and saying so is what keeps the fold
        # honest, because a row that quietly replaced twelve register filings
        # with one line reads exactly like a row that always was one line.
        "intervals": 1,
    }


def _companies_by_person(person_ids):
    """Which companies each row has a relation to, in one query rather than one
    per row. The values are what identity resolution compares."""
    companies = defaultdict(set)
    for person_id, company_id in (
        PersonCompanyRelation.objects
        .filter(person_id__in=person_ids)
        .values_list("person_id", "company_id")
    ):
        companies[person_id].add(company_id)
    return companies


def _cluster_persons(persons):
    """Group rows into people.

    Returns the clusters and the row objects keyed by id. Takes a materialised
    list rather than a queryset: resolving a person reads each row several
    times, and a queryset re-evaluated per read is how a page turns into
    hundreds of queries.
    """
    by_id = {person.id: person for person in persons}
    companies = _companies_by_person(list(by_id))
    clusters = cluster_evidence(
        PersonEvidence(
            id=person.id,
            name=person.name,
            address=person.address,
            person_ico=person.person_ico,
            companies=companies.get(person.id, ()),
            birth_date=person.birth_date,
        )
        for person in persons
    )
    return clusters, by_id


def _base_names(names):
    """The distinct base names of `names`, empty ones dropped.

    `base_name` keeps at least one token, so it is empty only for a row whose
    name is: those rows cannot be found by a name query and are handled by the
    caller that holds them.
    """
    return {base for base in (base_name(name) for name in names) if base}


def _candidate_rows(bases):
    """Every row that could belong to one of these base names, in one query.

    `base_name` is a suffix of `name_normalized` -- the title is *prefixed* to
    the normalised name and both sides have their diacritics stripped -- so
    `contains` is a superset of the answer and the exact filter removes what it
    over-matched: `novak` fetches `novakova`.

    One query for all the bases, not one per base, and no row limit on it. What
    sizes the query is the company, not the table: measured on production
    2026-09-24, the widest company has 187 distinct officer names and its OR'd
    query fetches 422 rows in 1.15 s, of which the exact filter keeps 352 -- so
    `contains` over-matched 17%, which is what that filter is there for. Base
    name groups are small: 143 617 distinct base names, of which 188 have ten
    rows or more and **none has fifty**; the commonest (`jan kovac`, 40 rows)
    fetches 72. Those counts are a snapshot -- the table grows by thousands of
    rows a day, and the same probes read 143 282 bases against 198 585 rows
    earlier the same day -- but the property that matters is structural: one
    company's officer names bound the fetch, so it does not grow with the table.

    The limit that used to stand here, `CLUSTER_CANDIDATE_LIMIT = 500`, was
    applied *before* the exact filter -- so a name common enough to overflow it
    would have lost siblings, and a person resolved from one graph would not have
    matched the same person resolved from another. That is the defect this
    replaces, so there is no limit here at all rather than a larger one.
    """
    query = Q()
    for base in sorted(bases):
        query |= Q(name_normalized__contains=base)
    return [
        row for row in Person.objects.filter(query).order_by("id")
        if base_name(row.name) in bases
    ]


def _resolve(persons):
    """Cluster the people these rows belong to, against the whole table.

    Returns `(clusters, by_id)` in `_cluster_persons`'s shape: each cluster a
    list of `PersonEvidence` sorted by row id, so `members[0]` is the row that
    stands for the person.

    **Whole table, and that is the whole point.** Clustering only the rows a
    caller happens to be holding gives one human several answers, because the
    lowest row id among, say, one company's officers is not the lowest of the
    human they belong to. Whoever keys anything on that id -- the graph keys its
    person nodes on it -- then gets one answer per caller.

    Clusters never cross a base name -- both rules in `cluster_evidence` group by
    it before anything else -- so restricting the candidates to these bases
    cannot lose a join.
    """
    bases = _base_names(person.name for person in persons)
    rows = _candidate_rows(bases) if bases else []
    # A row whose name is empty has no base name to be found by, so it can only
    # cluster with itself. It is added back rather than dropped: dropping it
    # would drop an officer out of a company's graph.
    known = {row.id for row in rows}
    rows.extend(person for person in persons if person.id not in known)
    if not rows:
        return [], {}
    return _cluster_persons(rows)


def _cluster_for(person):
    """The rows we believe are the same human as `person`.

    The cluster that holds this row, resolved the same way the company graph
    resolves its officers -- so the two views agree on which row stands for the
    person, which is what keeps the graph from drawing them twice.
    """
    clusters, by_id = _resolve([person])
    for members in clusters:
        if any(member.id == person.id for member in members):
            return members, by_id
    return [PersonEvidence(
        id=person.id, name=person.name, address=person.address,
        person_ico=person.person_ico, birth_date=person.birth_date,
    )], {person.id: person}


def _relation_sort_key(item):
    """Newest office first, unknown currency last.

    Matches the queryset ordering these payloads come from, so a merged list
    reads the same as an unmerged one. `date.min` stands in for a missing start
    date, which is what `nulls_last` does in SQL.
    """
    return (
        item["is_active"] is not None,
        bool(item["is_active"]),
        item["vznik_funkcie"] or date.min,
    )


def _is_richer(candidate, current) -> bool:
    return (
        (candidate["is_active"] is not None, len(candidate["role_display"] or ""))
        > (current["is_active"] is not None, len(current["role_display"] or ""))
    )


def _relations_by_person(person_ids, role=""):
    """Every relation of the given rows, grouped by the row it belongs to."""
    relations = (
        PersonCompanyRelation.objects
        .filter(person_id__in=person_ids)
        .select_related("company")
        .order_by(F("is_active").desc(nulls_last=True), "-vznik_funkcie")
    )
    if role:
        relations = relations.filter(role=role)

    grouped = defaultdict(list)
    for rel in relations:
        grouped[rel.person_id].append(_relation_payload(rel))
    return grouped


def _merged_relations(member_ids, grouped):
    """One person's companies, gathered from every row we believe is them.

    The claim is deduplicated because the cluster's rows are held to be one
    human: the same company in the same role from the same date, arriving twice,
    is one fact. The richer copy wins -- an `is_active` we actually read beats
    the `null` that means we never read that company's history, and the
    register's own wording beats the enum's label.

    A relation with no dates at all is then dropped when the same company and
    role has one that is dated. It is not a second tenure: it states no period,
    so it cannot be one, and it renders as "nevieme" -- which the register's own
    legend spells out as "we have not read this company yet". Next to a dated
    relation for the same office in the same company, that sentence is false:
    we demonstrably did read it. Measured on 2026-09-13, this drops 4 lines in
    the whole table, all of them created by grouping -- one row alone never
    showed the pair.

    What is left is one row per **office**, not per register filing: the periods
    that meet are folded by `_joined_periods`. Two rows survive it only where
    the office really did stop and start again.
    """
    payloads = [
        item for person_id in member_ids for item in grouped.get(person_id, [])
    ]
    payloads.sort(key=_relation_sort_key, reverse=True)

    best = {}
    order = []
    for item in payloads:
        key = (item["ico"], item["role"], item["vznik_funkcie"])
        current = best.get(key)
        if current is None:
            best[key] = item
            order.append(key)
        elif _is_richer(item, current):
            best[key] = item

    merged = [best[key] for key in order]
    dated_offices = {
        (item["ico"], item["role"])
        for item in merged
        if item["vznik_funkcie"] or item["zanik_funkcie"]
    }
    return _joined_periods([
        item for item in merged
        if item["vznik_funkcie"] or item["zanik_funkcie"]
        or (item["ico"], item["role"]) not in dated_offices
    ])


def _continues_period(previous, item) -> bool:
    """Two filings of one office, or one office written down twice.

    The register does not keep a function; it keeps filings. Each one ends the
    office and the next filing reopens it, so one continuous tenure from 2011
    arrives as a chain of intervals that meet day to day. Measured on person
    56172 (FREYSSINET CS): twelve relations, eleven of them meeting the next.

    **Both dates are required**, which is the whole of the rule. An open filing
    (`zanik_funkcie is None`) is the end of a chain by definition -- nothing can
    follow a function that has not ended -- and a filing whose start we do not
    know cannot be shown to meet anything, so it stands on its own. Guessing
    there would merge two tenures into one on no evidence, which is the failure
    this function exists to avoid; leaving them apart costs a duplicate line the
    reader can see.

    One day of slack, not zero: the register closes an office on the day it
    files and reopens it the next, so `zanik 2013-04-10` and `vznik 2013-04-11`
    is one tenure. It absorbs an overlap as well, and overlaps are the other
    shape of "the same office, written twice".
    """
    if previous["zanik_funkcie"] is None or item["vznik_funkcie"] is None:
        return False
    return (item["vznik_funkcie"] - previous["zanik_funkcie"]).days <= 1


def _join_periods(chain):
    """One office, from the first filing that opened it to the last that closed it.

    `vznik` is the earliest and `zanik` the latest, and `is_active` is taken
    from the **newest** filing, because a joined function is current exactly
    when its last period is. Not from the first, and not from any of them: the
    `None` that means "we never read this company" has to survive the fold, and
    a rule that let eleven `False`s outvote the one `True` would show a current
    officer as a former one -- the defect #86 removed, reached from the other
    side.

    The latest end date is the maximum rather than the last one in order. The
    chain is ordered by start date and a pair may overlap, so the filing that
    starts last is not always the one that ends last.

    The register's longest wording wins, which is the same tiebreak `_is_richer`
    uses a few lines up: filings of one office can carry slightly different
    labels, and the fuller one says more without claiming anything extra.
    """
    newest = chain[-1]
    ends = [item["zanik_funkcie"] for item in chain if item["zanik_funkcie"]]
    return {
        **newest,
        "vznik_funkcie": chain[0]["vznik_funkcie"],
        "zanik_funkcie": max(ends) if newest["zanik_funkcie"] else None,
        "role_display": max(
            (item["role_display"] or "" for item in chain), key=len
        ) or newest["role_display"],
        "intervals": sum(item["intervals"] for item in chain),
    }


def _joined_periods(items):
    """One row per office, its consecutive filings folded into one period.

    Why this is read-time and not a migration: the table's unique key is
    `(person_id, company_id, role, vznik_funkcie)`, which makes a re-import
    idempotent -- and would undo a write-time merge, because the merged row
    keeps the first filing's `vznik` and filings 2..12 would have nothing left
    to match, so the next import would create them again. Merging on the way out
    needs no bookkeeping about what has already been merged.

    Only filings of the **same** `(company, role)` are candidates: `konateľ`
    until 31 December and `prokurista` from 1 January are two offices, not one,
    and they stay two rows.
    """
    by_office = defaultdict(list)
    for item in items:
        by_office[(item["ico"], item["role"])].append(item)

    rows = []
    for filings in by_office.values():
        # Oldest first, so a chain is built in the direction it happened. An
        # open filing sorts last among those that start together, which is
        # where the chain has to end anyway.
        filings.sort(key=lambda item: (
            item["vznik_funkcie"] or date.min,
            item["zanik_funkcie"] or date.max,
        ))
        chain = [filings[0]]
        for item in filings[1:]:
            if _continues_period(chain[-1], item):
                chain.append(item)
            else:
                rows.append(_join_periods(chain))
                chain = [item]
        rows.append(_join_periods(chain))

    rows.sort(key=_relation_sort_key, reverse=True)
    return rows


def _active_rank(is_active):
    """Which of several readings of one edge's currency wins.

    `True` (the office is current) beats `False` (it ended) beats `None` (this
    company's history was never read -- the row's own help text). Only the first
    is a claim about today, and collapsing the rows by any other rule -- a `set`,
    the first row, the newest start date -- shows a current officer as a former
    one. That is the defect #86 removed, mirrored; measured on FREYSSINET CS
    (31798446), the same edge arrives eleven times as `False` and once as `True`.
    """
    if is_active is None:
        return 0
    return 2 if is_active else 1


def _edges_by_identity(candidates):
    """One edge per `(source, target, role)`, in the order they were found.

    The graph has no time axis, so twelve copies of one office say nothing the
    first one did not; the copies differ only in `vznik_funkcie`, which the edge
    does not carry. A different role on the same pair is a different fact and
    stays a separate edge.
    """
    merged = {}
    rank = {}
    for source, target, role, is_active in candidates:
        key = (source, target, role)
        if key not in merged:
            merged[key] = {
                "source": source,
                "target": target,
                "role": role,
                "isActive": is_active,
            }
            rank[key] = _active_rank(is_active)
        elif _active_rank(is_active) > rank[key]:
            merged[key]["isActive"] = is_active
            rank[key] = _active_rank(is_active)
    return list(merged.values())


def _parse_as_of(value):
    """The date a caller asked for, as `(date, error)`.

    `(None, None)` is "today", which is what the graph draws without the
    parameter. A malformed date is **refused** rather than ignored: quietly
    answering with today's company while the control still reads 2015 would put
    a period on the screen that the picture below it does not show, and nothing
    in the answer would say so.
    """
    if value is None or not str(value).strip():
        return None, None
    try:
        return date.fromisoformat(str(value).strip()), None
    except ValueError:
        return None, "Neplatný dátum. Očakávam formát RRRR-MM-DD."


def _in_force_at(rel, as_of) -> bool:
    """Whether this office was running on `as_of`.

    A period view asks a different question from the one the graph normally
    answers. Today's graph draws every relation we hold and marks each one
    current, ended or unknown; a period view draws only the offices in force on
    the date asked for -- which is why it can look like a different company.

    **The start date has to be known.** A row whose `vznik` we never read cannot
    be placed on a timeline at all: it may have begun before the date in
    question or after it, so drawing it would be a claim the row does not
    support. Those rows are left out and counted (`undated_excluded`) -- the
    same treatment `_continues_period` gives a filing with no start.

    An open end is not an unknown one. `zanik is None` means the office has not
    ended, so it was running on every date from the start onwards, and that is
    a statement about the past that the two dates it does carry support.
    """
    if rel.vznik_funkcie is None or rel.vznik_funkcie > as_of:
        return False
    return rel.zanik_funkcie is None or rel.zanik_funkcie >= as_of


def _state_at(relations, when):
    """Which offices this company's record holds on `when`.

    The identity of the state is the set of offices and not how many there are:
    one office ending as another begins is a different company drawn with the
    same number of lines.
    """
    return frozenset(
        (rel.person_id, rel.role, rel.vznik_funkcie, rel.zanik_funkcie)
        for rel in relations
        if _in_force_at(rel, when)
    )


def _period_years(relations, today):
    """The years worth offering a reader, newest first.

    A year is offered only when its 31 December shows a company that the next
    observation point does not -- otherwise two of these would draw the same
    graph, and a long-lived company would carry a chip for every year any
    filing happens to mention. That is what keeps the row a control rather than
    a list of dates.

    The current year is never offered: its 31 December is in the future, and
    the chip that means "now" is `Dnes`.
    """
    years = sorted(
        {
            value.year
            for rel in relations
            for value in (rel.vznik_funkcie, rel.zanik_funkcie)
            if value
        },
        reverse=True,
    )
    periods = []
    following = _state_at(relations, today)
    for year in years:
        if year >= today.year:
            continue
        state = _state_at(relations, date(year, 12, 31))
        if state != following:
            periods.append(year)
        following = state
    return periods


def _company_person_relations(company, as_of):
    """This company's relation rows, in three shapes.

    Returns `(all_relations, relations, undated)`: everything we hold for the
    company, the ones the date asked for leaves in force, and how many could not
    be placed at all because we never read their start date.

    `all_relations` is returned alongside because the period chips are a
    property of the whole record and must not move when one of them is chosen.
    """
    all_relations = list(
        PersonCompanyRelation.objects
        .filter(company=company)
        # `company` as well as `person`: the company graph knows the company
        # already, but `CompanyPersonsView` reads each relation's own company
        # back off the row for its office payload, and one join is what keeps a
        # company with 187 officers from answering with 187 more queries.
        .select_related("person", "company")
    )
    if as_of is None:
        return all_relations, all_relations, 0
    return (
        all_relations,
        [rel for rel in all_relations if _in_force_at(rel, as_of)],
        sum(1 for rel in all_relations if rel.vznik_funkcie is None),
    )


def _office_payload(rel) -> dict:
    """One office, as seen from a company.

    The mirror of `_relation_payload`, and deliberately the same shape: a
    company's own screen and a person's page state one fact, so they fold it
    with the same code (`_merged_relations`) and cannot disagree about how many
    register filings one tenure stands for. `ico` stays even though every row
    here shares it -- that is what `_merged_relations` and `_joined_periods` key
    on, and a second shape would be a second set of rules to drift.
    """
    return {
        "ico": rel.company.ico,
        # The company's name, which every row here shares: present because
        # `_relation_payload` carries it and the frontend reads one mapper for
        # both shapes. A field the other side of the contract fills in and this
        # one leaves empty is how `name` becomes the string "undefined" on
        # somebody's screen.
        "name": rel.company.nazov_UJ,
        "role": rel.role,
        "role_display": rel.role_display or rel.get_role_display(),
        "is_active": rel.is_active,
        "vznik_funkcie": rel.vznik_funkcie,
        "zanik_funkcie": rel.zanik_funkcie,
        "intervals": 1,
    }


def _edge_currency(rel, as_of):
    """What an edge's `isActive` says in the view the caller asked for.

    Today's graph carries the tri-state, because its question is whether the
    office still runs. A period view asks whether it ran *then*, and every edge
    it draws was in force on the date asked for -- that is what the filter
    means -- so `True` is the answer, and it is a claim about the period rather
    than about today. Reporting `rel.is_active` there would stamp today's
    currency on a past company, which is the defect #86 removed, mirrored.
    """
    return rel.is_active if as_of is None else True


def _person_company_count(member_ids, as_of=None) -> int:
    """How many companies we hold for this person, at the date asked for.

    Counted over the relations rather than read from a stored column, so a
    period view counts the companies the person was in *then*: printing today's
    count on a 2015 graph would be a number nothing in the data supports.
    """
    relations = list(
        PersonCompanyRelation.objects.filter(person_id__in=member_ids)
    )
    if as_of is not None:
        relations = [rel for rel in relations if _in_force_at(rel, as_of)]
    return len({rel.company_id for rel in relations})


def _can_fuse(entry, members) -> bool:
    """Whether these rows may be drawn as the person `entry` already holds.

    The two guards `cluster_evidence` refuses a join on, applied to the fold the
    graph does by name: rows stating two different birth dates, or two different
    person IČOs, are not one human however their names read. Without this, the
    drawing fix would quietly undo the only evidence in the table that can
    *refute* a merge -- which is the one thing `cluster_evidence` says that
    evidence is good for.
    """
    dates = {m.birth_date for m in members if m.birth_date}
    icos = {m.person_ico for m in members if m.person_ico}
    return len(entry["dates"] | dates) <= 1 and len(entry["icos"] | icos) <= 1


def _company_person_groups(relations):
    """One entry per human this company's relations describe.

    Clustering already gathers the rows one register document wrote twice --
    which is 84 % of the duplication -- but it refuses to when two of them carry
    two different postal codes, because then they *may* be two people. That
    refusal is right about the evidence and wrong on the screen: the two rows
    carry the same name, so the graph draws one person twice and the reader has
    no way to tell a duplicate from a colleague who happens to share the name.

    So this folds the clusters by base name inside one company anyway, and
    **discloses** what it folded -- `clusters` and `records` travel in the
    payload -- rather than hiding it. Measured on production 2026-09-28 over 300
    companies holding officers: 12 companies (4.0 %) hold a name this splits,
    21 duplicate labels in all. One of them, `00007838 Rudné bane, š.p.`, is
    František Pramuka written once at `Poráč 053 23` and once at `Spišská Nová
    Ves 052 01`, the second tenure starting a month after the first ended --
    a person who moved, not two people.

    What it will not fold is two rows that can be shown to be different people:
    see `_can_fuse`. Those keep a node each, which is the register's own answer.

    `relations` is what the caller decided to draw, in the order it wants them;
    the entries come back in that order.
    """
    clusters, _by_id = _resolve([rel.person for rel in relations])
    cluster_of = {row.id: members for members in clusters for row in members}

    entries = defaultdict(list)
    ordered = []
    for rel in relations:
        members = cluster_of[rel.person.id]
        primary = members[0]
        # Keyed on the base name, so `Ing. Miroslav Trnka` and `Miroslav Trnka`
        # are one person -- the same fold `cluster_evidence` rule 1 makes. A row
        # whose name is empty has no base name, and stays its own node rather
        # than joining every other nameless row in the company.
        key = primary.base or f"row:{primary.id}"
        entry = next((e for e in entries[key] if _can_fuse(e, members)), None)
        if entry is None:
            entry = {
                "members": {}, "clusters": [], "rows": [],
                "dates": set(), "icos": set(),
            }
            entries[key].append(entry)
            ordered.append(entry)
        if members not in entry["clusters"]:
            entry["clusters"].append(members)
        for member in members:
            entry["members"][member.id] = member
            if member.birth_date:
                entry["dates"].add(member.birth_date)
            if member.person_ico:
                entry["icos"].add(member.person_ico)
        entry["rows"].append(rel)

    groups = []
    for entry in ordered:
        members = sorted(entry["members"].values(), key=lambda m: m.id)
        groups.append({
            "primary": members[0],
            "members": members,
            # How many resolver clusters this one drawn person gathered. One is
            # the common case and means nothing; more is the merge this function
            # exists for, and the payload has to say so.
            "clusters": len(entry["clusters"]),
            "rows": entry["rows"],
        })
    return groups


class CompanyGraphView(APIView):
    """`GET /api/companies/<ico>/graph/`, optionally `?as_of=YYYY-MM-DD`.

    Without `as_of` this is the company as it stands now. With it, the same
    graph drawn from the offices in force on that date -- which is why the
    picture can differ completely, and why `meta.as_of` is echoed back.
    """

    permission_classes = [permissions.AllowAny]

    MAX_NODES = 200

    def get(self, request, ico):
        try:
            company = Company.objects.get(ico=ico)
        except Company.DoesNotExist:
            return Response(
                {"detail": "Firma s týmto IČO nebola nájdená."},
                status=status.HTTP_404_NOT_FOUND,
            )

        as_of, error = _parse_as_of(request.query_params.get("as_of"))
        if error:
            return Response(
                {"detail": error}, status=status.HTTP_400_BAD_REQUEST
            )

        nodes = {}
        candidates = []

        company_node_id = f"company_{company.ico}"
        nodes[company_node_id] = {
            "id": company_node_id,
            "type": "company",
            "label": company.nazov_UJ,
            "ico": company.ico,
            "status": "Vymazaná" if company.datum_zrusenia else "Aktívna",
        }

        all_relations, relations, undated = _company_person_relations(company, as_of)

        # The document this company was read from may name one person under two
        # sections, which is two rows and one human. The graph draws people, so
        # it draws the clusters -- one node per person, with every relation's own
        # role still on its own edge.
        #
        # Resolved against the whole table rather than this company's officers
        # alone, because the node id is `members[0].id` and the lowest row id
        # among one company's officers is not the lowest of the human they belong
        # to. Clustering locally gave a person one node id per company that named
        # a different member first, and the client dedups by exact id, so the
        # same human was drawn once per company: measured 2026-09-24 over a
        # 3 000-company sample, 144 humans arrived with more than one node id
        # (`Ing. Andrea Halušková` with four). `_resolve` is the same call the
        # person graph makes, so the two views now agree on the id.
        #
        # One entry per person, not per relation. An office arrives as many rows
        # (#93), so the old shape drew the same edge once per period -- and read
        # that person's other companies once per period too. Measured on
        # FREYSSINET CS: 21 edges of which 9 distinct, one pair twelve times.
        # `_company_person_groups` also folds the same-name clusters the resolver
        # deliberately leaves apart; see there for why, and for what it refuses.
        for group in _company_person_groups(relations):
            primary = group["primary"]
            person_node_id = f"person_{primary.id}"
            member_ids = [m.id for m in group["members"]]

            nodes[person_node_id] = {
                "id": person_node_id,
                "type": "person",
                "label": primary.name,
                "rolesCount": _person_company_count(member_ids, as_of),
                # What stands behind this one drawn person, so a merge is
                # visible rather than silent: `records` is how many register
                # rows it gathered and `clusters` how many of them identity
                # resolution had kept apart. One and one is the common case.
                "records": len(group["members"]),
                "clusters": group["clusters"],
            }

            for rel in group["rows"]:
                candidates.append((
                    person_node_id,
                    company_node_id,
                    rel.get_role_display(),
                    _edge_currency(rel, as_of),
                ))

            if len(nodes) >= self.MAX_NODES:
                break

            other_relations = list(
                PersonCompanyRelation.objects
                .filter(person_id__in=member_ids)
                .exclude(company=company)
                .select_related("company")
            )
            if as_of is not None:
                other_relations = [
                    rel for rel in other_relations if _in_force_at(rel, as_of)
                ]

            for other_rel in other_relations:
                other_company = other_rel.company
                other_node_id = f"company_{other_company.ico}"

                if other_node_id not in nodes:
                    nodes[other_node_id] = {
                        "id": other_node_id,
                        "type": "company",
                        "label": other_company.nazov_UJ,
                        "ico": other_company.ico,
                        "status": "Vymazaná" if other_company.datum_zrusenia else "Aktívna",
                    }

                candidates.append((
                    person_node_id,
                    other_node_id,
                    other_rel.get_role_display(),
                    _edge_currency(other_rel, as_of),
                ))

                if len(nodes) >= self.MAX_NODES:
                    break

            if len(nodes) >= self.MAX_NODES:
                break

        return Response({
            "nodes": list(nodes.values()),
            "edges": _edges_by_identity(candidates),
            "meta": {
                "center_node": company_node_id,
                "depth": 1,
                "total_nodes": len(nodes),
                "truncated": len(nodes) >= self.MAX_NODES,
                # The period the picture shows, echoed back so a cached or
                # hand-made request cannot be read as the current company.
                "as_of": as_of.isoformat() if as_of else None,
                # Which periods are worth offering. Computed from the whole
                # record and not from what was drawn, so the control does not
                # change shape when one of its own options is chosen.
                "periods": _period_years(all_relations, timezone.localdate()),
                # Relations the period asked for could not place, because the
                # register never stated when they began. Counted and sent rather
                # than silently dropped: a graph that quietly loses an officer
                # looks exactly like a company that never had one.
                "undated_excluded": undated,
            },
        })


class CompanyPersonsView(APIView):
    """`GET /api/companies/<ico>/persons/` -- the company's people, over time.

    The register's extract, and the Osoby cards built from it, show the bodies
    as they stand today. Everyone who held an office before is in the same
    stored relations -- the extractor keeps them and marks them ended
    (`is_active = False`) -- and until now nothing read them.

    Grouped by the same helper and from the same rows as `CompanyGraphView`, so
    the list and the graph cannot disagree about who is in the company, about
    how many register rows one person stands for, or about how many filings one
    tenure was folded from.

    `?as_of=YYYY-MM-DD` asks the graph's period question: who was in force then.
    Without it the answer is everyone we hold, which is the whole record this
    screen exists to show.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request, ico):
        try:
            company = Company.objects.get(ico=ico)
        except Company.DoesNotExist:
            return Response(
                {"detail": "Firma s týmto IČO nebola nájdená."},
                status=status.HTTP_404_NOT_FOUND,
            )

        as_of, error = _parse_as_of(request.query_params.get("as_of"))
        if error:
            return Response(
                {"detail": error}, status=status.HTTP_400_BAD_REQUEST
            )

        all_relations, relations, undated = _company_person_relations(company, as_of)

        groups = []
        for group in _company_person_groups(relations):
            members = group["members"]
            by_row = defaultdict(list)
            for rel in group["rows"]:
                by_row[rel.person_id].append(_office_payload(rel))
            groups.append({
                "id": members[0].id,
                "name": members[0].name,
                # How many register rows this one person gathered, and how many
                # of them identity resolution had kept apart -- the same two
                # disclosures the graph node carries, in the place where the
                # reader can act on them.
                "records": len(members),
                "clusters": group["clusters"],
                # The rows behind the grouping, with the evidence each one
                # carries. Not decoration: the grouping is a judgement about
                # identity, and one that is wrong has to be visible to the reader
                # it is wrong about. `birth_date` stays per row for the same
                # reason `PersonDetailView` keeps it there -- rows stating two
                # different dates are the one case this must not present as one
                # person, and `_can_fuse` is what keeps them apart.
                "members": [
                    {
                        "id": member.id,
                        "name": member.name,
                        "address": member.address,
                        "birth_date": member.birth_date,
                    }
                    for member in members
                ],
                "offices": _merged_relations(
                    [m.id for m in members], by_row
                ),
            })

        return Response({
            "ico": company.ico,
            "name": company.nazov_UJ,
            "as_of": as_of.isoformat() if as_of else None,
            "groups": groups,
            "periods": _period_years(all_relations, timezone.localdate()),
            "undated_excluded": undated,
        })


class PersonSearchView(APIView):
    """`GET /api/persons/?q=` -- the question the register cannot answer well.

    The register's own person search is diacritics-exact and current-records
    only: typing `novak` there returns nothing, and a person who left a company
    in 2019 is not in it at all. Ours searches a normalised column, so `kovac`
    finds `Kováč`, and it reads the relations we hold with their dates.

    One answer per person, not per row. The register renders the same officer
    under two sections of one document, which our extractor stores as two rows --
    so before this grouped them, searching `vacha` answered with the same man
    three times. The rows are still all there and each result says how many it
    gathered; see `connections.identity` for why they are grouped at read time
    rather than merged.

    What it does not do is pretend to be complete. Every response carries the
    coverage counts, because 19 906 companies out of 445 626 means most names
    return nothing -- and a search that returns an empty list without saying
    why reads as "this person is in no company", which is a different and
    false claim.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        query = (request.query_params.get("q") or "").strip()
        role = (request.query_params.get("role") or "").strip()

        if len(query) < MIN_QUERY_LENGTH:
            return Response({
                "query": query,
                "results": [],
                "total_matches": 0,
                "total_people": None,
                "truncated": False,
                "detail": (
                    f"Zadajte aspoň {MIN_QUERY_LENGTH} znaky."
                    if query else "Zadajte meno na vyhľadanie."
                ),
                "coverage": _coverage(),
            })

        # A person with no relation is not a search result: the question is
        # "in which companies does this name figure", and a name with no
        # companies is an answer we have nothing to say about.
        matches = Q(company_relations__isnull=False)
        if role:
            matches &= Q(company_relations__role=role)

        # Every token must appear somewhere in the normalised name, in any
        # order -- so `trnka miroslav` and `miroslav trnka` are one search, and
        # a title the register keeps attached ("Ing.") does not hide the person
        # from someone who leaves it out.
        persons = Person.objects.filter(matches)
        for token in normalize_name(query).split():
            persons = persons.filter(name_normalized__contains=token)

        persons = persons.distinct()

        total = persons.count()
        window = list(persons.order_by("name", "id")[:CLUSTER_SCAN_LIMIT])
        clusters, by_id = _cluster_persons(window)
        shown = clusters[:MAX_PERSON_RESULTS]

        grouped = _relations_by_person(
            [m.id for members in shown for m in members], role
        )

        results = []
        for members in shown:
            primary = by_id[members[0].id]
            results.append({
                "id": primary.id,
                "name": primary.name,
                "title": primary.title,
                "person_ico": primary.person_ico,
                # How many stored rows this one answer gathered. One for the
                # common case; more is the register having written the same
                # person twice, and saying so is what keeps the grouping honest.
                "records": len(members),
                "companies": _merged_relations([m.id for m in members], grouped),
            })

        return Response({
            "query": query,
            "role": role,
            "results": results,
            "total_matches": total,
            # `null` when the window stopped short of the match count: how many
            # distinct people are in the part we did not read is not something
            # this can know, and reporting the count it saw would be a smaller
            # number dressed as an answer. Same distinction as `coverage`.
            "total_people": len(clusters) if len(window) == total else None,
            "truncated": len(window) < total or len(clusters) > MAX_PERSON_RESULTS,
            "coverage": _coverage(),
        })


class PersonDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, pk):
        try:
            person = Person.objects.get(pk=pk)
        except Person.DoesNotExist:
            return Response(
                {"detail": "Osoba nebola nájdená."},
                status=status.HTTP_404_NOT_FOUND,
            )

        members, by_id = _cluster_for(person)
        member_ids = [m.id for m in members]

        return Response({
            "id": person.id,
            "name": person.name,
            "title": person.title,
            "person_ico": person.person_ico,
            "records": len(members),
            # The rows this page merged, with the evidence each one carries. Not
            # decoration: the grouping is a judgement about identity, and one
            # that is wrong has to be visible to the reader it is wrong about.
            # `birth_date` is per row rather than merged into one answer at the
            # top, because rows that state two different dates are the one case
            # this page must not present as one person.
            "members": [
                {
                    "id": member.id,
                    "name": by_id[member.id].name,
                    "address": by_id[member.id].address,
                    "birth_date": by_id[member.id].birth_date,
                }
                for member in members
            ],
            "companies": _merged_relations(
                member_ids, _relations_by_person(member_ids)
            ),
            # Observations about the person's company footprint -- never a
            # verdict about the person. See `person_risk.py` and §11.22.2: the
            # register holds "konateľ v 14 firmách, z toho 5 zrušených", which is
            # a fact with dates, and cannot hold "biely kôň", which is a claim.
            # Computed over `member_ids`, not `person.id`: the cluster is the
            # unit, or the counts would be of our rows rather than of a life.
            "red_flags": person_red_flags(member_ids),
            "coverage": _coverage(),
        })


class OrsrPersonSearchView(APIView):
    """`GET /api/persons/orsr/?q=` -- the register's own answer, on request.

    This is the one place a reader's typing reaches a third-party server, so it
    is deliberately the narrowest thing that is still useful:

    * **one** request per query (two when the query had diacritics the register
      would have rejected), never a pagination walk;
    * cached for `ORSR_PERSON_CACHE_SECONDS`, which removes nearly all repeat
      traffic;
    * rate-limited per caller, because the input is free text typed by anyone;
    * it returns the register's answer as the register gives it, including the
      fact that it does not say in what capacity the person is recorded --
      that would cost one request per company, and we do not spend other
      people's server budget to decorate a list.

    The register has no API and no bulk export; this is a form. That is the
    reason the button exists rather than a scheduled sync keyed on a name.
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [OrsrPersonThrottle]

    def get(self, request):
        query = (request.query_params.get("q") or "").strip()
        if len(query) < MIN_QUERY_LENGTH:
            return Response({
                "query": query,
                "hits": [],
                "total": 0,
                "detail": f"Zadajte aspoň {MIN_QUERY_LENGTH} znaky.",
            })

        cache_key = f"orsr_person_search:{normalize_name(query)}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response({**cached, "cached": True})

        from registers.scrapers.orsr_person_search import OrsrPersonSearch

        result = OrsrPersonSearch().search(query)

        payload = {
            "query": query,
            "hits": [hit.as_dict() for hit in result.hits],
            "total": result.total,
            "truncated": result.truncated,
            "source_url": result.source_url,
            "error": result.error,
            # Said out loud because the register's list looks like ours and is
            # not: it names companies, never the capacity, and covers current
            # records only.
            "note": (
                "Register vracia len mená firiem, nie funkciu — na to by bol "
                "jeden výpis pre každú firmu. Ukazuje tiež len aktuálne záznamy."
            ),
        }

        if not result.error:
            cache.set(cache_key, payload, settings.ORSR_PERSON_CACHE_SECONDS)

        return Response(payload)


class PersonGraphView(APIView):
    permission_classes = [permissions.AllowAny]

    MAX_NODES = 200

    def get(self, request, pk):
        try:
            person = Person.objects.get(pk=pk)
        except Person.DoesNotExist:
            return Response(
                {"detail": "Osoba nebola nájdená."},
                status=status.HTTP_404_NOT_FOUND,
            )

        members, _by_id = _cluster_for(person)
        member_ids = [m.id for m in members]

        # The cluster's own first row stands for the person, not the row that was
        # asked for. `_cluster_for` resolves against the whole table, so this is
        # the same id the company graph draws for this human -- and the client
        # keys nodes on that id, so a graph that starts at a person and expands
        # into a company that also names them must not open a second node for
        # them. Keying on `person.id` did exactly that whenever the requested row
        # was not the cluster's lowest.
        primary = members[0]

        nodes = {}
        edges = []

        person_node_id = f"person_{primary.id}"
        company_count = (
            PersonCompanyRelation.objects
            .filter(person_id__in=member_ids)
            .values("company")
            .distinct()
            .count()
        )
        nodes[person_node_id] = {
            "id": person_node_id,
            "type": "person",
            "label": primary.name,
            "rolesCount": company_count,
        }

        relations = (
            PersonCompanyRelation.objects
            .filter(person_id__in=member_ids)
            .select_related("company")
        )

        for rel in relations:
            company = rel.company
            company_node_id = f"company_{company.ico}"

            if company_node_id not in nodes:
                nodes[company_node_id] = {
                    "id": company_node_id,
                    "type": "company",
                    "label": company.nazov_UJ,
                    "ico": company.ico,
                    "status": "Vymazaná" if company.datum_zrusenia else "Aktívna",
                }

            edges.append({
                "source": person_node_id,
                "target": company_node_id,
                "role": rel.get_role_display(),
                "isActive": rel.is_active,
            })

            if len(nodes) >= self.MAX_NODES:
                break

        return Response({
            "nodes": list(nodes.values()),
            "edges": edges,
            "meta": {
                "center_node": person_node_id,
                "depth": 1,
                "total_nodes": len(nodes),
                "truncated": len(nodes) >= self.MAX_NODES,
            },
        })
