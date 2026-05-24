"""Routes for the LLM Q&A assistant."""
from django.urls import path 

from assistant import views

urlpatterns = [
    path("ask/", views.ask, name="assistant-ask"),
]