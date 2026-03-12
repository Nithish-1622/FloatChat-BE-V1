"""
URL routes for the ingestion app.
"""

from django.urls import path
from .views import (
    IngestionStatusView, 
    IngestFileView, 
    DatabaseStatsView,
    ProcessedFilesView
)

urlpatterns = [
    path('status/', IngestionStatusView.as_view(), name='ingestion-status'),
    path('ingest/', IngestFileView.as_view(), name='ingest-file'),
    path('stats/', DatabaseStatsView.as_view(), name='database-stats'),
    path('processed-files/', ProcessedFilesView.as_view(), name='processed-files'),
]
