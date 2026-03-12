"""
Serializers for chat API.
"""

from rest_framework import serializers


class ChatQuerySerializer(serializers.Serializer):
    """Serializer for chat query requests."""
    
    query = serializers.CharField(
        max_length=5000,
        required=True,
        help_text="Natural language query"
    )
    context = serializers.DictField(
        required=False,
        default=dict,
        help_text="Optional context from previous queries"
    )
    include_data = serializers.BooleanField(
        required=False,
        default=True,
        help_text="Whether to include raw data in response"
    )
    max_rows = serializers.IntegerField(
        required=False,
        default=100,
        min_value=1,
        max_value=10000,
        help_text="Maximum rows to return in data"
    )


class SQLPreviewSerializer(serializers.Serializer):
    """Serializer for SQL preview requests."""
    
    query = serializers.CharField(
        max_length=5000,
        required=True,
        help_text="Natural language query"
    )


class FeedbackSerializer(serializers.Serializer):
    """Serializer for user feedback."""
    
    query_id = serializers.CharField(
        required=True,
        help_text="ID of the query being rated"
    )
    rating = serializers.IntegerField(
        required=True,
        min_value=1,
        max_value=5,
        help_text="Rating from 1-5"
    )
    feedback_text = serializers.CharField(
        required=False,
        max_length=1000,
        allow_blank=True,
        help_text="Optional feedback text"
    )
    correct_response = serializers.CharField(
        required=False,
        max_length=5000,
        allow_blank=True,
        help_text="What the correct response should have been"
    )


class NumericSummarySerializer(serializers.Serializer):
    """Serializer for numeric summary."""
    
    total_records = serializers.IntegerField()
    columns_returned = serializers.ListField(child=serializers.CharField())
    numeric_stats = serializers.DictField()


class InsightField(serializers.Field):
    """Field that accepts either a string or a dict with key/value."""
    
    def to_representation(self, value):
        return value
    
    def to_internal_value(self, data):
        if isinstance(data, str):
            return data
        elif isinstance(data, dict):
            # Convert dict to string format
            key = data.get('key', '')
            value = data.get('value', data.get('description', ''))
            if key and value:
                return f"{key}: {value}"
            return key or value or str(data)
        return str(data)


class AnalyticsSummarySerializer(serializers.Serializer):
    """Serializer for analytics summary."""
    
    insights = serializers.ListField(child=InsightField())
    trends = serializers.CharField(allow_null=True)
    anomalies = serializers.CharField(allow_null=True)
    recommendations = serializers.CharField(allow_null=True)


class AIResponseSerializer(serializers.Serializer):
    """Serializer for AI response."""
    
    status = serializers.CharField()
    text_response = serializers.CharField()
    numeric_summary = NumericSummarySerializer()
    analytics = AnalyticsSummarySerializer()
    visualization = serializers.DictField(allow_null=True)
    data = serializers.ListField(
        child=serializers.DictField(),
        allow_null=True
    )
    query_info = serializers.DictField()
    execution_time_ms = serializers.FloatField()
    error = serializers.CharField(allow_null=True)
