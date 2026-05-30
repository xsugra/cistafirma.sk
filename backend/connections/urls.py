from django.urls import path

from .views import CompanyGraphView, PersonDetailView, PersonGraphView

urlpatterns = [
    path("companies/<str:ico>/graph/", CompanyGraphView.as_view(), name="company-graph"),
    path("persons/<int:pk>/", PersonDetailView.as_view(), name="person-detail"),
    path("persons/<int:pk>/graph/", PersonGraphView.as_view(), name="person-graph"),
]
