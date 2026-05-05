from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .models import AlertNotification, CompanyVisit, FavoriteCompany, IndicatorAlert, RevisitSchedule, SavedList, SavedScreenerFilter, SUPPORTED_LANGUAGES

User = get_user_model()


def validate_next_revisit_not_past(value):
    if value and value < timezone.localdate():
        raise serializers.ValidationError("Next revisit cannot be in the past.")
    return value


class SignupSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        validators=[
            UniqueValidator(
                queryset=User.objects.all(),
                message="Já existe uma conta com este email.",
            ),
        ],
    )
    password = serializers.CharField(write_only=True, min_length=8)
    allow_contact = serializers.BooleanField(required=False, default=False)
    language = serializers.CharField(required=False, allow_blank=True, default="")

    class Meta:
        model = User
        fields = ("email", "password", "allow_contact", "language")

    def validate_language(self, value):
        if value and value in SUPPORTED_LANGUAGES:
            return value
        return ""

    def create(self, validated_data):
        language = validated_data.get("language") or self.context.get("fallback_language", "en")
        user = User.objects.create_user(
            username=validated_data["email"],
            email=validated_data["email"],
            password=validated_data["password"],
            allow_contact=validated_data.get("allow_contact", False),
            language=language,
        )
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField()
    new_password = serializers.CharField(min_length=8)


class DeleteAccountSerializer(serializers.Serializer):
    email_confirmation = serializers.CharField()


class ChangeEmailSerializer(serializers.Serializer):
    new_email = serializers.EmailField()
    password = serializers.CharField()


class UpdatePreferencesSerializer(serializers.Serializer):
    allow_contact = serializers.BooleanField(required=False)
    learning_mode_enabled = serializers.BooleanField(required=False)


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField()
    password = serializers.CharField(min_length=8)


class FavoriteCompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = FavoriteCompany
        fields = ("id", "ticker", "created_at")
        read_only_fields = ("id", "created_at")


class SavedListSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedList
        fields = ("id", "name", "tickers", "years", "display_order", "share_token", "created_at", "updated_at")
        read_only_fields = ("id", "share_token", "created_at", "updated_at")


class SavedScreenerFilterSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedScreenerFilter
        fields = ("id", "name", "bounds", "sort", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class CompanyVisitSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyVisit
        fields = ("id", "ticker", "visited_at", "note", "created_at")
        read_only_fields = ("id", "created_at")


class RevisitScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = RevisitSchedule
        fields = ("id", "ticker", "next_revisit", "recurrence_days", "share_token", "notified_at", "dismissed_at", "created_at", "updated_at")
        read_only_fields = ("id", "share_token", "notified_at", "dismissed_at", "created_at", "updated_at")

    def validate_next_revisit(self, value):
        return validate_next_revisit_not_past(value)


class MarkVisitedSerializer(serializers.Serializer):
    ticker = serializers.CharField(max_length=10)
    note = serializers.CharField(required=False, default="", allow_blank=True)
    next_revisit = serializers.DateField(required=False)
    recurrence_days = serializers.ChoiceField(
        choices=[30, 90, 182, 365],
        required=False,
    )

    def validate_next_revisit(self, value):
        return validate_next_revisit_not_past(value)


class FeedbackSerializer(serializers.Serializer):
    email = serializers.EmailField()
    message = serializers.CharField(min_length=1, max_length=5000)
    human_check = serializers.IntegerField()


class IndicatorAlertSerializer(serializers.ModelSerializer):
    """Serialize IndicatorAlert rows. Ticker is uppercased on input so the
    alert checker can match against upper-case IndicatorSnapshot keys."""

    ticker = serializers.CharField(max_length=10)
    indicator = serializers.ChoiceField(choices=[(f, f) for f in IndicatorAlert.ALLOWED_INDICATORS])

    class Meta:
        model = IndicatorAlert
        fields = (
            "id", "ticker", "indicator", "comparison", "threshold", "active",
            "triggered_at", "created_at", "updated_at",
        )
        read_only_fields = ("id", "triggered_at", "created_at", "updated_at")

    def validate_ticker(self, value):
        return value.upper().strip()


class AlertNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertNotification
        fields = (
            "id", "ticker", "indicator", "comparison", "threshold",
            "indicator_value", "dismissed_at", "created_at",
        )
        read_only_fields = fields
