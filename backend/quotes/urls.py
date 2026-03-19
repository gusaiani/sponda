from django.urls import path

from .views import HealthView, OGImageView, PE10View, TickerListView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("tickers/", TickerListView.as_view(), name="ticker-list"),
    path("quote/<str:ticker>/", PE10View.as_view(), name="pe10"),
    path("og/home.png", OGImageView.as_view(), name="og-home"),
    path("og/<str:ticker>.png", OGImageView.as_view(), name="og-ticker"),
]
