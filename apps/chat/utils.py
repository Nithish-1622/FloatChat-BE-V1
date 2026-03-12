"""
Utility functions for the chat app.
"""

import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler for REST framework.
    
    Ensures all errors return a consistent JSON format.
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    
    if response is not None:
        # Customize the response format
        custom_response_data = {
            'status': 'error',
            'text_response': str(exc),
            'error': {
                'code': response.status_code,
                'message': str(exc),
                'detail': response.data
            },
            'numeric_summary': {},
            'analytics': {},
            'visualization': None,
            'data': None
        }
        response.data = custom_response_data
    else:
        # Handle unexpected exceptions
        logger.exception(f"Unexpected error: {exc}")
        
        custom_response_data = {
            'status': 'error',
            'text_response': 'An unexpected error occurred',
            'error': {
                'code': 500,
                'message': str(exc),
                'detail': None
            },
            'numeric_summary': {},
            'analytics': {},
            'visualization': None,
            'data': None
        }
        
        response = Response(
            custom_response_data,
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    return response


def sanitize_input(text: str) -> str:
    """
    Sanitize user input to prevent injection attacks.
    
    Args:
        text: Raw user input
        
    Returns:
        Sanitized text
    """
    if not text:
        return ""
    
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Limit length
    max_length = 5000
    if len(text) > max_length:
        text = text[:max_length]
    
    # Strip excessive whitespace
    text = ' '.join(text.split())
    
    return text.strip()


def format_error_response(error: str, code: int = 400) -> dict:
    """
    Format an error response in the standard structure.
    
    Args:
        error: Error message
        code: HTTP status code
        
    Returns:
        Formatted error dictionary
    """
    return {
        'status': 'error',
        'text_response': error,
        'error': {
            'code': code,
            'message': error
        },
        'numeric_summary': {},
        'analytics': {},
        'visualization': None,
        'data': None
    }
