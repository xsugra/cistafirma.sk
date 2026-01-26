# users/urls.py
from django.urls import path
from .views import RegisterView, \
    UserProfileView  # LoginView možno nebudeme potrebovať, ak použijeme TokenObtainPairView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),

    # Tu sme doplnili chýbajúci view:
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    path('profile/', UserProfileView.as_view(), name='profile'),
]