#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Portland Air Quality Preprocessing
Prepares data for Chapter 4 Methodology Implementation
Based on Chen et al. (2018): PM2.5 z-score standardization

@author: tzirath
"""

import pandas as pd
import numpy as np
import geopandas as gpd
from scipy.spatial import cKDTree
import glob
import time
import warnings
warnings.filterwarnings('ignore')

print("="*80)
print("PORTLAND AIR QUALITY PREPROCESSING")
print("Chapter 4 Methodology: Chen et al. (2018) Z-Score Standardization")
print("="*80)

# ============================================================================
# CONFIGURATION
# ============================================================================

BASE_DIR = '/Users/tzirath/Library/CloudStorage/OneDrive-MaynoothUniversity/PhD/ComputationalFramework/'
DATA_DIR = BASE_DIR + 'data/Portland/'
OUTPUT_DIR = BASE_DIR + 'preproccessing/processed/p_aq_processed/'

# Input files
AQ_DATA_PATH = DATA_DIR + 'p_airquality/portland_aq/'
ADDRESSES_PATH = DATA_DIR + 'p_address/p_address/Active_Address_Points.shp'
NEIGHBORHOODS_PATH = DATA_DIR + 'p_boundaries/Neighborhoods_regions/Neighborhoods_regions.shp'

# Chen et al. (2018) parameters
STUDY_YEAR = 2024
EPA_VALID_RANGE = (0, 500)  # μg/m³

TARGET_CRS = 'EPSG:6554'  # Oregon State Plane

import os
os.makedirs(OUTPUT_DIR, exist_ok=True)

start_time = time.time()

# ============================================================================
# STEP 1: LOAD AIR QUALITY DATA WITH COORDINATES
# ============================================================================

print("\n" + "="*80)
print("STEP 1: LOADING AIR QUALITY DATA")
print("="*80)

# Load all Excel files (coordinates should already be in each file)
all_files = glob.glob(AQ_DATA_PATH + "/*.xlsx")
print(f"\nFound {len(all_files)} Excel files:")

li = []
for filename in all_files:
    file_basename = filename.split('/')[-1]
    print(f"\n  Loading: {file_basename}")
    
    try:
        df_temp = pd.read_excel(filename, engine='openpyxl')
    except Exception as e:
        print(f"    ❌ Error reading file: {e}")
        print(f"    Skipping this file...")
        continue
    
    # Rename second column (index 1) to PM2.5
    if len(df_temp.columns) > 1:
        old_col_name = df_temp.columns[1]
        df_temp.rename(columns={old_col_name: 'PM2.5'}, inplace=True)
        print(f"    ✓ Renamed '{old_col_name}' to 'PM2.5'")
    
    # Check for coordinate columns
    if 'Longitude' not in df_temp.columns or 'Latitude' not in df_temp.columns:
        print(f"    ⚠️  Missing Longitude/Latitude columns - skipping file")
        print(f"    Available columns: {df_temp.columns.tolist()[:10]}...")  # Show first 10
        continue
    
    # Extract monitor name from filename
    monitor_name = file_basename.replace('.xlsx', '').replace('_', ' ').title()
    df_temp['monitor_name'] = monitor_name
    
    # Show coordinates
    lon = df_temp['Longitude'].iloc[0]
    lat = df_temp['Latitude'].iloc[0]
    print(f"    ✓ Monitor: {monitor_name}")
    print(f"    ✓ Coordinates: ({lon:.6f}, {lat:.6f})")
    print(f"    ✓ Loaded {len(df_temp):,} rows")
    
    li.append(df_temp)

if len(li) == 0:
    raise ValueError("No Excel files with Longitude/Latitude columns found!")

df = pd.concat(li, axis=0, ignore_index=True)
print(f"\n✓ Total rows loaded: {len(df):,}")
print(f"✓ Loaded {len(li)} monitor files")

# Show actual columns in the data
print(f"\n📋 COLUMNS IN LOADED DATA:")
print(f"  {df.columns.tolist()}")

# Filter to Portland, Oregon (if State/County columns exist)
if 'State Name' in df.columns and 'County Name' in df.columns:
    df = df[(df['State Name'] == 'Oregon') & (df['County Name'] == 'Multnomah')].copy()
    print(f"✓ Portland data (filtered by county): {len(df):,} rows")
else:
    print(f"✓ All data: {len(df):,} rows")

# Find the date column (might have different name)
date_col = None
for col in df.columns:
    if 'date' in col.lower() or 'time' in col.lower():
        date_col = col
        print(f"\n✓ Found date column: '{date_col}'")
        break

if date_col is None:
    raise ValueError(f"No date column found! Available columns: {df.columns.tolist()}")

# Parse dates - handle "24:00 1/1/2024" format
print(f"  Sample values: {df[date_col].head(3).tolist()}")

# Extract just the date portion (after the time)
df['Date Local'] = df[date_col].apply(lambda x: str(x).split()[-1] if pd.notna(x) else None)
df['Date Local'] = pd.to_datetime(df['Date Local'], format='%m/%d/%Y', errors='coerce')
df = df.dropna(subset=['Date Local'])
df['year'] = df['Date Local'].dt.year
df['month'] = df['Date Local'].dt.month

print(f"\n📅 DATE RANGE:")
print(f"  {df['Date Local'].min()} to {df['Date Local'].max()}")

# Filter to study year
df_2024 = df[df['year'] == STUDY_YEAR].copy()
print(f"\n✓ 2024 data: {len(df_2024):,} rows")

# ============================================================================
# DATA COMPLETION CHECK
# ============================================================================

print("\n" + "="*80)
print("MONITOR DATA COMPLETION ANALYSIS (2024)")
print("="*80)

# Calculate expected days (2024 is a leap year = 366 days)
days_in_year = 366
current_day = pd.Timestamp('2024-10-27')  # Based on your context
days_elapsed = (current_day - pd.Timestamp('2024-01-01')).days + 1

print(f"\nExpected days through {current_day.date()}: {days_elapsed}")

# Per-monitor completion
monitor_stats = df_2024.groupby('monitor_name').agg({
    'Date Local': ['count', 'min', 'max'],
    'PM2.5': lambda x: x.notna().sum()
}).round(2)

monitor_stats.columns = ['Total_Records', 'First_Date', 'Last_Date', 'Valid_PM25']
monitor_stats['Days_Coverage'] = df_2024.groupby('monitor_name')['Date Local'].nunique()
monitor_stats['Completion_%'] = (monitor_stats['Days_Coverage'] / days_elapsed * 100).round(1)
monitor_stats['PM25_Valid_%'] = (monitor_stats['Valid_PM25'] / monitor_stats['Total_Records'] * 100).round(1)

print("\n📊 PER-MONITOR COMPLETION:")
print(monitor_stats.to_string())

# City-wide summary
total_records = len(df_2024)
total_monitors = df_2024['monitor_name'].nunique()
avg_completion = monitor_stats['Completion_%'].mean()

print(f"\n🏙️  CITY-WIDE SUMMARY:")
print(f"  Total monitors: {total_monitors}")
print(f"  Total records: {total_records:,}")
print(f"  Average completion: {avg_completion:.1f}%")
print(f"  Date range: {df_2024['Date Local'].min().date()} to {df_2024['Date Local'].max().date()}")

# ============================================================================
# STEP 2: DATA VALIDATION
# ============================================================================

print("\n" + "="*80)
print("STEP 2: DATA VALIDATION")
print("="*80)

# PM2.5 column (renamed during loading)
pm25_col = 'PM2.5'
print(f"\nPM2.5 column: '{pm25_col}'")
print(f"  Sample values: {df_2024[pm25_col].head(3).tolist()}")
print(f"  Valid values: {df_2024[pm25_col].notna().sum():,}")
print(f"  Missing: {df_2024[pm25_col].isna().sum():,}")

# EPA range validation
valid_range = (df_2024['PM2.5'] >= EPA_VALID_RANGE[0]) & (df_2024['PM2.5'] <= EPA_VALID_RANGE[1])
invalid_count = (~valid_range).sum()
print(f"\n✓ Values within EPA range ({EPA_VALID_RANGE[0]}-{EPA_VALID_RANGE[1]} μg/m³): {valid_range.sum():,}")
if invalid_count > 0:
    print(f"⚠️  Excluded {invalid_count} values outside valid range")
    df_2024 = df_2024[valid_range].copy()

# Check monitoring stations
print(f"\n📊 MONITORING STATIONS:")
stations = df_2024.groupby(['monitor_name', 'Latitude', 'Longitude']).size().reset_index(name='records')
print(f"  Total stations: {len(stations)}")
for idx, station in stations.iterrows():
    print(f"  {station['monitor_name']}: {station['records']:,} records")
    print(f"    Location: ({station['Latitude']:.6f}, {station['Longitude']:.6f})")

# ============================================================================
# STEP 3: MONTHLY AGGREGATION (30-DAY AVERAGES)
# ============================================================================

print("\n" + "="*80)
print("STEP 3: MONTHLY AGGREGATION (Chen et al. 30-day window)")
print("="*80)

print("\nCalculating monthly averages per monitoring station...")

# Group by station and month
monthly_pm25 = df_2024.groupby(['monitor_name', 'Latitude', 'Longitude', 
                                 'year', 'month']).agg({
    'PM2.5': 'mean',
    'Date Local': 'count'
}).reset_index()

monthly_pm25.columns = ['monitor_name', 'Latitude', 'Longitude', 
                         'year', 'month', 'PM25_monthly', 'daily_records']

print(f"✓ Monthly averages calculated: {len(monthly_pm25)} station-months")

# Check coverage
print(f"\n📅 MONTHLY COVERAGE:")
for monitor in monthly_pm25['monitor_name'].unique():
    monitor_data = monthly_pm25[monthly_pm25['monitor_name'] == monitor]
    months_covered = monitor_data['month'].nunique()
    print(f"  {monitor}: {months_covered} months")

print(f"\n📊 MONTHLY PM2.5 STATISTICS:")
print(f"  Mean: {monthly_pm25['PM25_monthly'].mean():.2f} μg/m³")
print(f"  Median: {monthly_pm25['PM25_monthly'].median():.2f} μg/m³")
print(f"  Std Dev: {monthly_pm25['PM25_monthly'].std():.2f} μg/m³")
print(f"  Min: {monthly_pm25['PM25_monthly'].min():.2f} μg/m³")
print(f"  Max: {monthly_pm25['PM25_monthly'].max():.2f} μg/m³")

# ============================================================================
# STEP 4: CITY BASELINE CALCULATION (μ_City, σ_City)
# ============================================================================

print("\n" + "="*80)
print("STEP 4: CITY BASELINE CALCULATION")
print("="*80)

print("\n🔬 CALCULATING PORTLAND BASELINE (μ_City, σ_City):")
print("  Using ALL 2024 monthly averages across all monitors")

mu_city = monthly_pm25['PM25_monthly'].mean()
sigma_city = monthly_pm25['PM25_monthly'].std()

print(f"\n✅ CITY BASELINE PARAMETERS:")
print(f"  μ_City (mean): {mu_city:.3f} μg/m³")
print(f"  σ_City (std dev): {sigma_city:.3f} μg/m³")

print(f"\n📏 STANDARD DEVIATION THRESHOLDS:")
print(f"  -1 SD: {mu_city - sigma_city:.2f} μg/m³")
print(f"  Mean: {mu_city:.2f} μg/m³")
print(f"  +1 SD: {mu_city + sigma_city:.2f} μg/m³ (Chen et al. harm threshold)")
print(f"  +1.5 SD: {mu_city + 1.5*sigma_city:.2f} μg/m³")

# ============================================================================
# STEP 5: Z-SCORE STANDARDIZATION
# ============================================================================

print("\n" + "="*80)
print("STEP 5: Z-SCORE STANDARDIZATION")
print("="*80)

print("\nCalculating z-scores for each monthly average...")
print("  Formula: Z = (PM25_monthly - μ_City) / σ_City")

monthly_pm25['z_score'] = (monthly_pm25['PM25_monthly'] - mu_city) / sigma_city

print(f"\n✓ Z-scores calculated!")

print(f"\n📊 Z-SCORE DISTRIBUTION:")
print(f"  Mean z-score: {monthly_pm25['z_score'].mean():.3f} (should be ~0)")
print(f"  Std dev: {monthly_pm25['z_score'].std():.3f} (should be ~1)")
print(f"  Min: {monthly_pm25['z_score'].min():.2f}")
print(f"  Max: {monthly_pm25['z_score'].max():.2f}")

# Check z-score ranges
print(f"\n📈 Z-SCORE RANGE DISTRIBUTION:")
print(f"  Z ≤ -1.0 (Very low risk): {(monthly_pm25['z_score'] <= -1.0).sum()} months")
print(f"  -1.0 < Z ≤ 0.0 (Low risk): {((monthly_pm25['z_score'] > -1.0) & (monthly_pm25['z_score'] <= 0.0)).sum()} months")
print(f"  0.0 < Z ≤ +1.0 (Elevated risk): {((monthly_pm25['z_score'] > 0.0) & (monthly_pm25['z_score'] <= 1.0)).sum()} months")
print(f"  +1.0 < Z ≤ +1.5 (High risk): {((monthly_pm25['z_score'] > 1.0) & (monthly_pm25['z_score'] <= 1.5)).sum()} months")
print(f"  Z > +1.5 (Very high risk): {(monthly_pm25['z_score'] > 1.5).sum()} months")

# ============================================================================
# STEP 6: CREATE MONITORING STATIONS GEODATAFRAME
# ============================================================================

print("\n" + "="*80)
print("STEP 6: SPATIAL SETUP - MONITORING STATIONS")
print("="*80)

print("\nCreating monitoring stations GeoDataFrame...")

# Get unique station locations
stations_geo = monthly_pm25[['monitor_name', 'Latitude', 'Longitude']].drop_duplicates()

# Create geometry
from shapely.geometry import Point
stations_geo['geometry'] = stations_geo.apply(
    lambda row: Point(row['Longitude'], row['Latitude']), axis=1
)

stations_gdf = gpd.GeoDataFrame(stations_geo, geometry='geometry', crs='EPSG:4326')
stations_gdf = stations_gdf.to_crs(TARGET_CRS)

print(f"✓ Created {len(stations_gdf)} monitoring station points")
for idx, station in stations_gdf.iterrows():
    print(f"  {station['monitor_name']}")

# ============================================================================
# STEP 7: LOAD AND FILTER ADDRESSES
# ============================================================================

print("\n" + "="*80)
print("STEP 7: LOAD ADDRESSES")
print("="*80)

print("\nLoading addresses...")
essential_columns = ['ADDRESS_TY', 'geometry']
addresses_raw = gpd.read_file(ADDRESSES_PATH, columns=essential_columns)
print(f"✓ Addresses loaded: {len(addresses_raw):,}")

# Reproject
if addresses_raw.crs != TARGET_CRS:
    addresses_raw = addresses_raw.to_crs(TARGET_CRS)

# Load neighborhoods for spatial filter
print("\nLoading neighborhood boundaries...")
neighborhoods = gpd.read_file(NEIGHBORHOODS_PATH)
if neighborhoods.crs != TARGET_CRS:
    neighborhoods = neighborhoods.to_crs(TARGET_CRS)

study_area = neighborhoods.geometry.unary_union

# Spatial filtering
print("\nApplying spatial filter...")
within_boundaries = addresses_raw.geometry.within(study_area)
addresses = addresses_raw[within_boundaries].copy()
print(f"✓ Addresses within study area: {len(addresses):,}")

# Residential filtering
if 'ADDRESS_TY' in addresses.columns:
    residential_mask = addresses['ADDRESS_TY'].str.upper() == 'RESIDENTIAL'
    addresses = addresses[residential_mask].copy()
    print(f"✓ Residential addresses: {len(addresses):,}")

# ============================================================================
# STEP 8: DISTANCE TO NEAREST MONITOR
# ============================================================================

print("\n" + "="*80)
print("STEP 8: ASSIGN ADDRESSES TO NEAREST MONITOR")
print("="*80)

print("\nCalculating distances to nearest monitoring station...")

addr_coords = np.array([[point.x, point.y] for point in addresses.geometry])
station_coords = np.array([[point.x, point.y] for point in stations_gdf.geometry])

print(f"  Building spatial index...")
station_tree = cKDTree(station_coords)

print(f"  Computing distances...")
distances, nearest_indices = station_tree.query(addr_coords)

addresses['distance_to_monitor_m'] = distances
addresses['nearest_monitor_idx'] = nearest_indices
addresses['nearest_monitor_name'] = stations_gdf.iloc[nearest_indices]['monitor_name'].values

print(f"\n✓ Distance calculations complete!")

print(f"\n📊 DISTANCE STATISTICS:")
print(f"  Mean distance: {distances.mean():.1f} m")
print(f"  Median distance: {np.median(distances):.1f} m")
print(f"  Min: {distances.min():.1f} m")
print(f"  Max: {distances.max():.1f} m")

# Show monitor assignment distribution
print(f"\n📍 ADDRESS ASSIGNMENT TO MONITORS:")
for monitor in stations_gdf['monitor_name'].unique():
    count = (addresses['nearest_monitor_name'] == monitor).sum()
    pct = (count / len(addresses)) * 100
    print(f"  {monitor}: {count:,} addresses ({pct:.1f}%)")

# ============================================================================
# STEP 9: SAVE PROCESSED DATA
# ============================================================================

print("\n" + "="*80)
print("STEP 9: SAVING PROCESSED DATA")
print("="*80)

# Save monthly z-scores
monthly_output = OUTPUT_DIR + 'portland_monthly_pm25_zscores.csv'
monthly_pm25.to_csv(monthly_output, index=False)
print(f"✓ Saved monthly z-scores: {monthly_output}")

# Save city baseline parameters
baseline_output = OUTPUT_DIR + 'portland_city_baseline.csv'
baseline_df = pd.DataFrame({
    'parameter': ['mu_city', 'sigma_city', 'study_year'],
    'value': [mu_city, sigma_city, STUDY_YEAR]
})
baseline_df.to_csv(baseline_output, index=False)
print(f"✓ Saved city baseline: {baseline_output}")

# Save monitoring stations
stations_output = OUTPUT_DIR + 'portland_monitoring_stations.geojson'
stations_gdf.to_file(stations_output, driver='GeoJSON')
print(f"✓ Saved monitoring stations: {stations_output}")

# Save addresses with monitor assignments
addresses_output = OUTPUT_DIR + 'portland_addresses_with_monitors.geojson'
addresses.to_file(addresses_output, driver='GeoJSON')
print(f"✓ Saved addresses with monitor assignments: {addresses_output}")

# Save summary statistics
summary_stats = {
    'metric': [
        'total_monitors',
        'total_monthly_readings',
        'mu_city_ugm3',
        'sigma_city_ugm3',
        'threshold_minus1sd',
        'threshold_plus1sd_chen',
        'threshold_plus1.5sd',
        'total_addresses',
        'residential_addresses',
        'mean_distance_to_monitor_m'
    ],
    'value': [
        len(stations_gdf),
        len(monthly_pm25),
        mu_city,
        sigma_city,
        mu_city - sigma_city,
        mu_city + sigma_city,
        mu_city + 1.5*sigma_city,
        len(addresses_raw),
        len(addresses),
        distances.mean()
    ]
}
summary_df = pd.DataFrame(summary_stats)
summary_output = OUTPUT_DIR + 'portland_airquality_summary_stats.csv'
summary_df.to_csv(summary_output, index=False)
print(f"✓ Saved summary statistics: {summary_output}")

# ============================================================================
# FINAL SUMMARY
# ============================================================================

elapsed_time = time.time() - start_time

print("\n" + "="*80)
print("PREPROCESSING COMPLETE")
print("="*80)

print(f"\n⏱️  Total processing time: {elapsed_time:.1f} seconds")
print(f"\n📊 FINAL PREPROCESSING SUMMARY:")
print(f"  Monitoring stations: {len(stations_gdf)}")
print(f"  Monthly readings (2024): {len(monthly_pm25)}")
print(f"  City baseline μ: {mu_city:.2f} μg/m³")
print(f"  City baseline σ: {sigma_city:.2f} μg/m³")
print(f"  Residential addresses: {len(addresses):,}")
print(f"  Chen et al. +1 SD threshold: {mu_city + sigma_city:.2f} μg/m³")

print("\n✅ Data ready for methodology implementation:")
print(f"   Monthly z-scores: {monthly_output}")
print(f"   Addresses with monitors: {addresses_output}")
print(f"   City baseline: {baseline_output}")

print("\n" + "="*80)
