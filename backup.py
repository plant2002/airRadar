import os
import time
import logging
from datetime import datetime, timedelta

import mysql.connector
import pandas as pd

from sqlalchemy import select, func, or_

# OpenSky / Trino
os.environ["TRINO_CONFIG_DIR"] = os.path.expanduser("~/.trino")
os.makedirs(os.environ["TRINO_CONFIG_DIR"], exist_ok=True)

from pyopensky.trino import Trino
from pyopensky.schema import StateVectorsData4


logging.basicConfig(level=logging.INFO)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("trino").setLevel(logging.WARNING)

# -----------------------------
# CONFIG
# -----------------------------
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "airradar",
}

PROGRESS_FILE = "progress.txt"

# Start/resume point
start_day_index = 0
start_tile_index = 0
start_hour = 0

# Tile size: now that query is thinner, you can try 0.5 first
TILE_STEP = 0.5

# 15-second sampling
SECONDS_TO_KEEP = (0, 15, 30, 45)

# date range
START_DATE = datetime(2024, 1, 1, 0, 0, 0)
END_DATE   = datetime(2024, 1, 2, 0, 0, 0)

# If a query runs longer than this, consider shrinking tile size
POLITE_QUERY_SECONDS = 15


# -----------------------------
# PROGRESS
# -----------------------------
def load_progress():
    global start_day_index, start_tile_index, start_hour
    try:
        with open(PROGRESS_FILE, "r") as f:
            d, t, h = f.read().strip().split(",")
            start_day_index = int(d)
            start_tile_index = int(t)
            start_hour = int(h)
            print("Resuming from:", start_day_index, start_tile_index, start_hour)
    except Exception:
        print("No progress file, starting fresh")


def save_progress(day_index: int, tile_index: int, hour_value: int) -> None:
    with open(PROGRESS_FILE, "w") as f:
        f.write(f"{day_index},{tile_index},{hour_value}")
    print(f"Progress saved: day={day_index}, tile={tile_index}, hour={hour_value}")


# -----------------------------
# DATABASE
# -----------------------------
db = mysql.connector.connect(**DB_CONFIG)
db_cursor = db.cursor()

insert_sql = """
    INSERT INTO archive
    (ICAO24, CALLSIGN, LAT, LON, ALTITUDE, VELOCITY, HEADING, TIME1)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    ON DUPLICATE KEY UPDATE
        CALLSIGN=VALUES(CALLSIGN),
        LAT=VALUES(LAT),
        LON=VALUES(LON),
        ALTITUDE=VALUES(ALTITUDE),
        VELOCITY=VALUES(VELOCITY),
        HEADING=VALUES(HEADING)
"""


def save_to_db(df: pd.DataFrame) -> None:
    if df.empty:
        return

    rows = []
    for r in df.itertuples(index=False):
        t = r.time.to_pydatetime() if hasattr(r.time, "to_pydatetime") else r.time
        rows.append((
            r.icao24,
            r.callsign,
            r.lat,
            r.lon,
            r.geoaltitude,
            r.velocity,
            r.heading,
            t,
        ))

    try:
        db_cursor.executemany(insert_sql, rows)
        db.commit()
        print(f"Sent {len(rows)} rows to MySQL")
        print(f"MySQL affected-row count: {db_cursor.rowcount}")
    except Exception as e:
        print("Database error:", e)
        raise


# -----------------------------
# TRINO / OPENSKY
# -----------------------------
trino = Trino()


def build_query(start: datetime, stop: datetime, tile: dict):
    """
    Server-side filtering:
    - only needed columns
    - bounding box
    - non-null lat/lon
    - only timestamps where second in (0, 15, 30, 45)
    """

    return (
        select(StateVectorsData4)
        .with_only_columns(
            StateVectorsData4.time,
            StateVectorsData4.icao24,
            StateVectorsData4.lat,
            StateVectorsData4.lon,
            StateVectorsData4.velocity,
            StateVectorsData4.heading,
            StateVectorsData4.callsign,
            StateVectorsData4.geoaltitude,
        )
        # partition/time pruning
        .where(StateVectorsData4.hour >= start)
        .where(StateVectorsData4.hour < stop)
        .where(StateVectorsData4.time >= start)
        .where(StateVectorsData4.time < stop)
        # spatial bounds
        .where(StateVectorsData4.lon >= tile["lomin"])
        .where(StateVectorsData4.lon < tile["lomax"])
        .where(StateVectorsData4.lat >= tile["lamin"])
        .where(StateVectorsData4.lat < tile["lamax"])
        # avoid junk rows
        .where(StateVectorsData4.lat != None)
        .where(StateVectorsData4.lon != None)
        .where(StateVectorsData4.icao24 != None)
        # keep only 0,15,30,45 sec
        .where(
            or_(
                func.second(StateVectorsData4.time) == 0,
                func.second(StateVectorsData4.time) == 15,
                func.second(StateVectorsData4.time) == 30,
                func.second(StateVectorsData4.time) == 45,
            )
        )
    )


