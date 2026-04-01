# Portland Urban Mental Wellbeing Index — Environmental Exposure Preprocessing

A geospatial preprocessing and scoring pipeline for quantifying residential exposure to three urban environmental **contextual cues** linked to mental health outcomes: **air quality**, **greenspace access**, and **transit mobility**. Built to operationalise published epidemiological thresholds at city scale, producing address-level risk scores that aggregate into a composite planning indicator — the **Urban Mental Wellbeing Index (UMWI)** — for use in evidence-based urban health and land-use planning.

---

## Project Overview

This pipeline processes raw city data into address-level environmental exposure scores for all residential addresses in Portland. Each of the three preprocessing scripts implements a distinct literature-derived methodology, producing scored outputs that aggregate into the **Urban Mental Wellbeing Index (UMWI, 3–15 scale)** — a neighbourhood-level indicator designed to identify areas of compounded environmental disadvantage and support targeted planning and policy intervention.

| Contextual Cue | Script | Literature Basis |
|---|---|---|
| Air Quality | `p_pre_aq.py` + `p_aq_method.py` | Chen et al. (2018) — PM₂.₅ z-score standardisation |
| Greenspace | `p_pre_gs.py` | Gascon et al. (2018) — Parks ≥ 0.5 ha within 300–500 m |
| Transit Mobility | `p_pre_m.py` | Wang et al. (2019) — Transit within 850 m walkability threshold |

---

## Repository Structure

```
ComputationalFramework/
├── preproccessing/
│   ├── p_pre_aq.py          # Air quality preprocessing (PM2.5 z-scores)
│   ├── p_pre_gs.py          # Greenspace preprocessing (park distances)
│   └── p_pre_m.py           # Transit mobility preprocessing (stop distances)
├── analysis/
│   └── methodology/
│       └── p_aq_method.py   # Air quality risk scoring & population weighting
└── data/
    └── Portland/
        ├── p_airquality/portland_aq/   # EPA-format Excel files (per monitor)
        ├── p_address/p_address/        # Active_Address_Points.shp
        ├── p_boundaries/               # Neighborhoods_regions.shp
        ├── p_greenspace/p_parks/       # Parks.shp
        ├── p_mobility/                 # tm_stops.shp (TriMet)
        └── p_census/                   # p_population.xlsx
```

---

## Installation

```bash
pip install geopandas pandas numpy scipy matplotlib openpyxl shapely
```

Python 3.8+ required.

---

## Usage

```bash
# Air quality — preprocessing must run before methodology
python preproccessing/p_pre_aq.py
python analysis/methodology/p_aq_method.py

# Greenspace and transit (independent)
python preproccessing/p_pre_gs.py
python preproccessing/p_pre_m.py
```

The greenspace and transit scripts are fully independent. The air quality methodology script (`p_aq_method.py`) depends on outputs from `p_pre_aq.py` and must run second.

---

## Air Quality Preprocessing — Deep Dive (`p_pre_aq.py`)

### Overview

Implements the Chen et al. (2018) PM₂.₅ z-score standardisation methodology. Raw EPA monitor readings are aggregated to monthly averages, standardised against a Portland city baseline, and spatially assigned to residential addresses via nearest-monitor distance. The resulting z-scores feed into a 1–5 risk scoring scheme that is population-weighted to produce a single comparable city-level air quality indicator.

**Input:** EPA-format `.xlsx` files (one per monitoring station) with `Longitude`, `Latitude`, date, and PM₂.₅ columns  
**Output:** Monthly z-scores, city baseline parameters, and addresses linked to their nearest monitor

---

### Processing Pipeline

#### Step 1 — Load Monitor Data

All `.xlsx` files in `data/Portland/p_airquality/portland_aq/` are loaded and concatenated. The second column in each file is normalised to `PM2.5`. Monitor names are derived from filenames. If `State Name` and `County Name` columns are present, data is filtered to Oregon / Multnomah County.

```python
all_files = glob.glob(AQ_DATA_PATH + "/*.xlsx")
df_temp = pd.read_excel(filename, engine='openpyxl')
df_temp.rename(columns={old_col_name: 'PM2.5'}, inplace=True)
```

