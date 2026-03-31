import mysql.connector
from datetime import datetime, timedelta
import time
import pandas as pd
import os
os.environ["TRINO_CONFIG_DIR"] = os.path.expanduser("~/.trino")
os.makedirs(os.environ["TRINO_CONFIG_DIR"], exist_ok=True)
from traffic.data import opensky
import logging
import math
logging.basicConfig(level=logging.DEBUG)
# -----------------------------
# PROGRESS FILE
# -----------------------------
start_day_index = 0
start_tile_index = 0

try:
    with open("progress.txt", "r") as f:
        d, t = f.read().split(",")
        start_day_index = int(d)
        start_tile_index = int(t)
        print("Resuming from:", start_day_index, start_tile_index)
except:
    print("No progress file, starting fresh")
# -----------------------------
# DATABASE CONFIG
# -----------------------------
DB_CONFIG = {
    "host": "localhost",
    "user": "root",          # change if needed
    "password": "",          # your mysql password
    "database": "airradar"
}

# -----------------------------
# CONNECT DATABASE
# -----------------------------
db = mysql.connector.connect(**DB_CONFIG)
db_cursor = db.cursor()

insert_sql = """
    INSERT INTO archive
    (ICAO24, CALLSIGN, LAT, LON, ALTITUDE, VELOCITY, HEADING, TIME)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    ON DUPLICATE KEY UPDATE
    CALLSIGN=VALUES(CALLSIGN),
    LAT=VALUES(LAT),
    LON=VALUES(LON),
    ALTITUDE=VALUES(ALTITUDE),
    VELOCITY=VALUES(VELOCITY),
    HEADING=VALUES(HEADING)
    """
# -----------------------------
# SAVE TO DATABASE
# -----------------------------
def save_to_db(rows):

    if not rows:
        return

    try:
        db_cursor.executemany(insert_sql, rows)
        db.commit()
        print(f"Inserted/updated {db_cursor.rowcount} aircraft")

    except Exception as e:
        print("Database error:", e)

# -----------------------------
# FETCH FUNCTION
# -----------------------------
def fetch_trino(day, tile):
    start = day
    all_rows = []

    while start < day + timedelta(days=1):
        stop = min(start + timedelta(hours=1), day + timedelta(days=1))

        t0 = time.time()
        df_chunk = opensky.history(
            start=start,
            stop=stop,
            lat=(tile["lamin"], tile["lamax"]),
            lon=(tile["lomin"], tile["lomax"])
        )
        duration = time.time() - t0
        polite_sleep(duration)

        if df_chunk is not None and not df_chunk.empty:
            rows_chunk = df_chunk[[
                "time", "icao24", "lat", "lon", "velocity",  "heading", "callsign",
                "geoaltitude"
            ]].itertuples(index=False, name=None)

            all_rows.extend(rows_chunk)

        start = stop

    return clean_rows(all_rows)

# -----------------------------
# DYNAMIC FETCH FUNCTION
# -----------------------------
def fetch_with_dynamic_split(day, tile, max_duration=45, min_step=0.1):
    """
    Efficient dynamic fetch of OpenSky data with hourly chunks.
    Splits tiles if the query takes too long or tile is too large.
    """
    try:
        start_time = time.time()

        # Collect all rows for this tile
        start = day
        all_rows = []

        while start < day + timedelta(days=1):
            stop = min(start + timedelta(hours=1), day + timedelta(days=1))

            t0 = time.time()

            df_chunk = opensky.history(
                start=start,
                stop=stop,
                lat=(tile["lamin"], tile["lamax"]),
                lon=(tile["lomin"], tile["lomax"])
            )
            print(df_chunk.head())
            print(df_chunk.columns)
            print(len(df_chunk))

            duration = time.time() - t0
            polite_sleep(duration)

            if df_chunk is not None and not df_chunk.empty:
                rows_chunk = df_chunk[[
                "time", "icao24", "lat", "lon", "velocity",  "heading", "callsign",
                "geoaltitude"
                    ]].itertuples(index=False, name=None)
                all_rows.extend(rows_chunk)

            start = stop
        total_duration = time.time() - start_time

        # If too slow AND tile is still splittable, split into 4 subtiles
        if total_duration > max_duration and (tile["lamax"] - tile["lamin"] > min_step):
            mid_lat = (tile["lamin"] + tile["lamax"]) / 2
            mid_lon = (tile["lomin"] + tile["lomax"]) / 2

            subtiles = [
                {"lamin": tile["lamin"], "lamax": mid_lat, "lomin": tile["lomin"], "lomax": mid_lon},
                {"lamin": tile["lamin"], "lamax": mid_lat, "lomin": mid_lon, "lomax": tile["lomax"]},
                {"lamin": mid_lat, "lamax": tile["lamax"], "lomin": tile["lomin"], "lomax": mid_lon},
                {"lamin": mid_lat, "lamax": tile["lamax"], "lomin": mid_lon, "lomax": tile["lomax"]},
            ]

            # Reset all_rows, recursively fetch from subtiles
            all_rows = []
            total_duration = 0
            for st in subtiles:
                st_rows, st_duration = fetch_with_dynamic_split(day, st, max_duration, min_step)
                
                all_rows.extend(st_rows)
                total_duration += st_duration

                polite_sleep(st_duration)

            return all_rows, total_duration

        return clean_rows(all_rows), total_duration

    except Exception as e:
        print("Error fetching tile:", tile, e)
        return [], 0

