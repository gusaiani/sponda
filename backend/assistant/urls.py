"""Routes for the LLM Q&A assistant."""
from django.urls import path 

from assistant import views

urlpatterns = [
    path("ask/", views.ask, name="assistant-ask"),
    path("screen/", views.screen, name="assistant-screen"),
    path("indicators/", views.indicators, name="assistant-indicators"),
]