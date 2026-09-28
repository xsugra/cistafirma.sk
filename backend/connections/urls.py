from django.urls import path

from .views import (
    CompanyGraphView,
    CompanyPersonsView,
    OrsrPersonSearchView,
    PersonDetailView,
    PersonGraphView,
    PersonSearchView,
)

urlpatterns = [
    path("companies/<str:ico>/graph/", CompanyGraphView.as_view(), name="company-graph"),
    # The people of one company, with the history the graph's period control
    # shows on the canvas. `?as_of=YYYY-MM-DD` is the same period, asked of a
    # list instead of a picture.
    path("companies/<str:ico>/persons/", CompanyPersonsView.as_view(), name="company-persons"),
    # `persons/orsr/` must precede `persons/<int:pk>/`... it does not need to,
    # since "orsr" is not an int and the int converter will not match it -- but
    # it is listed here so the pair reads as the two halves of one answer.
    path("persons/", PersonSearchView.as_view(), name="person-search"),
    path("persons/orsr/", OrsrPersonSearchView.as_view(), name="person-orsr-search"),
    path("persons/<int:pk>/", PersonDetailView.as_view(), name="person-detail"),
    path("persons/<int:pk>/graph/", PersonGraphView.as_view(), name="person-graph"),
]
