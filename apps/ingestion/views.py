"""
Views for the ingestion app.
"""

import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings

from .pipeline import NetCDFIngestionPipeline, run_ingestion
from .models import ProcessedFile

logger = logging.getLogger(__name__)


class IngestionStatusView(APIView):
    """Check the status of the ingestion service."""
    
    def get(self, request):
        """Get ingestion service status."""
        try:
            pipeline = NetCDFIngestionPipeline()
            stats = pipeline.get_stats()
            
            return Response({
                'status': 'operational',
                'database_connected': True,
                'statistics': stats,
            })
        except Exception as e:
            logger.error(f"Ingestion status check failed: {e}")
            return Response({
                'status': 'error',
                'database_connected': False,
                'error': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class IngestFileView(APIView):
    """Trigger ingestion of a NetCDF file."""
    
    def post(self, request):
        """
        Ingest a NetCDF file.
        
        Request body:
        {
            "source": "path/to/file.nc or URL",
            "is_url": true/false,
            "is_directory": true/false,
            "force": true/false
        }
        """
        source = request.data.get('source')
        is_url = request.data.get('is_url', False)
        is_directory = request.data.get('is_directory', False)
        force = request.data.get('force', False)
        
        if not source:
            return Response({
                'status': 'error',
                'error': 'Source is required',
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            result = run_ingestion(
                source=source,
                is_url=is_url,
                is_directory=is_directory,
                force=force,
            )
            
            return Response({
                'status': 'success',
                'result': result,
            })
        except Exception as e:
            logger.error(f"Ingestion failed: {e}")
            return Response({
                'status': 'error',
                'error': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DatabaseStatsView(APIView):
    """Get database statistics."""
    
    def get(self, request):
        """Get current database statistics."""
        try:
            pipeline = NetCDFIngestionPipeline()
            stats = pipeline.get_stats()
            
            return Response({
                'status': 'success',
                'statistics': stats,
            })
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return Response({
                'status': 'error',
                'error': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProcessedFilesView(APIView):
    """List processed files."""
    
    def get(self, request):
        """Get list of processed files with pagination."""
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 50))
        status_filter = request.query_params.get('status')
        
        start = (page - 1) * page_size
        end = start + page_size
        
        queryset = ProcessedFile.objects.all()
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        total_count = queryset.count()
        files = queryset[start:end]
        
        return Response({
            'status': 'success',
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'files': [
                {
                    'id': f.id,
                    'file_path': f.file_path,
                    'file_name': f.file_name,
                    'processed_at': f.processed_at.isoformat(),
                    'records_inserted': f.records_inserted,
                    'status': f.status,
                    'error_message': f.error_message,
                }
                for f in files
            ],
        })
