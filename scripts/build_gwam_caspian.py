#!/usr/bin/env python3
import argparse
import bz2
import datetime as dt
from pathlib import Path
import os
import subprocess
import tempfile
import time

import requests

ROOT = "https://opendata.dwd.de/weather/maritime/wave_models/gwam/grib"
WEST, EAST, SOUTH, NORTH = 45.0, 56.0, 35.5, 48.5

PARAMS = [
    "swh", "mwd", "tm10",
    "shww", "mdww", "mpww", "ppww",
    "shts", "mdts", "mpts", "ppts",
    "sp_10m", "dd_10m",
]


def steps_for(days: int):
    horizon = min(days * 24, 174)
    return list(range(0, horizon + 1, 3))


def candidate_runs():
    now = dt.datetime.now(dt.timezone.utc)
    hour = 12 if now.hour >= 12 else 0
    anchor = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    for i in range(10):
        yield anchor - dt.timedelta(hours=12 * i)


def url_for(run: dt.datetime, param: str, step: int):
    hh = run.strftime("%H")
    stamp = run.strftime("%Y%m%d%H")
    upper = param.upper()
    return (
        f"{ROOT}/{hh}/{param}/"
        f"GWAM_{upper}_{stamp}_{step:03d}.grib2.bz2"
    )


def request_with_retry(session, method, url, *, timeout=90, tries=3):
    last = None
    for attempt in range(1, tries + 1):
        try:
            r = session.request(method, url, timeout=timeout, allow_redirects=True)
            return r
        except requests.RequestException as exc:
            last = exc
            if attempt < tries:
                time.sleep(2 * attempt)
    raise last


def exists(session, url):
    # DWD may not support HEAD uniformly through all mirrors; fall back to a tiny GET.
    try:
        r = request_with_retry(session, "HEAD", url, timeout=30, tries=1)
        if r.status_code == 200:
            return True
    except Exception:
        pass

    try:
        r = session.get(url, headers={"Range": "bytes=0-7"}, timeout=30)
        return r.status_code in (200, 206) and len(r.content) > 0
    except Exception:
        return False


def find_latest_complete(session, last_step):
    print(f"Searching latest complete DWD GWAM 00/12 UTC run with +{last_step}h available...")
    # Test several representative/final parameter files at the requested horizon.
    check_params = ("swh", "shww", "shts", "mwd", "sp_10m")
    for run in candidate_runs():
        label = run.strftime("%Y-%m-%d %HZ")
        ok = True
        for param in check_params:
            u = url_for(run, param, last_step)
            if not exists(session, u):
                ok = False
                break
        if ok:
            print(f"Using complete GWAM run: {label}")
            return run
        print(f"{label}: incomplete/not available")
    raise RuntimeError("No complete DWD GWAM run found in the last 5 days.")


def download_bz2(session, url):
    last = None
    for attempt in range(1, 4):
        try:
            r = session.get(url, timeout=120)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {url}")
            if len(r.content) < 20:
                raise RuntimeError(f"Response too small: {url}")
            return r.content
        except Exception as exc:
            last = exc
            if attempt < 3:
                time.sleep(2 * attempt)
    raise last


def crop_one(raw_grib: bytes, tempdir: Path):
    src = tempdir / "src.grib2"
    dst = tempdir / "crop.grib2"
    src.write_bytes(raw_grib)
    if dst.exists():
        dst.unlink()

    cmd = [
        "cdo", "-s", "-O", "-f", "grb2",
        f"sellonlatbox,{WEST},{EAST},{SOUTH},{NORTH}",
        str(src), str(dst),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            "CDO crop failed: "
            + (proc.stderr.strip() or proc.stdout.strip() or "unknown error")
        )

    data = dst.read_bytes()
    if not data.startswith(b"GRIB"):
        raise RuntimeError("Cropped output does not start with GRIB.")
    return data


def validate_grib(path: Path):
    if not path.exists() or path.stat().st_size < 8:
        raise RuntimeError(f"Invalid/empty output: {path}")
    with path.open("rb") as f:
        if f.read(4) != b"GRIB":
            raise RuntimeError("Final file does not start with GRIB.")


def github_output(key, value):
    p = os.environ.get("GITHUB_OUTPUT")
    if p:
        with open(p, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, choices=(3, 5, 7), default=5)
    ap.add_argument("--outdir", default="output")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    final = outdir / "DWD_GWAM_CASPIAN_WAVE.grib2"
    info = outdir / "DWD_GWAM_CASPIAN_WAVE_INFO.txt"

    steps = steps_for(args.days)
    session = requests.Session()
    session.headers.update({"User-Agent": "Caspian-Marine-GRIB-GWAM/1.0"})

    run = find_latest_complete(session, steps[-1])
    run_id = run.strftime("%Y%m%d_%H") + "Z"
    run_display = run.strftime("%Y-%m-%d %H:00 UTC")

    if final.exists():
        final.unlink()

    message_count = 0
    with tempfile.TemporaryDirectory(prefix="gwam_crop_") as td:
        tempdir = Path(td)
        with final.open("ab") as out:
            for si, step in enumerate(steps, start=1):
                print(f"[{si}/{len(steps)}] +{step:03d}h")
                for pi, param in enumerate(PARAMS, start=1):
                    url = url_for(run, param, step)
                    print(f"  {param} ({pi}/{len(PARAMS)})")
                    compressed = download_bz2(session, url)
                    try:
                        raw = bz2.decompress(compressed)
                    except OSError as exc:
                        raise RuntimeError(f"BZ2 decompression failed for {url}: {exc}")
                    if not raw.startswith(b"GRIB"):
                        raise RuntimeError(f"DWD file is not GRIB after decompression: {url}")

                    cropped = crop_one(raw, tempdir)
                    out.write(cropped)
                    message_count += 1
                    time.sleep(0.03)

    validate_grib(final)

    info.write_text(
        "\n".join([
            "DWD GWAM Caspian Wave GRIB",
            f"Source run: {run_display}",
            f"Forecast horizon: {args.days} days",
            "Temporal resolution: 3-hourly",
            "Source model: DWD GWAM global wave model",
            "Source grid: 0.25 degree",
            f"Area: lon {WEST}E to {EAST}E; lat {SOUTH}N to {NORTH}N",
            "Fields:",
            "  Total sea: SWH, MWD, TM10",
            "  Wind sea: SHWW, MDWW, MPWW, PPWW",
            "  Swell: SHTS, MDTS, MPTS, PPTS",
            "  Wave-model wind: SP_10M, DD_10M",
            f"Expected/cropped GRIB messages: {message_count}",
            f"Output size: {final.stat().st_size} bytes",
            "Source: DWD Open Data",
            "",
            "Planning/visualisation support only. Not a replacement for type-approved ECDIS, official ENC, official warnings, or Master's navigational judgement.",
        ]) + "\n",
        encoding="utf-8",
    )

    github_output("run_id", run_id)
    github_output("run_display", run_display)
    github_output("file", str(final))
    github_output("info", str(info))
    github_output("size", str(final.stat().st_size))
    github_output("messages", str(message_count))
    print(f"DONE: {final} ({final.stat().st_size} bytes, {message_count} messages)")


if __name__ == "__main__":
    main()
