"""
NetCDF Ingestion Pipeline for ARGO Ocean Data.

This module handles:
- Downloading ARGO NetCDF files
- Filtering data for Indian Ocean region
- Extracting and transforming variables
- Storing structured data in Neon PostgreSQL
"""

import os
import logging
import tempfile
from datetime import datetime
from typing import Optional, Dict, List, Tuple, Any
from contextlib import contextmanager

import requests
import numpy as np
import pandas as pd
import xarray as xr
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from .sa_models import (
    get_engine, get_session, create_tables,
    FloatSA, ProfileSA, MeasurementSA, ProcessedFileSA
)

logger = logging.getLogger(__name__)

# Indian Ocean bounding box
INDIAN_OCEAN_BOUNDS = {
    'lat_min': -60.0,
    'lat_max': 30.0,
    'lon_min': 20.0,
    'lon_max': 120.0,
}

# ARGO Variables to extract
ARGO_VARIABLES = [
    'PLATFORM_NUMBER',
    'JULD',
    'LATITUDE',
    'LONGITUDE',
    'PRES',
    'TEMP',
    'PSAL',
]

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# Batch size for bulk inserts
BATCH_SIZE = 1000


class NetCDFIngestionPipeline:
    """
    Pipeline for ingesting ARGO NetCDF data into PostgreSQL.
    """
    
    def __init__(self, database_url: str = None):
        """
        Initialize the pipeline.
        
        Args:
            database_url: PostgreSQL connection string
        """
        self.database_url = database_url or os.getenv('DATABASE_URL')
        self.engine = get_engine(self.database_url)
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Create database tables if they don't exist."""
        create_tables(self.engine)
    
    @contextmanager
    def _get_session(self):
        """Context manager for database sessions."""
        session = get_session(self.engine)
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def download_file(
        self, 
        url: str, 
        output_path: str = None,
        timeout: int = 300
    ) -> str:
        """
        Download a NetCDF file with streaming and retry logic.
        
        Args:
            url: URL of the NetCDF file
            output_path: Local path to save the file
            timeout: Request timeout in seconds
            
        Returns:
            Path to the downloaded file
        """
        if output_path is None:
            fd, output_path = tempfile.mkstemp(suffix='.nc')
            os.close(fd)
        
        for attempt in range(MAX_RETRIES):
            try:
                logger.info(f"Downloading {url} (attempt {attempt + 1}/{MAX_RETRIES})")
                
                response = requests.get(
                    url, 
                    stream=True, 
                    timeout=timeout,
                    headers={'Accept-Encoding': 'gzip, deflate'}
                )
                response.raise_for_status()
                
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                logger.info(f"Successfully downloaded to {output_path}")
                return output_path
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Download attempt {attempt + 1} failed: {e}")
                if attempt == MAX_RETRIES - 1:
                    raise
                import time
                time.sleep(RETRY_DELAY)
        
        return output_path
    
    def is_file_processed(self, file_path: str) -> bool:
        """
        Check if a file has already been processed.
        
        Args:
            file_path: Path or URL of the file
            
        Returns:
            True if already processed, False otherwise
        """
        with self._get_session() as session:
            result = session.query(ProcessedFileSA).filter(
                ProcessedFileSA.file_path == file_path,
                ProcessedFileSA.status == 'success'
            ).first()
            return result is not None
    
    def read_netcdf(self, file_path: str) -> xr.Dataset:
        """
        Read a NetCDF file using xarray.
        
        Args:
            file_path: Path to the NetCDF file
            
        Returns:
            xarray Dataset
        """
        logger.info(f"Reading NetCDF file: {file_path}")
        ds = xr.open_dataset(file_path)
        return ds
    
    def filter_indian_ocean(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Filter data to only include Indian Ocean region.
        
        Args:
            df: DataFrame with latitude and longitude columns
            
        Returns:
            Filtered DataFrame
        """
        mask = (
            (df['latitude'] >= INDIAN_OCEAN_BOUNDS['lat_min']) &
            (df['latitude'] <= INDIAN_OCEAN_BOUNDS['lat_max']) &
            (df['longitude'] >= INDIAN_OCEAN_BOUNDS['lon_min']) &
            (df['longitude'] <= INDIAN_OCEAN_BOUNDS['lon_max'])
        )
        
        filtered_df = df[mask].copy()
        logger.info(f"Filtered to {len(filtered_df)} Indian Ocean records from {len(df)} total")
        return filtered_df
    
    def extract_variables(self, ds: xr.Dataset) -> pd.DataFrame:
        """
        Extract relevant variables from the dataset and transform to tabular format.
        
        Args:
            ds: xarray Dataset
            
        Returns:
            pandas DataFrame with extracted variables
        """
        logger.info("Extracting variables from NetCDF dataset")
        
        records = []
        
        # Get dimensions
        n_prof = ds.dims.get('N_PROF', 0)
        n_levels = ds.dims.get('N_LEVELS', 0)
        
        if n_prof == 0:
            logger.warning("No profiles found in dataset")
            return pd.DataFrame()
        
        # Extract data arrays
        try:
            platform_numbers = ds['PLATFORM_NUMBER'].values if 'PLATFORM_NUMBER' in ds else None
            juld = ds['JULD'].values if 'JULD' in ds else None
            latitudes = ds['LATITUDE'].values if 'LATITUDE' in ds else None
            longitudes = ds['LONGITUDE'].values if 'LONGITUDE' in ds else None
            pressures = ds['PRES'].values if 'PRES' in ds else None
            temperatures = ds['TEMP'].values if 'TEMP' in ds else None
            salinities = ds['PSAL'].values if 'PSAL' in ds else None
        except KeyError as e:
            logger.error(f"Missing variable in dataset: {e}")
            raise
        
        # Reference date for JULD
        reference_date = np.datetime64('1950-01-01')
        
        for i in range(n_prof):
            # Get platform number
            if platform_numbers is not None:
                pn = platform_numbers[i]
                if isinstance(pn, bytes):
                    pn = pn.decode('utf-8').strip()
                elif isinstance(pn, np.ndarray):
                    pn = ''.join([chr(c) if c != 0 else '' for c in pn]).strip()
                else:
                    pn = str(pn).strip()
            else:
                continue
            
            # Get latitude and longitude
            lat = float(latitudes[i]) if latitudes is not None else None
            lon = float(longitudes[i]) if longitudes is not None else None
            
            if lat is None or lon is None or np.isnan(lat) or np.isnan(lon):
                continue
            
            # Get profile time
            if juld is not None:
                try:
                    juld_val = juld[i]
                    
                    # Handle different JULD formats
                    if np.issubdtype(juld_val.dtype, np.datetime64):
                        # Already datetime64 - use directly
                        profile_time = pd.Timestamp(juld_val)
                    else:
                        # JULD is days since 1950-01-01
                        if np.isnan(juld_val):
                            continue
                        profile_time = reference_date + np.timedelta64(int(float(juld_val) * 86400), 's')
                        profile_time = pd.Timestamp(profile_time)
                    
                    if pd.isna(profile_time):
                        continue
                except (ValueError, OverflowError, TypeError):
                    continue
            else:
                continue
            
            # Get measurements at each level
            for j in range(n_levels):
                pressure = pressures[i, j] if pressures is not None else None
                temperature = temperatures[i, j] if temperatures is not None else None
                salinity = salinities[i, j] if salinities is not None else None
                
                # Skip if all measurements are NaN
                if (pressure is None or np.isnan(pressure)) and \
                   (temperature is None or np.isnan(temperature)) and \
                   (salinity is None or np.isnan(salinity)):
                    continue
                
                # Convert NaN to None
                pressure = None if (pressure is not None and np.isnan(pressure)) else pressure
                temperature = None if (temperature is not None and np.isnan(temperature)) else temperature
                salinity = None if (salinity is not None and np.isnan(salinity)) else salinity
                
                records.append({
                    'platform_number': pn,
                    'profile_time': profile_time,
                    'latitude': lat,
                    'longitude': lon,
                    'pressure': float(pressure) if pressure is not None else None,
                    'temperature': float(temperature) if temperature is not None else None,
                    'salinity': float(salinity) if salinity is not None else None,
                })
        
        df = pd.DataFrame(records)
        logger.info(f"Extracted {len(df)} measurement records from {n_prof} profiles")
        return df
    
    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean and validate the extracted data.
        
        Args:
            df: Raw DataFrame
            
        Returns:
            Cleaned DataFrame
        """
        if df.empty:
            return df
        
        # Drop rows where all measurement values are null
        df = df.dropna(subset=['pressure', 'temperature', 'salinity'], how='all')
        
        # Drop duplicates
        df = df.drop_duplicates(subset=[
            'platform_number', 'profile_time', 'pressure'
        ])
        
        # Validate ranges
        # Temperature: -2 to 40°C
        # Salinity: 0 to 45 PSU
        # Pressure: 0 to 6000 dbar
        df = df[
            (df['temperature'].isna() | ((df['temperature'] >= -2) & (df['temperature'] <= 40))) &
            (df['salinity'].isna() | ((df['salinity'] >= 0) & (df['salinity'] <= 45))) &
            (df['pressure'].isna() | ((df['pressure'] >= 0) & (df['pressure'] <= 6000)))
        ]
        
        logger.info(f"Cleaned data: {len(df)} records remaining")
        return df
    
    def upsert_floats(
        self, 
        session, 
        platform_numbers: List[str]
    ) -> Dict[str, int]:
        """
        Upsert float records and return mapping of platform_number to float_id.
        
        Args:
            session: SQLAlchemy session
            platform_numbers: List of platform numbers
            
        Returns:
            Dictionary mapping platform_number to float_id
        """
        float_map = {}
        unique_platforms = list(set(platform_numbers))
        now = datetime.utcnow()
        
        for platform_number in unique_platforms:
            # Use PostgreSQL UPSERT
            stmt = insert(FloatSA).values(
                platform_number=platform_number,
                first_seen=now,
                last_seen=now
            ).on_conflict_do_update(
                index_elements=['platform_number'],
                set_=dict(last_seen=now)
            ).returning(FloatSA.id)
            
            result = session.execute(stmt)
            float_id = result.fetchone()[0]
            float_map[platform_number] = float_id
        
        session.commit()
        logger.info(f"Upserted {len(float_map)} floats")
        return float_map
    
    def upsert_profiles(
        self, 
        session, 
        df: pd.DataFrame, 
        float_map: Dict[str, int]
    ) -> Dict[Tuple[int, datetime], int]:
        """
        Upsert profile records and return mapping to profile_id.
        
        Args:
            session: SQLAlchemy session
            df: DataFrame with profile data
            float_map: Mapping of platform_number to float_id
            
        Returns:
            Dictionary mapping (float_id, profile_time) to profile_id
        """
        profile_map = {}
        
        # Get unique profiles
        profiles_df = df[['platform_number', 'profile_time', 'latitude', 'longitude']].drop_duplicates()
        
        for _, row in profiles_df.iterrows():
            float_id = float_map.get(row['platform_number'])
            if float_id is None:
                continue
            
            profile_time = row['profile_time']
            if isinstance(profile_time, pd.Timestamp):
                profile_time = profile_time.to_pydatetime()
            
            # Use PostgreSQL UPSERT
            stmt = insert(ProfileSA).values(
                float_id=float_id,
                latitude=row['latitude'],
                longitude=row['longitude'],
                profile_time=profile_time
            ).on_conflict_do_update(
                constraint='uq_float_profile_time',
                set_=dict(
                    latitude=row['latitude'],
                    longitude=row['longitude']
                )
            ).returning(ProfileSA.id)
            
            result = session.execute(stmt)
            profile_id = result.fetchone()[0]
            profile_map[(float_id, profile_time)] = profile_id
        
        session.commit()
        logger.info(f"Upserted {len(profile_map)} profiles")
        return profile_map
    
    def bulk_insert_measurements(
        self, 
        session, 
        df: pd.DataFrame, 
        float_map: Dict[str, int],
        profile_map: Dict[Tuple[int, datetime], int]
    ) -> int:
        """
        Bulk insert measurements.
        
        Args:
            session: SQLAlchemy session
            df: DataFrame with measurement data
            float_map: Mapping of platform_number to float_id
            profile_map: Mapping of (float_id, profile_time) to profile_id
            
        Returns:
            Number of inserted records
        """
        measurements = []
        
        for _, row in df.iterrows():
            float_id = float_map.get(row['platform_number'])
            if float_id is None:
                continue
            
            profile_time = row['profile_time']
            if isinstance(profile_time, pd.Timestamp):
                profile_time = profile_time.to_pydatetime()
            
            profile_id = profile_map.get((float_id, profile_time))
            if profile_id is None:
                continue
            
            measurements.append({
                'profile_id': profile_id,
                'pressure': row['pressure'],
                'temperature': row['temperature'],
                'salinity': row['salinity'],
            })
        
        # Bulk insert in batches
        inserted_count = 0
        for i in range(0, len(measurements), BATCH_SIZE):
            batch = measurements[i:i + BATCH_SIZE]
            session.execute(
                MeasurementSA.__table__.insert(),
                batch
            )
            inserted_count += len(batch)
            session.commit()
        
        logger.info(f"Bulk inserted {inserted_count} measurements")
        return inserted_count
    
    def record_processed_file(
        self, 
        session, 
        file_path: str, 
        records_inserted: int,
        status: str = 'success',
        error_message: str = None
    ):
        """
        Record that a file has been processed.
        
        Args:
            session: SQLAlchemy session
            file_path: Path or URL of the file
            records_inserted: Number of records inserted
            status: Processing status
            error_message: Error message if failed
        """
        file_name = os.path.basename(file_path)
        
        stmt = insert(ProcessedFileSA).values(
            file_path=file_path,
            file_name=file_name,
            processed_at=datetime.utcnow(),
            records_inserted=records_inserted,
            status=status,
            error_message=error_message
        ).on_conflict_do_update(
            index_elements=['file_path'],
            set_=dict(
                processed_at=datetime.utcnow(),
                records_inserted=records_inserted,
                status=status,
                error_message=error_message
            )
        )
        
        session.execute(stmt)
        session.commit()
    
    def ingest_file(
        self, 
        file_path: str, 
        is_url: bool = False,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Ingest a NetCDF file into the database.
        
        Args:
            file_path: Path or URL to the NetCDF file
            is_url: Whether file_path is a URL
            force: Force reprocessing even if already processed
            
        Returns:
            Dictionary with ingestion statistics
        """
        stats = {
            'file_path': file_path,
            'status': 'pending',
            'records_inserted': 0,
            'profiles_created': 0,
            'floats_created': 0,
            'error': None,
        }
        
        # Check if already processed
        if not force and self.is_file_processed(file_path):
            logger.info(f"File already processed: {file_path}")
            stats['status'] = 'skipped'
            return stats
        
        local_path = None
        ds = None
        
        try:
            # Download if URL
            if is_url:
                local_path = self.download_file(file_path)
            else:
                local_path = file_path
            
            # Read NetCDF
            ds = self.read_netcdf(local_path)
            
            # Extract variables
            df = self.extract_variables(ds)
            
            if df.empty:
                logger.warning(f"No data extracted from {file_path}")
                stats['status'] = 'empty'
                return stats
            
            # Filter Indian Ocean
            df = self.filter_indian_ocean(df)
            
            if df.empty:
                logger.warning(f"No Indian Ocean data in {file_path}")
                stats['status'] = 'no_matching_data'
                return stats
            
            # Clean data
            df = self.clean_data(df)
            
            # Insert into database
            with self._get_session() as session:
                # Upsert floats
                float_map = self.upsert_floats(
                    session, 
                    df['platform_number'].unique().tolist()
                )
                stats['floats_created'] = len(float_map)
                
                # Upsert profiles
                profile_map = self.upsert_profiles(session, df, float_map)
                stats['profiles_created'] = len(profile_map)
                
                # Bulk insert measurements
                records_inserted = self.bulk_insert_measurements(
                    session, df, float_map, profile_map
                )
                stats['records_inserted'] = records_inserted
                
                # Record processed file
                self.record_processed_file(
                    session, 
                    file_path, 
                    records_inserted,
                    status='success'
                )
            
            stats['status'] = 'success'
            logger.info(f"Successfully ingested {file_path}: {stats}")
            
        except Exception as e:
            logger.error(f"Error ingesting {file_path}: {e}")
            stats['status'] = 'failed'
            stats['error'] = str(e)
            
            # Record failed processing
            try:
                with self._get_session() as session:
                    self.record_processed_file(
                        session,
                        file_path,
                        0,
                        status='failed',
                        error_message=str(e)
                    )
            except Exception:
                pass
            
        finally:
            # Close dataset to avoid memory leaks
            if ds is not None:
                ds.close()
            
            # Clean up temporary file
            if is_url and local_path and os.path.exists(local_path):
                try:
                    os.remove(local_path)
                except Exception:
                    pass
        
        return stats
    
    def ingest_directory(
        self, 
        directory: str, 
        pattern: str = '*.nc',
        force: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Ingest all NetCDF files from a directory.
        
        Args:
            directory: Path to directory containing NetCDF files
            pattern: Glob pattern for file matching
            force: Force reprocessing
            
        Returns:
            List of ingestion statistics for each file
        """
        import glob
        
        files = glob.glob(os.path.join(directory, pattern))
        logger.info(f"Found {len(files)} files matching {pattern} in {directory}")
        
        results = []
        for file_path in files:
            result = self.ingest_file(file_path, is_url=False, force=force)
            results.append(result)
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get database statistics.
        
        Returns:
            Dictionary with database statistics
        """
        with self._get_session() as session:
            stats = {
                'total_floats': session.query(FloatSA).count(),
                'total_profiles': session.query(ProfileSA).count(),
                'total_measurements': session.query(MeasurementSA).count(),
                'processed_files': session.query(ProcessedFileSA).filter(
                    ProcessedFileSA.status == 'success'
                ).count(),
                'failed_files': session.query(ProcessedFileSA).filter(
                    ProcessedFileSA.status == 'failed'
                ).count(),
            }
        
        return stats


def run_ingestion(
    source: str, 
    is_url: bool = False, 
    is_directory: bool = False,
    force: bool = False,
    database_url: str = None
) -> Dict[str, Any]:
    """
    Run the ingestion pipeline.
    
    Args:
        source: File path, URL, or directory path
        is_url: Whether source is a URL
        is_directory: Whether source is a directory
        force: Force reprocessing
        database_url: Database connection string
        
    Returns:
        Ingestion results
    """
    pipeline = NetCDFIngestionPipeline(database_url=database_url)
    
    if is_directory:
        results = pipeline.ingest_directory(source, force=force)
        return {
            'type': 'directory',
            'source': source,
            'files_processed': len(results),
            'results': results,
            'stats': pipeline.get_stats(),
        }
    else:
        result = pipeline.ingest_file(source, is_url=is_url, force=force)
        return {
            'type': 'file',
            'source': source,
            'result': result,
            'stats': pipeline.get_stats(),
        }
