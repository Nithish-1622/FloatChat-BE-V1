"""
Database models for ARGO Ocean Data.

Tables:
- Float: Represents an ARGO float device
- Profile: Represents a measurement profile at a specific time/location
- Measurement: Individual measurements (pressure, temperature, salinity)
- ProcessedFile: Tracks which NetCDF files have been processed
"""

from django.db import models
from django.utils import timezone


class Float(models.Model):
    """
    Represents an ARGO float device.
    Each float has a unique platform_number.
    """
    platform_number = models.CharField(
        max_length=20, 
        unique=True, 
        db_index=True,
        help_text="Unique identifier for the ARGO float"
    )
    first_seen = models.DateTimeField(
        default=timezone.now,
        help_text="First time this float was observed"
    )
    last_seen = models.DateTimeField(
        default=timezone.now,
        help_text="Last time this float was observed"
    )
    
    class Meta:
        db_table = 'floats'
        ordering = ['platform_number']
        indexes = [
            models.Index(fields=['platform_number']),
        ]
    
    def __str__(self):
        return f"Float {self.platform_number}"


class Profile(models.Model):
    """
    Represents a measurement profile from a float at a specific time and location.
    Each profile is unique per float and timestamp.
    """
    float = models.ForeignKey(
        Float, 
        on_delete=models.CASCADE, 
        related_name='profiles',
        db_index=True
    )
    latitude = models.FloatField(
        db_index=True,
        help_text="Latitude in degrees (-90 to 90)"
    )
    longitude = models.FloatField(
        db_index=True,
        help_text="Longitude in degrees (-180 to 180)"
    )
    profile_time = models.DateTimeField(
        db_index=True,
        help_text="Time of the profile measurement"
    )
    
    class Meta:
        db_table = 'profiles'
        ordering = ['-profile_time']
        unique_together = ['float', 'profile_time']
        indexes = [
            models.Index(fields=['profile_time']),
            models.Index(fields=['latitude', 'longitude']),
            models.Index(fields=['float', 'profile_time']),
        ]
    
    def __str__(self):
        return f"Profile {self.id} - Float {self.float.platform_number} at {self.profile_time}"


class Measurement(models.Model):
    """
    Individual measurement data from a profile.
    Contains pressure, temperature, and salinity readings.
    """
    profile = models.ForeignKey(
        Profile, 
        on_delete=models.CASCADE, 
        related_name='measurements',
        db_index=True
    )
    pressure = models.FloatField(
        null=True, 
        blank=True,
        help_text="Pressure in decibars"
    )
    temperature = models.FloatField(
        null=True, 
        blank=True,
        help_text="Temperature in degrees Celsius"
    )
    salinity = models.FloatField(
        null=True, 
        blank=True,
        help_text="Practical salinity units (PSU)"
    )
    
    class Meta:
        db_table = 'measurements'
        ordering = ['pressure']
        indexes = [
            models.Index(fields=['profile']),
            models.Index(fields=['pressure']),
        ]
    
    def __str__(self):
        return f"Measurement @ {self.pressure}dbar - T:{self.temperature}°C, S:{self.salinity}PSU"


class ProcessedFile(models.Model):
    """
    Tracks which NetCDF files have been processed to prevent duplicate ingestion.
    """
    file_path = models.CharField(
        max_length=500, 
        unique=True,
        help_text="Path or URL of the processed file"
    )
    file_name = models.CharField(
        max_length=255,
        help_text="Name of the processed file"
    )
    processed_at = models.DateTimeField(
        default=timezone.now,
        help_text="When the file was processed"
    )
    records_inserted = models.IntegerField(
        default=0,
        help_text="Number of records inserted from this file"
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('success', 'Success'),
            ('failed', 'Failed'),
            ('partial', 'Partial'),
        ],
        default='success'
    )
    error_message = models.TextField(
        null=True, 
        blank=True,
        help_text="Error message if processing failed"
    )
    
    class Meta:
        db_table = 'processed_files'
        ordering = ['-processed_at']
        indexes = [
            models.Index(fields=['file_path']),
            models.Index(fields=['processed_at']),
        ]
    
    def __str__(self):
        return f"{self.file_name} - {self.status} ({self.processed_at})"