Date columns are detected by name pattern (`date` / `time`) and parsed from the format `HH:MM MM/DD/YYYY`. The pipeline then filters to `STUDY_YEAR = 2024`.

---

#### Step 2 — Data Validation

Monitor completeness is assessed against days elapsed in 2024 (a leap year, 366 days). Per-station statistics include total records, valid PM₂.₅ count, days of coverage, and completion percentage.

EPA range validation:

```python
EPA_VALID_RANGE = (0, 500)  # μg/m³
valid_range = (df['PM2.5'] >= 0) & (df['PM2.5'] <= 500)
```

Records outside this range are excluded before further processing.

---

#### Step 3 — Monthly Aggregation

Daily readings are grouped by monitor station and calendar month to produce 30-day averages, following the Chen et al. (2018) aggregation window:

```python
monthly_pm25 = df_2024.groupby(
    ['monitor_name', 'Latitude', 'Longitude', 'year', 'month']
)['PM2.5'].mean()
```

Output column: `PM25_monthly` — mean PM₂.₅ concentration per station-month in μg/m³.

---

#### Step 4 — City Baseline Calculation

A Portland-wide baseline (μ_City, σ_City) is calculated from all 2024 monthly averages across all monitors. These parameters define what constitutes "normal" air quality for the city and anchor all downstream z-score thresholds.

```python
mu_city    = monthly_pm25['PM25_monthly'].mean()   # μ_City
sigma_city = monthly_pm25['PM25_monthly'].std()    # σ_City
```

Standard deviation thresholds are printed for reference:

| Threshold | Formula |
|---|---|
| −1 SD | `μ − σ` |
| Mean | `μ` |
| +1 SD (Chen harm threshold) | `μ + σ` |
| +1.5 SD | `μ + 1.5σ` |

---

#### Step 5 — Z-Score Standardisation

Each monthly average is standardised against the city baseline:

```
Z = (PM2.5_monthly − μ_City) / σ_City
```

The resulting distribution should have mean ≈ 0 and std ≈ 1. Z-scores are then categorised into five risk bands:

| Risk Score | Level | Z-Score Range |
|---|---|---|
| 1 | Very Low Risk | Z ≤ −1.0 |
| 2 | Low Risk | −1.0 < Z ≤ 0.0 |
| 3 | Elevated Risk | 0.0 < Z ≤ +1.0 |
| 4 | High Risk | +1.0 < Z ≤ +1.5 (Chen et al. harm threshold) |
| 5 | Very High Risk | Z > +1.5 |

A city-level score ≥ 4.0 is associated with a **+6.67 percentage point increase in severe psychological distress** (Chen et al., 2018).

---

#### Step 6 — Spatial Setup

Monitoring station coordinates are converted from WGS84 to the project CRS:

```python
TARGET_CRS = 'EPSG:6554'   # NAD83(2011) / Oregon State Plane North (metres)

stations_gdf = gpd.GeoDataFrame(
    stations_geo, geometry='geometry', crs='EPSG:4326'
).to_crs(TARGET_CRS)
```

---

#### Step 7 — Address Filtering

Residential addresses are loaded from `Active_Address_Points.shp` (only `ADDRESS_TY` and `geometry` columns to minimise memory). Two-stage filtering is applied:

1. **Spatial** — addresses within the union of Portland neighbourhood polygons (`Neighborhoods_regions.shp`)
2. **Type** — records where `ADDRESS_TY == 'RESIDENTIAL'`

---

#### Step 8 — Assign Addresses to Nearest Monitor

A `cKDTree` is built on monitor coordinates (in EPSG:6554 metres). Each residential address is queried for its nearest monitor in a single vectorised pass:

```python
station_tree = cKDTree(station_coords)
distances, nearest_indices = station_tree.query(addr_coords)

addresses['distance_to_monitor_m'] = distances
addresses['nearest_monitor_name']  = stations_gdf.iloc[nearest_indices]['monitor_name'].values
```

Distance statistics (mean, median, min, max) and the per-monitor address assignment split are printed for verification.

