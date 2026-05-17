"""URL conf for ``/api/social/``."""
from django.urls import path

from social import views


urlpatterns = [
    # Sponds
    path("sponds/", views.SpondCreateView.as_view(), name="social-spond-create"),
    path("sponds/<uuid:pk>/", views.SpondDetailView.as_view(), name="social-spond-detail"),
    path("sponds/<uuid:pk>/like/", views.SpondLikeView.as_view(), name="social-spond-like"),

    # Feeds
    path("feed/", views.FollowingFeedView.as_view(), name="social-feed-following"),
    path("feed/global/", views.GlobalFeedView.as_view(), name="social-feed-global"),
    path("companies/<str:symbol>/sponds/", views.CompanyFeedView.as_view(), name="social-company-feed"),

    # Profiles & follow graph
    path("users/me/profile/", views.MyProfileUpdateView.as_view(), name="social-my-profile"),
    path("users/me/follow-requests/", views.FollowRequestListView.as_view(), name="social-follow-requests"),
    path("users/<str:handle>/", views.UserProfileView.as_view(), name="social-user-profile"),
    path("users/<str:handle>/follow/", views.FollowView.as_view(), name="social-follow"),
    path("users/<str:handle>/mute/", views.MuteView.as_view(), name="social-mute"),
    path("users/<str:handle>/block/", views.BlockView.as_view(), name="social-block"),
    path(
        "follow-requests/<int:follow_id>/<str:action>/",
        views.FollowRequestActionView.as_view(),
        name="social-follow-request-action",
    ),

    # Notifications
    path("notifications/", views.NotificationListView.as_view(), name="social-notifications"),
    path("notifications/mark-read/", views.NotificationsMarkReadView.as_view(), name="social-notifications-mark-read"),

    # Autocomplete
    path("autocomplete/handles/", views.HandleAutocompleteView.as_view(), name="social-autocomplete-handles"),
    path("autocomplete/tickers/", views.TickerAutocompleteView.as_view(), name="social-autocomplete-tickers"),
]
