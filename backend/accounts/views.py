from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.core.mail import send_mail
from django.db.models import Count, Max
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from quotes.models import LookupLog

from .models import FavoriteCompany, PageView, PasswordResetToken, SavedList
from .serializers import (
    ChangePasswordSerializer,
    FavoriteCompanySerializer,
    FeedbackSerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    ResetPasswordSerializer,
    SavedListSerializer,
    SignupSerializer,
)

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


class LogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response({"ok": True})


@method_decorator(ensure_csrf_cookie, name="dispatch")
class MeView(APIView):
    def get(self, request):
        if not request.user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        return Response({
            "email": request.user.email,
            "is_superuser": request.user.is_superuser,
            "date_joined": request.user.date_joined,
        })


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if not request.user.check_password(serializer.validated_data["current_password"]):
            return Response(
                {"error": "Senha atual incorreta"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save()
        login(request, request.user)  # Re-login to refresh session
        return Response({"ok": True})


class ForgotPasswordView(APIView):
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]

        # Always return success to avoid leaking whether email exists
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"ok": True})

        token_obj = PasswordResetToken.create_for_user(user)

        base_url = getattr(settings, "SITE_BASE_URL", "https://sponda.poe.ma")
        reset_url = f"{base_url}/reset-password?token={token_obj.token}"

        send_mail(
            subject="Sponda — Recuperação de senha",
            message=f"Olá,\n\nClique no link abaixo para redefinir sua senha:\n\n{reset_url}\n\nEste link expira em 24 horas.\n\nSe você não solicitou, ignore este email.\n\n— Sponda",
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@sponda.capital"),
            recipient_list=[email],
            fail_silently=True,
        )

        return Response({"ok": True})


