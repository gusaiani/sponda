from django.urls import path

from .views import HealthView, PE10View, TickerListView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("tickers/", TickerListView.as_view(), name="ticker-list"),
    path("quote/<str:ticker>/", PE10View.as_view(), name="pe10"),
]
