"""
Python Tool for safe internal processing and validation.

This tool:
- Validates and preprocesses parameters
- Executes approved internal Python logic
- Enforces security constraints
- Returns structured data
"""

import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, validator
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class QueryParameters(BaseModel):
    """Validated parameters for data queries."""
    
    start_date: Optional[datetime] = Field(None, description="Start date filter")
    end_date: Optional[datetime] = Field(None, description="End date filter")
    platform_numbers: Optional[List[str]] = Field(None, description="Float platform numbers")
    min_latitude: Optional[float] = Field(None, ge=-90, le=90)
    max_latitude: Optional[float] = Field(None, ge=-90, le=90)
    min_longitude: Optional[float] = Field(None, ge=-180, le=180)
    max_longitude: Optional[float] = Field(None, ge=-180, le=180)
    min_depth: Optional[float] = Field(None, ge=0, description="Minimum pressure/depth")
    max_depth: Optional[float] = Field(None, ge=0, description="Maximum pressure/depth")
    min_temperature: Optional[float] = Field(None, description="Minimum temperature")
    max_temperature: Optional[float] = Field(None, description="Maximum temperature")
    min_salinity: Optional[float] = Field(None, ge=0, description="Minimum salinity")
    max_salinity: Optional[float] = Field(None, ge=0, description="Maximum salinity")
    aggregation: Optional[str] = Field(None, description="Aggregation type: avg, sum, min, max, count")
    group_by: Optional[List[str]] = Field(None, description="Group by columns")
    order_by: Optional[str] = Field(None, description="Order by column")
    order_direction: Optional[str] = Field("ASC", description="Order direction: ASC or DESC")
    limit: Optional[int] = Field(1000, ge=1, le=10000, description="Result row limit")
    
    @validator('aggregation')
    def validate_aggregation(cls, v):
        if v and v.lower() not in ['avg', 'sum', 'min', 'max', 'count', 'mean', 'std']:
            raise ValueError(f"Invalid aggregation: {v}")
        return v.lower() if v else None
    
    @validator('group_by')
    def validate_group_by(cls, v):
        valid_columns = {
            'platform_number', 'profile_time', 'latitude', 'longitude',
            'year', 'month', 'day', 'hour', 'depth_bin', 'region'
        }
        if v:
            for col in v:
                if col.lower() not in valid_columns:
                    raise ValueError(f"Invalid group_by column: {col}")
        return v
    
    @validator('order_direction')
    def validate_order_direction(cls, v):
        if v and v.upper() not in ['ASC', 'DESC']:
            raise ValueError(f"Invalid order direction: {v}")
        return v.upper() if v else 'ASC'


class StatisticalResult(BaseModel):
    """Structured statistical result."""
    
    column: str
    count: int
    mean: Optional[float] = None
    std: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None
    q25: Optional[float] = None
    q50: Optional[float] = None
    q75: Optional[float] = None


