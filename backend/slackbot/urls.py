from django.urls import path

from slackbot import views

urlpatterns = [
    path("events/", views.slack_events, name="slack-events"),
    path("commands/", views.slack_commands, name="slack-commands"),
    path("interactions/", views.slack_interactions, name="slack-interactions"),
]
