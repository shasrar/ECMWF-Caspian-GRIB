# ECMWF-Caspian-GRIB

Automatically builds a **Caspian Sea-only ECMWF IFS-WAVE GRIB2** for qtVlm and other GRIB2 viewers.

## Direct latest download

After the first successful workflow run:

https://github.com/shasrar/ECMWF-Caspian-GRIB/releases/download/latest/ECMWF_CASPIAN_WAVE.grib2

## Contents

- Source: ECMWF IFS-WAVE Open Data
- Global source grid: 0.25°
- Final crop: **45°E–56°E, 35.5°N–48.5°N**
- Wave fields:
  - `swh` — significant wave height
  - `mwd` — mean wave direction
  - `mwp` — mean wave period
  - `pp1d` — peak wave period
- Scheduled horizon: **5 days**
- Scheduled build: twice daily
- Manual builds: 3, 5, 7, or 10 days

## How it works

The GitHub Actions workflow temporarily downloads the required global ECMWF fields, validates them, crops them to the Caspian Sea with CDO, deletes the global intermediate, and publishes only the much smaller Caspian GRIB2.

The global intermediate is intentionally **not committed to the repository**.

## qtVlm

Open the final file with:

`Data → GRIB Slot 1 → Open/Load`

## Navigation notice

This repository is a planning and visualisation aid only. qtVlm and these files do not replace type-approved ECDIS, official ENC, official meteorological warnings, or the Master's navigational judgement.
