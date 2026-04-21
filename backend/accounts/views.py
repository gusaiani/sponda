from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.core.mail import send_mail
from django.db import models
from django.template.loader import render_to_string
from django.db.models import Count, IntegerField, OuterRef, Q, Subquery
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from quotes.models import LookupLog

from .branding import POEMA_CTA, POEMA_DISCLAIMER, POEMA_PERFORMANCE_LINE
from .email_subjects import VERIFICATION_SUBJECTS, WELCOME_SUBJECTS, share_strings
from datetime import date, timedelta

from .models import CompanyVisit, EmailVerificationToken, FavoriteCompany, IndicatorAlert, PageView, PasswordResetToken, RevisitSchedule, SavedList, SavedScreenerFilter, SUPPORTED_LANGUAGES, UserOperation
from .serializers import (
    ChangeEmailSerializer,
    ChangePasswordSerializer,
    CompanyVisitSerializer,
    DeleteAccountSerializer,
    FavoriteCompanySerializer,
    FeedbackSerializer,
    ForgotPasswordSerializer,
    IndicatorAlertSerializer,
    LoginSerializer,
    MarkVisitedSerializer,
    ResetPasswordSerializer,
    RevisitScheduleSerializer,
    SavedListSerializer,
    SavedScreenerFilterSerializer,
    SignupSerializer,
    UpdatePreferencesSerializer,
)

User = get_user_model()


def _parse_accept_language(header_value):
    """Pick the highest-q supported locale from an Accept-Language header."""
    if not header_value:
        return "en"
    entries = []
    for piece in header_value.split(","):
        piece = piece.strip()
        if not piece:
            continue
        if ";" in piece:
            tag, *params = piece.split(";")
            quality = 1.0
            for param in params:
                param = param.strip()
                if param.startswith("q="):
                    try:
                        quality = float(param[2:])
                    except ValueError:
                        quality = 0.0
        else:
            tag = piece
            quality = 1.0
        entries.append((quality, tag.strip().lower()))
    entries.sort(key=lambda pair: pair[0], reverse=True)
    for _quality, tag in entries:
        primary = tag.split("-")[0]
        if primary in SUPPORTED_LANGUAGES:
            return primary
    return "en"


