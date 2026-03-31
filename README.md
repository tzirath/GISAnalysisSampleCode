# Portland Urban Mental Wellbeing Index — Environmental Exposure Preprocessing

A geospatial preprocessing and methodology pipeline for quantifying residential exposure to three urban environmental **contextual cues** linked to mental health outcomes: **air quality**, **greenspace access**, and **transit mobility**. Developed as part of a PhD thesis (Chapter 4) implementing published epidemiological thresholds at city scale for Portland, Oregon.

---
## Key Features

- **Scale**: 815,000+ residential addresses processed
- **Data Integration**: 30+ heterogeneous datasets (EPA, municipal GIS, Census, TriMet)
- **Quality Control**: 94-100% temporal data completeness achieved
- **Spatial Precision**: cKDTree indexing with Oregon State Plane (EPSG:6554) for accurate metric distances
- **Reproducible**: Modular design enabling replication across cities (Chicago, Manchester implementations included)
  
## Project Overview

This pipeline computes address-level environmental exposure scores for all residential addresses in Portland using literature-derived thresholds. Each script processes raw city data into a scored, population-weighted **contextual cue** that feeds into a composite Urban Mental Wellbeing Index (UMWI, 3–15 scale).

The three contextual cues operationalise findings from:

- **Air Quality** — Chen et al. (2018): PM₂.₅ z-score standardisation relative to a city baseline
- **Greenspace** — Gascon et al. (2018): proximity to parks ≥ 0.5 ha within 300–500 m
- **Transit Mobility** — Wang et al. (2019): distance to public transit within an 850 m walkability threshold

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
├── data/
│   └── Portland/
│       ├── p_airquality/portland_aq/   # EPA-format Excel files (per monitor)
│       ├── p_address/p_address/        # Active_Address_Points.shp
│       ├── p_boundaries/               # Neighborhoods_regions.shp
│       ├── p_greenspace/p_parks/       # Parks.shp
│       ├── p_mobility/                 # tm_stops.shp (TriMet)
│       └── p_census/                   # p_population.xlsx
└── results/
    └── methodology_output/portland/
        └── p_airquality_results/
            └── p_aq_method_results/    # Output files and figures
