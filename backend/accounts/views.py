from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from quotes.models import LookupLog

from .serializers import LoginSerializer, SignupSerializer

User = get_user_model()


class SignupView(APIView):
    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        login(request, user)
        return Response(
            {"email": user.email}, status=status.HTTP_201_CREATED
        )


class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            request,
            username=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        if user is None:
            return Response(
                {"error": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        login(request, user)
        return Response({"email": user.email})


class QuotaView(APIView):
    def get(self, request):
        limit = settings.SPONDA_FREE_LOOKUPS_PER_DAY
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

        if request.user.is_authenticated:
            used = LookupLog.objects.filter(
                user=request.user, timestamp__gte=today_start
            ).count()
        else:
            session_key = request.session.session_key
            if not session_key:
                used = 0
            else:
                used = LookupLog.objects.filter(
                    session_key=session_key, timestamp__gte=today_start
                ).count()

        return Response({
            "limit": limit,
            "used": used,
            "remaining": max(0, limit - used),
            "authenticated": request.user.is_authenticated,
        })
