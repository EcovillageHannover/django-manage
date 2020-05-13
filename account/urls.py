from django.urls import path
from django.conf.urls import url
from django.contrib.auth import views as auth_views
from django.contrib.auth import urls as auth_urls




from . import views

urlpatterns = [
    path('create/<str:token>', views.create),
    path('create/', views.create),
    path('create', views.create),
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('profile/', views.profile, name='profile'),
]
