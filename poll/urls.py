from django.conf.urls import url
from django.urls import path
from .views import *

app_name = "poll"
urlpatterns = [
    path('list/', poll_collection_list, name='list'),
    path('polls/<int:poll_collection_id>', poll_collection_view, name='view'),
    path('export_raw/<int:poll_id>', export_raw, name='export_raw'),
    path('export_pc_raw/<int:poll_collection_id>', export_pc_raw, name='export_pc_raw'),
    path('polls/<int:poll_collection_id>/export_voters', export_voters, name='export_voters'),
    path('api/vote/<int:poll_id>', api_vote, name='api_vote')
]
