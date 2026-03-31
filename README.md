# Portland Urban Mental Wellbeing Index — Environmental Exposure Preprocessing


A geospatial preprocessing pipeline for quantifying residential exposure to three urban environmental **contextual cues** linked to mental health outcomes: **air quality**, **greenspace access**, and **transit mobility**. Developed as part of a PhD thesis (Chapter 4) implementing published epidemiological thresholds at city scale for Portland, Oregon.

---

## Project Overview

This pipeline processes raw city data into address-level environmental exposure scores for all residential addresses in Portland. Each of the three preprocessing scripts implements a distinct literature-derived methodology, producing outputs that feed into a composite **Urban Mental Wellbeing Index (UMWI, 3–15 scale)**.

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

Implements the Chen et al. (2018) PM₂.₅ z-score standardisation methodology. Raw EPA monitor readings are aggregated to monthly averages, standardised against a Portland city baseline, and then spatially assigned to residential addresses via nearest-monitor distance.

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

### Spatial Operations

All distance calculations use **Oregon State Plane (NAD83)** — `EPSG:6554` — a metric CRS ensuring accuracy in metres. Inputs are reprojected before any spatial operation. Nearest-neighbour queries use `scipy.spatial.cKDTree`; addresses are processed in batches of 10,000 for memory efficiency.

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

## Replication for Other Cities

The pipeline is city-agnostic. Equivalent scripts exist for Manchester (`m_*`) and Chicago (`c_*`). To adapt for a new city:

1. **Air quality:** Provide EPA-format Excel files with `Longitude`, `Latitude`, and a PM₂.₅ column.
2. **Greenspace:** Supply a polygon parks shapefile. The 0.5 ha and 300/500 m thresholds are literature-based and should be retained for cross-city comparability.
3. **Transit:** Supply a point shapefile of stops with a route identifier. Update `infer_transit_type()` for the local agency's route numbering.
4. **CRS:** Replace `EPSG:6554` with an appropriate projected CRS for the target city.
5. **Area constant:** Update `portland_area_km2 = 375.0` in `p_pre_m.py` for stop density calculations.

All threshold constants (`MIN_PARK_SIZE_HECTARES`, `PROTECTIVE_DISTANCE_M`, `EXTENDED_BENEFIT_M`, `CRITICAL_THRESHOLD_M`, `EPA_VALID_RANGE`) are defined at the top of each script.

---

## Citations

Chen, H., Kwong, J. C., Copes, R., Tu, K., Villeneuve, P. J., van Donkelaar, A., Hystad, P., Martin, R. V., Murray, B. J., Jessiman, B., Wilton, A. S., Kopp, A., & Burnett, R. T. (2018). Living near major roads and the incidence of dementia, Parkinson's disease, and multiple sclerosis: A population-based cohort study. *The Lancet*, 389(10070), 718–726.

Gascon, M., Triguero-Mas, M., Martínez, D., Dadvand, P., Rojas-Rueda, D., Plasència, A., & Nieuwenhuijsen, M. J. (2018). Residential green spaces and mortality: A systematic review. *Environment International*, 86, 60–67.

Wang, R., Liu, Y., Xue, D., Yao, Y., Liu, P., & Helbich, M. (2019). Cross-sectional associations between long-term exposure to physical activity-friendly environments and depression among Chinese older adults: The moderating effects of urbanicity. *Health & Place*, 60, 102190.

---

## Author

## Author

**Tzirath Perez Oteiza, PhD**  
Data Science and Smart Cities  
Maynooth University, Ireland

📧 [tzirathperez@outlook.com](mailto:tzirathperez@outlook.com)  
🔗 [LinkedIn](https://www.linkedin.com/in/tzirath-perez/)
