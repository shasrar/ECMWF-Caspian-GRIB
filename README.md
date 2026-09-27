# Caspian Marine GRIB

Automatically builds small **Caspian Sea-only GRIB2** products for qtVlm and other GRIB2 viewers.

## Operational concept

### Main operational file — Combined
**NOAA GFS Weather + DWD GWAM Wave**

- GFS provides atmosphere/weather.
- GWAM provides Total Sea, Wind Sea and Swell.
- GWAM 10 m wind is excluded from the Combined file to avoid duplicate wind sources.

### Independent wave cross-check
**ECMWF IFS-WAVE**

### NOAA GFS Wave
**Not used for the Caspian Sea.**

Direct ecCodes validation of the Caspian subset showed that the GFS Wave messages contained only missing values over the Caspian area. GFS Wave is therefore deliberately excluded from the downloader, automated build and published GFS release.

## Direct latest downloads

### Combined Operational
https://github.com/shasrar/ECMWF-Caspian-GRIB/releases/download/combined-latest/CASPIAN_MARINE_COMPLETE.grib2

### ECMWF IFS-WAVE
https://github.com/shasrar/ECMWF-Caspian-GRIB/releases/download/latest/ECMWF_CASPIAN_WAVE.grib2

### NOAA GFS Weather
https://github.com/shasrar/ECMWF-Caspian-GRIB/releases/download/gfs-latest/GFS_CASPIAN_WEATHER.grib2

### DWD GWAM
https://github.com/shasrar/ECMWF-Caspian-GRIB/releases/download/gwam-latest/DWD_GWAM_CASPIAN_WAVE.grib2

## Common coverage

- Area: **45°E–56°E, 35.5°N–48.5°N**
- Intended for Caspian Sea voyage/weather planning

## Forecast horizons

- Combined Operational: **3 / 5 / 7 days**
- DWD GWAM: **3 / 5 / 7 days**
- ECMWF Wave: **3 / 5 / 7 / 10 days**
- GFS Weather: **3 / 5 / 7 / 10 days**

## ECMWF wave

Source: ECMWF IFS-WAVE Open Data, 0.25°.

Fields:
- swh — significant wave height
- mwd — mean wave direction
- mwp — mean wave period
- pp1d — peak wave period

## NOAA GFS weather

Source: NOAA/NCEP GFS 0.25° via NOMADS GRIB Filter.

Fields:
- 10u, 10v — 10 m wind vector
- gust — surface wind gust
- prmsl — mean sea-level pressure
- tp — precipitation
- vis — visibility
- 2t — 2 m air temperature
- 2d — 2 m dew point

## DWD GWAM

Source: DWD GWAM global wave model, 0.25° Open Data.

Fields:
- Total sea: swh, mwd, mwp
- Wind sea: shww, wvdir, mpww, PPWW
- Swell: shts, swdir, mpts, PPTS
- Wave-model wind exists in standalone GWAM, but is intentionally excluded from the Combined product.

## qtVlm

Recommended:
- **GRIB Slot 1:** Combined Operational
- **GRIB Slot 2:** ECMWF Wave for independent cross-check

Open files with:

Data → GRIB Slot → Open/Load

## Navigation notice

These products are planning and visualisation aids only. They do not replace type-approved ECDIS, official ENC, official meteorological warnings, MSI, company procedures, or the Master's navigational judgement.
