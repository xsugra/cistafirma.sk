import logging
from collections import defaultdict
from datetime import date

from django.conf import settings
from django.core.cache import cache
from django.db.models import F, Q
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from companies.models import Company
from companies.throttles import OrsrPersonThrottle
from .identity import PersonEvidence, base_name, cluster_evidence
from .models import Person, PersonCompanyRelation, normalize_name

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

#: Rows read to find the people one row belongs to, for the person page and the
#: graphs. Also a bound, and also a disclosed under-merge: it can leave a
#: sibling out, never pull a stranger in.
CLUSTER_CANDIDATE_LIMIT = 500


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
        )
        for person in persons
    )
    return clusters, by_id


def _cluster_for(person):
    """The rows we believe are the same human as `person`.

    Candidates are found the way search finds them -- every token of the name
    has to appear -- and `base_name` equality then does the rest, because the
    title is not part of a name and `name_normalized` keeps it.
    """
    tokens = base_name(person.name).split()
    if not tokens:
        return [PersonEvidence(
            id=person.id, name=person.name, address=person.address,
            person_ico=person.person_ico,
        )], {person.id: person}

    candidates = Person.objects.all()
    for token in tokens:
        candidates = candidates.filter(name_normalized__contains=token)
    rows = list(candidates.order_by("id")[:CLUSTER_CANDIDATE_LIMIT])
    if all(row.id != person.id for row in rows):
        rows.append(person)

    base = base_name(person.name)
    rows = [row for row in rows if base_name(row.name) == base]

    clusters, by_id = _cluster_persons(rows)
    for members in clusters:
        if any(m.id == person.id for m in members):
            return members, by_id
    return [PersonEvidence(
        id=person.id, name=person.name, address=person.address,
        person_ico=person.person_ico,
    )], by_id


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
    showed the pair. Dated relations are never collapsed into each other, so a
    real second tenure survives.
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
    return [
        item for item in merged
        if item["vznik_funkcie"] or item["zanik_funkcie"]
        or (item["ico"], item["role"]) not in dated_offices
    ]


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


class CompanyGraphView(APIView):
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

        relations = list(
            PersonCompanyRelation.objects
            .filter(company=company)
            .select_related("person")
        )

        # The document this company was read from may name one person under two
        # sections, which is two rows and one human. The graph draws people, so
        # it draws the clusters -- one node per person, with every relation's own
        # role still on its own edge.
        clusters, _by_id = _cluster_persons(
            [rel.person for rel in relations]
        )
        cluster_of = {row.id: members for members in clusters for row in members}

        # One iteration per person, not per relation. An office arrives as many
        # rows (#93), so the old shape drew the same edge once per period -- and
        # read that person's other companies once per period too. Measured on
        # FREYSSINET CS: 21 edges of which 9 distinct, one pair twelve times.
        by_person = {}
        for rel in relations:
            members = cluster_of[rel.person.id]
            primary = members[0]
            by_person.setdefault(primary.id, (members, []))[1].append(rel)

        for members, rows in by_person.values():
            primary = members[0]
            person_node_id = f"person_{primary.id}"
            member_ids = [m.id for m in members]

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

            for rel in rows:
                candidates.append((
                    person_node_id,
                    company_node_id,
                    rel.get_role_display(),
                    rel.is_active,
                ))

            if len(nodes) >= self.MAX_NODES:
                break

            other_relations = (
                PersonCompanyRelation.objects
                .filter(person_id__in=member_ids)
                .exclude(company=company)
                .select_related("company")
            )

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
                    other_rel.is_active,
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
            },
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
            # The rows this page merged, with the address each one carries. Not
            # decoration: the grouping is a judgement about identity, and one
            # that is wrong has to be visible to the reader it is wrong about.
            "members": [
                {
                    "id": member.id,
                    "name": by_id[member.id].name,
                    "address": by_id[member.id].address,
                }
                for member in members
            ],
            "companies": _merged_relations(
                member_ids, _relations_by_person(member_ids)
            ),
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

        nodes = {}
        edges = []

        person_node_id = f"person_{person.id}"
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
            "label": person.name,
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
