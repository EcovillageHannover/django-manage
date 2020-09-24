from django.conf.urls import url
from django.urls import path
from .views import *

app_name = "poll"
urlpatterns = [
    path('subscribe', subscribe, name='subscribe'),
    path('subscribe/<str:token>', subscribe_confirm, name='subscribe_confirm'),
]
