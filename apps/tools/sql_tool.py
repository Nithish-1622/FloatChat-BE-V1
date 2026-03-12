"""
SQL Tool for safe Text-to-SQL execution.

This tool:
- Converts natural language to SQL
- Validates queries before execution
- Enforces SELECT-only operations
- Blocks dangerous operations (DELETE, DROP, UPDATE, INSERT)
- Supports schema-aware query generation
"""

import re
import logging
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import os

from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# Database schema definition for AI context
DATABASE_SCHEMA = """
Database Schema for ARGO Ocean Data:

Table: floats
  - id: INTEGER PRIMARY KEY
  - platform_number: VARCHAR(20) UNIQUE NOT NULL (ARGO float identifier)
  - first_seen: TIMESTAMP (first observation time)
  - last_seen: TIMESTAMP (last observation time)

Table: profiles
  - id: INTEGER PRIMARY KEY
  - float_id: INTEGER FOREIGN KEY REFERENCES floats(id)
  - latitude: FLOAT NOT NULL (degrees, -90 to 90)
  - longitude: FLOAT NOT NULL (degrees, -180 to 180)
  - profile_time: TIMESTAMP NOT NULL (measurement time)
  - UNIQUE(float_id, profile_time)

Table: measurements
  - id: INTEGER PRIMARY KEY
  - profile_id: INTEGER FOREIGN KEY REFERENCES profiles(id)
  - pressure: FLOAT (decibars, equivalent to depth in meters)
  - temperature: FLOAT (degrees Celsius)
  - salinity: FLOAT (PSU - Practical Salinity Units)

Table: processed_files
  - id: INTEGER PRIMARY KEY
  - file_path: VARCHAR(500) UNIQUE
  - file_name: VARCHAR(255)
  - processed_at: TIMESTAMP
  - records_inserted: INTEGER
  - status: VARCHAR(20) ('success', 'failed', 'partial')

Important Notes:
- pressure in decibars ≈ depth in meters (pressure * 1.019716)
- Indian Ocean region: lat -60 to 30, lon 20 to 120
- Temperature range: -2 to 40°C
- Salinity range: 0 to 45 PSU
"""

# Dangerous SQL patterns to block
DANGEROUS_PATTERNS = [
    r'\bDELETE\b',
    r'\bDROP\b',
    r'\bTRUNCATE\b',
    r'\bUPDATE\b',
    r'\bINSERT\b',
    r'\bALTER\b',
    r'\bCREATE\b',
    r'\bGRANT\b',
    r'\bREVOKE\b',
    r'\bEXEC\b',
    r'\bEXECUTE\b',
    r';\s*--',  # SQL injection attempts
    r'UNION\s+ALL\s+SELECT',  # Potential injection
    r'INTO\s+OUTFILE',
    r'INTO\s+DUMPFILE',
    r'LOAD_FILE',
]


class SQLQueryResult(BaseModel):
    """Structured SQL query result."""
    
    success: bool
    data: Optional[List[Dict[str, Any]]] = None
    columns: Optional[List[str]] = None
    row_count: int = 0
    execution_time_ms: float = 0
    query: Optional[str] = None
    error: Optional[str] = None


