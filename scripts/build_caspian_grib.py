#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import time

import requests

ROOT = "https://data.ecmwf.int/forecasts"
MODEL = "ifs"
RESOLUTION = "0p25"
STREAM = "wave"
CORE_PARAMS = ("swh", "mwd", "mwp", "pp1d")

# Caspian Sea plus a small margin for approaches and ports.
WEST, EAST, SOUTH, NORTH = 45.0, 56.0, 35.5, 48.5


def forecast_steps(days: int):
    horizon = days * 24
    steps = list(range(0, min(horizon, 144) + 1, 3))
    if horizon > 144:
        steps.extend(range(150, horizon + 1, 6))
    return steps


def url_for(run: dt.datetime, step: int, ext: str):
    date = run.strftime("%Y%m%d")
    hh = run.strftime("%H")
    stamp = run.strftime("%Y%m%d%H") + "0000"
    return f"{ROOT}/{date}/{hh}z/{MODEL}/{RESOLUTION}/{STREAM}/{stamp}-{step}h-{STREAM}-fc.{ext}"


def get_with_retry(session, url, *, headers=None, timeout=90, tries=3):
    last = None
    for attempt in range(1, tries + 1):
        try:
            return session.get(url, headers=headers, timeout=timeout)
        except requests.RequestException as exc:
            last = exc
            if attempt < tries:
                time.sleep(2 * attempt)
    raise last


def parse_index(text: str):
    records = []
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue

        param = obj.get("param")
        if param not in CORE_PARAMS:
            continue
        if "_offset" not in obj or "_length" not in obj:
            continue

        records.append(
            {
                "param": param,
                "offset": int(obj["_offset"]),
                "length": int(obj["_length"]),
            }
        )
    return records


def index_for(session, run, step):
    url = url_for(run, step, "index")
    response = get_with_retry(session, url)
    if response.status_code != 200:
        raise RuntimeError(f"Index HTTP {response.status_code}: {url}")
    return parse_index(response.text)


def find_latest_complete_run(session, last_step):
    now = dt.datetime.now(dt.timezone.utc)
    hour = 12 if now.hour >= 12 else 0
    anchor = now.replace(hour=hour, minute=0, second=0, microsecond=0)

    print(f"Searching latest complete ECMWF 00/12 UTC run with +{last_step}h available...")
    for i in range(8):
        run = anchor - dt.timedelta(hours=12 * i)
        run_text = run.strftime("%Y-%m-%d %HZ")
        try:
            records = index_for(session, run, last_step)
            available = {r["param"] for r in records}
            if all(p in available for p in CORE_PARAMS):
                print(f"Using complete run: {run_text}")
                return run
            print(f"{run_text}: final step exists but core fields are incomplete.")
        except Exception as exc:
            print(f"{run_text}: not ready ({exc})")

    raise RuntimeError("No complete ECMWF 00/12 UTC run found in the last 4 days.")


def download_range(session, url, offset, length):
    end = offset + length - 1
    headers = {"Range": f"bytes={offset}-{end}"}
    last = None

    for attempt in range(1, 4):
        try:
            response = session.get(url, headers=headers, timeout=120)
            if response.status_code != 206:
                raise RuntimeError(f"Expected HTTP 206, got {response.status_code}")

            data = response.content
            if len(data) != length:
                raise RuntimeError(
                    f"Byte count mismatch: expected {length}, got {len(data)}"
                )
            if not data.startswith(b"GRIB"):
                raise RuntimeError("Downloaded field does not start with GRIB.")
            return data

        except Exception as exc:
            last = exc
            if attempt < 3:
                time.sleep(2 * attempt)

    raise last


def write_github_output(key, value):
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, choices=(3, 5, 7, 10), default=5)
    parser.add_argument("--outdir", default="output")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    global_path = outdir / "ECMWF_GLOBAL_WAVE_TEMP.grib2"

    steps = forecast_steps(args.days)
    last_step = steps[-1]

    session = requests.Session()
    session.headers.update(
        {"User-Agent": "ECMWF-Caspian-GRIB-GitHub-Actions/1.0"}
    )

    run = find_latest_complete_run(session, last_step)
    run_id = run.strftime("%Y%m%d_%H") + "Z"

    total_fields = 0
    with open(global_path, "wb") as output:
        for index, step in enumerate(steps, start=1):
            print(f"[{index}/{len(steps)}] +{step}h")
            records = index_for(session, run, step)
            by_param = {r["param"]: r for r in records}

            missing = [p for p in CORE_PARAMS if p not in by_param]
            if missing:
                raise RuntimeError(
                    f"Missing at +{step}h: {', '.join(missing)}"
                )

            grib_url = url_for(run, step, "grib2")
            for param in CORE_PARAMS:
                rec = by_param[param]
                data = download_range(
                    session,
                    grib_url,
                    rec["offset"],
                    rec["length"],
                )
                output.write(data)
                total_fields += 1

    if global_path.stat().st_size < 8:
        raise RuntimeError("Temporary global GRIB is empty.")

    with open(global_path, "rb") as f:
        if f.read(4) != b"GRIB":
            raise RuntimeError("Temporary global GRIB failed GRIB validation.")

    info_path = outdir / "ECMWF_CASPIAN_WAVE_INFO.txt"
    info = [
        "ECMWF Caspian Wave GRIB",
        f"Source run: {run.strftime('%Y-%m-%d %H:00 UTC')}",
        f"Forecast horizon: {args.days} days",
        "Temporal resolution: 3-hourly through +144h, then 6-hourly",
        "Fields: swh, mwd, mwp, pp1d",
        "Source grid: ECMWF IFS-WAVE Open Data 0.25 degree global",
        f"Caspian crop: lon {WEST}E to {EAST}E; lat {SOUTH}N to {NORTH}N",
        f"Downloaded field count: {total_fields}",
        "Source attribution: ECMWF Open Data",
        "",
        "Planning/visualisation support only. Not a replacement for type-approved ECDIS, official ENC, official warnings, or Master's navigational judgement.",
    ]
    info_path.write_text("\n".join(info) + "\n", encoding="utf-8")

    write_github_output("run_id", run_id)
    write_github_output("run_display", run.strftime("%Y-%m-%d %H:00 UTC"))
    write_github_output("days", str(args.days))
    write_github_output("global_file", str(global_path))
    write_github_output("info_file", str(info_path))

    print(
        f"Temporary global file ready: {global_path} "
        f"({global_path.stat().st_size / 1024 / 1024:.1f} MiB)"
    )


if __name__ == "__main__":
    main()
