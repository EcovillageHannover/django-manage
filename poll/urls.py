from django.conf.urls import url
from django.urls import path
from .views import vote, poll_view, result

app_name = "poll"
urlpatterns = [
    path('votes/<int:poll_id>', vote, name='vote'),
    path('polls/<int:poll_id>', poll_view, name='poll_view'),
    path('result/<int:poll_id>', result, name='result'),
]
