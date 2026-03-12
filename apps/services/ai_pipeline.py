"""
AI Pipeline Orchestrator for ARGO Ocean Analytics.

This module orchestrates the complete AI workflow:
1. NLP Layer (Intent + Entity Extraction)
2. Python Tool (Validation + Preprocessing)
3. SQL Tool (Text-to-SQL + Execution)
4. Plot Tool (Visualization Generation)
5. Response Formatting
"""

import os
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from groq import Groq

from apps.services.nlp_service import nlp_service, QueryIntent
from apps.tools.python_tool import python_tool
from apps.tools.sql_tool import sql_tool, get_database_schema
from apps.tools.plot_tool import plot_tool

logger = logging.getLogger(__name__)


class NumericSummary(BaseModel):
    """Numeric summary of query results."""
    total_records: int = 0
    columns_returned: List[str] = Field(default_factory=list)
    numeric_stats: Dict[str, Any] = Field(default_factory=dict)


class AnalyticsSummary(BaseModel):
    """Analytical summary of results."""
    insights: List[str] = Field(default_factory=list)
    trends: Optional[str] = None
    anomalies: Optional[str] = None
    recommendations: Optional[str] = None


class AIResponse(BaseModel):
    """Structured AI response."""
    status: str
    text_response: str
    numeric_summary: NumericSummary = Field(default_factory=NumericSummary)
    analytics: AnalyticsSummary = Field(default_factory=AnalyticsSummary)
    visualization: Optional[Dict[str, Any]] = None
    data: Optional[List[Dict[str, Any]]] = None
    query_info: Dict[str, Any] = Field(default_factory=dict)
    execution_time_ms: float = 0
    error: Optional[str] = None