# -----------------------------
# TIME CHUNKS
# -----------------------------
def generate_days(start_date, end_date):
    current = start_date
    while current < end_date:
        yield current
        current += timedelta(days=1)
# -----------------------------
# REST
# -----------------------------
def polite_sleep(duration):
    sleep_time = max(2, duration * 1.5)
    time.sleep(sleep_time)
# -----------------------------
# TILES
# -----------------------------
def generate_tiles(lat_min, lat_max, lon_min, lon_max, step=0.5):
    tiles = []
    
    lat = lat_min
    while lat < lat_max:
        lon = lon_min
        while lon < lon_max:
            tiles.append({
                "lamin": lat,
                "lamax": lat + step,
                "lomin": lon,
                "lomax": lon + step
            })
            lon += step
        lat += step

    return tiles
# -----------------------------
# CLEAN ROWS
# -----------------------------
def clean_rows(rows):
    cleaned = []
    for r in rows:
        lat, lon = r[2], r[3]
        if lat is None or lon is None or (isinstance(lat, float) and math.isnan(lat)) or (isinstance(lon, float) and math.isnan(lon)):
            continue
        cleaned.append(tuple(0 if x is None or (isinstance(x, float) and math.isnan(x)) else x for x in r))
    return cleaned
# -----------------------------
# TILES CHANGES
# -----------------------------
tiles = generate_tiles(44.00, 48.00, 11.00, 19.00, step=0.25)

# -----------------------------
# TIMEFRAME CHANGES
# -----------------------------
start_date = datetime(2024, 1, 1)
end_date   = datetime(2024, 1, 2)
# -----------------------------
# MAIN LOOP
# -----------------------------
for day_index, day in enumerate(generate_days(start_date, end_date)):

    if day_index < start_day_index:
        continue

    print("Processing day:", day.date())

    for tile_index, tile in enumerate(tiles):
        if tile_index < start_tile_index and day_index == start_day_index:
            continue
        try:
            print("Tile:", tile)
            
            #FETCH DATA + QUERY DURATION
            rows, query_duration = fetch_with_dynamic_split(day, tile)
            print(f"Server query time: {query_duration:.2f}s")

            #QUERY TIME WARNING
            if query_duration > 30:
                print(f"⚠️ Slow query: {query_duration:.2f}s")

            # SAVE TO PARQUET
            if rows:
                df = pd.DataFrame(
                    rows,
                    columns=["time", "icao24", "lat", "lon", "velocity",  "heading", "callsign", "geoaltitude"]
                )
                filename = f"parquet/year={day.year}/month={day.month}/day={day.day}/tile={tile_index}.parquet"
                os.makedirs(os.path.dirname(filename), exist_ok=True)
                df.to_parquet(filename, index=False)
                print(f"Saving {len(rows)} rows to {filename}")
            else:
                print("No data for this tile")

            
            #SAVE TO DATABASE
            save_to_db(rows)

            # SAVE PROGRESS
            with open("progress.txt", "w") as f:
                f.write(f"{day_index},{tile_index}")

            time.sleep(2)

        except Exception as e:
            print("Error:", e)
            time.sleep(10)