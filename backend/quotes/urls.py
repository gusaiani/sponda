from django.urls import path

from .views import HealthView, PE10View

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("quote/<str:ticker>/", PE10View.as_view(), name="pe10"),
]