```

---

## Methodology

### 1. Air Quality — Chen et al. (2018)

Monthly PM₂.₅ readings from EPA-format Excel files are aggregated per monitoring station, then standardised against a Portland-wide city baseline (μ_City, σ_City). Each month receives a risk score on a 1–5 scale based on its z-score (Table 4.4). Annual address scores are averaged across 12 months and aggregated to a population-weighted city score.

**Z-score formula:**

```
Z = (PM2.5_monthly − μ_City) / σ_City
```

**Risk score thresholds (Table 4.4):**

| Risk Score | Level | Z-Score Range |
|---|---|---|
| 1 | Very Low Risk | Z ≤ −1.0 |
| 2 | Low Risk | −1.0 < Z ≤ 0.0 |
| 3 | Elevated Risk | 0.0 < Z ≤ +1.0 |
| 4 | High Risk | +1.0 < Z ≤ +1.5 (Chen et al. harm threshold) |
| 5 | Very High Risk | Z > +1.5 |

**City-level population-weighted score:**

```
City Score = Σ(Risk_Score_j × Population_j) / Σ(Population_j)
```

A city score ≥ 4.0 corresponds to the Chen et al. (2018) +1 SD harm threshold and is associated with a **+6.67 percentage point increase in severe psychological distress**.

**Quality control:** Values outside `EPA_VALID_RANGE = (0, 500) μg/m³` are excluded.

---

### 2. Greenspace — Gascon et al. (2018)

Parks are filtered to ≥ 0.5 ha (`MIN_PARK_SIZE_HECTARES = 0.5`; 5,000 m²) based on Gascon et al.'s finding that only parks of this size produce measurable mental health benefits. Distance is calculated from each residential address to the **nearest eligible park boundary** (not centroid) using a cKDTree spatial index.

**Distance thresholds:**

| Distance | Effect | Effect Size |
|---|---|---|
| ≤ 300 m (`PROTECTIVE_DISTANCE_M`) | Strong protective effect | OR = 0.18 — 82% lower depression risk |
| ≤ 500 m (`EXTENDED_BENEFIT_M`) | Moderate protective effect | OR ≈ 0.84 — 16% lower depression risk |
| > 500 m | Reduced / no protective effect | — |

---

### 3. Transit Mobility — Wang et al. (2019)

Distance from each residential address to the nearest TriMet transit stop (bus, MAX light rail, streetcar) is calculated. Addresses beyond the critical walkability threshold are flagged as having **elevated depression risk** per Wang et al.

**Distance thresholds:**

| Distance | Classification |
|---|---|
| ≤ 400 m (`OPTIMAL_THRESHOLD_M`) | Strong accessibility — 5-minute walk |
| ≤ 850 m (`CRITICAL_THRESHOLD_M`) | Acceptable accessibility — 10-minute walk at 5 km/h |
| > 850 m | Elevated depression risk (Wang et al., 2019) |

Portland transit classification uses TriMet route numbering to distinguish stop types:

- **MAX Light Rail (Rail):** routes 90, 100, 190, 200, 290
- **Portland Streetcar:** NS (North-South), Loop
- **WES Commuter Rail:** routes prefixed `WES`
- **Bus:** all remaining numeric routes

---

## Technical Approach

### Coordinate Reference System

All spatial operations use **Oregon State Plane (NAD83)** — `TARGET_CRS = 'EPSG:6554'` — a metric CRS ensuring accurate distance calculations in metres. All input datasets are reprojected to this CRS before processing.

### Spatial Indexing

Distance calculations for large address datasets use **`scipy.spatial.cKDTree`** for efficient nearest-neighbour queries. Greenspace distances are measured to **park boundary vertices** (not centroids) for spatial accuracy. Transit and air quality distances are measured to point geometries (stop and monitor locations respectively).

Addresses are processed in **batches of 10,000** to manage memory.

### Address Filtering

Residential filtering is applied in two stages:
1. **Spatial filter** — addresses falling within Portland neighbourhood boundaries (`Neighborhoods_regions.shp`)
2. **Type filter** — records where `ADDRESS_TY == 'RESIDENTIAL'`

### Quality Control

- PM₂.₅ readings outside `(0, 500) μg/m³` are excluded prior to aggregation
- Monitor data completeness is reported per station (days covered / days elapsed)
- Addresses inside or touching park boundaries (`distance < 1.0 m`) are flagged
- Addresses > 5 km from the nearest feature are reported as potential outliers
- All intermediate statistics are printed for audit and reproducibility

---

## Installation

### Prerequisites

- Python 3.8+
- The following libraries:

```bash
pip install geopandas pandas numpy scipy matplotlib openpyxl shapely
```

### Clone the Repository

```bash
git clone <your-repo-url>
cd ComputationalFramework
```

---

## Usage

Scripts must be run in order within each cue domain. Preprocessing outputs are consumed by the methodology script.

### Air Quality

```bash
# Step 1: Preprocess PM2.5 monitor data
python preproccessing/p_pre_aq.py

