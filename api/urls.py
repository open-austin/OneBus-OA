from django.urls import path
from . import views

urlpatterns = [
    path("", views.determine_stops_and_pois, name="determine_stops_and_pois"),
]
