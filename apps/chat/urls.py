"""
URL routes for the chat app.
"""

from django.urls import path
from .views import (
    ChatQueryView,
    SQLPreviewView,
    SchemaView,
    ContextView,
    FeedbackView,
    HealthCheckView,
    SampleQueriesView
)

urlpatterns = [
    # Main chat endpoint
    path('chat/', ChatQueryView.as_view(), name='chat-query'),
    
    # SQL preview
    path('chat/sql-preview/', SQLPreviewView.as_view(), name='sql-preview'),
    
    # Schema information
    path('chat/schema/', SchemaView.as_view(), name='schema'),
    
    # Conversation context management
    path('chat/context/', ContextView.as_view(), name='context'),
    
    # User feedback
    path('chat/feedback/', FeedbackView.as_view(), name='feedback'),
    
    # Sample queries
    path('chat/samples/', SampleQueriesView.as_view(), name='samples'),
    
    # Health check
    path('health/', HealthCheckView.as_view(), name='health'),
]
