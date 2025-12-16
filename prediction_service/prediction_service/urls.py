"""
URL configuration for the prediction Django service.
"""

from django.contrib import admin
from django.urls import path

from prediction_api.views import predict_view, health_check

urlpatterns = [
    path("admin/", admin.site.urls),
    path("predict/", predict_view),
    path("health/", health_check),
]

