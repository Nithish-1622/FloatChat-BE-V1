"""
Management command to initialize the database.
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from apps.ingestion.sa_models import create_tables, get_engine


def main():
    """Create all database tables."""
    print("Initializing database...")
    
    try:
        engine = get_engine()
        create_tables(engine)
        print("Database tables created successfully!")
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute("SELECT 1")
            print("Database connection verified!")
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
