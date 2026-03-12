"""
Plot Tool for automated visualization generation.

This tool:
- Automatically selects appropriate chart types
- Generates structured plot configurations for React
- Supports multiple visualization types
- Produces JSON compatible with common React chart libraries
"""

import logging
from typing import Any, Dict, List, Optional, Union
from enum import Enum
from pydantic import BaseModel, Field
import numpy as np

logger = logging.getLogger(__name__)


class ChartType(str, Enum):
    """Supported chart types."""
    LINE = "line"
    BAR = "bar"
    SCATTER = "scatter"
    HISTOGRAM = "histogram"
    HEATMAP = "heatmap"
    MAP = "map"
    AREA = "area"
    PIE = "pie"
    PROFILE = "profile"  # Inverted line plot for depth profiles


class AxisConfig(BaseModel):
    """Axis configuration."""
    label: str
    field: str
    type: str = "number"  # number, time, category
    min: Optional[float] = None
    max: Optional[float] = None
    inverted: bool = False
    tick_format: Optional[str] = None


class SeriesConfig(BaseModel):
    """Data series configuration."""
    name: str
    field: str
    color: Optional[str] = None
    type: Optional[str] = None  # For mixed charts


class PlotConfig(BaseModel):
    """Complete plot configuration."""
    chart_type: ChartType
    title: str
    subtitle: Optional[str] = None
    x_axis: AxisConfig
    y_axis: AxisConfig
    series: List[SeriesConfig]
    data: List[Dict[str, Any]]
    options: Dict[str, Any] = Field(default_factory=dict)
    legend: bool = True
    tooltip: bool = True
    responsive: bool = True