class PythonTool:
    """
    Safe Python execution tool for data processing and validation.
    
    This tool does NOT allow arbitrary code execution.
    It provides a set of predefined, safe operations.
    """
    
    ALLOWED_OPERATIONS = {
        'validate_parameters',
        'compute_statistics',
        'aggregate_data',
        'calculate_derived_values',
        'format_output',
        'preprocess_query',
    }
    
    def __init__(self, max_rows: int = 10000):
        """
        Initialize the Python tool.
        
        Args:
            max_rows: Maximum number of rows to process
        """
        self.max_rows = max_rows
    
    def execute(
        self, 
        operation: str, 
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a safe Python operation.
        
        Args:
            operation: Name of the operation to execute
            params: Parameters for the operation
            
        Returns:
            Result dictionary
        """
        if operation not in self.ALLOWED_OPERATIONS:
            raise ValueError(f"Operation '{operation}' is not allowed")
        
        method = getattr(self, f'_op_{operation}', None)
        if method is None:
            raise ValueError(f"Operation '{operation}' is not implemented")
        
        logger.info(f"Executing Python operation: {operation}")
        return method(params)
    
    def _op_validate_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and normalize query parameters.
        
        Args:
            params: Raw parameters from user query
            
        Returns:
            Validated parameters
        """
        try:
            validated = QueryParameters(**params)
            return {
                'status': 'success',
                'validated_params': validated.dict(exclude_none=True),
                'errors': None
            }
        except Exception as e:
            return {
                'status': 'error',
                'validated_params': None,
                'errors': str(e)
            }
    
    def _op_compute_statistics(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute statistics on data.
        
        Args:
            params: Dictionary with 'data' (list of dicts) and 'columns' to analyze
            
        Returns:
            Statistical results
        """
        data = params.get('data', [])
        columns = params.get('columns', ['temperature', 'salinity', 'pressure'])
        
        if not data:
            return {
                'status': 'error',
                'error': 'No data provided',
                'statistics': None
            }
        
        # Limit data size
        if len(data) > self.max_rows:
            data = data[:self.max_rows]
        
        df = pd.DataFrame(data)
        results = []
        
        for col in columns:
            if col not in df.columns:
                continue
            
            series = pd.to_numeric(df[col], errors='coerce').dropna()
            
            if len(series) == 0:
                continue
            
            stats = StatisticalResult(
                column=col,
                count=int(len(series)),
                mean=float(series.mean()),
                std=float(series.std()),
                min=float(series.min()),
                max=float(series.max()),
                q25=float(series.quantile(0.25)),
                q50=float(series.quantile(0.50)),
                q75=float(series.quantile(0.75)),
            )
            results.append(stats.dict())
        
        return {
            'status': 'success',
            'statistics': results,
            'row_count': len(data)
        }
    
    def _op_aggregate_data(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Aggregate data by specified columns.
        
        Args:
            params: Dictionary with 'data', 'group_by', 'aggregation', 'value_columns'
            
        Returns:
            Aggregated data
        """
        data = params.get('data', [])
        group_by = params.get('group_by', [])
        aggregation = params.get('aggregation', 'mean')
        value_columns = params.get('value_columns', ['temperature', 'salinity'])
        
        if not data:
            return {
                'status': 'error',
                'error': 'No data provided',
                'aggregated_data': None
            }
        
        if len(data) > self.max_rows:
            data = data[:self.max_rows]
        
        df = pd.DataFrame(data)
        
        # Validate columns exist
        missing_cols = [c for c in group_by if c not in df.columns]
        if missing_cols:
            return {
                'status': 'error',
                'error': f'Missing columns: {missing_cols}',
                'aggregated_data': None
            }
        
        # Apply aggregation
        agg_funcs = {
            'mean': 'mean',
            'avg': 'mean',
            'sum': 'sum',
            'min': 'min',
            'max': 'max',
            'count': 'count',
            'std': 'std',
        }
        
        agg_func = agg_funcs.get(aggregation.lower(), 'mean')
        
        # Filter value columns that exist
        valid_value_cols = [c for c in value_columns if c in df.columns]
        
        if not valid_value_cols:
            return {
                'status': 'error',
                'error': 'No valid value columns found',
                'aggregated_data': None
            }
        
        if group_by:
            result_df = df.groupby(group_by)[valid_value_cols].agg(agg_func).reset_index()
        else:
            result_df = df[valid_value_cols].agg(agg_func).to_frame().T
        
        # Handle NaN values
        result_df = result_df.replace({np.nan: None})
        
        return {
            'status': 'success',
            'aggregated_data': result_df.to_dict('records'),
            'columns': list(result_df.columns),
            'row_count': len(result_df)
        }
    
    def _op_calculate_derived_values(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate derived oceanographic values.
        
        Args:
            params: Dictionary with 'data' and 'calculations'
            
        Returns:
            Data with derived values
        """
        data = params.get('data', [])
        calculations = params.get('calculations', ['density', 'depth'])
        
        if not data:
            return {
                'status': 'error',
                'error': 'No data provided',
                'data': None
            }
        
        if len(data) > self.max_rows:
            data = data[:self.max_rows]
        
        df = pd.DataFrame(data)
        
        # Calculate potential density (simplified approximation)
        if 'density' in calculations:
            if 'temperature' in df.columns and 'salinity' in df.columns:
                # Simplified seawater density equation
                T = df['temperature'].fillna(20)
                S = df['salinity'].fillna(35)
                # UNESCO equation approximation
                df['density'] = (
                    999.842594 + 
                    6.793952e-2 * T - 
                    9.095290e-3 * T**2 + 
                    1.001685e-4 * T**3 - 
                    1.120083e-6 * T**4 + 
                    6.536336e-9 * T**5 +
                    S * (0.824493 - 4.0899e-3 * T + 7.6438e-5 * T**2 - 
                         8.2467e-7 * T**3 + 5.3875e-9 * T**4)
                )
        
        # Calculate depth from pressure (simplified)
        if 'depth' in calculations:
            if 'pressure' in df.columns:
                # Simplified: depth ≈ pressure * 1.019716
                df['depth'] = df['pressure'] * 1.019716
        
        # Calculate temperature anomaly
        if 'temp_anomaly' in calculations:
            if 'temperature' in df.columns:
                mean_temp = df['temperature'].mean()
                df['temp_anomaly'] = df['temperature'] - mean_temp
        
        # Handle NaN values
        df = df.replace({np.nan: None})
        
        return {
            'status': 'success',
            'data': df.to_dict('records'),
            'added_columns': [c for c in calculations if c in df.columns],
            'row_count': len(df)
        }
    
    def _op_format_output(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format data for output.
        
        Args:
            params: Dictionary with 'data', 'format_type', and options
            
        Returns:
            Formatted data
        """
        data = params.get('data', [])
        format_type = params.get('format_type', 'table')
        decimal_places = params.get('decimal_places', 2)
        
        if not data:
            return {
                'status': 'error',
                'error': 'No data provided',
                'formatted_data': None
            }
        
        df = pd.DataFrame(data)
        
        # Round numeric columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            df[col] = df[col].round(decimal_places)
        
        # Handle NaN values
        df = df.replace({np.nan: None})
        
        if format_type == 'table':
            return {
                'status': 'success',
                'formatted_data': df.to_dict('records'),
                'columns': list(df.columns),
                'row_count': len(df)
            }
        elif format_type == 'summary':
            summary = {
                'total_rows': len(df),
                'columns': list(df.columns),
                'numeric_summary': {}
            }
            for col in numeric_cols:
                summary['numeric_summary'][col] = {
                    'min': df[col].min(),
                    'max': df[col].max(),
                    'mean': df[col].mean(),
                }
            return {
                'status': 'success',
                'formatted_data': summary
            }
        else:
            return {
                'status': 'error',
                'error': f'Unknown format type: {format_type}',
                'formatted_data': None
            }
    
    def _op_preprocess_query(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Preprocess query parameters for SQL generation.
        
        Args:
            params: Dictionary with raw query parameters
            
        Returns:
            Preprocessed parameters ready for SQL tool
        """
        # Validate parameters first
        validation = self._op_validate_parameters(params)
        if validation['status'] == 'error':
            return validation
        
        validated_params = validation['validated_params']
        
        # Add derived parameters
        preprocessed = {
            **validated_params,
            'processed_at': datetime.utcnow().isoformat(),
        }
        
        # Note: No default date range applied - queries work on all available data
        # Users can explicitly filter by date if needed
        
        # Set default limit if not provided
        if 'limit' not in preprocessed:
            preprocessed['limit'] = 1000
        
        return {
            'status': 'success',
            'preprocessed_params': preprocessed
        }


# Singleton instance
python_tool = PythonTool()


def execute_python_operation(
    operation: str, 
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Execute a Python tool operation.
    
    Args:
        operation: Operation name
        params: Operation parameters
        
    Returns:
        Operation result
    """
    return python_tool.execute(operation, params)
