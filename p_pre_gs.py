#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Portland Greenspace Preprocessing
Prepares data for Chapter 4 Methodology Implementation
Includes comprehensive descriptive statistics for thesis

Based on Gascon et al. (2018): Parks ≥0.5 hectares within 300m-500m buffers

@author: tzirath
"""

import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial import cKDTree
import time
import warnings
warnings.filterwarnings('ignore')

print("="*80)
print("PORTLAND GREENSPACE PREPROCESSING")
print("Chapter 4 Methodology: Gascon et al. (2018) Thresholds")
print("="*80)

# ============================================================================
# CONFIGURATION
# ============================================================================

BASE_DIR = '/.../PhD/ComputationalFramework/data/Portland'
OUTPUT_DIR = '/.../PhD/ComputationalFramework/preproccessing/processed/p_gs_processed/'

ADDRESSES_PATH = BASE_DIR + '/p_address/p_address/Active_Address_Points.shp'
PARKS_PATH = BASE_DIR + '/p_greenspace/p_parks/Parks.shp'
NEIGHBORHOODS_PATH = BASE_DIR + '/p_boundaries/Neighborhoods_regions/Neighborhoods_regions.shp'

# Gascon et al. (2018) thresholds from Chapter 4
MIN_PARK_SIZE_HECTARES = 0.5
MIN_PARK_SIZE_M2 = 5000  # 0.5 hectares = 5,000 m²
PROTECTIVE_DISTANCE_M = 300
EXTENDED_BENEFIT_M = 500

TARGET_CRS = 'EPSG:6554'  # State Plane: NAD83 / Oregon North (meters)

start_time = time.time()

# ============================================================================
# STEP 1: LOAD RAW DATA
# ============================================================================

print("\n" + "="*80)
print("STEP 1: LOADING RAW DATA")
print("="*80)

print("\nLoading neighborhood boundaries...")
neighborhoods = gpd.read_file(NEIGHBORHOODS_PATH)
print(f"✓ Neighborhoods loaded: {len(neighborhoods)}")

print("\nLoading parks...")
parks_raw = gpd.read_file(PARKS_PATH)
print(f"✓ Parks loaded: {len(parks_raw)}")

print("\nLoading addresses (essential columns only)...")
essential_columns = ['ADDRESS_TY', 'geometry']
addresses_raw = gpd.read_file(ADDRESSES_PATH, columns=essential_columns)
print(f"✓ Addresses loaded: {len(addresses_raw):,}")

# ============================================================================
# STEP 2: GREENSPACE DESCRIPTIVE STATISTICS (RAW)
# ============================================================================

print("\n" + "="*80)
print("STEP 2: GREENSPACE DESCRIPTIVE STATISTICS (BEFORE FILTERING)")
print("="*80)

# Reproject parks to calculate areas in square meters
if parks_raw.crs != TARGET_CRS:
    parks_raw = parks_raw.to_crs(TARGET_CRS)

parks_raw['area_m2'] = parks_raw.geometry.area
parks_raw['area_hectares'] = parks_raw['area_m2'] / 10000

print("\n📊 RAW GREENSPACE STATISTICS:")
print(f"Total parks: {len(parks_raw):,}")
print(f"\nArea Distribution:")
print(f"  Mean area: {parks_raw['area_hectares'].mean():.2f} hectares")
print(f"  Median area: {parks_raw['area_hectares'].median():.2f} hectares")
print(f"  Std dev: {parks_raw['area_hectares'].std():.2f} hectares")
print(f"  Min area: {parks_raw['area_hectares'].min():.4f} hectares")
print(f"  Max area: {parks_raw['area_hectares'].max():.2f} hectares")
print(f"  Total greenspace: {parks_raw['area_hectares'].sum():.2f} hectares")

# Size distribution
print(f"\n📏 Size Distribution (Before 0.5 ha Filter):")
size_bins = [0, 0.1, 0.5, 1, 5, 10, parks_raw['area_hectares'].max()]
size_labels = ['<0.1 ha', '0.1-0.5 ha', '0.5-1 ha', '1-5 ha', '5-10 ha', '>10 ha']
parks_raw['size_category'] = pd.cut(parks_raw['area_hectares'], bins=size_bins, labels=size_labels)

size_counts = parks_raw['size_category'].value_counts().sort_index()
for category, count in size_counts.items():
    pct = (count / len(parks_raw)) * 100
    print(f"  {category}: {count:,} parks ({pct:.1f}%)")

# ============================================================================
# STEP 3: APPLY GASCON ET AL. (2018) 0.5 HECTARE FILTER
# ============================================================================

print("\n" + "="*80)
print("STEP 3: APPLYING GASCON ET AL. (2018) METHODOLOGY")
print("="*80)

print(f"\n🔬 Literature-Based Filtering:")
print(f"Minimum park size: {MIN_PARK_SIZE_HECTARES} hectares ({MIN_PARK_SIZE_M2:,} m²)")
print(f"Rationale: Gascon et al. (2018) - parks ≥0.5 ha provide measurable")
print(f"           mental health benefits through stress reduction")

parks_before = len(parks_raw)
parks = parks_raw[parks_raw['area_hectares'] >= MIN_PARK_SIZE_HECTARES].copy()
parks_excluded = parks_before - len(parks)

# CRITICAL: Reset index to create contiguous 0,1,2... indices for distance mapping
parks = parks.reset_index(drop=True)

print(f"\n✓ Eligible parks (≥0.5 ha): {len(parks):,}")
print(f"✗ Excluded parks (<0.5 ha): {parks_excluded:,}")
print(f"  Exclusion rate: {(parks_excluded/parks_before)*100:.1f}%")

# ============================================================================
# STEP 4: GREENSPACE STATISTICS (AFTER FILTERING)
# ============================================================================

print("\n" + "="*80)
print("STEP 4: GREENSPACE STATISTICS (AFTER 0.5 HA FILTERING)")
print("="*80)

print("\n📊 ELIGIBLE GREENSPACE STATISTICS:")
print(f"Total eligible parks: {len(parks):,}")
print(f"\nArea Distribution (Eligible Parks):")
print(f"  Mean area: {parks['area_hectares'].mean():.2f} hectares")
print(f"  Median area: {parks['area_hectares'].median():.2f} hectares")
print(f"  Std dev: {parks['area_hectares'].std():.2f} hectares")
print(f"  Min area: {parks['area_hectares'].min():.2f} hectares")
print(f"  Max area: {parks['area_hectares'].max():.2f} hectares")
print(f"  Total eligible greenspace: {parks['area_hectares'].sum():.2f} hectares")

retained_area_pct = (parks['area_hectares'].sum() / parks_raw['area_hectares'].sum()) * 100
print(f"  % of total greenspace retained: {retained_area_pct:.1f}%")

# Size distribution of eligible parks
print(f"\n📏 Size Distribution (Eligible Parks Only):")
size_counts_eligible = parks['size_category'].value_counts().sort_index()
for category, count in size_counts_eligible.items():
    if count > 0:
        pct = (count / len(parks)) * 100
        print(f"  {category}: {count:,} parks ({pct:.1f}%)")

# ============================================================================
# STEP 5: ADDRESS FILTERING (SPATIAL + RESIDENTIAL)
# ============================================================================

print("\n" + "="*80)
print("STEP 5: ADDRESS FILTERING")
print("="*80)

# Reproject addresses
if addresses_raw.crs != TARGET_CRS:
    addresses_raw = addresses_raw.to_crs(TARGET_CRS)

# Create study area from neighborhoods
print("\nDefining study area from neighborhood boundaries...")
if neighborhoods.crs != TARGET_CRS:
    neighborhoods = neighborhoods.to_crs(TARGET_CRS)

study_area = neighborhoods.geometry.unary_union

# Spatial filtering
print("\nApplying spatial filter (addresses within neighborhoods)...")
addresses_before = len(addresses_raw)
within_boundaries = addresses_raw.geometry.within(study_area)
addresses = addresses_raw[within_boundaries].copy()
spatial_excluded = addresses_before - len(addresses)

print(f"✓ Addresses within study area: {len(addresses):,}")
print(f"✗ Excluded (outside boundaries): {spatial_excluded:,}")

# Residential filtering
print("\n📊 ADDRESS TYPE DISTRIBUTION:")
if 'ADDRESS_TY' in addresses.columns:
    address_types = addresses['ADDRESS_TY'].value_counts()
    for addr_type, count in address_types.items():
        pct = (count / len(addresses)) * 100
        print(f"  {addr_type}: {count:,} ({pct:.1f}%)")
    
    # Filter to residential
    before_res_filter = len(addresses)
    residential_mask = addresses['ADDRESS_TY'].str.upper() == 'RESIDENTIAL'
    addresses = addresses[residential_mask].copy()
    nonres_excluded = before_res_filter - len(addresses)
    
    print(f"\n✓ Final residential addresses: {len(addresses):,}")
    print(f"✗ Excluded (non-residential): {nonres_excluded:,}")

# ============================================================================
# STEP 6: DISTANCE CALCULATION TO NEAREST ELIGIBLE PARKS
# ============================================================================

print("\n" + "="*80)
print("STEP 6: DISTANCE CALCULATIONS")
print("="*80)

print("\nExtracting address coordinates...")
addr_coords = np.array([[point.x, point.y] for point in addresses.geometry])
print(f"✓ Coordinates extracted: {len(addr_coords):,} addresses")

print("\nExtracting park boundary coordinates...")
park_boundary_coords = []
park_indices = []

for idx, park in parks.iterrows():
    if park.geometry.geom_type == 'Polygon':
        boundary_coords = list(park.geometry.exterior.coords)
        park_boundary_coords.extend(boundary_coords)
        park_indices.extend([idx] * len(boundary_coords))
    elif park.geometry.geom_type == 'MultiPolygon':
        for polygon in park.geometry.geoms:
            boundary_coords = list(polygon.exterior.coords)
            park_boundary_coords.extend(boundary_coords)
            park_indices.extend([idx] * len(boundary_coords))

park_boundary_coords = np.array(park_boundary_coords)
park_indices = np.array(park_indices)

print(f"✓ Boundary points extracted: {len(park_boundary_coords):,} from {len(parks)} parks")

print("\nBuilding spatial index...")
park_tree = cKDTree(park_boundary_coords)

print("Computing distances (batch processing)...")
batch_size = 10000
distances = []
nearest_park_indices = []

for i in range(0, len(addr_coords), batch_size):
    batch_end = min(i + batch_size, len(addr_coords))
    batch_coords = addr_coords[i:batch_end]
    
    batch_distances, batch_nearest_indices = park_tree.query(batch_coords)
    
    distances.extend(batch_distances)
    nearest_park_indices.extend(batch_nearest_indices)
    
    if (i // batch_size + 1) % 10 == 0:
        print(f"  Processed {batch_end:,} / {len(addr_coords):,} addresses")

distances = np.array(distances)
nearest_parks = park_indices[np.array(nearest_park_indices)]

# Add to dataframe
addresses['distance_to_park_m'] = distances
addresses['nearest_park_idx'] = nearest_parks

# Add park names if available
if 'NAME' in parks.columns:
    addresses['nearest_park_name'] = parks['NAME'].iloc[nearest_parks].values
elif 'SITE_NAME' in parks.columns:
    addresses['nearest_park_name'] = parks['SITE_NAME'].iloc[nearest_parks].values

print(f"\n✓ Distance calculations complete!")

# ============================================================================
# STEP 7: DISTANCE DESCRIPTIVE STATISTICS
# ============================================================================

print("\n" + "="*80)
print("STEP 7: DISTANCE STATISTICS (FOR CHAPTER 5 RESULTS)")
print("="*80)

print("\n📊 DISTANCE DISTRIBUTION:")
print(f"  Mean distance: {distances.mean():.1f} m")
print(f"  Median distance: {np.median(distances):.1f} m")
print(f"  Std dev: {distances.std():.1f} m")
print(f"  Min distance: {distances.min():.1f} m")
print(f"  Max distance: {distances.max():.1f} m")

# Quartiles
q25, q50, q75 = np.percentile(distances, [25, 50, 75])
print(f"\n📈 Quartiles:")
print(f"  25th percentile: {q25:.1f} m")
print(f"  50th percentile (median): {q50:.1f} m")
print(f"  75th percentile: {q75:.1f} m")

# Literature-based thresholds from Gascon et al. (2018)
print(f"\n🔬 GASCON ET AL. (2018) THRESHOLD ANALYSIS:")
within_300m = (distances <= PROTECTIVE_DISTANCE_M).sum()
within_500m = (distances <= EXTENDED_BENEFIT_M).sum()
beyond_500m = (distances > EXTENDED_BENEFIT_M).sum()

print(f"  Within 300m (OR=0.18, 82% lower depression risk):")
print(f"    {within_300m:,} addresses ({(within_300m/len(addresses))*100:.1f}%)")
print(f"  Within 500m (OR≈0.84, 16% lower depression risk):")
print(f"    {within_500m:,} addresses ({(within_500m/len(addresses))*100:.1f}%)")
print(f"  Beyond 500m (reduced/no protective effect):")
print(f"    {beyond_500m:,} addresses ({(beyond_500m/len(addresses))*100:.1f}%)")

# Custom distance bins for visualization
print(f"\n📏 DISTANCE DISTRIBUTION BY BIN:")
distance_bins = [0, 300, 500, 1000, 1500, 2000, distances.max()]
distance_labels = ['0-300m', '301-500m', '501-1000m', '1001-1500m', '1501-2000m', '>2000m']
addresses['distance_category'] = pd.cut(distances, bins=distance_bins, labels=distance_labels)

distance_counts = addresses['distance_category'].value_counts().sort_index()
for category, count in distance_counts.items():
    pct = (count / len(addresses)) * 100
    print(f"  {category}: {count:,} addresses ({pct:.1f}%)")

# ============================================================================
# STEP 8: VALIDATION CHECKS
# ============================================================================

print("\n" + "="*80)
print("STEP 8: VALIDATION CHECKS")
print("="*80)

# Addresses inside parks
inside_parks = addresses[addresses['distance_to_park_m'] < 1.0]
print(f"\n✓ Addresses inside/touching parks: {len(inside_parks):,}")
if len(inside_parks) > 0:
    print(f"  Min distance: {inside_parks['distance_to_park_m'].min():.2f} m")

# Sample verification
print("\n📋 SAMPLE DISTANCE CHECK (5 random addresses):")
sample_indices = np.random.choice(len(addresses), min(5, len(addresses)), replace=False)
for idx in sample_indices:
    addr = addresses.iloc[idx]
    print(f"  {addr['distance_to_park_m']:.1f}m to park")

# Check for unreasonable distances
max_reasonable = 5000
far_addresses = addresses[addresses['distance_to_park_m'] > max_reasonable]
print(f"\n⚠️  Addresses >5km from nearest park: {len(far_addresses):,}")
if len(far_addresses) > 0:
    print(f"  Max distance: {addresses['distance_to_park_m'].max():.1f} m")

# ============================================================================
# STEP 9: SAVE PROCESSED DATA
# ============================================================================

print("\n" + "="*80)
print("STEP 9: SAVING PROCESSED DATA")
print("="*80)

import os
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Save eligible parks
parks_output = OUTPUT_DIR + 'portland_parks_eligible.geojson'
parks[['geometry', 'area_m2', 'area_hectares', 'NAME' if 'NAME' in parks.columns else 'SITE_NAME']].to_file(
    parks_output, driver='GeoJSON'
)
print(f"✓ Saved eligible parks: {parks_output}")

# Save processed addresses with distances
addresses_output = OUTPUT_DIR + 'portland_addresses_with_distances.geojson'
addresses.to_file(addresses_output, driver='GeoJSON')
print(f"✓ Saved addresses with distances: {addresses_output}")

# Save summary statistics to CSV
summary_stats = {
    'metric': [
        'total_raw_parks',
        'total_eligible_parks',
        'parks_excluded_size',
        'total_raw_addresses',
        'addresses_within_boundaries',
        'final_residential_addresses',
        'mean_distance_m',
        'median_distance_m',
        'within_300m_count',
        'within_300m_percent',
        'within_500m_count',
        'within_500m_percent',
        'beyond_500m_count',
        'beyond_500m_percent'
    ],
    'value': [
        parks_before,
        len(parks),
        parks_excluded,
        addresses_before,
        len(addresses) + nonres_excluded,
        len(addresses),
        distances.mean(),
        np.median(distances),
        within_300m,
        (within_300m/len(addresses))*100,
        within_500m,
        (within_500m/len(addresses))*100,
        beyond_500m,
        (beyond_500m/len(addresses))*100
    ]
}

summary_df = pd.DataFrame(summary_stats)
summary_output = OUTPUT_DIR + 'portland_greenspace_summary_stats.csv'
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
print(f"\n📊 FINAL DATASET SUMMARY:")
print(f"  Eligible parks (≥0.5 ha): {len(parks):,}")
print(f"  Residential addresses: {len(addresses):,}")
print(f"  Mean distance to park: {distances.mean():.1f} m")
print(f"  Addresses within 300m protective buffer: {(within_300m/len(addresses))*100:.1f}%")

print("\n✅ Data ready for methodology implementation:")
print(f"   {addresses_output}")
print(f"   {parks_output}")

print("\n" + "="*80)
