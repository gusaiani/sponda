from django.urls import path

from .views import CompanyAnalysisView, FundamentalsView, HealthView, LogoProxyView, MultiplesHistoryView, PE10View, ScreenerCountriesView, ScreenerSectorsView, ScreenerView, SitemapView, TickerDetailView, TickerListView, TickerPeersView, TickerSearchView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("tickers/", TickerListView.as_view(), name="ticker-list"),
    path("tickers/search/", TickerSearchView.as_view(), name="ticker-search"),
    path("tickers/<str:symbol>/", TickerDetailView.as_view(), name="ticker-detail"),
    path("tickers/<str:symbol>/peers/", TickerPeersView.as_view(), name="ticker-peers"),
    path("logos/<str:symbol>.png", LogoProxyView.as_view(), name="logo-proxy"),
    path("quote/<str:ticker>/", PE10View.as_view(), name="pe10"),
    path("quote/<str:ticker>/multiples-history/", MultiplesHistoryView.as_view(), name="multiples-history"),
    path("quote/<str:ticker>/fundamentals/", FundamentalsView.as_view(), name="fundamentals"),
    path("quote/<str:ticker>/analysis/", CompanyAnalysisView.as_view(), name="company-analysis"),
    path("screener/", ScreenerView.as_view(), name="screener"),
    path("screener/sectors/", ScreenerSectorsView.as_view(), name="screener-sectors"),
    path("screener/countries/", ScreenerCountriesView.as_view(), name="screener-countries"),
    path("sitemap.xml", SitemapView.as_view(), name="sitemap"),
]
