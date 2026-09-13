from django.urls import path

from .views import (
    CompanyGraphView,
    OrsrPersonSearchView,
    PersonDetailView,
    PersonGraphView,
    PersonSearchView,
)

urlpatterns = [
    path("companies/<str:ico>/graph/", CompanyGraphView.as_view(), name="company-graph"),
    # `persons/orsr/` must precede `persons/<int:pk>/`... it does not need to,
    # since "orsr" is not an int and the int converter will not match it -- but
    # it is listed here so the pair reads as the two halves of one answer.
    path("persons/", PersonSearchView.as_view(), name="person-search"),
    path("persons/orsr/", OrsrPersonSearchView.as_view(), name="person-orsr-search"),
    path("persons/<int:pk>/", PersonDetailView.as_view(), name="person-detail"),
    path("persons/<int:pk>/graph/", PersonGraphView.as_view(), name="person-graph"),
]
