import logging

from django.conf import settings
from django.core.cache import cache
from django.db.models import F, Q
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from companies.models import Company
from companies.throttles import OrsrPersonThrottle
from .models import Person, PersonCompanyRelation, normalize_name

logger = logging.getLogger(__name__)

#: Enough to see the shape of an answer without becoming a way to enumerate
#: the graph. A common surname matches thousands of people in this database.
MAX_PERSON_RESULTS = 50
MIN_QUERY_LENGTH = 2


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
        edges = []

        company_node_id = f"company_{company.ico}"
        nodes[company_node_id] = {
            "id": company_node_id,
            "type": "company",
            "label": company.nazov_UJ,
            "ico": company.ico,
            "status": "Vymazaná" if company.datum_zrusenia else "Aktívna",
        }

        relations = (
            PersonCompanyRelation.objects
            .filter(company=company)
            .select_related("person")
        )

        for rel in relations:
            person = rel.person
            person_node_id = f"person_{person.id}"

            if person_node_id not in nodes:
                company_count = (
                    person.company_relations
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

            edges.append({
                "source": person_node_id,
                "target": company_node_id,
                "role": rel.get_role_display(),
                "isActive": rel.is_active,
            })

            if len(nodes) >= self.MAX_NODES:
                break

            other_relations = (
                PersonCompanyRelation.objects
                .filter(person=person)
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

                edges.append({
                    "source": person_node_id,
                    "target": other_node_id,
                    "role": other_rel.get_role_display(),
                    "isActive": other_rel.is_active,
                })

                if len(nodes) >= self.MAX_NODES:
                    break

            if len(nodes) >= self.MAX_NODES:
                break

        return Response({
            "nodes": list(nodes.values()),
            "edges": edges,
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
        persons = persons.order_by("name", "id")[:MAX_PERSON_RESULTS]

        results = []
        for person in persons:
            person_relations = (
                PersonCompanyRelation.objects
                .filter(person=person)
                .select_related("company")
                .order_by(F("is_active").desc(nulls_last=True), "-vznik_funkcie")
            )
            if role:
                person_relations = person_relations.filter(role=role)

            results.append({
                "id": person.id,
                "name": person.name,
                "title": person.title,
                "person_ico": person.person_ico,
                "companies": [_relation_payload(rel) for rel in person_relations],
            })

        return Response({
            "query": query,
            "role": role,
            "results": results,
            "total_matches": total,
            "truncated": total > len(results),
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

        relations = (
            PersonCompanyRelation.objects
            .filter(person=person)
            .select_related("company")
            # Unknown (`null`) sorts last rather than first: in Postgres a
            # descending sort puts nulls first, which would open the list with
            # the rows we know least about.
            .order_by(F("is_active").desc(nulls_last=True), "-vznik_funkcie")
        )

        return Response({
            "id": person.id,
            "name": person.name,
            "title": person.title,
            "person_ico": person.person_ico,
            "companies": [_relation_payload(rel) for rel in relations],
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

        nodes = {}
        edges = []

        person_node_id = f"person_{person.id}"
        company_count = (
            person.company_relations
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
            .filter(person=person)
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