# Step 2: Compute risk scores and population-weighted city score
python analysis/methodology/p_aq_method.py
```

### Greenspace

```bash
python preproccessing/p_pre_gs.py
```

### Transit Mobility

```bash
python preproccessing/p_pre_m.py
```

---

## Output Files

### Air Quality Preprocessing (`p_pre_aq.py`)

| File | Format | Description |
|---|---|---|
| `portland_monthly_pm25_zscores.csv` | CSV | Monthly PM₂.₅ averages and z-scores per monitor |
| `portland_city_baseline.csv` | CSV | City-wide μ_City and σ_City parameters |
| `portland_monitoring_stations.geojson` | GeoJSON | Monitor locations in `EPSG:6554` |
| `portland_addresses_with_monitors.geojson` | GeoJSON | Residential addresses with nearest monitor assignment and distance |
| `portland_airquality_summary_stats.csv` | CSV | Summary statistics table |

### Air Quality Methodology (`p_aq_method.py`)

| File | Format | Description |
|---|---|---|
| `portland_airquality_comprehensive_results.xlsx` | XLSX (9 sheets) | Full results: city score, monthly distribution, annual stats, monitor scores, neighbourhood rankings |
| `portland_addresses_with_aq_scores.geojson` | GeoJSON | Address-level annual risk scores |
| `portland_neighborhood_aq_stats.csv` | CSV | Mean air quality score and population per neighbourhood |
| `portland_city_aq_score.csv` | CSV | Final population-weighted city score |
| `fig1_portland_aq_map.png` | PNG (300 dpi) | Choropleth: neighbourhood air quality risk |
| `fig2_monthly_risk_distribution.png` | PNG (300 dpi) | Bar chart: monthly risk score distribution |
| `fig3_annual_score_distribution.png` | PNG (300 dpi) | Histogram: address-level annual scores |
| `fig4_zscore_timeline.png` | PNG (300 dpi) | Line plot: monthly z-scores by monitor |
| `fig5_spatial_detail_monitors_addresses.png` | PNG (300 dpi) | Address-level scores with monitor locations |

### Greenspace Preprocessing (`p_pre_gs.py`)

| File | Format | Description |
|---|---|---|
| `portland_parks_eligible.geojson` | GeoJSON | Parks filtered to ≥ 0.5 ha |
| `portland_addresses_with_distances.geojson` | GeoJSON | Residential addresses with distance to nearest eligible park boundary |
| `portland_greenspace_summary_stats.csv` | CSV | Summary including 300 m and 500 m threshold counts |

### Transit Preprocessing (`p_pre_m.py`)

| File | Format | Description |
|---|---|---|
| `portland_transit_stops_combined.geojson` | GeoJSON | All TriMet stops with transit type classification |
| `portland_{type}_stops.geojson` | GeoJSON | Stops split by type (bus, rail, streetcar) |
| `portland_addresses_with_transit_distances.geojson` | GeoJSON | Residential addresses with distance to nearest stop and stop type |
| `portland_transit_summary_stats.csv` | CSV | Coverage statistics at 400 m and 850 m thresholds |

---

## Data Sources

| Dataset | Source | File |
|---|---|---|
| PM₂.₅ monitor readings | EPA / local monitoring network | Excel files in `portland_aq/` |
| Residential address points | City of Portland Bureau of Development Services | `Active_Address_Points.shp` |
| Neighbourhood boundaries | City of Portland | `Neighborhoods_regions.shp` |
| Parks | Portland Parks & Recreation | `Parks.shp` |
| Transit stops | TriMet General Transit Feed Specification (GTFS) | `tm_stops.shp` |
| Neighbourhood population | US Census Bureau | `p_population.xlsx` |

---

## Replication for Other Cities

The pipeline is city-agnostic in structure. Equivalent scripts exist in this repository for Manchester (`m_*`) and Chicago (`c_*`). To adapt for a new city:

1. **Air quality:** Provide EPA-format Excel files with `Longitude`, `Latitude`, and a PM₂.₅ column. Update `AQ_DATA_PATH` and verify the date column name.
2. **Greenspace:** Supply a polygon parks shapefile and update `PARKS_PATH`. The 0.5 ha and 300/500 m thresholds are literature-based and should be retained for cross-city comparability.
3. **Transit:** Supply a point shapefile of transit stops with a route identifier column. Update the transit type inference logic in `infer_transit_type()` for the local agency's route numbering scheme.
4. **CRS:** Replace `EPSG:6554` with the appropriate projected CRS for accurate metre-based distance calculations.
5. **Area constant:** Update `portland_area_km2 = 375.0` in `p_pre_m.py` for transit density calculations.

All threshold values (`MIN_PARK_SIZE_HECTARES`, `PROTECTIVE_DISTANCE_M`, `EXTENDED_BENEFIT_M`, `CRITICAL_THRESHOLD_M`, `EPA_VALID_RANGE`) are defined as named constants at the top of each script for easy reconfiguration.

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

*Contact*: [tzirathperez@outlook.com](mailto:tzirathperez@outlook.com) | [LinkedIn](https://www.linkedin.com/in/tzirath-perez/)
