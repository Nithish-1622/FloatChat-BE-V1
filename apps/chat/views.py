"""
Views for the chat API.
"""

import logging
import uuid
from datetime import datetime

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.throttling import AnonRateThrottle
from django.conf import settings

from .serializers import (
    ChatQuerySerializer,
    SQLPreviewSerializer,
    FeedbackSerializer
)
from .utils import sanitize_input, format_error_response
from apps.services.ai_pipeline import ai_pipeline, process_query
from apps.services.nlp_service import nlp_service
from apps.tools.sql_tool import sql_tool, get_database_schema

logger = logging.getLogger(__name__)


class ChatRateThrottle(AnonRateThrottle):
    """Custom rate throttle for chat endpoint."""
    rate = '60/minute'


class ChatQueryView(APIView):
    """
    Main chat endpoint for natural language queries.
    
    POST /api/v1/chat/
    
    Request:
    {
        "query": "What is the average temperature in the Indian Ocean?",
        "context": {},
        "include_data": true,
        "max_rows": 100
    }
    
    Response:
    {
        "status": "success",
        "text_response": "...",
        "numeric_summary": {...},
        "analytics": {...},
        "visualization": {...},
        "data": [...],
        "query_info": {...},
        "execution_time_ms": 123.45
    }
    """
    
    throttle_classes = [ChatRateThrottle]
    
    def post(self, request):
        """Process a natural language query."""
        serializer = ChatQuerySerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                format_error_response(str(serializer.errors)),
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Sanitize input
        query = sanitize_input(serializer.validated_data['query'])
        
        if not query:
            return Response(
                format_error_response("Query cannot be empty"),
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Log query (without sensitive info)
        query_id = str(uuid.uuid4())[:8]
        logger.info(f"Query [{query_id}]: {query[:100]}...")
        
        try:
            # Process through AI pipeline
            response = ai_pipeline.process(query)
            
            # Convert to dict and add query ID
            response_dict = response.dict()
            response_dict['query_id'] = query_id
            
            # Handle data limiting
            max_rows = serializer.validated_data.get('max_rows', 100)
            include_data = serializer.validated_data.get('include_data', True)
            
            if not include_data:
                response_dict['data'] = None
            elif response_dict.get('data') and len(response_dict['data']) > max_rows:
                response_dict['data'] = response_dict['data'][:max_rows]
                response_dict['data_truncated'] = True
                response_dict['total_rows_available'] = len(response.data) if response.data else 0
            
            logger.info(
                f"Query [{query_id}] completed in {response.execution_time_ms:.2f}ms"
            )
            
            return Response(response_dict)
            
        except Exception as e:
            logger.exception(f"Query [{query_id}] failed: {e}")
            return Response(
                format_error_response(str(e), 500),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SQLPreviewView(APIView):
    """
    Preview the SQL that would be generated for a query.
    
    POST /api/v1/chat/sql-preview/
    
    Request:
    {
        "query": "Show me temperature data for float 123"
    }
    
    Response:
    {
        "sql": "SELECT ...",
        "intent": {...},
        "valid": true
    }
    """
    
    def post(self, request):
        """Generate SQL preview without executing."""
        serializer = SQLPreviewSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                {'error': str(serializer.errors)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        query = sanitize_input(serializer.validated_data['query'])
        
        try:
            result = ai_pipeline.generate_sql_from_natural_language(query)
            return Response(result)
            
        except Exception as e:
            logger.exception(f"SQL preview failed: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SchemaView(APIView):
    """
    Get the database schema information.
    
    GET /api/v1/chat/schema/
    """
    
    def get(self, request):
        """Return database schema information."""
        return Response({
            'schema': get_database_schema(),
            'tables': [
                {
                    'name': 'floats',
                    'description': 'ARGO float devices',
                    'columns': ['id', 'platform_number', 'first_seen', 'last_seen']
                },
                {
                    'name': 'profiles',
                    'description': 'Measurement profiles at specific times/locations',
                    'columns': ['id', 'float_id', 'latitude', 'longitude', 'profile_time']
                },
                {
                    'name': 'measurements',
                    'description': 'Individual measurements',
                    'columns': ['id', 'profile_id', 'pressure', 'temperature', 'salinity']
                }
            ]
        })


class ContextView(APIView):
    """
    Manage conversation context.
    
    GET /api/v1/chat/context/ - Get current context
    DELETE /api/v1/chat/context/ - Reset context
    """
    
    def get(self, request):
        """Get current conversation context."""
        context = nlp_service.get_context()
        return Response({
            'context': context,
            'status': 'active'
        })
    
    def delete(self, request):
        """Reset conversation context."""
        nlp_service.reset_context()
        return Response({
            'status': 'reset',
            'message': 'Conversation context has been reset'
        })


class FeedbackView(APIView):
    """
    Submit feedback for a query response.
    
    POST /api/v1/chat/feedback/
    """
    
    def post(self, request):
        """Submit feedback."""
        serializer = FeedbackSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                {'error': str(serializer.errors)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Log feedback (in production, store in database)
        feedback_data = serializer.validated_data
        logger.info(
            f"Feedback received for query {feedback_data['query_id']}: "
            f"rating={feedback_data['rating']}"
        )
        
        return Response({
            'status': 'received',
            'message': 'Thank you for your feedback'
        })


class HealthCheckView(APIView):
    """
    Health check endpoint.
    
    GET /api/v1/health/
    """
    
    def get(self, request):
        """Check system health."""
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'components': {}
        }
        
        # Check database
        try:
            from apps.ingestion.pipeline import NetCDFIngestionPipeline
            pipeline = NetCDFIngestionPipeline()
            stats = pipeline.get_stats()
            health_status['components']['database'] = {
                'status': 'connected',
                'floats': stats.get('total_floats', 0),
                'profiles': stats.get('total_profiles', 0),
                'measurements': stats.get('total_measurements', 0)
            }
        except Exception as e:
            health_status['components']['database'] = {
                'status': 'error',
                'error': str(e)
            }
            health_status['status'] = 'degraded'
        
        # Check AI service
        try:
            if ai_pipeline.groq_client:
                health_status['components']['ai'] = {
                    'status': 'available',
                    'provider': 'groq'
                }
            else:
                health_status['components']['ai'] = {
                    'status': 'limited',
                    'provider': 'rule_based'
                }
        except Exception as e:
            health_status['components']['ai'] = {
                'status': 'error',
                'error': str(e)
            }
        
        return Response(health_status)


class SampleQueriesView(APIView):
    """
    Get sample queries for the UI.
    
    GET /api/v1/chat/samples/
    """
    
    def get(self, request):
        """Return sample queries."""
        samples = [
            {
                'category': 'Basic Queries',
                'queries': [
                    "How many floats are in the database?",
                    "Show me the latest temperature data",
                    "What is the average salinity?",
                ]
            },
            {
                'category': 'Time-based Analysis',
                'queries': [
                    "Show temperature trends over the last month",
                    "What was the average temperature in 2023?",
                    "Monthly temperature variations",
                ]
            },
            {
                'category': 'Depth Profiles',
                'queries': [
                    "Show temperature profile by depth",
                    "How does salinity change with depth?",
                    "Temperature at 500 meters depth",
                ]
            },
            {
                'category': 'Geographic Analysis',
                'queries': [
                    "Map of temperature distribution",
                    "Show data from the northern Indian Ocean",
                    "Temperature comparison between regions",
                ]
            },
            {
                'category': 'Statistical Analysis',
                'queries': [
                    "Statistics for temperature data",
                    "What is the temperature distribution?",
                    "Maximum and minimum temperatures recorded",
                ]
            }
        ]
        
        return Response({'samples': samples})
