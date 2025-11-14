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
]
