from django.urls import path

from .views import FundamentalsView, HealthView, MultiplesHistoryView, OGImageView, PE10View, TickerListView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("tickers/", TickerListView.as_view(), name="ticker-list"),
    path("quote/<str:ticker>/", PE10View.as_view(), name="pe10"),
    path("quote/<str:ticker>/multiples-history/", MultiplesHistoryView.as_view(), name="multiples-history"),
    path("quote/<str:ticker>/fundamentals/", FundamentalsView.as_view(), name="fundamentals"),
    path("og/home.png", OGImageView.as_view(), name="og-home"),
    path("og/<str:ticker>.png", OGImageView.as_view(), name="og-ticker"),
]
