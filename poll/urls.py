from django.conf.urls import url
from django.urls import path
from .views import *

app_name = "poll"
urlpatterns = [
    path('list/', poll_collection_list, name='list'),
    path('polls/<int:poll_collection_id>', poll_collection_view, name='view'),
    path('vote/<int:poll_id>', vote, name='vote'),
]
