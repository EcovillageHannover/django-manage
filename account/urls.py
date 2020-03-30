from django.urls import path

from . import views

urlpatterns = [
    path('create/<str:token>', views.create),
    path('create/', views.create),
    path('create', views.create),
]
