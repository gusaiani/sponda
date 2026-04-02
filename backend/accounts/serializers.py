from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .models import FavoriteCompany, SavedList

User = get_user_model()


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

    class Meta:
        model = User
        fields = ("email", "password", "allow_contact")

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["email"],
            email=validated_data["email"],
            password=validated_data["password"],
            allow_contact=validated_data.get("allow_contact", False),
        )
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField()
    new_password = serializers.CharField(min_length=8)


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


class FeedbackSerializer(serializers.Serializer):
    email = serializers.EmailField()
    message = serializers.CharField(min_length=1, max_length=5000)
    human_check = serializers.IntegerField()