class SQLTool:
    """
    Safe SQL execution tool for ARGO ocean data queries.
    
    Features:
    - Schema-aware query validation
    - SELECT-only enforcement
    - Query timeout handling
    - Result pagination
    - Dangerous pattern blocking
    """
    
    def __init__(
        self, 
        database_url: str = None,
        max_rows: int = 10000,
        timeout_seconds: int = 30
    ):
        """
        Initialize the SQL tool.
        
        Args:
            database_url: PostgreSQL connection string
            max_rows: Maximum rows to return
            timeout_seconds: Query timeout
        """
        self.database_url = database_url or os.getenv('DATABASE_URL')
        self.max_rows = max_rows
        self.timeout_seconds = timeout_seconds
        self._engine = None
    
    @property
    def engine(self):
        """Lazy-load database engine."""
        if self._engine is None:
            if not self.database_url:
                raise ValueError("DATABASE_URL is not configured")
            
            conn_str = self.database_url
            
            # Check if using SQLite
            if conn_str.startswith('sqlite'):
                self._engine = create_engine(conn_str)
                self._is_sqlite = True
            else:
                # Ensure SSL for Neon PostgreSQL
                if 'sslmode' not in conn_str:
                    conn_str += '?sslmode=require' if '?' not in conn_str else '&sslmode=require'
                
                self._engine = create_engine(
                    conn_str,
                    poolclass=QueuePool,
                    pool_size=5,
                    max_overflow=10,
                    pool_timeout=30,
                    pool_pre_ping=True,
                )
                self._is_sqlite = False
        return self._engine
    
    @property
    def is_sqlite(self):
        """Check if using SQLite database."""
        # Ensure engine is initialized
        _ = self.engine
        return getattr(self, '_is_sqlite', False)
    
    def get_schema(self) -> str:
        """Get the database schema definition."""
        return DATABASE_SCHEMA
    
    def validate_query(self, query: str) -> Tuple[bool, Optional[str]]:
        """
        Validate SQL query for safety.
        
        Args:
            query: SQL query string
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Normalize query
        normalized = query.upper().strip()
        
        # Check if it starts with SELECT
        if not normalized.startswith('SELECT'):
            return False, "Only SELECT queries are allowed"
        
        # Check for dangerous patterns
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, normalized, re.IGNORECASE):
                return False, f"Query contains forbidden pattern: {pattern}"
        
        # Check for multiple statements
        if ';' in query[:-1]:  # Allow trailing semicolon
            return False, "Multiple SQL statements are not allowed"
        
        # Check for subqueries that might modify data
        if 'INTO' in normalized and 'INSERT' not in normalized:
            # SELECT INTO is blocked
            if 'INTO' in normalized.split('FROM')[0]:
                return False, "SELECT INTO is not allowed"
        
        return True, None
    
    def execute(
        self, 
        query: str, 
        params: Dict[str, Any] = None
    ) -> SQLQueryResult:
        """
        Execute a validated SQL query.
        
        Args:
            query: SQL query string
            params: Query parameters for safe binding
            
        Returns:
            SQLQueryResult with data or error
        """
        # Validate query
        is_valid, error = self.validate_query(query)
        if not is_valid:
            logger.warning(f"Invalid query rejected: {error}")
            return SQLQueryResult(
                success=False,
                error=error,
                query=query
            )
        
        # Add LIMIT if not present
        if 'LIMIT' not in query.upper():
            query = f"{query.rstrip(';')} LIMIT {self.max_rows}"
        
        start_time = datetime.now()
        
        try:
            with self.engine.connect() as conn:
                # Set statement timeout (PostgreSQL only)
                if not self.is_sqlite:
                    conn.execute(
                        text(f"SET statement_timeout = '{self.timeout_seconds}s'")
                    )
                
                # Execute query
                if params:
                    result = conn.execute(text(query), params)
                else:
                    result = conn.execute(text(query))
                
                # Fetch results
                columns = list(result.keys())
                rows = result.fetchall()
                
                # Convert to list of dicts
                data = [dict(zip(columns, row)) for row in rows]
                
                # Handle datetime serialization
                for row in data:
                    for key, value in row.items():
                        if isinstance(value, datetime):
                            row[key] = value.isoformat()
                
                execution_time = (datetime.now() - start_time).total_seconds() * 1000
                
                logger.info(f"Query executed successfully: {len(data)} rows in {execution_time:.2f}ms")
                
                return SQLQueryResult(
                    success=True,
                    data=data,
                    columns=columns,
                    row_count=len(data),
                    execution_time_ms=execution_time,
                    query=query
                )
                
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Query execution failed: {e}")
            
            return SQLQueryResult(
                success=False,
                error=str(e),
                execution_time_ms=execution_time,
                query=query
            )
    
    def generate_query(self, intent: Dict[str, Any]) -> str:
        """
        Generate SQL query from structured intent.
        
        Args:
            intent: Dictionary with query intent and parameters
            
        Returns:
            Generated SQL query
        """
        query_type = intent.get('query_type', 'data')
        
        if query_type == 'count':
            return self._generate_count_query(intent)
        elif query_type == 'aggregate':
            return self._generate_aggregate_query(intent)
        elif query_type == 'time_series':
            return self._generate_time_series_query(intent)
        elif query_type == 'profile':
            return self._generate_profile_query(intent)
        elif query_type == 'spatial':
            return self._generate_spatial_query(intent)
        elif query_type == 'statistics':
            return self._generate_statistics_query(intent)
        else:
            return self._generate_data_query(intent)
    
    def _generate_count_query(self, intent: Dict[str, Any]) -> str:
        """Generate COUNT query."""
        table = intent.get('table', 'measurements')
        where_clause = self._build_where_clause(intent)
        
        if table == 'floats':
            return f"SELECT COUNT(*) as count FROM floats"
        elif table == 'profiles':
            query = f"""
            SELECT COUNT(*) as count 
            FROM profiles p
            JOIN floats f ON p.float_id = f.id
            {where_clause}
            """
        else:
            query = f"""
            SELECT COUNT(*) as count 
            FROM measurements m
            JOIN profiles p ON m.profile_id = p.id
            JOIN floats f ON p.float_id = f.id
            {where_clause}
            """
        return query.strip()
    
    def _generate_aggregate_query(self, intent: Dict[str, Any]) -> str:
        """Generate aggregate query."""
        aggregation = intent.get('aggregation', 'avg')
        column = intent.get('column', 'temperature')
        group_by = intent.get('group_by', [])
        where_clause = self._build_where_clause(intent)
        
        # Map aggregation functions
        agg_map = {
            'avg': 'AVG', 'mean': 'AVG',
            'sum': 'SUM', 'min': 'MIN', 'max': 'MAX',
            'count': 'COUNT', 'std': 'STDDEV'
        }
        agg_func = agg_map.get(aggregation.lower(), 'AVG')
        
        # Build select columns
        select_cols = [f"{agg_func}(m.{column}) as {aggregation}_{column}"]
        group_cols = []
        
        for gb in group_by:
            if gb == 'year':
                select_cols.insert(0, "EXTRACT(YEAR FROM p.profile_time) as year")
                group_cols.append("EXTRACT(YEAR FROM p.profile_time)")
            elif gb == 'month':
                select_cols.insert(0, "EXTRACT(MONTH FROM p.profile_time) as month")
                group_cols.append("EXTRACT(MONTH FROM p.profile_time)")
            elif gb == 'platform_number':
                select_cols.insert(0, "f.platform_number")
                group_cols.append("f.platform_number")
            elif gb == 'depth_bin':
                select_cols.insert(0, "FLOOR(m.pressure / 100) * 100 as depth_bin")
                group_cols.append("FLOOR(m.pressure / 100)")
        
        query = f"""
        SELECT {', '.join(select_cols)}
        FROM measurements m
        JOIN profiles p ON m.profile_id = p.id
        JOIN floats f ON p.float_id = f.id
        {where_clause}
        """
        
        if group_cols:
            query += f"\nGROUP BY {', '.join(group_cols)}"
        
        # Add ORDER BY
        if group_cols:
            query += f"\nORDER BY {group_cols[0]}"
        
        return query.strip()
    
    def _generate_time_series_query(self, intent: Dict[str, Any]) -> str:
        """Generate time series query."""
        column = intent.get('column', 'temperature')
        interval = intent.get('interval', 'day')
        aggregation = intent.get('aggregation', 'avg')
        where_clause = self._build_where_clause(intent)
        
        agg_map = {'avg': 'AVG', 'mean': 'AVG', 'min': 'MIN', 'max': 'MAX'}
        agg_func = agg_map.get(aggregation.lower(), 'AVG')
        
        # Time truncation based on interval
        time_trunc = f"DATE_TRUNC('{interval}', p.profile_time)"
        
        query = f"""
        SELECT 
            {time_trunc} as time_bucket,
            {agg_func}(m.{column}) as {aggregation}_{column},
            COUNT(*) as measurement_count
        FROM measurements m
        JOIN profiles p ON m.profile_id = p.id
        JOIN floats f ON p.float_id = f.id
        {where_clause}
        GROUP BY {time_trunc}
        ORDER BY time_bucket
        """
        
        return query.strip()
    
    def _generate_profile_query(self, intent: Dict[str, Any]) -> str:
        """Generate depth profile query."""
        platform_number = intent.get('platform_number')
        profile_id = intent.get('profile_id')
        where_clause = self._build_where_clause(intent)
        
        query = f"""
        SELECT 
            f.platform_number,
            p.profile_time,
            p.latitude,
            p.longitude,
            m.pressure,
            m.temperature,
            m.salinity
        FROM measurements m
        JOIN profiles p ON m.profile_id = p.id
        JOIN floats f ON p.float_id = f.id
        {where_clause}
        ORDER BY f.platform_number, p.profile_time, m.pressure
        """
        
        return query.strip()
    
    def _generate_spatial_query(self, intent: Dict[str, Any]) -> str:
        """Generate spatial/geographic query."""
        column = intent.get('column', 'temperature')
        aggregation = intent.get('aggregation', 'avg')
        where_clause = self._build_where_clause(intent)
        
        agg_map = {'avg': 'AVG', 'mean': 'AVG', 'min': 'MIN', 'max': 'MAX'}
        agg_func = agg_map.get(aggregation.lower(), 'AVG')
        
        query = f"""
        SELECT 
            p.latitude,
            p.longitude,
            {agg_func}(m.{column}) as {aggregation}_{column},
            COUNT(*) as measurement_count
        FROM measurements m
        JOIN profiles p ON m.profile_id = p.id
        JOIN floats f ON p.float_id = f.id
        {where_clause}
        GROUP BY p.latitude, p.longitude
        ORDER BY p.latitude, p.longitude
        """
        
        return query.strip()
    
    def _generate_statistics_query(self, intent: Dict[str, Any]) -> str:
        """Generate statistics query."""
        column = intent.get('column', 'temperature')
        where_clause = self._build_where_clause(intent)
        
        query = f"""
        SELECT 
            COUNT(m.{column}) as count,
            AVG(m.{column}) as mean,
            STDDEV(m.{column}) as std,
            MIN(m.{column}) as min,
            MAX(m.{column}) as max,
            PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY m.{column}) as q25,
            PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY m.{column}) as median,
            PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY m.{column}) as q75
        FROM measurements m
        JOIN profiles p ON m.profile_id = p.id
        JOIN floats f ON p.float_id = f.id
        {where_clause}
        """
        
        return query.strip()
    
    def _generate_data_query(self, intent: Dict[str, Any]) -> str:
        """Generate generic data query."""
        columns = intent.get('columns', ['temperature', 'salinity', 'pressure'])
        where_clause = self._build_where_clause(intent)
        limit = intent.get('limit', 1000)
        
        select_cols = [
            'f.platform_number',
            'p.profile_time',
            'p.latitude',
            'p.longitude'
        ]
        
        for col in columns:
            if col in ['pressure', 'temperature', 'salinity']:
                select_cols.append(f'm.{col}')
        
        query = f"""
        SELECT {', '.join(select_cols)}
        FROM measurements m
        JOIN profiles p ON m.profile_id = p.id
        JOIN floats f ON p.float_id = f.id
        {where_clause}
        ORDER BY p.profile_time DESC
        LIMIT {limit}
        """
        
        return query.strip()
    
    def _build_where_clause(self, intent: Dict[str, Any]) -> str:
        """Build WHERE clause from intent."""
        conditions = []
        
        # Date filters
        start_date = intent.get('start_date')
        end_date = intent.get('end_date')
        if start_date:
            conditions.append(f"p.profile_time >= '{start_date}'")
        if end_date:
            conditions.append(f"p.profile_time <= '{end_date}'")
        
        # Platform filter
        platform_numbers = intent.get('platform_numbers', [])
        if platform_numbers:
            platforms_str = ','.join(f"'{p}'" for p in platform_numbers)
            conditions.append(f"f.platform_number IN ({platforms_str})")
        
        platform_number = intent.get('platform_number')
        if platform_number:
            conditions.append(f"f.platform_number = '{platform_number}'")
        
        # Geographic filters
        min_lat = intent.get('min_latitude')
        max_lat = intent.get('max_latitude')
        min_lon = intent.get('min_longitude')
        max_lon = intent.get('max_longitude')
        
        if min_lat is not None:
            conditions.append(f"p.latitude >= {min_lat}")
        if max_lat is not None:
            conditions.append(f"p.latitude <= {max_lat}")
        if min_lon is not None:
            conditions.append(f"p.longitude >= {min_lon}")
        if max_lon is not None:
            conditions.append(f"p.longitude <= {max_lon}")
        
        # Depth/pressure filters
        min_depth = intent.get('min_depth')
        max_depth = intent.get('max_depth')
        if min_depth is not None:
            conditions.append(f"m.pressure >= {min_depth}")
        if max_depth is not None:
            conditions.append(f"m.pressure <= {max_depth}")
        
        # Temperature filters
        min_temp = intent.get('min_temperature')
        max_temp = intent.get('max_temperature')
        if min_temp is not None:
            conditions.append(f"m.temperature >= {min_temp}")
        if max_temp is not None:
            conditions.append(f"m.temperature <= {max_temp}")
        
        # Salinity filters
        min_sal = intent.get('min_salinity')
        max_sal = intent.get('max_salinity')
        if min_sal is not None:
            conditions.append(f"m.salinity >= {min_sal}")
        if max_sal is not None:
            conditions.append(f"m.salinity <= {max_sal}")
        
        if conditions:
            return "WHERE " + " AND ".join(conditions)
        return ""


# Singleton instance
sql_tool = SQLTool()


def execute_sql_query(
    query: str, 
    params: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Execute a SQL query using the SQL tool.
    
    Args:
        query: SQL query string
        params: Query parameters
        
    Returns:
        Query result dictionary
    """
    result = sql_tool.execute(query, params)
    return result.dict()


def generate_sql_from_intent(intent: Dict[str, Any]) -> str:
    """
    Generate SQL from structured intent.
    
    Args:
        intent: Query intent dictionary
        
    Returns:
        Generated SQL query
    """
    return sql_tool.generate_query(intent)


def get_database_schema() -> str:
    """Get the database schema description."""
    return sql_tool.get_schema()
