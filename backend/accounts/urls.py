from django.urls import path

from .views import LoginView, QuotaView, SignupView

urlpatterns = [
    path("signup/", SignupView.as_view(), name="signup"),
    path("login/", LoginView.as_view(), name="login"),
    path("quota/", QuotaView.as_view(), name="quota"),
]