class PlotTool:
    """
    Visualization tool for generating chart configurations.
    
    Auto-selects chart types based on data characteristics:
    - Time-based → Line chart
    - Depth-based → Inverted line (profile) plot
    - Distribution → Histogram
    - Comparison → Bar chart
    - Correlation → Scatter plot
    - Geographic → Map visualization
    """
    
    # Color palette for visualizations
    COLORS = [
        "#2563eb",  # Blue
        "#dc2626",  # Red
        "#16a34a",  # Green
        "#ca8a04",  # Yellow
        "#9333ea",  # Purple
        "#0891b2",  # Cyan
        "#ea580c",  # Orange
        "#4f46e5",  # Indigo
    ]
    
    # Variable display names and units
    VARIABLE_INFO = {
        'temperature': {'name': 'Temperature', 'unit': '°C'},
        'salinity': {'name': 'Salinity', 'unit': 'PSU'},
        'pressure': {'name': 'Pressure/Depth', 'unit': 'dbar'},
        'depth': {'name': 'Depth', 'unit': 'm'},
        'latitude': {'name': 'Latitude', 'unit': '°'},
        'longitude': {'name': 'Longitude', 'unit': '°'},
        'density': {'name': 'Density', 'unit': 'kg/m³'},
    }
    
    def __init__(self):
        """Initialize the plot tool."""
        pass
    
    def auto_select_chart_type(
        self, 
        data: List[Dict[str, Any]], 
        intent: Dict[str, Any]
    ) -> ChartType:
        """
        Automatically select the appropriate chart type.
        
        Args:
            data: Data to visualize
            intent: Query intent with context
            
        Returns:
            Recommended chart type
        """
        query_type = intent.get('query_type', '')
        columns = list(data[0].keys()) if data else []
        
        # Check for time series
        time_cols = ['time_bucket', 'profile_time', 'year', 'month', 'day', 'date']
        has_time = any(col in columns for col in time_cols)
        
        # Check for depth/pressure data
        depth_cols = ['pressure', 'depth', 'depth_bin']
        has_depth = any(col in columns for col in depth_cols)
        
        # Check for geographic data
        geo_cols = ['latitude', 'longitude', 'lat', 'lon']
        has_geo = sum(1 for col in geo_cols if col in columns) >= 2
        
        # Check for aggregated/grouped data
        is_aggregated = 'aggregation' in intent or any(
            col.startswith(('avg_', 'sum_', 'min_', 'max_', 'count'))
            for col in columns
        )
        
        # Decision logic
        if query_type == 'profile' or (has_depth and 'temperature' in columns):
            return ChartType.PROFILE
        
        if has_geo and not has_time:
            return ChartType.MAP
        
        if has_time:
            return ChartType.LINE
        
        if query_type == 'statistics' or intent.get('show_distribution'):
            return ChartType.HISTOGRAM
        
        if is_aggregated and len(data) <= 20:
            return ChartType.BAR
        
        # Check for correlation analysis
        numeric_cols = [c for c in columns if c not in ['platform_number', 'profile_time']]
        if len(numeric_cols) >= 2 and len(data) > 10:
            return ChartType.SCATTER
        
        # Default to line if multiple data points, bar otherwise
        if len(data) > 10:
            return ChartType.LINE
        
        return ChartType.BAR
    
    def generate_plot_config(
        self,
        data: List[Dict[str, Any]],
        intent: Dict[str, Any],
        chart_type: ChartType = None
    ) -> Dict[str, Any]:
        """
        Generate a complete plot configuration.
        
        Args:
            data: Data to visualize
            intent: Query intent with context
            chart_type: Override auto-selected chart type
            
        Returns:
            Plot configuration dictionary
        """
        if not data:
            return self._empty_config(intent)
        
        # Auto-select chart type if not specified
        if chart_type is None:
            chart_type = self.auto_select_chart_type(data, intent)
        
        logger.info(f"Generating {chart_type.value} plot for {len(data)} data points")
        
        # Generate based on chart type
        if chart_type == ChartType.LINE:
            return self._generate_line_config(data, intent)
        elif chart_type == ChartType.BAR:
            return self._generate_bar_config(data, intent)
        elif chart_type == ChartType.SCATTER:
            return self._generate_scatter_config(data, intent)
        elif chart_type == ChartType.HISTOGRAM:
            return self._generate_histogram_config(data, intent)
        elif chart_type == ChartType.PROFILE:
            return self._generate_profile_config(data, intent)
        elif chart_type == ChartType.MAP:
            return self._generate_map_config(data, intent)
        elif chart_type == ChartType.HEATMAP:
            return self._generate_heatmap_config(data, intent)
        else:
            return self._generate_line_config(data, intent)
    
    def _get_variable_label(self, field: str) -> str:
        """Get display label for a variable."""
        if field in self.VARIABLE_INFO:
            info = self.VARIABLE_INFO[field]
            return f"{info['name']} ({info['unit']})"
        
        # Check for aggregated fields
        for prefix in ['avg_', 'mean_', 'sum_', 'min_', 'max_', 'count_']:
            if field.startswith(prefix):
                base = field[len(prefix):]
                agg_name = prefix.rstrip('_').title()
                if base in self.VARIABLE_INFO:
                    info = self.VARIABLE_INFO[base]
                    return f"{agg_name} {info['name']} ({info['unit']})"
                return f"{agg_name} {base.title()}"
        
        return field.replace('_', ' ').title()
    
    def _empty_config(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Generate empty plot configuration."""
        return {
            'chart_type': 'empty',
            'title': 'No Data Available',
            'subtitle': intent.get('description', 'No matching data found'),
            'data': [],
            'message': 'The query returned no data to visualize'
        }
    
    def _generate_line_config(
        self, 
        data: List[Dict[str, Any]], 
        intent: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate line chart configuration."""
        columns = list(data[0].keys())
        
        # Find x-axis (time column)
        x_field = None
        for col in ['time_bucket', 'profile_time', 'year', 'month', 'date']:
            if col in columns:
                x_field = col
                break
        
        if x_field is None:
            x_field = columns[0]
        
        # Find y-axis values (numeric columns)
        excluded = {x_field, 'platform_number', 'id', 'count', 'measurement_count'}
        y_fields = [c for c in columns if c not in excluded and not c.endswith('_id')]
        
        # Build series
        series = []
        for i, field in enumerate(y_fields[:4]):  # Max 4 series
            series.append({
                'name': self._get_variable_label(field),
                'field': field,
                'color': self.COLORS[i % len(self.COLORS)]
            })
        
        return {
            'chart_type': 'line',
            'title': intent.get('title', 'Time Series Analysis'),
            'subtitle': intent.get('description', ''),
            'x_axis': {
                'label': self._get_variable_label(x_field),
                'field': x_field,
                'type': 'time' if 'time' in x_field or 'date' in x_field else 'category'
            },
            'y_axis': {
                'label': self._get_variable_label(y_fields[0]) if y_fields else 'Value',
                'field': y_fields[0] if y_fields else 'value',
                'type': 'number'
            },
            'series': series,
            'data': data,
            'options': {
                'smooth': True,
                'showPoints': len(data) <= 50,
                'animation': True
            },
            'legend': len(series) > 1,
            'tooltip': True,
            'responsive': True
        }
    
    def _generate_bar_config(
        self, 
        data: List[Dict[str, Any]], 
        intent: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate bar chart configuration."""
        columns = list(data[0].keys())
        
        # Find category field
        category_fields = ['platform_number', 'year', 'month', 'depth_bin', 'region']
        x_field = None
        for col in category_fields:
            if col in columns:
                x_field = col
                break
        
        if x_field is None:
            x_field = columns[0]
        
        # Find value fields
        excluded = {x_field, 'id', 'count'}
        y_fields = [c for c in columns if c not in excluded and not c.endswith('_id')]
        
        series = []
        for i, field in enumerate(y_fields[:3]):
            series.append({
                'name': self._get_variable_label(field),
                'field': field,
                'color': self.COLORS[i % len(self.COLORS)]
            })
        
        return {
            'chart_type': 'bar',
            'title': intent.get('title', 'Comparison Analysis'),
            'subtitle': intent.get('description', ''),
            'x_axis': {
                'label': self._get_variable_label(x_field),
                'field': x_field,
                'type': 'category'
            },
            'y_axis': {
                'label': self._get_variable_label(y_fields[0]) if y_fields else 'Value',
                'field': y_fields[0] if y_fields else 'value',
                'type': 'number'
            },
            'series': series,
            'data': data,
            'options': {
                'stacked': False,
                'horizontal': len(data) > 10,
                'animation': True
            },
            'legend': len(series) > 1,
            'tooltip': True,
            'responsive': True
        }
    
    def _generate_scatter_config(
        self, 
        data: List[Dict[str, Any]], 
        intent: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate scatter plot configuration."""
        columns = list(data[0].keys())
        
        # Find x and y numeric fields
        numeric_candidates = ['temperature', 'salinity', 'pressure', 'latitude', 'longitude']
        numeric_fields = [c for c in columns if c in numeric_candidates or 
                         any(c.startswith(p) for p in ['avg_', 'mean_', 'sum_'])]
        
        x_field = numeric_fields[0] if len(numeric_fields) > 0 else columns[0]
        y_field = numeric_fields[1] if len(numeric_fields) > 1 else columns[1]
        
        # Color by category if available
        color_field = None
        for col in ['platform_number', 'year', 'month']:
            if col in columns:
                color_field = col
                break
        
        return {
            'chart_type': 'scatter',
            'title': intent.get('title', 'Correlation Analysis'),
            'subtitle': intent.get('description', f'{self._get_variable_label(x_field)} vs {self._get_variable_label(y_field)}'),
            'x_axis': {
                'label': self._get_variable_label(x_field),
                'field': x_field,
                'type': 'number'
            },
            'y_axis': {
                'label': self._get_variable_label(y_field),
                'field': y_field,
                'type': 'number'
            },
            'series': [{
                'name': 'Data Points',
                'x_field': x_field,
                'y_field': y_field,
                'color_field': color_field,
                'color': self.COLORS[0]
            }],
            'data': data,
            'options': {
                'point_size': 6,
                'opacity': 0.7,
                'show_regression': True,
                'animation': True
            },
            'legend': color_field is not None,
            'tooltip': True,
            'responsive': True
        }
    
    def _generate_histogram_config(
        self, 
        data: List[Dict[str, Any]], 
        intent: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate histogram configuration."""
        columns = list(data[0].keys())
        
        # Find numeric field to histogram
        value_field = intent.get('column', 'temperature')
        if value_field not in columns:
            for col in ['temperature', 'salinity', 'pressure']:
                if col in columns:
                    value_field = col
                    break
        
        # Extract values and compute bins
        values = [row.get(value_field) for row in data if row.get(value_field) is not None]
        
        if values:
            hist_values, bin_edges = np.histogram(values, bins=20)
            hist_data = [
                {
                    'bin_start': float(bin_edges[i]),
                    'bin_end': float(bin_edges[i + 1]),
                    'bin_label': f"{bin_edges[i]:.1f}-{bin_edges[i+1]:.1f}",
                    'count': int(hist_values[i])
                }
                for i in range(len(hist_values))
            ]
        else:
            hist_data = []
        
        return {
            'chart_type': 'histogram',
            'title': intent.get('title', f'Distribution of {self._get_variable_label(value_field)}'),
            'subtitle': intent.get('description', f'Based on {len(values)} measurements'),
            'x_axis': {
                'label': self._get_variable_label(value_field),
                'field': 'bin_label',
                'type': 'category'
            },
            'y_axis': {
                'label': 'Frequency',
                'field': 'count',
                'type': 'number'
            },
            'series': [{
                'name': 'Frequency',
                'field': 'count',
                'color': self.COLORS[0]
            }],
            'data': hist_data,
            'options': {
                'bin_count': 20,
                'show_density': False,
                'animation': True
            },
            'statistics': {
                'mean': float(np.mean(values)) if values else None,
                'std': float(np.std(values)) if values else None,
                'min': float(np.min(values)) if values else None,
                'max': float(np.max(values)) if values else None,
                'count': len(values)
            },
            'legend': False,
            'tooltip': True,
            'responsive': True
        }
    
    def _generate_profile_config(
        self, 
        data: List[Dict[str, Any]], 
        intent: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate depth profile (inverted line) configuration."""
        columns = list(data[0].keys())
        
        # Y-axis is depth/pressure (inverted)
        y_field = 'pressure' if 'pressure' in columns else 'depth'
        
        # X-axis values
        x_fields = []
        for col in ['temperature', 'salinity']:
            if col in columns:
                x_fields.append(col)
        
        if not x_fields:
            x_fields = [c for c in columns if c not in [y_field, 'platform_number', 'profile_time', 'latitude', 'longitude']]
        
        series = []
        for i, field in enumerate(x_fields[:2]):
            series.append({
                'name': self._get_variable_label(field),
                'field': field,
                'color': self.COLORS[i % len(self.COLORS)]
            })
        
        return {
            'chart_type': 'profile',
            'title': intent.get('title', 'Depth Profile'),
            'subtitle': intent.get('description', 'Temperature and Salinity vs Depth'),
            'x_axis': {
                'label': self._get_variable_label(x_fields[0]) if x_fields else 'Value',
                'field': x_fields[0] if x_fields else 'value',
                'type': 'number'
            },
            'y_axis': {
                'label': self._get_variable_label(y_field),
                'field': y_field,
                'type': 'number',
                'inverted': True  # Key for depth profiles
            },
            'series': series,
            'data': sorted(data, key=lambda x: x.get(y_field, 0)),
            'options': {
                'smooth': True,
                'showPoints': True,
                'animation': True
            },
            'legend': len(series) > 1,
            'tooltip': True,
            'responsive': True
        }
    
    def _generate_map_config(
        self, 
        data: List[Dict[str, Any]], 
        intent: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate map visualization configuration."""
        columns = list(data[0].keys())
        
        # Find value field for coloring
        value_field = None
        for col in ['avg_temperature', 'temperature', 'avg_salinity', 'salinity', 'measurement_count']:
            if col in columns:
                value_field = col
                break
        
        return {
            'chart_type': 'map',
            'title': intent.get('title', 'Geographic Distribution'),
            'subtitle': intent.get('description', 'ARGO Float Observations'),
            'latitude_field': 'latitude' if 'latitude' in columns else 'lat',
            'longitude_field': 'longitude' if 'longitude' in columns else 'lon',
            'value_field': value_field,
            'data': data,
            'options': {
                'center': [0, 70],  # Indian Ocean center
                'zoom': 3,
                'marker_size': 8,
                'color_scale': 'viridis',
                'show_legend': value_field is not None,
                'cluster_markers': len(data) > 100,
                'animation': True
            },
            'bounds': {
                'lat_min': -60,
                'lat_max': 30,
                'lon_min': 20,
                'lon_max': 120
            },
            'legend': value_field is not None,
            'tooltip': True,
            'responsive': True
        }
    
    def _generate_heatmap_config(
        self, 
        data: List[Dict[str, Any]], 
        intent: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate heatmap configuration."""
        columns = list(data[0].keys())
        
        # Find dimensions and value
        x_field = 'longitude' if 'longitude' in columns else columns[0]
        y_field = 'latitude' if 'latitude' in columns else columns[1]
        value_field = intent.get('column', 'temperature')
        
        return {
            'chart_type': 'heatmap',
            'title': intent.get('title', 'Heat Map'),
            'subtitle': intent.get('description', ''),
            'x_axis': {
                'label': self._get_variable_label(x_field),
                'field': x_field,
                'type': 'number'
            },
            'y_axis': {
                'label': self._get_variable_label(y_field),
                'field': y_field,
                'type': 'number'
            },
            'value_field': value_field,
            'value_label': self._get_variable_label(value_field),
            'data': data,
            'options': {
                'color_scale': 'RdBu',
                'reverse_scale': False,
                'animation': True
            },
            'legend': True,
            'tooltip': True,
            'responsive': True
        }


# Singleton instance
plot_tool = PlotTool()


def generate_visualization(
    data: List[Dict[str, Any]],
    intent: Dict[str, Any],
    chart_type: str = None
) -> Dict[str, Any]:
    """
    Generate visualization configuration.
    
    Args:
        data: Data to visualize
        intent: Query intent
        chart_type: Override chart type (optional)
        
    Returns:
        Plot configuration dictionary
    """
    ct = ChartType(chart_type) if chart_type else None
    return plot_tool.generate_plot_config(data, intent, ct)


def auto_select_chart(
    data: List[Dict[str, Any]],
    intent: Dict[str, Any]
) -> str:
    """
    Auto-select appropriate chart type.
    
    Args:
        data: Data to visualize
        intent: Query intent
        
    Returns:
        Chart type string
    """
    return plot_tool.auto_select_chart_type(data, intent).value
