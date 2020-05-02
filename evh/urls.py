"""evh_account URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from evh import views
from django.conf import settings
from django.http import HttpResponse
from django.views.static import serve
from django.views.decorators.http import require_GET


# Sorry mum. But somehow this is necessary
def serve_hull(*args, **kwargs):
    kwargs['document_root'] = settings.STATIC_ROOT
    return serve(*args, **kwargs)

@require_GET
def robots_txt(request):
    lines = [
        "User-Agent: *",
        "Disallow: /",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")

urlpatterns = [
    path('', views.index, name='index'),
    path("robots.txt", robots_txt),
    path('account/', include('account.urls')),
    re_path(r'^static/(?P<path>.*)$', serve_hull),
]




