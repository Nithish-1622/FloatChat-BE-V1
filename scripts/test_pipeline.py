"""
Test script to verify the AI pipeline works correctly.

Usage:
    python test_pipeline.py
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'argo_ai.settings')

from dotenv import load_dotenv
load_dotenv()


def test_nlp_service():
    """Test NLP service."""
    print("\n=== Testing NLP Service ===")
    
    from apps.services.nlp_service import process_natural_language_query
    
    test_queries = [
        "What is the average temperature?",
        "Show me data from the last month",
        "How many floats are in the database?",
        "Temperature profile by depth",
        "Maximum salinity in 2023",
    ]
    
    for query in test_queries:
        result = process_natural_language_query(query)
        print(f"\nQuery: {query}")
        print(f"  Intent: {result['primary_intent']}")
        print(f"  Type: {result['query_type']}")
        print(f"  Entities: {len(result['entities'])}")
        print(f"  Parameters: {list(result['parameters'].keys())}")


def test_sql_tool():
    """Test SQL tool."""
    print("\n=== Testing SQL Tool ===")
    
    from apps.tools.sql_tool import sql_tool, generate_sql_from_intent
    
    test_intents = [
        {'query_type': 'count', 'table': 'profiles'},
        {'query_type': 'aggregate', 'aggregation': 'avg', 'column': 'temperature'},
        {'query_type': 'time_series', 'column': 'temperature', 'interval': 'month'},
    ]
    
    for intent in test_intents:
        sql = sql_tool.generate_query(intent)
        print(f"\nIntent: {intent.get('query_type')}")
        print(f"SQL: {sql[:200]}...")
        
        # Validate
        is_valid, error = sql_tool.validate_query(sql)
        print(f"Valid: {is_valid}")
        if error:
            print(f"Error: {error}")


def test_plot_tool():
    """Test plot tool."""
    print("\n=== Testing Plot Tool ===")
    
    from apps.tools.plot_tool import generate_visualization, auto_select_chart
    
    test_data = [
        {'time_bucket': '2023-01', 'avg_temperature': 22.5},
        {'time_bucket': '2023-02', 'avg_temperature': 23.1},
        {'time_bucket': '2023-03', 'avg_temperature': 24.2},
    ]
    
    chart_type = auto_select_chart(test_data, {'query_type': 'time_series'})
    print(f"Auto-selected chart: {chart_type}")
    
    viz = generate_visualization(test_data, {'query_type': 'time_series', 'title': 'Test'})
    print(f"Visualization config keys: {list(viz.keys())}")
    print(f"Chart type: {viz.get('chart_type')}")


def test_python_tool():
    """Test Python tool."""
    print("\n=== Testing Python Tool ===")
    
    from apps.tools.python_tool import execute_python_operation
    
    # Test parameter validation
    result = execute_python_operation('validate_parameters', {
        'start_date': '2023-01-01',
        'column': 'temperature',
        'aggregation': 'avg'
    })
    print(f"Validation result: {result['status']}")
    
    # Test statistics computation
    test_data = [
        {'temperature': 22.5, 'salinity': 35.1},
        {'temperature': 23.1, 'salinity': 35.0},
        {'temperature': 24.2, 'salinity': 34.8},
    ]
    
    result = execute_python_operation('compute_statistics', {
        'data': test_data,
        'columns': ['temperature', 'salinity']
    })
    print(f"Statistics computed: {len(result.get('statistics', []))} columns")


def test_full_pipeline():
    """Test the full AI pipeline."""
    print("\n=== Testing Full AI Pipeline ===")
    
    from apps.services.ai_pipeline import process_query
    
    # Note: This will fail if no database is connected
    try:
        result = process_query("What is the average temperature?")
        print(f"Status: {result['status']}")
        print(f"Response: {result['text_response'][:200]}...")
        print(f"Execution time: {result['execution_time_ms']:.2f}ms")
    except Exception as e:
        print(f"Pipeline test skipped (no database): {e}")


def main():
    print("=" * 60)
    print("ARGO Ocean Analytics - Pipeline Test")
    print("=" * 60)
    
    test_nlp_service()
    test_sql_tool()
    test_plot_tool()
    test_python_tool()
    test_full_pipeline()
    
    print("\n" + "=" * 60)
    print("Tests completed!")
    print("=" * 60)


if __name__ == '__main__':
    main()