def fetch_chunk(start: datetime, stop: datetime, tile: dict, retries: int = 5) -> pd.DataFrame:
    query = build_query(start, stop, tile)

    for attempt in range(1, retries + 1):
        try:
            print(f"Attempt {attempt}/{retries}")
            return trino.query(query)
        except RuntimeError as e:
            if "QUERY_QUEUE_FULL" in str(e):
                print("⚠️ Queue full, waiting 60 seconds before retry...")
                time.sleep(60)
            else:
                print("Unexpected OpenSky/Trino error:", e)
                raise
        except Exception as e:
            print("Unexpected query error:", e)
            raise

    return pd.DataFrame()


# -----------------------------
# DATA CLEANUP
# -----------------------------
def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(
            columns=["time", "icao24", "lat", "lon", "velocity", "heading", "callsign", "geoaltitude"]
        )

    # rename to match your downstream code
    rename_map = {
        "timestamp": "time",
        "latitude": "lat",
        "longitude": "lon",
        "groundspeed": "velocity",
        "track": "heading",
    }
    df = df.rename(columns=rename_map).copy()

    expected = ["time", "icao24", "lat", "lon", "velocity", "heading", "callsign", "geoaltitude"]
    missing = [c for c in expected if c not in df.columns]
    if missing:
        raise ValueError(f"Missing expected columns from query result: {missing}")

    df = df[expected].copy()
    df = df.dropna(subset=["time", "icao24", "lat", "lon"])

    df["time"] = pd.to_datetime(df["time"])

    if "callsign" in df.columns:
        df["callsign"] = df["callsign"].astype(object)
        df["callsign"] = df["callsign"].where(df["callsign"].isna(), df["callsign"].str.strip())

    # convert NaN to None for MySQL friendliness
    df = df.where(pd.notna(df), None)

    return df


# -----------------------------
# STORAGE
# -----------------------------
def save_parquet(df: pd.DataFrame, day: datetime, tile_index: int, hour_value: int) -> None:
    filename = os.path.abspath(
        f"parquet/year={day.year}/month={day.month}/day={day.day}/tile={tile_index}_{hour_value}.parquet"
    )
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    df.to_parquet(filename, index=False)
    print(f"Saved {len(df)} rows to {filename}")
    print("File exists:", os.path.exists(filename))
    print("File size:", os.path.getsize(filename))


# -----------------------------
# HELPERS
# -----------------------------
def polite_sleep(duration: float) -> None:
    # lighter than before because you're already limiting the result set
    sleep_time = max(2, min(10, duration * 0.5))
    time.sleep(sleep_time)


def generate_days(start_date: datetime, end_date: datetime):
    current = start_date
    while current < end_date:
        yield current
        current += timedelta(days=1)


def generate_tiles(lat_min, lat_max, lon_min, lon_max, step=0.5):
    tiles = []
    lat = lat_min
    while lat < lat_max:
        lon = lon_min
        while lon < lon_max:
            tiles.append({
                "lamin": lat,
                "lamax": min(lat + step, lat_max),
                "lomin": lon,
                "lomax": min(lon + step, lon_max),
            })
            lon += step
        lat += step
    return tiles


# -----------------------------
# MAIN FETCH
# -----------------------------
def fetch_and_save_tile(day, tile, tile_index, end_time, day_index):
    if day_index == start_day_index and tile_index == start_tile_index:
        start = day + timedelta(hours=start_hour)
    else:
        start = day

    while start < end_time:
        stop = min(start + timedelta(hours=1), end_time)

        print(f"\nFetching chunk {start} -> {stop}")
        print("Bounds:", (tile["lomin"], tile["lamin"], tile["lomax"], tile["lamax"]))

        t0 = time.time()
        df_raw = fetch_chunk(start, stop, tile)
        duration = time.time() - t0

        print("df_raw is None:", df_raw is None)
        print("df_raw type:", type(df_raw))
        print(f"Query time: {duration:.2f}s")

        if duration > POLITE_QUERY_SECONDS:
            print(f"⚠️ Query exceeded polite target ({POLITE_QUERY_SECONDS}s). Consider smaller tiles.")

        if df_raw is None or df_raw.empty:
            print("No data in this chunk")
        else:
            df = normalize_df(df_raw)
            print("Chunk rows after normalize:", len(df))

            if not df.empty:
                save_parquet(df, day, tile_index, start.hour)
                save_to_db(df)
            else:
                print("All rows were filtered out")

        save_progress(day_index, tile_index, start.hour)
        polite_sleep(duration)
        start = stop


# -----------------------------
# RUN
# -----------------------------
def main():
    load_progress()

    tiles = generate_tiles(44.00, 48.00, 11.00, 19.00, step=TILE_STEP)

    for day_index, day in enumerate(generate_days(START_DATE, END_DATE)):
        if day_index < start_day_index:
            continue

        print("\nProcessing day:", day.date())

        for tile_index, tile in enumerate(tiles):
            if day_index == start_day_index and tile_index < start_tile_index:
                continue

            try:
                print("Tile:", tile)
                day_end = min(day + timedelta(days=1), END_DATE)
                fetch_and_save_tile(day, tile, tile_index, day_end, day_index)
                time.sleep(2)

            except Exception as e:
                print("Error:", e)
                raise


if __name__ == "__main__":
    main()