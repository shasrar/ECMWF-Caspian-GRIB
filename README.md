# Caspian Marine GRIB

Small **Caspian Sea-only GRIB2** products for qtVlm and other GRIB2 viewers.

## Recommended qtVlm comparison

### Slot 1 — Combined A
**NOAA GFS Weather + DWD GWAM Wave**

### Slot 2 — Combined B
**NOAA GFS Weather + ECMWF IFS-WAVE**

Both files use GFS for the atmospheric fields, so the comparison is designed to isolate the wave-model difference as much as practical.

The downloader can also report:
- source-run freshness for GFS / GWAM / ECMWF,
- whether the two Combined files use the same GFS Weather run,
- the common valid-time overlap for comparison,
- the GWAM vs ECMWF initialization-time difference.

## Products

### Combined A
Tag: `combined-latest`

Weather:
- 10 m wind
- gust
- MSLP
- precipitation
- visibility
- 2 m temperature
- dew point

Wave:
- GWAM Total Sea
- Wind Sea
- Swell
- directions and periods

Horizons: **3 / 5 / 7 days**

### Combined B
Tag: `combined-ecmwf-latest`

Same GFS Weather fields as above.

Wave:
- ECMWF SWH
- MWD
- MWP
- PP1D

Horizons: **3 / 5 / 7 / 10 days**

### Standalone products
- ECMWF Wave: `latest`
- GFS Weather: `gfs-latest`
- GWAM Wave: `gwam-latest`

## NOAA GFS Wave

**Not used for the Caspian Sea.**

Direct ecCodes inspection of the generated Caspian subset showed that the GFS Wave messages contained only missing values over the area, so GFS Wave is excluded from the downloader and Caspian GFS workflow.

## Coverage

**45°E–56°E, 35.5°N–48.5°N**

## Downloader workflow

Basic mode:
- Combined A and Combined B only
- Refresh comparison metadata
- Download Comparison Pair

Advanced mode:
- standalone ECMWF Wave
- standalone GFS Weather
- standalone GWAM Wave
- selective downloads

Default horizon: **7 days**

## Navigation notice

These files are planning and visualisation aids only. They do not replace type-approved ECDIS, official ENC, official meteorological warnings, MSI, company procedures, or the Master's navigational judgement.
