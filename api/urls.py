from django.urls import path
from . import views

urlpatterns = [
    path('', views.getExample),
    path('signup/', views.signupUser),
    path('login/', views.loginUser),
    path('refresh-token/', views.refreshToken),
]