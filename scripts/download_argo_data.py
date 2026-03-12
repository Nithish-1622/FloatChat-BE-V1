#!/usr/bin/env python
"""
Download ARGO NetCDF files from the official FTP server.

This script:
1. Parses the ARGO global profile index file
2. Filters for Indian Ocean region
3. Downloads NetCDF files from IFREMER FTP
4. Optionally ingests them into the database

Usage:
    python scripts/download_argo_data.py --index "C:\path\to\ar_index_global_prof.txt.gz"
    python scripts/download_argo_data.py --index "C:\path\to\ar_index_global_prof.txt.gz" --limit 100
    python scripts/download_argo_data.py --index "C:\path\to\ar_index_global_prof.txt.gz" --ingest
"""

import os
import sys
import gzip
import argparse
import ftplib
from pathlib import Path
from datetime import datetime
import logging

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'argo_ai.settings')
import django
django.setup()

from apps.ingestion.pipeline import run_ingestion

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ARGO FTP settings
ARGO_FTP_HOST = "ftp.ifremer.fr"
ARGO_FTP_ROOT = "/ifremer/argo/dac"

# Indian Ocean bounding box
INDIAN_OCEAN_BOUNDS = {
    'lat_min': -60,
    'lat_max': 30,
    'lon_min': 20,
    'lon_max': 120,
}


