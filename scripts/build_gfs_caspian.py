#!/usr/bin/env python3
import argparse
import datetime as dt
import os
from pathlib import Path
import time

import requests

NOMADS = "https://nomads.ncep.noaa.gov/cgi-bin"
WEST, EAST, SOUTH, NORTH = 45.0, 56.0, 35.5, 48.5

WEATHER_GROUPS = [
    (
        "wind10m",
        {
            "var_UGRD": "on",
            "var_VGRD": "on",
            "lev_10_m_above_ground": "on",
        },
    ),
    (
        "temp2m",
        {
            "var_TMP": "on",
            "var_DPT": "on",
            "lev_2_m_above_ground": "on",
        },
    ),
    (
        "mslp",
        {
            "var_PRMSL": "on",
            "lev_mean_sea_level": "on",
        },
    ),
    (
        "surface",
        {
            "var_GUST": "on",
            "var_APCP": "on",
            "var_VIS": "on",
            "lev_surface": "on",
        },
    ),
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


def fetch_grib(session, url, params, tries=3):
    last = None
    for attempt in range(1, tries + 1):
        try:
            r = session.get(url, params=params, timeout=120)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {r.url}")
            data = r.content
            if not data.startswith(b"GRIB"):
                preview = data[:160].decode("utf-8", errors="replace").replace("\n", " ")
                raise RuntimeError(f"Response is not GRIB: {preview}")
            return data
        except Exception as exc:
            last = exc
            if attempt < tries:
                time.sleep(2 * attempt)
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
            data = fetch_grib(session, url, params, tries=1)
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


def build_weather(session, run, steps, path):
    request_count = 0
    with open(path, "wb") as out:
        for i, step in enumerate(steps, start=1):
            print(f"[weather {i}/{len(steps)}] +{step:03d}h")
            for group_name, group_params in WEATHER_GROUPS:
                url, params = weather_request(run, step, group_params)
                try:
                    data = fetch_grib(session, url, params)
                    out.write(data)
                    request_count += 1
                except Exception as exc:
                    # Some accumulated fields can be absent at f000.
                    if step == 0 and group_name == "surface":
                        print(f"  surface group at f000 skipped: {exc}")
                        continue
                    raise
                time.sleep(0.12)
    return request_count


def build_wave(session, run, steps, path):
    request_count = 0
    with open(path, "wb") as out:
        for i, step in enumerate(steps, start=1):
            print(f"[wave {i}/{len(steps)}] +{step:03d}h")
            url, params = wave_request(run, step)
            data = fetch_grib(session, url, params)
            out.write(data)
            request_count += 1
            time.sleep(0.12)
    return request_count


def validate_file(path):
    p = Path(path)
    if not p.exists() or p.stat().st_size < 8:
        raise RuntimeError(f"Invalid/empty output: {p}")
    with p.open("rb") as f:
        if f.read(4) != b"GRIB":
            raise RuntimeError(f"Output does not start with GRIB: {p}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("weather", "wave"), required=True)
    ap.add_argument("--days", type=int, choices=(3, 5, 7, 10), default=5)
    ap.add_argument("--outdir", default="output")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    steps = steps_for(args.days)
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "ECMWF-Caspian-GRIB/GFS-builder-1.0",
            "Accept": "*/*",
        }
    )

    run = find_latest_complete(session, args.mode, steps[-1])
    run_id = run.strftime("%Y%m%d_%H") + "Z"
    run_display = run.strftime("%Y-%m-%d %H:00 UTC")

    if args.mode == "weather":
        final = outdir / "GFS_CASPIAN_WEATHER.grib2"
        count = build_weather(session, run, steps, final)
        fields = "UGRD/VGRD 10m, TMP/DPT 2m, PRMSL, GUST, APCP, VIS"
    else:
        final = outdir / "GFS_CASPIAN_WAVE.grib2"
        count = build_wave(session, run, steps, final)
        fields = "HTSGW, PERPW, DIRPW"

    validate_file(final)

    info = outdir / (
        "GFS_CASPIAN_WEATHER_INFO.txt"
        if args.mode == "weather"
        else "GFS_CASPIAN_WAVE_INFO.txt"
    )
    info.write_text(
        "\n".join(
            [
                f"NOAA GFS Caspian {args.mode.title()} GRIB",
                f"Source run: {run_display}",
                f"Forecast horizon: {args.days} days",
                "Temporal resolution: 3-hourly",
                "Source grid: 0.25 degree",
                f"Area: lon {WEST}E to {EAST}E; lat {SOUTH}N to {NORTH}N",
                f"Fields: {fields}",
                f"NOMADS subset requests written: {count}",
                f"Output size: {final.stat().st_size} bytes",
                "Source: NOAA/NCEP NOMADS",
                "",
                "Planning/visualisation support only. Not a replacement for type-approved ECDIS, official ENC, official warnings, or Master's navigational judgement.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    github_output("run_id", run_id)
    github_output("run_display", run_display)
    github_output("file", str(final))
    github_output("info", str(info))
    github_output("size", str(final.stat().st_size))
    print(f"DONE: {final} ({final.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