class AIPipeline:
    """
    AI Pipeline orchestrator for processing natural language queries.
    
    Flow:
    User Input → NLP → Python Tool → SQL Tool → Plot Tool → Response
    """
    
    def __init__(self, groq_api_key: str = None):
        """
        Initialize the AI pipeline.
        
        Args:
            groq_api_key: Groq API key for LLM operations
        """
        self.groq_api_key = groq_api_key or os.getenv('GROQ_API_KEY')
        self.groq_client = None
        
        if self.groq_api_key:
            self.groq_client = Groq(api_key=self.groq_api_key)
        
        self.max_rows = int(os.getenv('MAX_QUERY_ROWS', '10000'))
    
    def process(self, user_query: str) -> AIResponse:
        """
        Process a user query through the complete AI pipeline.
        
        Args:
            user_query: Natural language query from user
            
        Returns:
            AIResponse with results, visualizations, and insights
        """
        start_time = datetime.now()
        
        try:
            logger.info(f"Processing query: {user_query}")
            
            # Step 1: NLP - Intent Classification & Entity Extraction
            intent = nlp_service.process_query(user_query)
            logger.info(f"Intent: {intent.primary_intent}, Type: {intent.query_type}")
            
            # Step 2: Python Tool - Validate & Preprocess Parameters
            preprocessed = python_tool.execute(
                'preprocess_query',
                intent.parameters
            )
            
            if preprocessed['status'] == 'error':
                return self._error_response(
                    f"Parameter validation failed: {preprocessed.get('errors')}",
                    start_time
                )
            
            params = preprocessed.get('preprocessed_params', intent.parameters)
            
            # Step 3: SQL Tool - Generate & Execute Query
            sql_intent = {
                'query_type': intent.query_type,
                **params
            }
            
            sql_query = sql_tool.generate_query(sql_intent)
            logger.info(f"Generated SQL: {sql_query[:200]}...")
            
            sql_result = sql_tool.execute(sql_query)
            
            if not sql_result.success:
                return self._error_response(
                    f"Query execution failed: {sql_result.error}",
                    start_time
                )
            
            data = sql_result.data or []
            
            # Step 4: Python Tool - Compute Statistics
            statistics = None
            if data and intent.primary_intent in ['statistics', 'average', 'list']:
                stats_result = python_tool.execute(
                    'compute_statistics',
                    {'data': data, 'columns': params.get('columns', ['temperature', 'salinity', 'pressure'])}
                )
                if stats_result['status'] == 'success':
                    statistics = stats_result.get('statistics')
            
            # Step 5: Plot Tool - Generate Visualization
            visualization = plot_tool.generate_plot_config(data, {
                **sql_intent,
                'title': self._generate_title(intent),
                'description': intent.description
            })
            
            # Step 6: Generate Insights (using Groq if available)
            insights = self._generate_insights(data, statistics, intent)
            
            # Step 7: Format Response
            text_response = self._generate_text_response(
                intent, data, statistics, insights
            )
            
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return AIResponse(
                status='success',
                text_response=text_response,
                numeric_summary=NumericSummary(
                    total_records=len(data),
                    columns_returned=list(data[0].keys()) if data else [],
                    numeric_stats=self._format_numeric_stats(statistics)
                ),
                analytics=AnalyticsSummary(
                    insights=insights.get('insights', []),
                    trends=insights.get('trends'),
                    anomalies=insights.get('anomalies'),
                    recommendations=insights.get('recommendations')
                ),
                visualization=visualization,
                data=data[:100] if len(data) > 100 else data,  # Limit data in response
                query_info={
                    'intent': intent.primary_intent,
                    'query_type': intent.query_type,
                    'sql_query': sql_query,
                    'parameters': params,
                    'execution_time_ms': sql_result.execution_time_ms
                },
                execution_time_ms=execution_time
            )
            
        except Exception as e:
            logger.exception(f"Pipeline error: {e}")
            return self._error_response(str(e), start_time)
    
    def _error_response(self, error: str, start_time: datetime) -> AIResponse:
        """Generate error response."""
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return AIResponse(
            status='error',
            text_response=f"I encountered an error processing your request: {error}",
            error=error,
            execution_time_ms=execution_time
        )
    
    def _generate_title(self, intent: QueryIntent) -> str:
        """Generate visualization title from intent."""
        titles = {
            'count': 'Record Count',
            'average': 'Average Analysis',
            'statistics': 'Statistical Summary',
            'time_series': 'Time Series Analysis',
            'profile': 'Depth Profile',
            'spatial': 'Geographic Distribution',
            'compare': 'Comparison Analysis',
            'extreme': 'Extreme Values',
            'list': 'Data Overview'
        }
        
        base_title = titles.get(intent.primary_intent, 'Data Analysis')
        column = intent.parameters.get('column', '')
        
        if column:
            return f"{base_title} - {column.title()}"
        
        return base_title
    
    def _format_numeric_stats(self, statistics: Optional[List[Dict]]) -> Dict[str, Any]:
        """Format statistics for response."""
        if not statistics:
            return {}
        
        result = {}
        for stat in statistics:
            col = stat.get('column', 'unknown')
            result[col] = {
                'count': stat.get('count'),
                'mean': round(stat.get('mean', 0), 4) if stat.get('mean') else None,
                'std': round(stat.get('std', 0), 4) if stat.get('std') else None,
                'min': round(stat.get('min', 0), 4) if stat.get('min') else None,
                'max': round(stat.get('max', 0), 4) if stat.get('max') else None,
                'median': round(stat.get('q50', 0), 4) if stat.get('q50') else None,
            }
        
        return result
    
    def _generate_insights(
        self,
        data: List[Dict[str, Any]],
        statistics: Optional[List[Dict]],
        intent: QueryIntent
    ) -> Dict[str, Any]:
        """Generate analytical insights from data."""
        insights = {
            'insights': [],
            'trends': None,
            'anomalies': None,
            'recommendations': None
        }
        
        if not data:
            insights['insights'].append("No data available for analysis.")
            return insights
        
        # Basic insights from statistics
        if statistics:
            for stat in statistics:
                col = stat.get('column', 'value')
                mean = stat.get('mean')
                std = stat.get('std')
                
                if mean is not None:
                    insights['insights'].append(
                        f"The average {col} is {mean:.2f}"
                    )
                
                if std is not None and mean is not None:
                    cv = (std / mean * 100) if mean != 0 else 0
                    if cv > 50:
                        insights['insights'].append(
                            f"High variability detected in {col} (CV: {cv:.1f}%)"
                        )
        
        # Record count insight
        insights['insights'].append(
            f"Analysis based on {len(data)} records"
        )
        
        # Time-based insights
        if 'time_bucket' in data[0] or 'profile_time' in data[0]:
            time_field = 'time_bucket' if 'time_bucket' in data[0] else 'profile_time'
            times = [row.get(time_field) for row in data if row.get(time_field)]
            if times:
                insights['trends'] = f"Data spans from earliest to most recent observations"
        
        # Use Groq for enhanced insights if available
        if self.groq_client and len(data) > 0:
            try:
                enhanced = self._get_llm_insights(data[:50], statistics, intent)
                if enhanced:
                    insights.update(enhanced)
            except Exception as e:
                logger.warning(f"LLM insights failed: {e}")
        
        return insights
    
    def _get_llm_insights(
        self,
        data: List[Dict[str, Any]],
        statistics: Optional[List[Dict]],
        intent: QueryIntent
    ) -> Optional[Dict[str, Any]]:
        """Get enhanced insights from LLM."""
        if not self.groq_client:
            return None
        
        # Prepare context
        data_summary = f"Data sample (first few records): {data[:5]}"
        stats_summary = f"Statistics: {statistics}" if statistics else "No statistics computed"
        
        prompt = f"""You are an oceanographic data analyst. Analyze this ARGO ocean data and provide insights.

Query: {intent.description}
Intent: {intent.primary_intent}

{data_summary}

{stats_summary}

Provide:
1. Key insights (2-3 bullet points)
2. Any notable trends
3. Potential anomalies
4. Recommendations for further analysis

Keep response concise and factual. Format as JSON with keys: insights (list), trends (string), anomalies (string), recommendations (string).
"""
        
        try:
            response = self.groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": "You are an oceanographic data analyst providing insights on ARGO ocean data. Respond in JSON format only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            result_text = response.choices[0].message.content
            
            # Parse JSON response
            import json
            
            # Try to extract JSON from response
            json_match = result_text
            if '```json' in result_text:
                json_match = result_text.split('```json')[1].split('```')[0]
            elif '```' in result_text:
                json_match = result_text.split('```')[1].split('```')[0]
            
            try:
                return json.loads(json_match.strip())
            except json.JSONDecodeError:
                # If JSON parsing fails, extract insights manually
                return {
                    'insights': [result_text[:200] if result_text else "Analysis completed"],
                    'trends': None,
                    'anomalies': None,
                    'recommendations': None
                }
                
        except Exception as e:
            logger.warning(f"Groq API call failed: {e}")
            return None
    
    def _generate_text_response(
        self,
        intent: QueryIntent,
        data: List[Dict[str, Any]],
        statistics: Optional[List[Dict]],
        insights: Dict[str, Any]
    ) -> str:
        """Generate human-readable text response."""
        if not data:
            return "I couldn't find any data matching your query. Try adjusting your filters or date range."
        
        response_parts = []
        
        # Opening statement based on intent
        if intent.primary_intent == 'count':
            response_parts.append(f"I found {len(data)} records matching your query.")
        
        elif intent.primary_intent == 'average':
            col = intent.parameters.get('column', 'value')
            if statistics:
                for stat in statistics:
                    if stat['column'] == col:
                        response_parts.append(
                            f"The average {col} is {stat['mean']:.2f}."
                        )
                        break
        
        elif intent.primary_intent == 'statistics':
            response_parts.append(f"Here's the statistical summary based on {len(data)} measurements:")
            if statistics:
                for stat in statistics:
                    response_parts.append(
                        f"- {stat['column'].title()}: mean={stat['mean']:.2f}, "
                        f"range=[{stat['min']:.2f}, {stat['max']:.2f}]"
                    )
        
        elif intent.primary_intent == 'time_series':
            response_parts.append(
                f"Here's the time series analysis showing {len(data)} data points."
            )
        
        elif intent.primary_intent == 'profile':
            response_parts.append(
                f"Here's the depth profile with {len(data)} measurements."
            )
        
        elif intent.primary_intent == 'spatial':
            response_parts.append(
                f"Here's the geographic distribution of {len(data)} observations."
            )
        
        else:
            response_parts.append(
                f"I retrieved {len(data)} records for your analysis."
            )
        
        # Add insights
        if insights.get('insights'):
            response_parts.append("\n\nKey findings:")
            for insight in insights['insights'][:3]:
                response_parts.append(f"• {insight}")
        
        # Add trends if available
        if insights.get('trends'):
            response_parts.append(f"\n\nTrend: {insights['trends']}")
        
        return "\n".join(response_parts)
    
    def generate_sql_from_natural_language(
        self, 
        query: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Generate SQL from natural language using LLM.
        
        This is an advanced feature that uses the LLM to generate
        more complex SQL queries that the rule-based system might miss.
        """
        if not self.groq_client:
            # Fall back to rule-based approach
            intent = nlp_service.process_query(query)
            sql = sql_tool.generate_query({
                'query_type': intent.query_type,
                **intent.parameters
            })
            return {
                'sql': sql,
                'method': 'rule_based',
                'intent': intent.dict()
            }
        
        schema = get_database_schema()
        
        prompt = f"""You are a SQL expert. Convert this natural language query to PostgreSQL.

Database Schema:
{schema}

User Query: {query}

Requirements:
1. Only generate SELECT queries
2. Use proper JOINs between tables
3. Include appropriate WHERE clauses
4. Add LIMIT clause (max 10000)
5. Use aggregations where appropriate

Return ONLY the SQL query, no explanations.
"""
        
        try:
            response = self.groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": "You are a PostgreSQL expert. Generate only valid SELECT queries."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            sql = response.choices[0].message.content.strip()
            
            # Clean SQL
            if sql.startswith('```sql'):
                sql = sql[6:]
            if sql.startswith('```'):
                sql = sql[3:]
            if sql.endswith('```'):
                sql = sql[:-3]
            sql = sql.strip()
            
            # Validate
            is_valid, error = sql_tool.validate_query(sql)
            
            if is_valid:
                return {
                    'sql': sql,
                    'method': 'llm',
                    'valid': True
                }
            else:
                # Fall back to rule-based
                intent = nlp_service.process_query(query)
                sql = sql_tool.generate_query({
                    'query_type': intent.query_type,
                    **intent.parameters
                })
                return {
                    'sql': sql,
                    'method': 'rule_based_fallback',
                    'llm_error': error,
                    'intent': intent.dict()
                }
                
        except Exception as e:
            logger.error(f"LLM SQL generation failed: {e}")
            # Fall back to rule-based
            intent = nlp_service.process_query(query)
            sql = sql_tool.generate_query({
                'query_type': intent.query_type,
                **intent.parameters
            })
            return {
                'sql': sql,
                'method': 'rule_based_fallback',
                'error': str(e)
            }


# Singleton instance
ai_pipeline = AIPipeline()


def process_query(user_query: str) -> Dict[str, Any]:
    """
    Process a user query through the AI pipeline.
    
    Args:
        user_query: Natural language query
        
    Returns:
        Structured response dictionary
    """
    response = ai_pipeline.process(user_query)
    return response.dict()


def get_sql_for_query(query: str) -> Dict[str, Any]:
    """
    Get the SQL that would be generated for a query.
    
    Args:
        query: Natural language query
        
    Returns:
        Dictionary with SQL and metadata
    """
    return ai_pipeline.generate_sql_from_natural_language(query)