---

#### Step 9 — Save Outputs

| File | Format | Contents |
|---|---|---|
| `portland_monthly_pm25_zscores.csv` | CSV | Monthly PM₂.₅ averages, z-scores per monitor-month |
| `portland_city_baseline.csv` | CSV | μ_City and σ_City parameters |
| `portland_monitoring_stations.geojson` | GeoJSON | Station point locations in EPSG:6554 |
| `portland_addresses_with_monitors.geojson` | GeoJSON | Residential addresses with nearest monitor and distance |
| `portland_airquality_summary_stats.csv` | CSV | Full summary statistics table |

All files written to `preproccessing/processed/p_aq_processed/`.

---

### Air Quality Output Visualisations

Spatial and statistical outputs generated from the processed data:

**Neighbourhood-level air quality risk map**

![Air Quality Risk Map](results/methodology_output/portland/p_airquality_results/p_aq_method_results/fig1_portland_aq_map.png)

**Monthly risk score distribution (2024)**

![Monthly Risk Distribution](results/methodology_output/portland/p_airquality_results/p_aq_method_results/fig2_monthly_risk_distribution.png)

**Annual address-level score distribution**

![Annual Score Distribution](results/methodology_output/portland/p_airquality_results/p_aq_method_results/fig3_annual_score_distribution.png)

**Monthly PM₂.₅ z-score timeline by monitor**

![Z-Score Timeline](results/methodology_output/portland/p_airquality_results/p_aq_method_results/fig4_zscore_timeline.png)

**Address-level scores with monitor locations**

![Spatial Detail](results/methodology_output/portland/p_airquality_results/p_aq_method_results/fig5_spatial_detail_monitors_addresses.png)

---

## Greenspace Preprocessing (`p_pre_gs.py`)

Implements Gascon et al. (2018). Parks are filtered to ≥ 0.5 ha (`MIN_PARK_SIZE_HECTARES = 0.5`; 5,000 m²). Distance is measured from each residential address to the **nearest eligible park boundary** (not centroid) using `cKDTree` over boundary vertex coordinates, processed in batches of 10,000 addresses.

**Distance thresholds:**

| Distance | Effect | Effect Size |
|---|---|---|
| ≤ 300 m (`PROTECTIVE_DISTANCE_M`) | Strong protective effect | OR = 0.18 — 82% lower depression risk |
| ≤ 500 m (`EXTENDED_BENEFIT_M`) | Moderate protective effect | OR ≈ 0.84 — 16% lower depression risk |
| > 500 m | Reduced / no protective effect | — |

**Outputs:**

| File | Description |
|---|---|
| `portland_parks_eligible.geojson` | Parks filtered to ≥ 0.5 ha |
| `portland_addresses_with_distances.geojson` | Addresses with distance to nearest eligible park boundary |
| `portland_greenspace_summary_stats.csv` | Counts at 300 m and 500 m thresholds |

---

## Transit Mobility Preprocessing (`p_pre_m.py`)

Implements Wang et al. (2019). Distance from each residential address to the nearest TriMet stop is calculated using `cKDTree`. Addresses beyond 850 m are flagged as having **elevated depression risk**.

Transit types are inferred from TriMet route numbering:

- **MAX Light Rail:** routes 90, 100, 190, 200, 290
- **Portland Streetcar:** NS, Loop
- **WES Commuter Rail:** `WES`-prefixed routes
- **Bus:** all remaining numeric routes

**Distance thresholds:**

| Distance | Classification |
|---|---|
| ≤ 400 m (`OPTIMAL_THRESHOLD_M`) | Strong accessibility — 5-min walk |
| ≤ 850 m (`CRITICAL_THRESHOLD_M`) | Acceptable — 10-min walk at 5 km/h |
| > 850 m | Elevated depression risk (Wang et al., 2019) |

**Outputs:**

| File | Description |
|---|---|
| `portland_transit_stops_combined.geojson` | All TriMet stops with type classification |
| `portland_{type}_stops.geojson` | Stops by type (bus / rail / streetcar) |
| `portland_addresses_with_transit_distances.geojson` | Addresses with distance and nearest stop type |
| `portland_transit_summary_stats.csv` | Coverage at 400 m and 850 m thresholds |

