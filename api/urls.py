"""
API endpoint configurations.
"""

from django.urls import path
from . import views

urlpatterns = [
    path("", views.get_example),
    path("signup/", views.signup_user),
    path("login/", views.login_user),
    path("refresh-token/", views.refresh_token),
    path("parking-lots/", views.parking_lots),
    path("cadmin/parking-lots/", views.cadmin_parking_lots),
    path("cadmin/parking-spots/", views.cadmin_parking_spots),
    path("parking-events/", views.post_parking_spot_event),
]