class SignupView(APIView):
    def post(self, request):
        fallback_language = _parse_accept_language(request.headers.get("Accept-Language", ""))
        serializer = SignupSerializer(
            data=request.data,
            context={"fallback_language": fallback_language},
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        login(request, user)

        base_url = getattr(settings, "SITE_BASE_URL", "https://sponda.poe.ma")
        _send_welcome_email(user, base_url)
        _send_verification_email(user, base_url)

        return Response(
            {"email": user.email}, status=status.HTTP_201_CREATED
        )


def _resolve_language(user):
    language = getattr(user, "language", None) or "en"
    if language not in SUPPORTED_LANGUAGES:
        language = "en"
    return language


def _send_welcome_email(user, base_url):
    """Send a welcome email in the user's preferred language."""
    language = _resolve_language(user)
    context = {
        "base_url": base_url,
        "poema_performance_line": POEMA_PERFORMANCE_LINE,
        "poema_disclaimer": POEMA_DISCLAIMER,
        "poema_cta": POEMA_CTA,
        **share_strings(language),
    }
    html_message = render_to_string(f"emails/welcome_{language}.html", context)
    plain_message = render_to_string(f"emails/welcome_{language}.txt", context)

    send_mail(
        subject=WELCOME_SUBJECTS[language],
        message=plain_message,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@sponda.capital"),
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=True,
    )


def _send_verification_email(user, base_url):
    """Send email verification link in the user's preferred language."""
    language = _resolve_language(user)
    token_obj = EmailVerificationToken.create_for_user(user)
    verify_url = f"{base_url}/verify-email?token={token_obj.token}"

    context = {"verify_url": verify_url}
    html_message = render_to_string(f"emails/verification_{language}.html", context)
    plain_message = render_to_string(f"emails/verification_{language}.txt", context)

    send_mail(
        subject=VERIFICATION_SUBJECTS[language],
        message=plain_message,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@sponda.capital"),
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=True,
    )




def _check_operation_permission(user):
    """Check if user can perform a write operation. Returns (allowed, error_response_or_none)."""
    allowed, error_message = UserOperation.check_permission(user)
    if not allowed:
        return False, Response(
            {"error": error_message, "verification_required": not user.email_verified},
            status=status.HTTP_403_FORBIDDEN,
        )
    return True, None


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
                {"error": "Email ou senha incorretos"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        login(request, user)
        return Response({"email": user.email})


class LogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response({"ok": True})


class TrackPageView(APIView):
    """Frontend-initiated page view tracking. Works in both dev and prod."""

    def post(self, request):
        path = request.data.get("path", "")
        if not path:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        ip_address = self._get_client_ip(request)
        ip_hash = PageView.hash_ip(ip_address)
        user = request.user if request.user.is_authenticated else None
        session_key = request.session.session_key or ""

        PageView.objects.create(
            path=path,
            ip_hash=ip_hash,
            user=user,
            session_key=session_key,
        )

        return Response({"ok": True}, status=status.HTTP_201_CREATED)

    @staticmethod
    def _get_client_ip(request):
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "0.0.0.0")


@method_decorator(ensure_csrf_cookie, name="dispatch")
class MeView(APIView):
    def get(self, request):
        if not request.user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        return Response({
            "email": request.user.email,
            "is_superuser": request.user.is_superuser,
            "email_verified": request.user.email_verified,
            "date_joined": request.user.date_joined,
            "allow_contact": request.user.allow_contact,
        })


class VerifyEmailView(APIView):
    def post(self, request):
        token_string = request.data.get("token", "")
        if not token_string:
            return Response(
                {"error": "Token é obrigatório"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token_obj = EmailVerificationToken.objects.select_related("user").get(
                token=token_string
            )
        except EmailVerificationToken.DoesNotExist:
            return Response(
                {"error": "Link inválido ou expirado"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not token_obj.is_valid:
            return Response(
                {"error": "Link inválido ou expirado"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token_obj.user.email_verified = True
        token_obj.user.save(update_fields=["email_verified"])
        token_obj.used = True
        token_obj.save(update_fields=["used"])

        return Response({"ok": True})


class ResendVerificationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.email_verified:
            return Response(
                {"error": "Email já verificado"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        base_url = getattr(settings, "SITE_BASE_URL", "https://sponda.poe.ma")
        _send_verification_email(request.user, base_url)

        return Response({"ok": True})


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


class ChangeEmailView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangeEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_email = serializer.validated_data["new_email"].strip().lower()
        password = serializer.validated_data["password"]

        if not request.user.check_password(password):
            return Response(
                {"error": "Senha incorreta"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_email == request.user.email.strip().lower():
            return Response(
                {"error": "O novo email deve ser diferente do atual"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if User.objects.filter(email__iexact=new_email).exclude(pk=request.user.pk).exists():
            return Response(
                {"error": "Já existe uma conta com este email"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        request.user.email = new_email
        request.user.username = new_email
        request.user.email_verified = False
        request.user.save(update_fields=["email", "username", "email_verified"])

        EmailVerificationToken.objects.filter(
            user=request.user, used=False
        ).update(used=True)

        base_url = getattr(settings, "SITE_BASE_URL", "https://sponda.poe.ma")
        _send_verification_email(request.user, base_url)

        return Response({"email": request.user.email, "email_verified": False})


class UpdatePreferencesView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        serializer = UpdatePreferencesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        request.user.allow_contact = serializer.validated_data["allow_contact"]
        request.user.save(update_fields=["allow_contact"])

        return Response({"allow_contact": request.user.allow_contact})


class DeleteAccountView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        serializer = DeleteAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        confirmation = serializer.validated_data["email_confirmation"].strip().lower()
        if confirmation != request.user.email.strip().lower():
            return Response(
                {"error": "Confirmação de email não confere"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        logout(request)
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


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
            subject="Sponda · Recuperação de senha",
            message=f"Olá,\n\nClique no link abaixo para redefinir sua senha:\n\n{reset_url}\n\nEste link expira em 24 horas.\n\nSe você não solicitou, ignore este email.\n\nSponda",
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

    MAX_FAVORITES = 20

    def post(self, request):
        allowed, error_response = _check_operation_permission(request.user)
        if not allowed:
            return error_response

        ticker = request.data.get("ticker", "").upper()
        if not ticker:
            return Response(
                {"error": "Ticker é obrigatório"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not request.user.email_verified:
            current_count = FavoriteCompany.objects.filter(user=request.user).count()
            if current_count >= self.MAX_FAVORITES:
                return Response(
                    {"error": f"Limite de {self.MAX_FAVORITES} favoritos atingido"},
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

        UserOperation.record(request.user, "favorite")
        return Response({"ticker": ticker}, status=status.HTTP_201_CREATED)


class FavoriteDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, ticker):
        allowed, error_response = _check_operation_permission(request.user)
        if not allowed:
            return error_response

        ticker = ticker.upper()
        deleted, _ = FavoriteCompany.objects.filter(
            user=request.user, ticker=ticker
        ).delete()
        if not deleted:
            return Response(status=status.HTTP_404_NOT_FOUND)
        UserOperation.record(request.user, "unfavorite")
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Company Visits ──


class MarkVisitedView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        allowed, error_response = _check_operation_permission(request.user)
        if not allowed:
            return error_response

        serializer = MarkVisitedSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ticker = serializer.validated_data["ticker"].upper()
        note = serializer.validated_data.get("note", "")
        today = date.today()

        visit, _ = CompanyVisit.objects.get_or_create(
            user=request.user,
            ticker=ticker,
            visited_at=today,
            defaults={"note": note},
        )
        if note and not visit.note:
            visit.note = note
            visit.save(update_fields=["note"])

        result = {"visit": CompanyVisitSerializer(visit).data, "schedule": None}

        next_revisit = serializer.validated_data.get("next_revisit")
        recurrence_days = serializer.validated_data.get("recurrence_days")

        if next_revisit:
            schedule, _ = RevisitSchedule.objects.update_or_create(
                user=request.user,
                ticker=ticker,
                defaults={
                    "next_revisit": next_revisit,
                    "recurrence_days": recurrence_days,
                    "share_token": RevisitSchedule.generate_share_token(),
                },
            )
            result["schedule"] = RevisitScheduleSerializer(schedule).data
        else:
            # If a recurring schedule exists, bump it forward
            try:
                schedule = RevisitSchedule.objects.get(user=request.user, ticker=ticker)
                if schedule.recurrence_days:
                    schedule.next_revisit = today + timedelta(days=schedule.recurrence_days)
                    schedule.notified_at = None
                    schedule.save(update_fields=["next_revisit", "notified_at"])
                result["schedule"] = RevisitScheduleSerializer(schedule).data
            except RevisitSchedule.DoesNotExist:
                pass

        UserOperation.record(request.user, "mark_visited")
        return Response(result, status=status.HTTP_201_CREATED)


class VisitListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        visits = CompanyVisit.objects.filter(user=request.user)
        ticker = request.query_params.get("ticker")
        if ticker:
            visits = visits.filter(ticker=ticker.upper())
        serializer = CompanyVisitSerializer(visits, many=True)
        return Response(serializer.data)


class VisitDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        try:
            visit = CompanyVisit.objects.get(pk=pk, user=request.user)
        except CompanyVisit.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        note = request.data.get("note")
        if note is not None:
            visit.note = note
            visit.save(update_fields=["note"])
        return Response(CompanyVisitSerializer(visit).data)

    def delete(self, request, pk):
        deleted, _ = CompanyVisit.objects.filter(pk=pk, user=request.user).delete()
        if not deleted:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class RevisitScheduleListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        schedules = RevisitSchedule.objects.filter(user=request.user)
        if request.query_params.get("status") == "due":
            schedules = schedules.filter(next_revisit__lte=date.today())
        serializer = RevisitScheduleSerializer(schedules, many=True)
        return Response(serializer.data)


class RevisitScheduleDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        try:
            schedule = RevisitSchedule.objects.get(pk=pk, user=request.user)
        except RevisitSchedule.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = RevisitScheduleSerializer(schedule, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        deleted, _ = RevisitSchedule.objects.filter(pk=pk, user=request.user).delete()
        if not deleted:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SharedVisitsView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, token):
        try:
            schedule = RevisitSchedule.objects.select_related("user").get(share_token=token)
        except RevisitSchedule.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        visits = CompanyVisit.objects.filter(user=schedule.user, ticker=schedule.ticker)
        return Response({
            "ticker": schedule.ticker,
            "next_revisit": schedule.next_revisit,
            "recurrence_days": schedule.recurrence_days,
            "shared_by": schedule.user.email,
            "visits": CompanyVisitSerializer(visits, many=True).data,
        })


REMINDER_DROPDOWN_LIMIT = 10
REMINDER_PAGE_SIZE = 30


def _pending_reminders_queryset(user):
    """Due revisit schedules not yet acknowledged (visited today or dismissed)."""
    today = date.today()
    visited_today = CompanyVisit.objects.filter(
        user=user,
        visited_at=today,
    ).values_list("ticker", flat=True)
    return (
        RevisitSchedule.objects.filter(
            user=user,
            next_revisit__lte=today,
        )
        .exclude(ticker__in=visited_today)
        .filter(Q(dismissed_at__isnull=True) | Q(dismissed_at__lt=models.F("next_revisit")))
    )


class PendingRemindersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        pending = _pending_reminders_queryset(request.user)
        total = pending.count()
        schedules = pending[:REMINDER_DROPDOWN_LIMIT]
        serializer = RevisitScheduleSerializer(schedules, many=True)
        return Response({
            "count": total,
            "schedules": serializer.data,
        })


class RemindersListView(APIView):
    """Paginated list of pending reminders for the notifications index page."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            page = max(1, int(request.query_params.get("page", 1)))
        except ValueError:
            page = 1
        pending = _pending_reminders_queryset(request.user)
        total = pending.count()
        start = (page - 1) * REMINDER_PAGE_SIZE
        end = start + REMINDER_PAGE_SIZE
        schedules = pending[start:end]
        serializer = RevisitScheduleSerializer(schedules, many=True)
        return Response({
            "count": total,
            "page": page,
            "page_size": REMINDER_PAGE_SIZE,
            "schedules": serializer.data,
        })


class DismissReminderView(APIView):
    """Mark a single revisit reminder as seen without visiting the company."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            schedule = RevisitSchedule.objects.get(pk=pk, user=request.user)
        except RevisitSchedule.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        schedule.dismissed_at = date.today()
        schedule.save(update_fields=["dismissed_at"])
        return Response(RevisitScheduleSerializer(schedule).data)


class DismissAllRemindersView(APIView):
    """Mark all currently-pending revisit reminders as seen."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        pending_ids = list(_pending_reminders_queryset(request.user).values_list("id", flat=True))
        RevisitSchedule.objects.filter(id__in=pending_ids).update(dismissed_at=date.today())
        return Response({"dismissed": len(pending_ids)})


# ── Saved Lists ──


class SavedListListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        saved_lists = SavedList.objects.filter(user=request.user)
        serializer = SavedListSerializer(saved_lists, many=True)
        return Response(serializer.data)

    def post(self, request):
        allowed, error_response = _check_operation_permission(request.user)
        if not allowed:
            return error_response

        serializer = SavedListSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        saved_list = SavedList.objects.create(
            user=request.user,
            name=serializer.validated_data["name"],
            tickers=serializer.validated_data["tickers"],
            years=serializer.validated_data.get("years", 10),
            share_token=SavedList.generate_share_token(),
        )

        UserOperation.record(request.user, "save_list")
        return Response(
            SavedListSerializer(saved_list).data,
            status=status.HTTP_201_CREATED,
        )


class SavedListDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        allowed, error_response = _check_operation_permission(request.user)
        if not allowed:
            return error_response

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
        UserOperation.record(request.user, "update_list")
        return Response(SavedListSerializer(saved_list).data)

    def delete(self, request, pk):
        allowed, error_response = _check_operation_permission(request.user)
        if not allowed:
            return error_response

        deleted, _ = SavedList.objects.filter(
            user=request.user, pk=pk
        ).delete()
        if not deleted:
            return Response(status=status.HTTP_404_NOT_FOUND)
        UserOperation.record(request.user, "delete_list")
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReorderListsView(APIView):
    """Update the display order of all saved lists for the current user."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        ordered_ids = request.data.get("ordered_ids", [])
        if not isinstance(ordered_ids, list):
            return Response(
                {"error": "ordered_ids must be a list"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_lists = SavedList.objects.filter(user=request.user)
        list_map = {saved_list.id: saved_list for saved_list in user_lists}

        for position, list_id in enumerate(ordered_ids):
            if list_id in list_map:
                list_map[list_id].display_order = position
                list_map[list_id].save(update_fields=["display_order"])

        return Response({"ok": True})


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


# ── Saved screener filters ──


# Kept in sync with quotes.views.SCREENER_FILTERABLE_FIELDS and
# SCREENER_SORTABLE_FIELDS. Duplicated (rather than imported) because accounts
# shouldn't depend on quotes, and the list changes rarely. If either drifts,
# the other must be updated. market_cap is sortable but not filterable.
_SCREENER_BOUND_FIELDS = {
    "pe10", "pfcf10", "peg", "pfcf_peg",
    "debt_to_equity", "debt_ex_lease_to_equity", "liabilities_to_equity",
    "current_ratio", "debt_to_avg_earnings", "debt_to_avg_fcf",
}
_SCREENER_SORTABLE_FIELDS = _SCREENER_BOUND_FIELDS | {"market_cap", "ticker"}


def _validate_screener_payload(bounds, sort):
    """Return (error_message_or_none). Accepts bounds dict and sort string."""
    if bounds is not None:
        if not isinstance(bounds, dict):
            return "bounds must be an object"
        for key, value in bounds.items():
            if key not in _SCREENER_BOUND_FIELDS:
                return f"Unknown indicator: {key!r}"
            if not isinstance(value, dict):
                return f"bounds[{key!r}] must be an object"
            for side, raw in value.items():
                if side not in ("min", "max"):
                    return f"bounds[{key!r}] may only contain min/max"
                if raw is None or raw == "":
                    continue
                if not isinstance(raw, (str, int, float)):
                    return f"bounds[{key!r}][{side!r}] must be numeric or string"
    if sort is not None:
        sort_field = sort.lstrip("-") if isinstance(sort, str) else sort
        if sort_field not in _SCREENER_SORTABLE_FIELDS:
            return f"Invalid sort field: {sort!r}"
    return None


class SavedScreenerFilterListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        filters = SavedScreenerFilter.objects.filter(user=request.user)
        serializer = SavedScreenerFilterSerializer(filters, many=True)
        return Response(serializer.data)

    def post(self, request):
        allowed, error_response = _check_operation_permission(request.user)
        if not allowed:
            return error_response

        serializer = SavedScreenerFilterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        error = _validate_screener_payload(
            serializer.validated_data.get("bounds"),
            serializer.validated_data.get("sort"),
        )
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        saved = SavedScreenerFilter.objects.create(
            user=request.user,
            name=serializer.validated_data["name"],
            bounds=serializer.validated_data.get("bounds", {}) or {},
            sort=serializer.validated_data.get("sort", "-market_cap"),
        )
        UserOperation.record(request.user, "save_screener_filter")
        return Response(
            SavedScreenerFilterSerializer(saved).data,
            status=status.HTTP_201_CREATED,
        )


class SavedScreenerFilterDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        allowed, error_response = _check_operation_permission(request.user)
        if not allowed:
            return error_response

        try:
            saved = SavedScreenerFilter.objects.get(user=request.user, pk=pk)
        except SavedScreenerFilter.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = SavedScreenerFilterSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        error = _validate_screener_payload(
            serializer.validated_data.get("bounds"),
            serializer.validated_data.get("sort"),
        )
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        if "name" in serializer.validated_data:
            saved.name = serializer.validated_data["name"]
        if "bounds" in serializer.validated_data:
            saved.bounds = serializer.validated_data["bounds"] or {}
        if "sort" in serializer.validated_data:
            saved.sort = serializer.validated_data["sort"]
        saved.save()
        UserOperation.record(request.user, "update_screener_filter")
        return Response(SavedScreenerFilterSerializer(saved).data)

    def delete(self, request, pk):
        allowed, error_response = _check_operation_permission(request.user)
        if not allowed:
            return error_response

        deleted, _ = SavedScreenerFilter.objects.filter(
            user=request.user, pk=pk,
        ).delete()
        if not deleted:
            return Response(status=status.HTTP_404_NOT_FOUND)
        UserOperation.record(request.user, "delete_screener_filter")
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Homepage Layout ──


VALID_LAYOUT_TYPES = {"ticker", "list"}


class HomepageLayoutView(APIView):
    def get(self, request):
        if not request.user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        return Response({"layout": request.user.homepage_layout})

    def put(self, request):
        if not request.user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        layout = request.data.get("layout")
        if not isinstance(layout, list):
            return Response(
                {"error": "layout must be a list"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        for item in layout:
            if not isinstance(item, dict) or item.get("type") not in VALID_LAYOUT_TYPES or "id" not in item:
                return Response(
                    {"error": "Each item must have a valid type (ticker or list) and an id"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        request.user.homepage_layout = layout
        request.user.save(update_fields=["homepage_layout"])
        return Response({"layout": layout})


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
        """List all users with email, last login, and visit counts per period.

        Uses Subquery to avoid the 4-way LEFT JOIN that creates a cartesian
        product explosion (PageView x LookupLog x Favorites x SavedLists).
        Each count is an independent correlated subquery, which PostgreSQL
        executes efficiently via index scans.
        """
        annotations = {}
        for period_name, cutoff in boundaries.items():
            annotations[f"page_views_{period_name}"] = Subquery(
                PageView.objects.filter(
                    user=OuterRef("pk"), timestamp__gte=cutoff
                ).values("user").annotate(count=Count("id")).values("count"),
                output_field=IntegerField(),
            )
            annotations[f"lookups_{period_name}"] = Subquery(
                LookupLog.objects.filter(
                    user=OuterRef("pk"), timestamp__gte=cutoff
                ).values("user").annotate(count=Count("id")).values("count"),
                output_field=IntegerField(),
            )
        annotations["favorites_count"] = Subquery(
            FavoriteCompany.objects.filter(
                user=OuterRef("pk")
            ).values("user").annotate(count=Count("id")).values("count"),
            output_field=IntegerField(),
        )
        annotations["saved_lists_count"] = Subquery(
            SavedList.objects.filter(
                user=OuterRef("pk")
            ).values("user").annotate(count=Count("id")).values("count"),
            output_field=IntegerField(),
        )
        annotations["visits_count"] = Subquery(
            CompanyVisit.objects.filter(
                user=OuterRef("pk")
            ).values("user").annotate(count=Count("ticker", distinct=True)).values("count"),
            output_field=IntegerField(),
        )

        users = (
            User.objects.all()
            .annotate(**annotations)
            .order_by("-last_login")
        )

        user_list = []
        for user in users:
            visit_counts = {
                period_name: getattr(user, f"page_views_{period_name}") or 0
                for period_name in boundaries
            }
            lookup_counts = {
                period_name: getattr(user, f"lookups_{period_name}") or 0
                for period_name in boundaries
            }
            user_list.append({
                "email": user.email,
                "date_joined": user.date_joined,
                "last_login": user.last_login,
                "allow_contact": user.allow_contact,
                "is_superuser": user.is_superuser,
                "page_views": visit_counts,
                "lookups": lookup_counts,
                "favorites_count": user.favorites_count or 0,
                "saved_lists_count": user.saved_lists_count or 0,
                "visits_count": user.visits_count or 0,
            })

        return user_list

    def _get_page_view_stats(self, boundaries):
        """Total page views and unique visitors per period.

        Uses a single aggregate query instead of separate COUNT calls per
        period, reducing ~18 queries to 1.
        """
        aggregations = {}
        for period_name, cutoff in boundaries.items():
            period_filter = Q(timestamp__gte=cutoff)
            aggregations[f"{period_name}_total"] = Count(
                "id", filter=period_filter
            )
            aggregations[f"{period_name}_unique"] = Count(
                "ip_hash", filter=period_filter, distinct=True
            )
            aggregations[f"{period_name}_authenticated"] = Count(
                "id", filter=period_filter & ~Q(user=None)
            )
            aggregations[f"{period_name}_anonymous"] = Count(
                "id", filter=period_filter & Q(user=None)
            )
        aggregations["all_time_total"] = Count("id")
        aggregations["all_time_unique"] = Count("ip_hash", distinct=True)

        result = PageView.objects.aggregate(**aggregations)

        stats = {}
        for period_name in boundaries:
            stats[period_name] = {
                "total_views": result[f"{period_name}_total"],
                "unique_visitors": result[f"{period_name}_unique"],
                "authenticated_views": result[f"{period_name}_authenticated"],
                "anonymous_views": result[f"{period_name}_anonymous"],
            }
        stats["all_time"] = {
            "total_views": result["all_time_total"],
            "unique_visitors": result["all_time_unique"],
        }
        return stats

    def _get_top_pages(self, boundaries):
        """Top 10 most visited pages in the last month."""
        month_cutoff = boundaries["month"]
        return list(
            PageView.objects.filter(timestamp__gte=month_cutoff)
            .values("path")
            .annotate(view_count=Count("id"))
            .order_by("-view_count")[:10]
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
        """New user signups per period.

        Uses a single aggregate query instead of separate COUNT calls per
        period, reducing 5 queries to 1.
        """
        aggregations = {"total": Count("id")}
        for period_name, cutoff in boundaries.items():
            aggregations[period_name] = Count(
                "id", filter=Q(date_joined__gte=cutoff)
            )
        return User.objects.aggregate(**aggregations)


class AdminTopPagesView(APIView):
    """Returns the full list of most visited pages in the last 30 days."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        boundaries = _time_boundaries()
        pages = list(
            PageView.objects.filter(timestamp__gte=boundaries["month"])
            .values("path")
            .annotate(view_count=Count("id"))
            .order_by("-view_count")
        )
        return Response({"pages": pages})


class IndicatorAlertListView(APIView):
    """List / create indicator alerts for the signed-in user."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        alerts = IndicatorAlert.objects.filter(user=request.user)
        ticker_filter = request.query_params.get("ticker")
        if ticker_filter:
            alerts = alerts.filter(ticker=ticker_filter.upper())
        serializer = IndicatorAlertSerializer(alerts, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = IndicatorAlertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticker = serializer.validated_data["ticker"]
        indicator = serializer.validated_data["indicator"]
        comparison = serializer.validated_data["comparison"]
        # Enforce the unique_together constraint with a clean 400 instead of a
        # 500 from the DB.
        if IndicatorAlert.objects.filter(
            user=request.user,
            ticker=ticker,
            indicator=indicator,
            comparison=comparison,
        ).exists():
            return Response(
                {"error": "An alert for this ticker, indicator, and comparison already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        alert = serializer.save(user=request.user)
        return Response(
            IndicatorAlertSerializer(alert).data,
            status=status.HTTP_201_CREATED,
        )


class IndicatorAlertDetailView(APIView):
    """Update / delete a single alert. Scoped to the owning user."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            alert = IndicatorAlert.objects.get(pk=pk, user=request.user)
        except IndicatorAlert.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = IndicatorAlertSerializer(alert, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        deleted, _ = IndicatorAlert.objects.filter(pk=pk, user=request.user).delete()
        if not deleted:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)
