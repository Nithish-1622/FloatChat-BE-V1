from django.contrib import admin
from .models import Float, Profile, Measurement, ProcessedFile


@admin.register(Float)
class FloatAdmin(admin.ModelAdmin):
    list_display = ['platform_number', 'first_seen', 'last_seen']
    search_fields = ['platform_number']
    list_filter = ['first_seen', 'last_seen']
    ordering = ['platform_number']


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['id', 'float', 'latitude', 'longitude', 'profile_time']
    list_filter = ['profile_time']
    search_fields = ['float__platform_number']
    ordering = ['-profile_time']
    raw_id_fields = ['float']


@admin.register(Measurement)
class MeasurementAdmin(admin.ModelAdmin):
    list_display = ['id', 'profile', 'pressure', 'temperature', 'salinity']
    list_filter = ['profile__profile_time']
    ordering = ['profile', 'pressure']
    raw_id_fields = ['profile']


@admin.register(ProcessedFile)
class ProcessedFileAdmin(admin.ModelAdmin):
    list_display = ['file_name', 'status', 'records_inserted', 'processed_at']
    list_filter = ['status', 'processed_at']
    search_fields = ['file_name', 'file_path']
    ordering = ['-processed_at']
