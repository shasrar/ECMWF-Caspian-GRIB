#!/usr/bin/env python3
import argparse
import datetime as dt
import os
from pathlib import Path
import time

import requests

NOMADS = "https://nomads.ncep.noaa.gov/cgi-bin"
WEST, EAST, SOUTH, NORTH = 45.0, 56.0, 35.5, 48.5
HORIZONS = (3, 5, 7, 10)

WEATHER_GROUPS = [
    ("wind10m", {"var_UGRD": "on", "var_VGRD": "on", "lev_10_m_above_ground": "on"}),
    ("temp2m", {"var_TMP": "on", "var_DPT": "on", "lev_2_m_above_ground": "on"}),
    ("mslp", {"var_PRMSL": "on", "lev_mean_sea_level": "on"}),
    ("surface", {"var_GUST": "on", "var_APCP": "on", "var_VIS": "on", "lev_surface": "on"}),
]

WAVE_PARAMS = {
    "var_HTSGW": "on",
    "var_PERPW": "on",
    "var_DIRPW": "on",
    "lev_surface": "on",
}


def steps_for(days: int):
    return list(range(0, days * 24 + 1, 3))


def candidate_runs():
    now = dt.datetime.now(dt.timezone.utc)
    cycle = (now.hour // 6) * 6
    anchor = now.replace(hour=cycle, minute=0, second=0, microsecond=0)
    for i in range(12):
        yield anchor - dt.timedelta(hours=6 * i)


def common_region():
    return {
        "subregion": "",
        "leftlon": str(WEST),
        "rightlon": str(EAST),
        "toplat": str(NORTH),
        "bottomlat": str(SOUTH),
    }


def weather_request(run, step, extra):
    hh = run.strftime("%H")
    date = run.strftime("%Y%m%d")
    params = {
        "file": f"gfs.t{hh}z.pgrb2.0p25.f{step:03d}",
        "dir": f"/gfs.{date}/{hh}/atmos",
        **common_region(),
        **extra,
    }
    return f"{NOMADS}/filter_gfs_0p25.pl", params


def wave_request(run, step):
    hh = run.strftime("%H")
    date = run.strftime("%Y%m%d")
    params = {
        "file": f"gfswave.t{hh}z.global.0p25.f{step:03d}.grib2",
        "dir": f"/gfs.{date}/{hh}/wave/gridded",
        **common_region(),
        **WAVE_PARAMS,
    }
    return f"{NOMADS}/filter_gfswave.pl", params


def fetch_grib(session, url, params, tries=6):
    last = None
    for attempt in range(1, tries + 1):
        try:
            r = session.get(
                url,
                params=params,
                timeout=120,
                allow_redirects=True,
            )
            if r.status_code != 200:
                location = r.headers.get("Location", "")
                detail = f"HTTP {r.status_code}: {r.url}"
                if location:
                    detail += f" -> {location}"
                raise RuntimeError(detail)

            data = r.content
            if not data.startswith(b"GRIB"):
                preview = data[:160].decode("utf-8", errors="replace").replace("\n", " ")
                raise RuntimeError(f"Response is not GRIB: {preview}")
            return data

        except Exception as exc:
            last = exc
            if attempt < tries:
                wait = min(30, 5 * attempt)
                print(f"  NOMADS retry {attempt}/{tries - 1} after {wait}s: {exc}")
                time.sleep(wait)
    raise last


def find_latest_complete(session, mode, last_step):
    print(f"Searching latest complete {mode.upper()} run with +{last_step}h available...")
    for run in candidate_runs():
        label = run.strftime("%Y-%m-%d %HZ")
        try:
            if mode == "weather":
                url, params = weather_request(run, last_step, WEATHER_GROUPS[0][1])
            else:
                url, params = wave_request(run, last_step)
            data = fetch_grib(session, url, params, tries=2)
            if data.startswith(b"GRIB"):
                print(f"Using {mode} run: {label}")
                return run
        except Exception as exc:
            print(f"{label}: not complete/available ({exc})")
    raise RuntimeError(f"No complete {mode} run found in the last 72 hours.")


def github_output(key, value):
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")


def validate_file(path):
    p = Path(path)
    if not p.exists() or p.stat().st_size < 8:
        raise RuntimeError(f"Invalid/empty output: {p}")
    with p.open("rb") as f:
        if f.read(4) != b"GRIB":
            raise RuntimeError(f"Output does not start with GRIB: {p}")


def build_multi(session, run, mode, horizons, outdir):
    max_days = max(horizons)
    steps = steps_for(max_days)
    prefix = "GFS_CASPIAN_WEATHER" if mode == "weather" else "GFS_CASPIAN_WAVE"
    paths = {d: outdir / f"{prefix}_{d}D.grib2" for d in horizons}
    handles = {d: open(paths[d], "wb") for d in horizons}
    counts = {d: 0 for d in horizons}

    try:
        for i, step in enumerate(steps, start=1):
            print(f"[{mode} {i}/{len(steps)}] +{step:03d}h")
            if mode == "weather":
                requests_this_step = []
                for group_name, group_params in WEATHER_GROUPS:
                    url, params = weather_request(run, step, group_params)
                    try:
                        data = fetch_grib(session, url, params)
                        requests_this_step.append(data)
                    except Exception as exc:
                        if step == 0 and group_name == "surface":
                            print(f"  surface group at f000 skipped: {exc}")
                            continue
                        raise
                    time.sleep(0.35)
            else:
                url, params = wave_request(run, step)
                requests_this_step = [fetch_grib(session, url, params)]
                time.sleep(0.35)

            for d in horizons:
                if step <= d * 24:
                    for data in requests_this_step:
                        handles[d].write(data)
                        counts[d] += 1
    finally:
        for h in handles.values():
            h.close()

    fields = (
        "UGRD/VGRD 10m, TMP/DPT 2m, PRMSL, GUST, APCP, VIS"
        if mode == "weather"
        else "HTSGW, PERPW, DIRPW"
    )
    run_display = run.strftime("%Y-%m-%d %H:00 UTC")

    for d in horizons:
        validate_file(paths[d])
        info = outdir / f"{prefix}_{d}D_INFO.txt"
        info.write_text(
            "\n".join([
                f"NOAA GFS Caspian {mode.title()} GRIB",
                f"Source run: {run_display}",
                f"Forecast horizon: {d} days",
                "Temporal resolution: 3-hourly",
                "Source grid: 0.25 degree",
                f"Area: lon {WEST}E to {EAST}E; lat {SOUTH}N to {NORTH}N",
                f"Fields: {fields}",
                f"NOMADS subset requests written: {counts[d]}",
                f"Output size: {paths[d].stat().st_size} bytes",
                "Source: NOAA/NCEP NOMADS",
                "",
                "Planning/visualisation support only. Not a replacement for type-approved ECDIS, official ENC, official warnings, or Master's navigational judgement.",
            ]) + "\n",
            encoding="utf-8",
        )
        print(f"DONE {mode} {d}D: {paths[d]} ({paths[d].stat().st_size} bytes)")

    return run


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("weather", "wave"), required=True)
    ap.add_argument("--days", type=int, choices=HORIZONS, default=5)
    ap.add_argument("--all-horizons", action="store_true")
    ap.add_argument("--outdir", default="output")
    args = ap.parse_args()

    horizons = list(HORIZONS) if args.all_horizons else [args.days]
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({"User-Agent": "Caspian-Marine-GRIB/GFS-builder-1.1", "Accept": "*/*"})

    max_days = max(horizons)
    run = find_latest_complete(session, args.mode, max_days * 24)
    build_multi(session, run, args.mode, horizons, outdir)

    github_output("run_id", run.strftime("%Y%m%d_%H") + "Z")
    github_output("run_display", run.strftime("%Y-%m-%d %H:00 UTC"))


if __name__ == "__main__":
    main()
