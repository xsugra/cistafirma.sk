from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import authenticate, login
from .serializers import UserRegistrationSerializer, UserDetailSerializer


# 1. Registrácia
class RegisterView(generics.CreateAPIView):
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]


# 2. Login (Session based pre začiatok, alebo JWT)
@csrf_exempt
class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # Frontend pošle 'username' (čo môže byť email) a 'password'
        username_or_email = request.data.get('username')
        password = request.data.get('password')

        # Náš custom backend v backends.py toto spracuje
        user = authenticate(
            request,
            username=username_or_email,
            password=password
        )

        if user is not None:
            login(request, user)
            return Response(UserDetailSerializer(user).data)
        else:
            return Response(
                {"error": "Nesprávne údaje"},
                status=status.HTTP_401_UNAUTHORIZED
            )


# 3. Profil Užívateľa (Zobrazenie + Update)
class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        # Vráti profil aktuálne prihláseného užívateľa
        return self.request.user
