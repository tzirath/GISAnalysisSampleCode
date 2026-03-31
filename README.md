# GISAnalysisSampleCode
# Portland Air Quality Analysis Pipeline
   
   Geospatial preprocessing pipeline for population-level environmental 
   exposure assessment across 815,000+ residential addresses.
   
   ## Methodology
   Based on Chen et al. (2018) epidemiological thresholds for PM2.5 
   air quality risk assessment using z-score standardization.
   
   ## Key Features
   - Multi-source data integration (EPA, Census, municipal GIS)
   - Spatial quality control (CRS validation, boundary checks)
   - Nearest-neighbor assignment using cKDTree
   - Population-weighted risk aggregation
   - Reproducible analysis pipeline
   
   ## Technologies
   - GeoPandas, SciPy (spatial operations)
   - Pandas, NumPy (data processing)
   - Matplotlib (visualization)
