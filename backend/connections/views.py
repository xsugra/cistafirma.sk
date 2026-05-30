from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from companies.models import Company
from .models import Person, PersonCompanyRelation


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
            .order_by("-is_active", "-vznik_funkcie")
        )

        return Response({
            "id": person.id,
            "name": person.name,
            "title": person.title,
            "person_ico": person.person_ico,
            "companies": [
                {
                    "ico": rel.company.ico,
                    "name": rel.company.nazov_UJ,
                    "role": rel.get_role_display(),
                    "role_display": rel.role_display,
                    "is_active": rel.is_active,
                    "vznik_funkcie": rel.vznik_funkcie,
                    "zanik_funkcie": rel.zanik_funkcie,
                }
                for rel in relations
            ],
        })


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
