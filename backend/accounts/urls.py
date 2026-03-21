from django.urls import path

from .views import (
    AdminDashboardView,
    ChangePasswordView,
    FavoriteDetailView,
    FavoriteListView,
    FeedbackView,
    ForgotPasswordView,
    GoogleAuthView,
    LoginView,
    LogoutView,
    MeView,
    QuotaView,
    ResetPasswordView,
    SavedListDetailView,
    SavedListListView,
    SharedListView,
    SignupView,
)

urlpatterns = [
    path("signup/", SignupView.as_view(), name="signup"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("forgot-password/", ForgotPasswordView.as_view(), name="forgot-password"),
    path("reset-password/", ResetPasswordView.as_view(), name="reset-password"),
    path("google/", GoogleAuthView.as_view(), name="google-auth"),
    path("quota/", QuotaView.as_view(), name="quota"),
    path("favorites/", FavoriteListView.as_view(), name="favorite-list"),
    path("favorites/<str:ticker>/", FavoriteDetailView.as_view(), name="favorite-detail"),
    path("lists/", SavedListListView.as_view(), name="list-list"),
    path("lists/<int:pk>/", SavedListDetailView.as_view(), name="list-detail"),
    path("lists/shared/<str:token>/", SharedListView.as_view(), name="shared-list"),
    path("feedback/", FeedbackView.as_view(), name="feedback"),
    path("admin/dashboard/", AdminDashboardView.as_view(), name="admin-dashboard"),
]