---

## Technical Approach

### cKDTree Nearest-Neighbour Indexing

The most computationally significant decision across all three scripts is replacing brute-force distance loops with a **k-d tree spatial index** (`scipy.spatial.cKDTree`). A naïve approach — computing the Euclidean distance from every address to every park boundary vertex or transit stop — would scale as O(n × m), making it infeasible for a city-wide dataset. The k-d tree reduces nearest-neighbour queries to **O(n log m)**, partitioning the coordinate space into a binary search tree that avoids redundant comparisons.

```python
# Build once, query for all addresses in a single pass
park_tree = cKDTree(park_boundary_coords)
distances, nearest_indices = park_tree.query(addr_coords)
```

The tree is built once on the feature set (park vertices, transit stops, or monitor locations) and then queried for the entire residential address dataset in a vectorised call — no Python loop over addresses.

For large inputs the query is batched in **chunks of 10,000 addresses** to keep peak memory bounded, with the tree itself held in memory throughout:

```python
for i in range(0, len(addr_coords), 10000):
    batch_distances, batch_indices = park_tree.query(addr_coords[i:i+10000])
```

---

### Boundary-Vertex Distance for Greenspace

Transit and air quality use point geometries (stop locations, monitor coordinates), so a standard nearest-point query is exact. Greenspace requires a meaningfully different approach: **distance to the nearest park edge**, not the centroid.

Measuring from an address to a park centroid would overestimate the true walking distance for large, irregularly shaped parks. Instead, `p_pre_gs.py` decomposes every eligible park polygon into its exterior boundary vertices and builds the k-d tree over those vertices:

```python
for idx, park in parks.iterrows():
    if park.geometry.geom_type == 'Polygon':
        boundary_coords = list(park.geometry.exterior.coords)
    elif park.geometry.geom_type == 'MultiPolygon':
        for polygon in park.geometry.geoms:
            boundary_coords = list(polygon.exterior.coords)
    park_boundary_coords.extend(boundary_coords)
    park_indices.extend([idx] * len(boundary_coords))
```

Each boundary point retains its parent park index, so after querying the nearest vertex the result maps directly back to the park it belongs to. A **critical implementation detail** is that the park GeoDataFrame index is reset to contiguous integers after the 0.5 ha filter — without this, the index-based lookup would silently return wrong parks:

```python
parks = parks[parks['area_hectares'] >= 0.5].copy()
parks = parks.reset_index(drop=True)   # ensures park_indices[i] == parks.iloc[i]
```

---

### Population-Weighted City Score (Air Quality Methodology)

The final air quality score is not a simple average — it is a **population-weighted mean** over neighbourhood-level risk scores, implemented via a spatial join followed by a weighted aggregation:

```python
# Spatial join: assign each address to a neighbourhood
addresses_with_nbhd = gpd.sjoin(addresses, neighborhoods, how='left', predicate='within')

# Aggregate to neighbourhood level
nbhd_stats['weighted_score'] = nbhd_stats['mean_aq_score'] * nbhd_stats['population']
city_aq_score = nbhd_stats['weighted_score'].sum() / nbhd_stats['population'].sum()
```

This ensures that a neighbourhood housing 50,000 residents contributes proportionally more to the city score than one housing 2,000, reflecting the actual population distribution of exposure rather than treating all neighbourhoods as equal units.

---

### Coordinate Reference System

All spatial operations use **Oregon State Plane (NAD83)** — `EPSG:6554` — a metric CRS ensuring distances are in metres without projection distortion. Every input dataset is reprojected to this CRS before any distance calculation or spatial join.

### Address Filtering

Applied consistently across all three scripts:
1. **Spatial filter** — within Portland neighbourhood boundaries
2. **Type filter** — `ADDRESS_TY == 'RESIDENTIAL'`

### Validation