def parse_index_file(index_path: str, limit: int = None) -> list:
    """
    Parse ARGO global profile index file and filter for Indian Ocean.
    
    Index file format (comma-separated):
    file,date,latitude,longitude,ocean,profiler_type,institution,date_update
    
    Example:
    aoml/1900722/profiles/D1900722_001.nc,20040724235200,-0.017,-82.51,P,845,AO,20190113100209
    """
    profiles = []
    
    logger.info(f"Parsing index file: {index_path}")
    
    # Determine if gzipped
    open_func = gzip.open if index_path.endswith('.gz') else open
    mode = 'rt' if index_path.endswith('.gz') else 'r'
    
    line_count = 0
    indian_ocean_count = 0
    
    with open_func(index_path, mode, encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            
            # Skip headers and comments
            if not line or line.startswith('#') or line.startswith('file,'):
                continue
            
            line_count += 1
            
            try:
                parts = line.split(',')
                if len(parts) < 4:
                    continue
                
                file_path = parts[0]
                lat = float(parts[2]) if parts[2] else None
                lon = float(parts[3]) if parts[3] else None
                
                # Skip if no coordinates
                if lat is None or lon is None:
                    continue
                
                # Filter for Indian Ocean
                if (INDIAN_OCEAN_BOUNDS['lat_min'] <= lat <= INDIAN_OCEAN_BOUNDS['lat_max'] and
                    INDIAN_OCEAN_BOUNDS['lon_min'] <= lon <= INDIAN_OCEAN_BOUNDS['lon_max']):
                    
                    indian_ocean_count += 1
                    profiles.append({
                        'file_path': file_path,
                        'latitude': lat,
                        'longitude': lon,
                        'date': parts[1] if len(parts) > 1 else None,
                        'ocean': parts[4] if len(parts) > 4 else None,
                    })
                    
                    if limit and len(profiles) >= limit:
                        break
                        
            except (ValueError, IndexError) as e:
                continue
    
    logger.info(f"Parsed {line_count:,} profiles, found {indian_ocean_count:,} in Indian Ocean")
    if limit:
        logger.info(f"Limited to {len(profiles)} profiles")
    
    return profiles


def connect_ftp():
    """Create FTP connection with retry logic."""
    ftp = ftplib.FTP(ARGO_FTP_HOST, timeout=120)
    ftp.login()  # Anonymous login
    ftp.set_pasv(True)  # Use passive mode (better for firewalls)
    return ftp


def download_from_ftp(profiles: list, output_dir: str, max_files: int = None) -> list:
    """
    Download NetCDF files from ARGO FTP server.
    
    Args:
        profiles: List of profile dicts with 'file_path' key
        output_dir: Local directory to save files
        max_files: Maximum number of files to download
        
    Returns:
        List of downloaded file paths
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    downloaded_files = []
    failed_files = []
    
    logger.info(f"Connecting to {ARGO_FTP_HOST}...")
    
    ftp = None
    retry_count = 0
    max_retries = 3
    
    try:
        ftp = connect_ftp()
        logger.info("Connected to ARGO FTP server (anonymous login, passive mode)")
        
        total = min(len(profiles), max_files) if max_files else len(profiles)
        
        for i, profile in enumerate(profiles[:max_files] if max_files else profiles):
            file_path = profile['file_path']
            
            # Full FTP path
            remote_path = f"{ARGO_FTP_ROOT}/{file_path}"
            
            # Local file path (flatten directory structure)
            filename = file_path.replace('/', '_')
            local_path = output_path / filename
            
            # Skip if already downloaded
            if local_path.exists() and local_path.stat().st_size > 0:
                logger.debug(f"[{i+1}/{total}] Skipping {filename} (already exists)")
                downloaded_files.append(str(local_path))
                continue
            
            # Retry logic for each file
            for attempt in range(max_retries):
                try:
                    logger.info(f"[{i+1}/{total}] Downloading {filename}...")
                    
                    with open(local_path, 'wb') as f:
                        ftp.retrbinary(f'RETR {remote_path}', f.write)
                    
                    downloaded_files.append(str(local_path))
                    break  # Success
                    
                except (ftplib.error_temp, TimeoutError, OSError) as e:
                    logger.warning(f"Attempt {attempt+1}/{max_retries} failed for {file_path}: {e}")
                    if local_path.exists():
                        local_path.unlink()
                    
                    # Reconnect FTP
                    try:
                        ftp.quit()
                    except:
                        pass
                    
                    if attempt < max_retries - 1:
                        logger.info("Reconnecting to FTP...")
                        import time
                        time.sleep(2)
                        ftp = connect_ftp()
                    else:
                        failed_files.append(file_path)
                        
                except ftplib.error_perm as e:
                    logger.warning(f"Permission denied for {file_path}: {e}")
                    failed_files.append(file_path)
                    if local_path.exists():
                        local_path.unlink()
                    break  # Don't retry permission errors
        
        if ftp:
            ftp.quit()
        
    except Exception as e:
        logger.error(f"FTP connection error: {e}")
        if ftp:
            try:
                ftp.quit()
            except:
                pass
    
    logger.info(f"Downloaded {len(downloaded_files)} files, {len(failed_files)} failed")
    return downloaded_files


def ingest_files(file_paths: list):
    """Ingest downloaded NetCDF files into the database."""
    logger.info(f"Ingesting {len(file_paths)} files...")
    
    total_floats = 0
    total_profiles = 0
    total_measurements = 0
    
    for i, file_path in enumerate(file_paths):
        try:
            logger.info(f"[{i+1}/{len(file_paths)}] Ingesting {Path(file_path).name}...")
            
            result = run_ingestion(
                source=file_path,
                is_url=False,
                is_directory=False,
                force=False
            )
            
            if result.get('status') == 'success':
                total_floats += result.get('floats_created', 0) + result.get('floats_updated', 0)
                total_profiles += result.get('profiles_created', 0)
                total_measurements += result.get('measurements_created', 0)
            
        except Exception as e:
            logger.error(f"Failed to ingest {file_path}: {e}")
    
    logger.info(f"Ingestion complete: {total_floats} floats, {total_profiles} profiles, {total_measurements} measurements")


def main():
    parser = argparse.ArgumentParser(
        description='Download and ingest ARGO NetCDF files from FTP server'
    )
    parser.add_argument(
        '--index',
        required=False,
        help='Path to ARGO index file (ar_index_global_prof.txt or .gz)'
    )
    parser.add_argument(
        '--output',
        default='./data/argo_nc',
        help='Directory to save downloaded files (default: ./data/argo_nc)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=50,
        help='Maximum number of files to download (default: 50)'
    )
    parser.add_argument(
        '--ingest',
        action='store_true',
        help='Ingest downloaded files into database'
    )
    parser.add_argument(
        '--download-only',
        action='store_true',
        help='Only download files, do not ingest'
    )
    parser.add_argument(
        '--ingest-only',
        type=str,
        default=None,
        help='Skip download, only ingest files from specified directory'
    )
    
    args = parser.parse_args()
    
    if args.ingest_only:
        # Only ingest existing files
        nc_dir = Path(args.ingest_only)
        if not nc_dir.exists():
            logger.error(f"Directory not found: {args.ingest_only}")
            sys.exit(1)
        
        nc_files = list(nc_dir.glob('*.nc'))
        if not nc_files:
            logger.error(f"No .nc files found in {args.ingest_only}")
            sys.exit(1)
        
        logger.info(f"Found {len(nc_files)} NetCDF files to ingest")
        ingest_files([str(f) for f in nc_files])
        return
    
    # Need index file for download mode
    if not args.index:
        logger.error("--index is required unless using --ingest-only")
        parser.print_help()
        sys.exit(1)
    
    # Parse index file
    profiles = parse_index_file(args.index, limit=args.limit * 2)  # Parse more than needed
    
    if not profiles:
        logger.error("No Indian Ocean profiles found in index file")
        sys.exit(1)
    
    # Download files
    output_dir = Path(args.output)
    downloaded_files = download_from_ftp(profiles, output_dir, max_files=args.limit)
    
    if not downloaded_files:
        logger.error("No files were downloaded")
        sys.exit(1)
    
    # Ingest if requested
    if args.ingest and not args.download_only:
        ingest_files(downloaded_files)
    elif not args.download_only:
        logger.info(f"\nFiles saved to: {output_dir.absolute()}")
        logger.info(f"To ingest these files, run:")
        logger.info(f"  python scripts/download_argo_data.py --ingest-only \"{output_dir.absolute()}\"")


if __name__ == '__main__':
    main()
