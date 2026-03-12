"""
NLP Service for intent classification and entity extraction.

This service:
- Classifies user query intents
- Extracts entities (dates, locations, variables, etc.)
- Links entities to database schema
- Maintains conversation context
"""

import re
import logging
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dateutil import parser as date_parser
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ExtractedEntity(BaseModel):
    """Extracted entity from user query."""
    type: str
    value: Any
    confidence: float = 1.0
    raw_text: Optional[str] = None


class QueryIntent(BaseModel):
    """Classified query intent."""
    primary_intent: str
    secondary_intent: Optional[str] = None
    query_type: str
    confidence: float = 1.0
    entities: List[ExtractedEntity] = Field(default_factory=list)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    description: str = ""


class ConversationContext(BaseModel):
    """Maintains conversation context."""
    last_query: Optional[str] = None
    last_intent: Optional[str] = None
    last_entities: Dict[str, Any] = Field(default_factory=dict)
    session_start: datetime = Field(default_factory=datetime.utcnow)
    query_count: int = 0


class NLPService:
    """
    Natural Language Processing service for ARGO ocean data queries.
    
    Features:
    - Intent classification
    - Entity extraction (dates, floats, regions, variables)
    - Schema linking
    - Context memory for follow-up queries
    """
    
    # Intent patterns
    INTENT_PATTERNS = {
        'count': [
            r'how many', r'count', r'number of', r'total',
            r'how much', r'\bcount\b'
        ],
        'average': [
            r'average', r'mean', r'avg\b', r'typical'
        ],
        'statistics': [
            r'statistics', r'stats', r'summary', r'describe',
            r'distribution', r'variance', r'std', r'standard deviation'
        ],
        'time_series': [
            r'over time', r'trend', r'time series', r'monthly',
            r'yearly', r'daily', r'history', r'historical', r'change'
        ],
        'profile': [
            r'profile', r'depth profile', r'vertical', r'at depth',
            r'by depth', r'pressure profile'
        ],
        'spatial': [
            r'location', r'where', r'geographic', r'spatial',
            r'map', r'region', r'area', r'coordinates'
        ],
        'compare': [
            r'compare', r'difference', r'between', r'vs',
            r'versus', r'comparison'
        ],
        'extreme': [
            r'maximum', r'minimum', r'highest', r'lowest',
            r'max\b', r'min\b', r'extreme', r'peak', r'hottest', r'coldest'
        ],
        'correlation': [
            r'correlation', r'relationship', r'relate',
            r'associated', r'connection'
        ],
        'list': [
            r'list', r'show', r'display', r'get', r'fetch',
            r'retrieve', r'what are', r'which'
        ],
    }
    
    # Variable patterns
    VARIABLE_PATTERNS = {
        'temperature': [
            r'temperature', r'temp\b', r'thermal', r'warm', r'cold',
            r'hot', r'heat', r'°C', r'celsius'
        ],
        'salinity': [
            r'salinity', r'salt', r'saline', r'psu', r'freshwater'
        ],
        'pressure': [
            r'pressure', r'depth', r'deep', r'shallow',
            r'surface', r'dbar', r'meters', r'\bm\b'
        ],
    }
    
    # Region patterns
    REGION_PATTERNS = {
        'indian_ocean': [
            r'indian ocean', r'arabian sea', r'bay of bengal',
            r'andaman', r'indian'
        ],
        'north': [
            r'north', r'northern'
        ],
        'south': [
            r'south', r'southern'
        ],
        'equatorial': [
            r'equator', r'equatorial', r'tropical'
        ],
    }
    
    # Time patterns
    TIME_PATTERNS = {
        'relative': {
            r'today': 0,
            r'yesterday': -1,
            r'last week': -7,
            r'last month': -30,
            r'last year': -365,
            r'past week': -7,
            r'past month': -30,
            r'past year': -365,
            r'this year': 0,
            r'this month': 0,
        },
        'absolute': [
            r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
            r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]* \d{4}',
        ]
    }
    
    # Aggregation keywords
    AGGREGATION_KEYWORDS = {
        'avg': ['average', 'mean', 'avg'],
        'sum': ['sum', 'total', 'cumulative'],
        'min': ['minimum', 'min', 'lowest', 'coldest'],
        'max': ['maximum', 'max', 'highest', 'hottest', 'peak'],
        'count': ['count', 'number', 'how many'],
        'std': ['standard deviation', 'std', 'variance'],
    }
    
    # Grouping keywords
    GROUPING_KEYWORDS = {
        'year': ['yearly', 'annual', 'by year', 'each year', 'per year'],
        'month': ['monthly', 'by month', 'each month', 'per month'],
        'day': ['daily', 'by day', 'each day', 'per day'],
        'platform_number': ['by float', 'each float', 'per float', 'by platform'],
        'depth_bin': ['by depth', 'depth layer', 'depth band'],
    }
    
    def __init__(self):
        """Initialize the NLP service."""
        self.context = ConversationContext()
    
    def process_query(self, query: str) -> QueryIntent:
        """
        Process a natural language query.
        
        Args:
            query: User's natural language query
            
        Returns:
            QueryIntent with classification and entities
        """
        logger.info(f"Processing query: {query}")
        
        # Normalize query
        normalized = query.lower().strip()
        
        # Update context
        self.context.query_count += 1
        
        # Extract intent
        primary_intent, secondary_intent, confidence = self._classify_intent(normalized)
        
        # Determine query type
        query_type = self._determine_query_type(primary_intent, normalized)
        
        # Extract entities
        entities = self._extract_entities(normalized)
        
        # Build parameters
        parameters = self._build_parameters(entities, normalized, primary_intent)
        
        # Generate description
        description = self._generate_description(primary_intent, parameters)
        
        # Create intent object
        intent = QueryIntent(
            primary_intent=primary_intent,
            secondary_intent=secondary_intent,
            query_type=query_type,
            confidence=confidence,
            entities=entities,
            parameters=parameters,
            description=description
        )
        
        # Update context for follow-up queries
        self.context.last_query = query
        self.context.last_intent = primary_intent
        self.context.last_entities = {e.type: e.value for e in entities}
        
        logger.info(f"Intent: {primary_intent}, Type: {query_type}, Entities: {len(entities)}")
        
        return intent
    
    def _classify_intent(self, query: str) -> Tuple[str, Optional[str], float]:
        """
        Classify the primary and secondary intent.
        
        Returns:
            Tuple of (primary_intent, secondary_intent, confidence)
        """
        scores = {}
        
        for intent, patterns in self.INTENT_PATTERNS.items():
            score = sum(1 for p in patterns if re.search(p, query))
            if score > 0:
                scores[intent] = score
        
        if not scores:
            return 'list', None, 0.5
        
        sorted_intents = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        primary = sorted_intents[0][0]
        secondary = sorted_intents[1][0] if len(sorted_intents) > 1 else None
        
        # Calculate confidence based on match strength
        total_patterns = sum(len(p) for p in self.INTENT_PATTERNS.values())
        confidence = min(1.0, sorted_intents[0][1] / 3)
        
        return primary, secondary, confidence
    
    def _determine_query_type(self, intent: str, query: str) -> str:
        """Determine the SQL query type needed."""
        intent_to_type = {
            'count': 'count',
            'average': 'aggregate',
            'statistics': 'statistics',
            'time_series': 'time_series',
            'profile': 'profile',
            'spatial': 'spatial',
            'compare': 'aggregate',
            'extreme': 'aggregate',
            'correlation': 'data',
            'list': 'data',
        }
        
        return intent_to_type.get(intent, 'data')
    
    def _extract_entities(self, query: str) -> List[ExtractedEntity]:
        """Extract entities from query."""
        entities = []
        
        # Extract variables
        for var, patterns in self.VARIABLE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query):
                    entities.append(ExtractedEntity(
                        type='variable',
                        value=var,
                        raw_text=pattern
                    ))
                    break
        
        # Extract time references
        time_entities = self._extract_time_entities(query)
        entities.extend(time_entities)
        
        # Extract platform numbers
        platform_match = re.search(r'float\s*[#]?(\d+)', query)
        if platform_match:
            entities.append(ExtractedEntity(
                type='platform_number',
                value=platform_match.group(1),
                raw_text=platform_match.group(0)
            ))
        
        # Extract depth/pressure values
        depth_match = re.search(r'(\d+)\s*(?:m|meters?|dbar|decibars?)', query)
        if depth_match:
            entities.append(ExtractedEntity(
                type='depth',
                value=float(depth_match.group(1)),
                raw_text=depth_match.group(0)
            ))
        
        # Extract temperature values
        temp_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:°C|celsius|degrees?)', query)
        if temp_match:
            entities.append(ExtractedEntity(
                type='temperature_value',
                value=float(temp_match.group(1)),
                raw_text=temp_match.group(0)
            ))
        
        # Extract regions
        for region, patterns in self.REGION_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query):
                    entities.append(ExtractedEntity(
                        type='region',
                        value=region,
                        raw_text=pattern
                    ))
                    break
        
        # Extract aggregation type
        for agg, keywords in self.AGGREGATION_KEYWORDS.items():
            for kw in keywords:
                if kw in query:
                    entities.append(ExtractedEntity(
                        type='aggregation',
                        value=agg,
                        raw_text=kw
                    ))
                    break
        
        # Extract grouping
        for group, keywords in self.GROUPING_KEYWORDS.items():
            for kw in keywords:
                if kw in query:
                    entities.append(ExtractedEntity(
                        type='group_by',
                        value=group,
                        raw_text=kw
                    ))
                    break
        
        # Extract limit/top N
        limit_match = re.search(r'(?:top|first|last|limit)\s*(\d+)', query)
        if limit_match:
            entities.append(ExtractedEntity(
                type='limit',
                value=int(limit_match.group(1)),
                raw_text=limit_match.group(0)
            ))
        
        return entities
    
    def _extract_time_entities(self, query: str) -> List[ExtractedEntity]:
        """Extract time-related entities."""
        entities = []
        now = datetime.utcnow()
        
        # Check relative time patterns
        for pattern, days_delta in self.TIME_PATTERNS['relative'].items():
            if re.search(pattern, query):
                if days_delta <= 0:
                    start_date = now + timedelta(days=days_delta)
                    end_date = now
                else:
                    start_date = datetime(now.year, 1, 1)
                    end_date = now
                
                entities.append(ExtractedEntity(
                    type='start_date',
                    value=start_date.isoformat(),
                    raw_text=pattern
                ))
                entities.append(ExtractedEntity(
                    type='end_date',
                    value=end_date.isoformat(),
                    raw_text=pattern
                ))
                break
        
        # Check absolute date patterns
        for pattern in self.TIME_PATTERNS['absolute']:
            matches = re.findall(pattern, query, re.IGNORECASE)
            for match in matches:
                try:
                    parsed_date = date_parser.parse(match)
                    entities.append(ExtractedEntity(
                        type='date',
                        value=parsed_date.isoformat(),
                        raw_text=match
                    ))
                except (ValueError, TypeError):
                    pass
        
        # Check for year mentions
        year_match = re.search(r'\b(20\d{2}|19\d{2})\b', query)
        if year_match and not entities:
            year = int(year_match.group(1))
            entities.append(ExtractedEntity(
                type='start_date',
                value=datetime(year, 1, 1).isoformat(),
                raw_text=year_match.group(0)
            ))
            entities.append(ExtractedEntity(
                type='end_date',
                value=datetime(year, 12, 31).isoformat(),
                raw_text=year_match.group(0)
            ))
        
        # Check for month mentions
        month_patterns = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12
        }
        for month_name, month_num in month_patterns.items():
            if month_name in query:
                # Default to current year if not specified
                year = now.year
                if year_match:
                    year = int(year_match.group(1))
                
                start_date = datetime(year, month_num, 1)
                if month_num == 12:
                    end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
                else:
                    end_date = datetime(year, month_num + 1, 1) - timedelta(days=1)
                
                entities.append(ExtractedEntity(
                    type='start_date',
                    value=start_date.isoformat(),
                    raw_text=month_name
                ))
                entities.append(ExtractedEntity(
                    type='end_date',
                    value=end_date.isoformat(),
                    raw_text=month_name
                ))
                break
        
        return entities
    
    def _build_parameters(
        self, 
        entities: List[ExtractedEntity], 
        query: str,
        intent: str
    ) -> Dict[str, Any]:
        """Build query parameters from entities."""
        params = {}
        
        for entity in entities:
            if entity.type == 'variable':
                if 'column' not in params:
                    params['column'] = entity.value
                if 'columns' not in params:
                    params['columns'] = []
                params['columns'].append(entity.value)
            
            elif entity.type == 'start_date':
                params['start_date'] = entity.value
            
            elif entity.type == 'end_date':
                params['end_date'] = entity.value
            
            elif entity.type == 'platform_number':
                params['platform_number'] = entity.value
                if 'platform_numbers' not in params:
                    params['platform_numbers'] = []
                params['platform_numbers'].append(entity.value)
            
            elif entity.type == 'depth':
                # Interpret depth context
                if 'below' in query or 'deeper than' in query:
                    params['min_depth'] = entity.value
                elif 'above' in query or 'shallower than' in query:
                    params['max_depth'] = entity.value
                else:
                    # Default: around this depth
                    params['min_depth'] = max(0, entity.value - 50)
                    params['max_depth'] = entity.value + 50
            
            elif entity.type == 'temperature_value':
                if 'warmer than' in query or 'above' in query or 'greater than' in query:
                    params['min_temperature'] = entity.value
                elif 'colder than' in query or 'below' in query or 'less than' in query:
                    params['max_temperature'] = entity.value
            
            elif entity.type == 'aggregation':
                params['aggregation'] = entity.value
            
            elif entity.type == 'group_by':
                if 'group_by' not in params:
                    params['group_by'] = []
                params['group_by'].append(entity.value)
            
            elif entity.type == 'limit':
                params['limit'] = entity.value
            
            elif entity.type == 'region':
                # Set geographic bounds based on region
                if entity.value == 'north':
                    params['min_latitude'] = 0
                    params['max_latitude'] = 30
                elif entity.value == 'south':
                    params['min_latitude'] = -60
                    params['max_latitude'] = 0
                elif entity.value == 'equatorial':
                    params['min_latitude'] = -10
                    params['max_latitude'] = 10
        
        # Set default column if not extracted
        if 'column' not in params:
            # Infer from query
            if 'temperature' in query or 'temp' in query:
                params['column'] = 'temperature'
            elif 'salinity' in query or 'salt' in query:
                params['column'] = 'salinity'
            elif 'pressure' in query or 'depth' in query:
                params['column'] = 'pressure'
            else:
                params['column'] = 'temperature'  # Default
        
        # Set default aggregation based on intent
        if intent in ['average'] and 'aggregation' not in params:
            params['aggregation'] = 'avg'
        elif intent == 'extreme':
            if 'maximum' in query or 'highest' in query or 'hottest' in query:
                params['aggregation'] = 'max'
            else:
                params['aggregation'] = 'min'
        elif intent == 'count' and 'aggregation' not in params:
            params['aggregation'] = 'count'
        
        # Set default limit
        if 'limit' not in params:
            params['limit'] = 1000
        
        return params
    
    def _generate_description(self, intent: str, params: Dict[str, Any]) -> str:
        """Generate a human-readable description of the query."""
        column = params.get('column', 'data')
        aggregation = params.get('aggregation', '')
        
        descriptions = {
            'count': f"Counting records",
            'average': f"Calculating average {column}",
            'statistics': f"Computing statistics for {column}",
            'time_series': f"Analyzing {column} over time",
            'profile': f"Creating depth profile for {column}",
            'spatial': f"Mapping {column} distribution",
            'compare': f"Comparing {column} values",
            'extreme': f"Finding {aggregation} {column}",
            'list': f"Retrieving {column} data",
        }
        
        desc = descriptions.get(intent, f"Querying {column} data")
        
        # Add filters
        filters = []
        if params.get('start_date'):
            filters.append(f"from {params['start_date'][:10]}")
        if params.get('end_date'):
            filters.append(f"to {params['end_date'][:10]}")
        if params.get('platform_number'):
            filters.append(f"for float {params['platform_number']}")
        
        if filters:
            desc += " " + " ".join(filters)
        
        return desc
    
    def get_context(self) -> Dict[str, Any]:
        """Get current conversation context."""
        return self.context.dict()
    
    def reset_context(self):
        """Reset conversation context."""
        self.context = ConversationContext()


# Singleton instance
nlp_service = NLPService()


def process_natural_language_query(query: str) -> Dict[str, Any]:
    """
    Process a natural language query.
    
    Args:
        query: User's natural language query
        
    Returns:
        Processed intent and entities
    """
    intent = nlp_service.process_query(query)
    return intent.dict()


def get_conversation_context() -> Dict[str, Any]:
    """Get the current conversation context."""
    return nlp_service.get_context()


def reset_conversation() -> None:
    """Reset the conversation context."""
    nlp_service.reset_context()