- PM₂.₅ values outside `(0, 500) μg/m³` excluded
- Monitor completeness reported (days covered / days elapsed in 2024)
- Park boundary distances < 1.0 m flagged (address inside park)
- Addresses > 5 km from nearest feature reported as outliers
- Intermediate statistics printed at every stage for audit

---

## Data Sources

| Dataset | Source | File |
|---|---|---|
| PM₂.₅ monitor readings | EPA / local monitoring network | `.xlsx` files in `portland_aq/` |
| Residential address points | City of Portland Bureau of Development Services | `Active_Address_Points.shp` |
| Neighbourhood boundaries | City of Portland | `Neighborhoods_regions.shp` |
| Parks | Portland Parks & Recreation | `Parks.shp` |
| Transit stops | TriMet GTFS | `tm_stops.shp` |
| Neighbourhood population | US Census Bureau | `p_population.xlsx` |

---

## Scalability and Replication

The pipeline is city-agnostic by design. Equivalent scripts covering **Manchester** (`m_*`) and **Chicago** (`c_*`) are structured identically, enabling cross-city comparison of UMWI scores on a standardised 3–15 scale. All city-specific constants are isolated to the configuration block at the top of each script, with no hard-coded values in the processing logic.

To adapt for a new city:

1. **Air quality:** Provide EPA-format Excel files with `Longitude`, `Latitude`, and a PM₂.₅ column.
2. **Greenspace:** Supply a polygon parks shapefile. The 0.5 ha and 300/500 m thresholds are literature-based and should be retained for cross-city comparability.
3. **Transit:** Supply a point shapefile of stops with a route identifier. Update `infer_transit_type()` for the local agency's route numbering.
4. **CRS:** Replace `EPSG:6554` with an appropriate projected CRS for the target city.
5. **Area constant:** Update `portland_area_km2 = 375.0` in `p_pre_m.py` for stop density calculations.

All threshold constants (`MIN_PARK_SIZE_HECTARES`, `PROTECTIVE_DISTANCE_M`, `EXTENDED_BENEFIT_M`, `CRITICAL_THRESHOLD_M`, `EPA_VALID_RANGE`) are defined at the top of each script.

---

## Planning and Policy Applications

The UMWI pipeline is designed to produce outputs directly usable in planning workflows:

- **Neighbourhood ranking** — population-weighted scores identify areas of compounded environmental disadvantage across all three cues simultaneously
- **Threshold-based targeting** — the 300/500 m greenspace buffers and 850 m transit threshold map directly onto planning standards for park catchment and walkability zoning
- **Equity analysis** — by operating at the residential address level and aggregating via census population weights, the index can be cross-tabulated against socioeconomic deprivation data to identify environmental justice gaps
- **Cross-city benchmarking** — consistent methodology across Portland, Manchester, and Chicago enables comparative analysis of how urban form affects mental health exposure profiles

---

## Citations

Chen, H., Kwong, J. C., Copes, R., Tu, K., Villeneuve, P. J., van Donkelaar, A., Hystad, P., Martin, R. V., Murray, B. J., Jessiman, B., Wilton, A. S., Kopp, A., & Burnett, R. T. (2018). Living near major roads and the incidence of dementia, Parkinson's disease, and multiple sclerosis: A population-based cohort study. *The Lancet*, 389(10070), 718–726.

Gascon, M., Triguero-Mas, M., Martínez, D., Dadvand, P., Rojas-Rueda, D., Plasència, A., & Nieuwenhuijsen, M. J. (2018). Residential green spaces and mortality: A systematic review. *Environment International*, 86, 60–67.

Wang, R., Liu, Y., Xue, D., Yao, Y., Liu, P., & Helbich, M. (2019). Cross-sectional associations between long-term exposure to physical activity-friendly environments and depression among Chinese older adults: The moderating effects of urbanicity. *Health & Place*, 60, 102190.

---

## Author

**Tzirath Perez Oteiza, PhD**  
Data Science and Smart Cities  
Maynooth University, Ireland

📧 tzirathperez@outlook.com  
🔗 [LinkedIn](https://www.linkedin.com/in/tzirath-perez/)

*Research interests: urban health analytics, geospatial data pipelines, environmental exposure modelling, evidence-based planning*
