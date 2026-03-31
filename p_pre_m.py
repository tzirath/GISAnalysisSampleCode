#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Portland Mobility/Transit Accessibility Preprocessing
Prepares data for Chapter 4 Methodology Implementation
Includes comprehensive descriptive statistics for thesis

Based on Wang et al. (2019): Transit within 850m (10-minute walk)

Portland-specific adaptations:
- TriMet transit system (bus, MAX light rail, streetcar)
- Neighborhood boundaries
- ADDRESS_TYPE column for residential filtering
- Oregon State Plane coordinate system

@author: tzirath
"""

import geopandas as gpd
import pandas as pd
import numpy as np
from scipy.spatial import cKDTree
import time
import warnings
warnings.filterwarnings('ignore')

print("="*80)
print("PORTLAND MOBILITY/TRANSIT ACCESSIBILITY PREPROCESSING")
print("Chapter 4 Methodology: Wang et al. (2019) Thresholds")
print("TriMet Transit Network")
print("="*80)

# ============================================================================
# CONFIGURATION
# ============================================================================

BASE_DIR = 'PhD/ComputationalFramework/'
DATA_DIR = BASE_DIR + 'data/Portland/'
OUTPUT_DIR = BASE_DIR + 'preproccessing/processed/p_m_processed/'

# Input files
TRANSIT_STOPS_PATH = DATA_DIR + '/p_mobility/tm_stops.shp'
ADDRESSES_PATH = DATA_DIR + '/p_address/p_address/Active_Address_Points.shp'
NEIGHBORHOODS_PATH = DATA_DIR + 'p_boundaries/Neighborhoods_regions/Neighborhoods_regions.shp'

# Wang et al. (2019) threshold from Chapter 4
CRITICAL_THRESHOLD_M = 850  # 10-minute walk at 5 km/h
OPTIMAL_THRESHOLD_M = 400   # 5-minute walk

TARGET_CRS = 'EPSG:6554'  # NAD83(2011) / Oregon North

import os
os.makedirs(OUTPUT_DIR, exist_ok=True)

start_time = time.time()

# ============================================================================
# STEP 1: LOAD RAW DATA
# ============================================================================

print("\n" + "="*80)
print("STEP 1: LOADING RAW DATA")
print("="*80)

print("\nLoading transit stops...")
transit_stops_raw = gpd.read_file(TRANSIT_STOPS_PATH)
print(f"✓ Transit stops loaded: {len(transit_stops_raw):,}")
print(f"  Columns: {list(transit_stops_raw.columns)}")

print("\nLoading addresses (essential columns only)...")
essential_columns = ['ADDRESS_TY', 'geometry']
addresses_raw = gpd.read_file(ADDRESSES_PATH, columns=essential_columns)
print(f"✓ Addresses loaded: {len(addresses_raw):,}")

print("\nLoading neighborhood boundaries...")
neighborhoods = gpd.read_file(NEIGHBORHOODS_PATH)
print(f"✓ Neighborhoods loaded: {len(neighborhoods)}")

# ============================================================================
# STEP 2: IDENTIFY TRANSIT TYPES (PORTLAND-SPECIFIC)
# ============================================================================

print("\n" + "="*80)
print("STEP 2: IDENTIFYING TRANSIT TYPES IN TRIMET DATA")
print("="*80)

# Reproject to target CRS for distance calculations
if transit_stops_raw.crs != TARGET_CRS:
    transit_stops_raw = transit_stops_raw.to_crs(TARGET_CRS)

# Try to identify transit type column
type_col = None
for col in ['type', 'stop_type', 'mode', 'route_type', 'rte_type', 'TYPE', 'STOP_TYPE']:
    if col in transit_stops_raw.columns:
        type_col = col
        print(f"✓ Found transit type column: '{col}'")
        break

# If no direct type column, try to infer from route information
if type_col is None:
    print("⚠️  No direct transit type column found")
    print("Attempting to infer from route data...")
    
    # Check for route-related columns
    route_col = None
    for col in ['route_id', 'rte', 'route', 'line_id', 'line']:
        if col in transit_stops_raw.columns:
            route_col = col
            print(f"✓ Found route column: '{col}'")
            break
    
    if route_col:
        # TriMet route numbering:
        # Bus: numeric (1-299)
        # MAX Light Rail: 90, 100, 190, 200, 290
        # Portland Streetcar: NS (North-South), Loop
        # WES Commuter Rail: starts with letter
        
        def infer_transit_type(route):
            route_str = str(route).upper()
            # MAX lines
            if route_str in ['90', '100', '190', '200', '290']:
                return 'Rail'
            # Streetcar
            elif 'NS' in route_str or 'LOOP' in route_str or 'STREETCAR' in route_str:
                return 'Streetcar'
            # WES
            elif route_str.startswith('WES') or route_str == 'WES':
                return 'Rail'
            # Everything else is bus
            else:
                return 'Bus'
        
        transit_stops_raw['transit_type'] = transit_stops_raw[route_col].apply(infer_transit_type)
        print("✓ Inferred transit types from route data")
    else:
        # Last resort: all stops are Bus
        print("⚠️  Cannot distinguish transit types, treating all as 'Bus'")
        transit_stops_raw['transit_type'] = 'Bus'
else:
    # Use the existing type column
    transit_stops_raw['transit_type'] = transit_stops_raw[type_col]

# Standardize transit types
print("\n📊 TRANSIT TYPE DISTRIBUTION (before standardization):")
print(transit_stops_raw['transit_type'].value_counts())

# Map to standard categories
type_mapping = {
    'bus': 'Bus',
    'BUS': 'Bus',
    'rail': 'Rail',
    'RAIL': 'Rail',
    'light rail': 'Rail',
    'MAX': 'Rail',
    'streetcar': 'Streetcar',
    'STREETCAR': 'Streetcar',
}

if transit_stops_raw['transit_type'].dtype == 'object':
    transit_stops_raw['transit_type'] = transit_stops_raw['transit_type'].str.strip().map(
        lambda x: type_mapping.get(x, x) if pd.notna(x) else 'Bus'
    )

print("\n📊 TRANSIT TYPE DISTRIBUTION (standardized):")
type_counts = transit_stops_raw['transit_type'].value_counts()
for transit_type, count in type_counts.items():
    pct = (count / len(transit_stops_raw)) * 100
    print(f"  {transit_type}: {count:,} ({pct:.1f}%)")

# Create separate datasets by type
transit_types = transit_stops_raw['transit_type'].unique()
stops_by_type = {}
for ttype in transit_types:
    stops_by_type[ttype] = transit_stops_raw[transit_stops_raw['transit_type'] == ttype].copy()
    print(f"✓ Created {ttype} stops dataset: {len(stops_by_type[ttype]):,} stops")

# ============================================================================
# STEP 3: TRANSIT NETWORK DESCRIPTIVE STATISTICS
# ============================================================================

print("\n" + "="*80)
print("STEP 3: TRANSIT NETWORK DESCRIPTIVE STATISTICS")
print("="*80)

print("\n📊 TRANSIT NETWORK STATISTICS:")
print(f"Total transit stops: {len(transit_stops_raw):,}")
for ttype in sorted(transit_types):
    count = len(stops_by_type[ttype])
    pct = (count / len(transit_stops_raw)) * 100
    print(f"  {ttype} stops: {count:,} ({pct:.1f}%)")

# Calculate transit stop density
portland_area_km2 = 375.0
total_stops_per_km2 = len(transit_stops_raw) / portland_area_km2
print(f"\nTransit density:")
print(f"  Total: {total_stops_per_km2:.2f} stops per km²")
for ttype in sorted(transit_types):
    count = len(stops_by_type[ttype])
    density = count / portland_area_km2
    print(f"  {ttype}: {density:.2f} stops per km²")

# ============================================================================
# STEP 4: ADDRESS FILTERING (SPATIAL + RESIDENTIAL)
# ============================================================================

print("\n" + "="*80)
print("STEP 4: ADDRESS FILTERING")
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
    print(f"  Exclusion rate: {(nonres_excluded/before_res_filter)*100:.1f}%")
else:
    print("⚠️  ADDRESS_TY column not found, using all addresses")

# ============================================================================
# STEP 5: DISTANCE CALCULATION TO NEAREST TRANSIT STOP
# ============================================================================

print("\n" + "="*80)
print("STEP 5: DISTANCE CALCULATIONS TO NEAREST TRANSIT STOP")
print("="*80)

print("\nExtracting address coordinates...")
addr_coords = np.array([[point.x, point.y] for point in addresses.geometry])
print(f"✓ Coordinates extracted: {len(addr_coords):,} addresses")

print("\nExtracting transit stop coordinates...")
stop_coords = np.array([[point.x, point.y] for point in transit_stops_raw.geometry])
print(f"✓ Stop coordinates extracted: {len(stop_coords):,} transit stops")

print("\nBuilding spatial index...")
stop_tree = cKDTree(stop_coords)

print("Computing distances (batch processing)...")
batch_size = 10000
distances = []
nearest_stop_indices = []

for i in range(0, len(addr_coords), batch_size):
    batch_end = min(i + batch_size, len(addr_coords))
    batch_coords = addr_coords[i:batch_end]
    
    batch_distances, batch_nearest_indices = stop_tree.query(batch_coords)
    
    distances.extend(batch_distances)
    nearest_stop_indices.extend(batch_nearest_indices)
    
    if (i // batch_size + 1) % 10 == 0:
        print(f"  Processed {batch_end:,} / {len(addr_coords):,} addresses")

distances = np.array(distances)
nearest_stops = np.array(nearest_stop_indices)

# Add to dataframe
addresses['distance_to_transit_m'] = distances
addresses['nearest_stop_idx'] = nearest_stops
addresses['nearest_stop_type'] = transit_stops_raw['transit_type'].iloc[nearest_stops].values

# Add stop names if available
if 'stop_name' in transit_stops_raw.columns:
    addresses['nearest_stop_name'] = transit_stops_raw['stop_name'].iloc[nearest_stops].values

print(f"\n✓ Distance calculations complete!")

# Analyze nearest stop type distribution
print("\n📊 NEAREST STOP TYPE DISTRIBUTION:")
stop_type_counts = addresses['nearest_stop_type'].value_counts()
for stop_type, count in stop_type_counts.items():
    pct = (count / len(addresses)) * 100
    print(f"  Nearest to {stop_type}: {count:,} addresses ({pct:.1f}%)")

# ============================================================================
# STEP 6: DISTANCE DESCRIPTIVE STATISTICS
# ============================================================================

print("\n" + "="*80)
print("STEP 6: DISTANCE STATISTICS (FOR CHAPTER 5 RESULTS)")
print("="*80)

print("\n📊 DISTANCE DISTRIBUTION (ALL TRANSIT):")
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

# Literature-based thresholds from Wang et al. (2019)
print(f"\n🔬 WANG ET AL. (2019) THRESHOLD ANALYSIS:")
within_400m = (distances <= OPTIMAL_THRESHOLD_M).sum()
within_850m = (distances <= CRITICAL_THRESHOLD_M).sum()
beyond_850m = (distances > CRITICAL_THRESHOLD_M).sum()

print(f"  Within 400m (strong accessibility, 5-min walk):")
print(f"    {within_400m:,} addresses ({(within_400m/len(addresses))*100:.1f}%)")
print(f"  Within 850m (acceptable accessibility, 10-min walk):")
print(f"    {within_850m:,} addresses ({(within_850m/len(addresses))*100:.1f}%)")
print(f"  Beyond 850m (elevated depression risk - Wang et al.):")
print(f"    {beyond_850m:,} addresses ({(beyond_850m/len(addresses))*100:.1f}%)")

# Distance distribution by nearest stop type
print(f"\n📊 DISTANCE BY NEAREST STOP TYPE:")
for stop_type in sorted(transit_types):
    type_addresses = addresses[addresses['nearest_stop_type'] == stop_type]
    if len(type_addresses) > 0:
        type_distances = type_addresses['distance_to_transit_m']
        print(f"\n  Nearest to {stop_type} stops ({len(type_addresses):,} addresses):")
        print(f"    Mean: {type_distances.mean():.1f} m")
        print(f"    Median: {type_distances.median():.1f} m")
        print(f"    Within 400m: {(type_distances <= 400).sum():,} ({(type_distances <= 400).sum()/len(type_addresses)*100:.1f}%)")
        print(f"    Within 850m: {(type_distances <= 850).sum():,} ({(type_distances <= 850).sum()/len(type_addresses)*100:.1f}%)")

# Custom distance bins for visualization
print(f"\n🔍 DISTANCE DISTRIBUTION BY BIN:")
distance_bins = [0, 400, 850, 1000, 1500, 2000, distances.max()]
distance_labels = ['0-400m', '401-850m', '851-1000m', '1001-1500m', '1501-2000m', '>2000m']
addresses['distance_category'] = pd.cut(distances, bins=distance_bins, labels=distance_labels)

distance_counts = addresses['distance_category'].value_counts().sort_index()
for category, count in distance_counts.items():
    pct = (count / len(addresses)) * 100
    print(f"  {category}: {count:,} addresses ({pct:.1f}%)")

# ============================================================================
# STEP 7: VALIDATION CHECKS
# ============================================================================

print("\n" + "="*80)
print("STEP 7: VALIDATION CHECKS")
print("="*80)

# Addresses very close to stops
at_stops = addresses[addresses['distance_to_transit_m'] < 10.0]
print(f"\n✓ Addresses at/very near stops (<10m): {len(at_stops):,}")
if len(at_stops) > 0:
    print(f"  Min distance: {at_stops['distance_to_transit_m'].min():.2f} m")
    at_stops_by_type = at_stops['nearest_stop_type'].value_counts()
    for stop_type, count in at_stops_by_type.items():
        print(f"  Near {stop_type}: {count:,}")

# Sample verification
print("\n📋 SAMPLE DISTANCE CHECK (5 random addresses):")
sample_indices = np.random.choice(len(addresses), min(5, len(addresses)), replace=False)
for idx in sample_indices:
    addr = addresses.iloc[idx]
    print(f"  {addr['distance_to_transit_m']:.1f}m to nearest {addr['nearest_stop_type']} stop")

# Check for very far addresses
max_reasonable = 5000
far_addresses = addresses[addresses['distance_to_transit_m'] > max_reasonable]
print(f"\n⚠️  Addresses >5km from nearest stop: {len(far_addresses):,}")
if len(far_addresses) > 0:
    print(f"  Max distance: {addresses['distance_to_transit_m'].max():.1f} m")
    print(f"  These may be in rural/edge areas with no transit service")

# Transit coverage analysis
print(f"\n📊 TRANSIT SERVICE COVERAGE:")
coverage_thresholds = [400, 850, 1000, 1500]
for threshold in coverage_thresholds:
    covered = (distances <= threshold).sum()
    pct = (covered / len(addresses)) * 100
    print(f"  {threshold}m coverage: {covered:,} addresses ({pct:.1f}%)")

# ============================================================================
# STEP 8: SAVE PROCESSED DATA
# ============================================================================

print("\n" + "="*80)
print("STEP 8: SAVING PROCESSED DATA")
print("="*80)

# Save combined transit stops
stops_output = OUTPUT_DIR + 'portland_transit_stops_combined.geojson'
transit_stops_raw.to_file(stops_output, driver='GeoJSON')
print(f"✓ Saved combined transit stops: {stops_output}")

# Save separate transit type files
for ttype, stops_data in stops_by_type.items():
    type_output = OUTPUT_DIR + f'portland_{ttype.lower()}_stops.geojson'
    stops_data.to_file(type_output, driver='GeoJSON')
    print(f"✓ Saved {ttype} stops: {type_output}")

# Save processed addresses with distances
addresses_output = OUTPUT_DIR + 'portland_addresses_with_transit_distances.geojson'
addresses.to_file(addresses_output, driver='GeoJSON')
print(f"✓ Saved addresses with distances: {addresses_output}")

# Save summary statistics to CSV
summary_metrics = [
    'total_transit_stops',
    'total_stops_per_km2',
    'total_addresses',
    'final_residential_addresses',
    'mean_distance_m',
    'median_distance_m',
    'within_400m_count',
    'within_400m_percent',
    'within_850m_count',
    'within_850m_percent',
    'beyond_850m_count',
    'beyond_850m_percent'
]

summary_values = [
    len(transit_stops_raw),
    total_stops_per_km2,
    addresses_before,
    len(addresses),
    distances.mean(),
    np.median(distances),
    within_400m,
    (within_400m/len(addresses))*100,
    within_850m,
    (within_850m/len(addresses))*100,
    beyond_850m,
    (beyond_850m/len(addresses))*100
]

# Add metrics for each transit type
for ttype in sorted(transit_types):
    summary_metrics.extend([
        f'{ttype.lower()}_stops',
        f'{ttype.lower()}_stops_per_km2',
        f'nearest_to_{ttype.lower()}_count',
        f'nearest_to_{ttype.lower()}_percent'
    ])
    
    type_count = len(stops_by_type[ttype])
    type_density = type_count / portland_area_km2
    nearest_count = stop_type_counts.get(ttype, 0)
    nearest_pct = (nearest_count / len(addresses)) * 100 if len(addresses) > 0 else 0
    
    summary_values.extend([
        type_count,
        type_density,
        nearest_count,
        nearest_pct
    ])

summary_stats = {
    'metric': summary_metrics,
    'value': summary_values
}

summary_df = pd.DataFrame(summary_stats)
summary_output = OUTPUT_DIR + 'portland_transit_summary_stats.csv'
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
print(f"  Total transit stops: {len(transit_stops_raw):,}")
for ttype in sorted(transit_types):
    print(f"    {ttype}: {len(stops_by_type[ttype]):,}")
print(f"  Residential addresses: {len(addresses):,}")
print(f"  Mean distance to transit: {distances.mean():.1f} m")
print(f"  Addresses within 850m (Wang et al. threshold): {(within_850m/len(addresses))*100:.1f}%")

print("\n✅ Data ready for methodology implementation:")
print(f"   {addresses_output}")
print(f"   {stops_output}")

print("\n🔑 PORTLAND-SPECIFIC ADAPTATIONS:")
print("  • TriMet transit system with type classification")
print("  • ADDRESS_TYPE column for residential filtering")
print("  • Neighborhood boundaries")
print("  • Oregon State Plane CRS (EPSG:6554)")
print("  • Same detailed statistics as Manchester preprocessing")

print("\n" + "="*80)
