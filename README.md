# Caspian Marine GRIB

Automatically builds small **Caspian Sea-only GRIB2** products for qtVlm and other GRIB2 viewers.

## Direct latest downloads

### ECMWF IFS-WAVE
https://github.com/shasrar/ECMWF-Caspian-GRIB/releases/download/latest/ECMWF_CASPIAN_WAVE.grib2

### NOAA GFS Weather
https://github.com/shasrar/ECMWF-Caspian-GRIB/releases/download/gfs-latest/GFS_CASPIAN_WEATHER.grib2

### NOAA GFS Wave
https://github.com/shasrar/ECMWF-Caspian-GRIB/releases/download/gfs-latest/GFS_CASPIAN_WAVE.grib2

## Common coverage

- Area: **45°E–56°E, 35.5°N–48.5°N**
- Intended for Caspian Sea voyage/weather planning
- Default forecast horizon: **5 days**

## ECMWF wave

Source: ECMWF IFS-WAVE Open Data, 0.25°.

Fields:
- `swh` — significant wave height
- `mwd` — mean wave direction
- `mwp` — mean wave period
- `pp1d` — peak wave period

The ECMWF workflow downloads the required global fields temporarily on GitHub Actions, crops them to the Caspian Sea, validates the GRIB2, deletes the global intermediate, and publishes only the Caspian file.

## NOAA GFS weather

Source: NOAA/NCEP GFS 0.25° via NOMADS GRIB Filter.

Fields currently included:
- `10u`, `10v` — 10 m wind vector
- `gust` — surface wind gust
- `prmsl` — mean sea-level pressure
- `tp` — accumulated precipitation products returned by NOMADS
- `vis` — visibility
- `2t` — 2 m air temperature
- `2d` — 2 m dew point

The GFS weather file is subset by NOMADS directly to the Caspian area; the vessel PC does not download the global model.

## NOAA GFS Wave

Source: NOAA/NCEP GFS Wave 0.25° via NOMADS GRIB Filter.

Fields:
- `swh` / HTSGW — significant height of combined wind waves and swell
- `perpw` / PERPW — primary wave mean period
- `dirpw` / DIRPW — primary wave direction

## Automation

- ECMWF workflow: twice daily, with fallback to the latest complete 00/12 UTC run.
- GFS workflow: four times daily, with fallback to the latest complete 00/06/12/18 UTC run.
- Manual workflow runs can select 3, 5, 7, or 10 days.

## qtVlm

Recommended comparison:
- GRIB Slot 1: ECMWF Wave
- GRIB Slot 2: GFS Weather or GFS Wave

Open files with:

`Data → GRIB Slot → Open/Load`

## Navigation notice

These products are planning and visualisation aids only. They do not replace type-approved ECDIS, official ENC, official meteorological warnings, MSI, company procedures, or the Master's navigational judgement.


## DWD GWAM

Source: DWD GWAM global wave model, 0.25° Open Data.

Direct latest download:

https://github.com/shasrar/ECMWF-Caspian-GRIB/releases/download/gwam-latest/DWD_GWAM_CASPIAN_WAVE.grib2

Fields:
- Total sea: `swh`, `mwd`, `mwp` (DWD source directory `tm10`)
- Wind sea: `shww`, `wvdir` (DWD `mdww`), `mpww`, `PPWW`
- Swell: `shts`, `swdir` (DWD `mdts`), `mpts`, `PPTS`
- Wave-model wind: `10si` (DWD `sp_10m`), `10wdir` (DWD `dd_10m`)

The GWAM workflow downloads each compressed DWD global field temporarily on GitHub Actions, decompresses it, crops it immediately to the Caspian Sea, discards the global field, and publishes only the final Caspian GRIB2.

GWAM scheduled build: twice daily, with fallback to the latest complete 00/12 UTC run.
