"""
URL configuration for argo_ai project.
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('apps.chat.urls')),
    path('api/v1/ingestion/', include('apps.ingestion.urls')),
]
