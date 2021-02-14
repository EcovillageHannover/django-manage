from django.conf.urls import url
from django.urls import path
from .views import *

app_name = "blackboard"

urlpatterns = [
    path('', index, name='index'),
    path('view/<int:item_id>', view, name='view'),
    path('create/', ItemCreate.as_view(), name='create'),
    path('edit/<int:pk>', ItemUpdate.as_view(), name='edit'),
    path('delete/<int:pk>', ItemDelete.as_view(), name='delete'),
    path('mail/<int:pk>', mail, name='mail'),
]