class ResetPasswordView(APIView):
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            token_obj = PasswordResetToken.objects.select_related("user").get(
                token=serializer.validated_data["token"]
            )
        except PasswordResetToken.DoesNotExist:
            return Response(
                {"error": "Link inválido ou expirado"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not token_obj.is_valid:
            return Response(
                {"error": "Link inválido ou expirado"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token_obj.user.set_password(serializer.validated_data["password"])
        token_obj.user.save()
        token_obj.used = True
        token_obj.save()

        return Response({"ok": True})


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


# ── Favorites ──


class FavoriteListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        favorites = FavoriteCompany.objects.filter(user=request.user)
        serializer = FavoriteCompanySerializer(favorites, many=True)
        return Response(serializer.data)

    def post(self, request):
        ticker = request.data.get("ticker", "").upper()
        if not ticker:
            return Response(
                {"error": "Ticker é obrigatório"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        _, created = FavoriteCompany.objects.get_or_create(
            user=request.user, ticker=ticker
        )
        if not created:
            return Response(
                {"error": "Empresa já está nos favoritos"},
                status=status.HTTP_409_CONFLICT,
            )

        return Response({"ticker": ticker}, status=status.HTTP_201_CREATED)


class FavoriteDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, ticker):
        ticker = ticker.upper()
        deleted, _ = FavoriteCompany.objects.filter(
            user=request.user, ticker=ticker
        ).delete()
        if not deleted:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Saved Lists ──


class SavedListListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        saved_lists = SavedList.objects.filter(user=request.user)
        serializer = SavedListSerializer(saved_lists, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = SavedListSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        saved_list = SavedList.objects.create(
            user=request.user,
            name=serializer.validated_data["name"],
            tickers=serializer.validated_data["tickers"],
            years=serializer.validated_data.get("years", 10),
            share_token=SavedList.generate_share_token(),
        )

        return Response(
            SavedListSerializer(saved_list).data,
            status=status.HTTP_201_CREATED,
        )


class SavedListDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        try:
            saved_list = SavedList.objects.get(user=request.user, pk=pk)
        except SavedList.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = SavedListSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        if "tickers" in serializer.validated_data:
            saved_list.tickers = serializer.validated_data["tickers"]
        if "years" in serializer.validated_data:
            saved_list.years = serializer.validated_data["years"]
        if "name" in serializer.validated_data:
            saved_list.name = serializer.validated_data["name"]

        saved_list.save()
        return Response(SavedListSerializer(saved_list).data)

    def delete(self, request, pk):
        deleted, _ = SavedList.objects.filter(
            user=request.user, pk=pk
        ).delete()
        if not deleted:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SharedListView(APIView):
    """Public view for shared list links — no auth required."""

    def get(self, request, token):
        try:
            saved_list = SavedList.objects.select_related("user").get(
                share_token=token
            )
        except SavedList.DoesNotExist:
            return Response(
                {"error": "Lista não encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response({
            "name": saved_list.name,
            "tickers": saved_list.tickers,
            "years": saved_list.years,
            "shared_by": saved_list.user.email,
            "created_at": saved_list.created_at,
        })


# ── Feedback ──


class FeedbackView(APIView):
    EXPECTED_ANSWER = 7  # "What is 3 + 4?"

    def post(self, request):
        serializer = FeedbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if serializer.validated_data["human_check"] != self.EXPECTED_ANSWER:
            return Response(
                {"error": "Resposta incorreta à verificação"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = serializer.validated_data["email"]
        message = serializer.validated_data["message"]

        feedback_recipient = getattr(
            settings, "FEEDBACK_EMAIL", "gustavo@poe.ma"
        )

        send_mail(
            subject=f"Sponda Feedback de {email}",
            message=f"De: {email}\n\n{message}",
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@sponda.capital"),
            recipient_list=[feedback_recipient],
            fail_silently=True,
        )

        return Response({"ok": True}, status=status.HTTP_201_CREATED)


# ── Google OAuth ──


class GoogleAuthView(APIView):
    """Exchange a Google OAuth authorization code for a session."""

    def post(self, request):
        # This requires GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in settings
        google_client_id = getattr(settings, "GOOGLE_CLIENT_ID", None)
        google_client_secret = getattr(settings, "GOOGLE_CLIENT_SECRET", None)

        if not google_client_id or not google_client_secret:
            return Response(
                {"error": "Google auth not configured"},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )

        code = request.data.get("code")
        redirect_uri = request.data.get("redirect_uri")
        if not code or not redirect_uri:
            return Response(
                {"error": "Missing code or redirect_uri"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        import requests as http_requests

        # Exchange code for tokens
        token_response = http_requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": google_client_id,
                "client_secret": google_client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=10,
        )

        if token_response.status_code != 200:
            return Response(
                {"error": "Failed to exchange code"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token_data = token_response.json()
        id_token = token_data.get("id_token")

        if not id_token:
            return Response(
                {"error": "No id_token received"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Decode the ID token (Google's tokeninfo endpoint validates it)
        info_response = http_requests.get(
            f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token}",
            timeout=10,
        )

        if info_response.status_code != 200:
            return Response(
                {"error": "Invalid token"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        info = info_response.json()
        email = info.get("email")

        if not email:
            return Response(
                {"error": "No email in token"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Find or create user
        user, created = User.objects.get_or_create(
            email=email,
            defaults={"username": email},
        )

        login(request, user)
        return Response({
            "email": user.email,
            "created": created,
        })


# ── Admin Analytics Dashboard ──


def _time_boundaries():
    """Return cutoff timestamps for day, week, month, year."""
    now = timezone.now()
    return {
        "day": now - timezone.timedelta(days=1),
        "week": now - timezone.timedelta(weeks=1),
        "month": now - timezone.timedelta(days=30),
        "year": now - timezone.timedelta(days=365),
    }


class AdminDashboardView(APIView):
    """Super-admin analytics endpoint. Returns users, page views, and usage stats."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        boundaries = _time_boundaries()

        return Response({
            "users": self._get_user_stats(boundaries),
            "page_views": self._get_page_view_stats(boundaries),
            "top_pages": self._get_top_pages(boundaries),
            "top_tickers": self._get_top_tickers(boundaries),
            "signup_stats": self._get_signup_stats(boundaries),
            "favorites_count": FavoriteCompany.objects.count(),
            "saved_lists_count": SavedList.objects.count(),
        })

    def _get_user_stats(self, boundaries):
        """List all users with email, last login, and visit counts per period."""
        users = User.objects.all().order_by("-last_login")
        user_list = []

        for user in users:
            visit_counts = {}
            for period_name, cutoff in boundaries.items():
                visit_counts[period_name] = PageView.objects.filter(
                    user=user, timestamp__gte=cutoff
                ).count()

            lookup_counts = {}
            for period_name, cutoff in boundaries.items():
                lookup_counts[period_name] = LookupLog.objects.filter(
                    user=user, timestamp__gte=cutoff
                ).count()

            user_list.append({
                "email": user.email,
                "date_joined": user.date_joined,
                "last_login": user.last_login,
                "allow_contact": user.allow_contact,
                "is_superuser": user.is_superuser,
                "page_views": visit_counts,
                "lookups": lookup_counts,
                "favorites_count": user.favorites.count(),
                "saved_lists_count": user.saved_lists.count(),
            })

        return user_list

    def _get_page_view_stats(self, boundaries):
        """Total page views and unique visitors per period."""
        stats = {}
        for period_name, cutoff in boundaries.items():
            period_views = PageView.objects.filter(timestamp__gte=cutoff)
            stats[period_name] = {
                "total_views": period_views.count(),
                "unique_visitors": period_views.values("ip_hash").distinct().count(),
                "authenticated_views": period_views.exclude(user=None).count(),
                "anonymous_views": period_views.filter(user=None).count(),
            }
        stats["all_time"] = {
            "total_views": PageView.objects.count(),
            "unique_visitors": PageView.objects.values("ip_hash").distinct().count(),
        }
        return stats

    def _get_top_pages(self, boundaries):
        """Most visited pages in the last month."""
        month_cutoff = boundaries["month"]
        return list(
            PageView.objects.filter(timestamp__gte=month_cutoff)
            .values("path")
            .annotate(view_count=Count("id"))
            .order_by("-view_count")[:20]
        )

    def _get_top_tickers(self, boundaries):
        """Most looked-up tickers per period."""
        stats = {}
        for period_name, cutoff in boundaries.items():
            stats[period_name] = list(
                LookupLog.objects.filter(timestamp__gte=cutoff)
                .values("ticker")
                .annotate(lookup_count=Count("id"))
                .order_by("-lookup_count")[:10]
            )
        return stats

    def _get_signup_stats(self, boundaries):
        """New user signups per period."""
        stats = {}
        for period_name, cutoff in boundaries.items():
            stats[period_name] = User.objects.filter(date_joined__gte=cutoff).count()
        stats["total"] = User.objects.count()
        return stats
