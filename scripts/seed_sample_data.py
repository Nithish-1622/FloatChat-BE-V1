"""
Seed script to populate the database with sample ARGO ocean data.
This is for testing purposes when real NetCDF files are not available.
"""

import os
import sys
import random
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'argo_ai.settings')

import django
django.setup()

from django.utils import timezone
from apps.ingestion.models import Float, Profile, Measurement


def generate_sample_data():
    """Generate realistic ARGO ocean data for the Indian Ocean."""
    
    print("Seeding sample ARGO ocean data...")
    
    # Indian Ocean bounds
    LAT_MIN, LAT_MAX = -60, 30
    LON_MIN, LON_MAX = 20, 120
    
    # Sample float platform numbers (realistic ARGO float IDs)
    float_ids = [
        '2901001', '2901002', '2901003', '2901004', '2901005',
        '2901006', '2901007', '2901008', '2901009', '2901010',
        '5901001', '5901002', '5901003', '5901004', '5901005',
        '6901001', '6901002', '6901003', '6901004', '6901005',
    ]
    
    floats_created = 0
    profiles_created = 0
    measurements_created = 0
    
    # Time range: last 2 years
    end_date = timezone.now()
    start_date = end_date - timedelta(days=730)
    
    for platform_number in float_ids:
        # Create or get float
        float_obj, created = Float.objects.get_or_create(
            platform_number=platform_number,
            defaults={
                'first_seen': start_date,
                'last_seen': end_date,
            }
        )
        
        if created:
            floats_created += 1
            print(f"  Created float: {platform_number}")
        
        # Generate base position in Indian Ocean
        base_lat = random.uniform(LAT_MIN, LAT_MAX)
        base_lon = random.uniform(LON_MIN, LON_MAX)
        
        # Generate profiles over time (every 10 days on average)
        num_profiles = random.randint(50, 100)
        current_time = start_date
        
        for i in range(num_profiles):
            # Slight drift in position
            lat = base_lat + random.uniform(-2, 2)
            lon = base_lon + random.uniform(-2, 2)
            
            # Clamp to Indian Ocean bounds
            lat = max(LAT_MIN, min(LAT_MAX, lat))
            lon = max(LON_MIN, min(LON_MAX, lon))
            
            # Time increment (5-15 days)
            current_time += timedelta(days=random.randint(5, 15))
            if current_time > end_date:
                break
            
            # Create profile
            profile, created = Profile.objects.get_or_create(
                float=float_obj,
                profile_time=current_time,
                defaults={
                    'latitude': round(lat, 4),
                    'longitude': round(lon, 4),
                }
            )
            
            if created:
                profiles_created += 1
                
                # Generate measurements at different depths
                depths = [5, 10, 20, 50, 100, 200, 500, 1000, 1500, 2000]
                
                for depth in depths:
                    # Realistic temperature profile (decreases with depth)
                    # Surface: ~25-30°C, Deep: ~2-4°C
                    if depth < 100:
                        temp = random.uniform(22, 30) - (depth * 0.05)
                    elif depth < 500:
                        temp = random.uniform(10, 18) - ((depth - 100) * 0.02)
                    else:
                        temp = random.uniform(2, 6)
                    
                    # Realistic salinity (PSU) - fairly constant ~34-36
                    salinity = random.uniform(34.0, 36.5)
                    
                    # Convert depth to pressure (roughly 1 dbar per meter)
                    pressure = depth
                    
                    Measurement.objects.create(
                        profile=profile,
                        pressure=round(pressure, 2),
                        temperature=round(temp, 3),
                        salinity=round(salinity, 3),
                    )
                    measurements_created += 1
        
        # Update float last_seen
        float_obj.last_seen = current_time
        float_obj.save()
    
    print(f"\nSeeding complete!")
    print(f"  Floats created: {floats_created}")
    print(f"  Profiles created: {profiles_created}")
    print(f"  Measurements created: {measurements_created}")
    
    return {
        'floats': floats_created,
        'profiles': profiles_created,
        'measurements': measurements_created,
    }


def clear_data():
    """Clear all existing data."""
    print("Clearing existing data...")
    Measurement.objects.all().delete()
    Profile.objects.all().delete()
    Float.objects.all().delete()
    print("Data cleared.")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Seed sample ARGO ocean data')
    parser.add_argument('--clear', action='store_true', help='Clear existing data before seeding')
    args = parser.parse_args()
    
    if args.clear:
        clear_data()
    
    generate_sample_data()
