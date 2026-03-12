"""
Script to ingest ARGO NetCDF data from a URL or local file.

Usage:
    python ingest_data.py <source> [--url] [--directory] [--force]

Examples:
    # Ingest from URL
    python ingest_data.py https://example.com/argo_data.nc --url
    
    # Ingest from local file
    python ingest_data.py /path/to/data.nc
    
    # Ingest all files from directory
    python ingest_data.py /path/to/data/ --directory
"""

import os
import sys
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from apps.ingestion.pipeline import run_ingestion


def main():
    parser = argparse.ArgumentParser(
        description='Ingest ARGO NetCDF data into the database'
    )
    parser.add_argument(
        'source',
        help='File path, URL, or directory to ingest'
    )
    parser.add_argument(
        '--url',
        action='store_true',
        help='Source is a URL'
    )
    parser.add_argument(
        '--directory',
        action='store_true',
        help='Source is a directory'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force reprocessing of already processed files'
    )
    
    args = parser.parse_args()
    
    print(f"Starting ingestion from: {args.source}")
    print(f"  URL: {args.url}")
    print(f"  Directory: {args.directory}")
    print(f"  Force: {args.force}")
    print()
    
    try:
        result = run_ingestion(
            source=args.source,
            is_url=args.url,
            is_directory=args.directory,
            force=args.force
        )
        
        print("\n=== Ingestion Complete ===")
        print(f"Type: {result.get('type')}")
        print(f"Source: {result.get('source')}")
        
        if 'stats' in result:
            stats = result['stats']
            print(f"\nDatabase Statistics:")
            print(f"  Total Floats: {stats.get('total_floats', 0)}")
            print(f"  Total Profiles: {stats.get('total_profiles', 0)}")
            print(f"  Total Measurements: {stats.get('total_measurements', 0)}")
            print(f"  Processed Files: {stats.get('processed_files', 0)}")
        
        if 'result' in result:
            r = result['result']
            print(f"\nFile Result:")
            print(f"  Status: {r.get('status')}")
            print(f"  Records Inserted: {r.get('records_inserted', 0)}")
            print(f"  Profiles Created: {r.get('profiles_created', 0)}")
            print(f"  Floats Created: {r.get('floats_created', 0)}")
            if r.get('error'):
                print(f"  Error: {r['error']}")
        
        if 'results' in result:
            print(f"\nFiles Processed: {result.get('files_processed', 0)}")
            for r in result['results']:
                status_icon = "✓" if r['status'] == 'success' else "✗"
                print(f"  {status_icon} {r['file_path']}: {r['records_inserted']} records")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
