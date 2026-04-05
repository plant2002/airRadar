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

logging.basicConfig(level=logging.INFO)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("trino").setLevel(logging.WARNING)
# -----------------------------
# PROGRESS FILE
# -----------------------------
start_day_index = 0
start_tile_index = 0
hour = 0

try:
    with open("progress.txt", "r") as f:
        d, t, h = f.read().strip().split(",")
        start_day_index = int(d)
        start_tile_index = int(t)
        hour = int(h)
        print("Resuming from:", start_day_index, start_tile_index, hour)
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
# -----------------------------
# SAVE TO DATABASE
# -----------------------------
def save_to_db(rows):
    if not rows:
        return

    db_rows = []
    for r in rows:
        t, icao24, lat, lon, velocity, heading, callsign, geoaltitude = r
        if hasattr(t, "to_pydatetime"):
            t = t.to_pydatetime()

        db_rows.append((
            icao24, 
            callsign,
            lat,
            lon,
            geoaltitude,
            velocity,
            heading,
            t
        ))

    try:
        db_cursor.executemany(insert_sql, db_rows)
        db.commit()
        print(f"Sent {len(db_rows)} rows to MySQL")
        print(f"MySQL affected-row count: {db_cursor.rowcount}")

    except Exception as e:
        print("Database error:", e)
        raise

# -----------------------------
# FETCH FUNCTION
# -----------------------------

def fetch_and_save_tile(day, tile, tile_index, end_time, day_index):
    if day_index == start_day_index and tile_index == start_tile_index:
        start = day + timedelta (hours=hour)
    else: 
        start = day
    while start < end_time:
        stop = min(start + timedelta(hours=1), end_time)
        print(f"Fetching chunk {start} -> {stop}")
        print("Bounds:", (tile["lomin"], tile["lamin"], tile["lomax"], tile["lamax"]))

        t0 = time.time()

        df_chunk = None

        for attempt in range(5):
            try:
                print(f"Attempt {attempt+1}/5")

                df_chunk = opensky.history(
                    start=start,
                    stop=stop,
                    bounds=(
                        tile["lomin"],
                        tile["lamin"],
                        tile["lomax"],
                        tile["lamax"]
                    )
                )
                break  # success → exit retry loop

            except RuntimeError as e:
                if "QUERY_QUEUE_FULL" in str(e):
                    print("⚠️ Queue full, waiting 60 seconds before retry...")
                    time.sleep(60)
                else:
                    print("Unexpected OpenSky error:", e)
                    raise

        duration = time.time() - t0
        print("df_chunk is None:", df_chunk is None)
        print("df_chunk type:", type(df_chunk))
        if duration > 30:
            print(f"⚠️ Slow chunk: {duration:.2f}s for tile {tile_index}, hour {start.hour}")

        if df_chunk is None:
            print("No data in this chunk")
        else:
            df_data = df_chunk.data
            print("df_data empty:", df_data.empty)
            print("Chunk rows:", len(df_data))

            if not df_data.empty:
                rows = list(df_data[
                    ["timestamp", "icao24", "latitude", "longitude", "groundspeed", "track", "callsign", "geoaltitude"]
                ].itertuples(index=False, name=None))

                rows = clean_rows(rows)
                print("Cleaned rows:", len(rows))

                if rows:
                    df = pd.DataFrame(
                        rows,
                        columns=["time", "icao24", "lat", "lon", "velocity", "heading", "callsign", "geoaltitude"]
                    )

                    filename = os.path.abspath(
                        f"parquet/year={day.year}/month={day.month}/day={day.day}/tile={tile_index}_{start.hour}.parquet"
                    )
                    os.makedirs(os.path.dirname(filename), exist_ok=True)
                    df.to_parquet(filename, index=False)

                    print(f"Saved {len(rows)} rows to {filename}")
                    print("File exists:", os.path.exists(filename))
                    print("File size:", os.path.getsize(filename))

                    save_to_db(rows)
                else:
                    print("All rows were filtered out by clean_rows()")
            else:
                print("No data in this chunk")

        polite_sleep(duration)
        current_hour = start.hour
        with open("progress.txt", "w") as f:
             f.write(f"{day_index},{tile_index},{current_hour}")
        print(f"Progress saved: day={day_index}, tile={tile_index}, hour={current_hour}")
        start = stop
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
        # unpack for readability
        t, icao24, lat, lon, velocity, heading, callsign, geoaltitude = r

        # skip rows without coordinates
        if pd.isna(lat) or pd.isna(lon):
            continue

        fixed = []
        for x in r:
            if pd.isna(x):
                fixed.append(None)
            else:
                # convert pandas Timestamp to plain Python datetime
                if hasattr(x, "to_pydatetime"):
                    fixed.append(x.to_pydatetime())
                else:
                    fixed.append(x)

        cleaned.append(tuple(fixed))

    return cleaned
# -----------------------------
# TILES CHANGES
# -----------------------------
tiles = generate_tiles(44.00, 48, 11.00, 19.00, step=0.2)
# -----------------------------
# TIMEFRAME CHANGES
# -----------------------------
start_date = datetime(2024, 1, 1, 0, 0, 0)
end_date   = datetime(2024, 1, 2, 0, 0, 0)

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
            day_end = min(day + timedelta(days = 1), end_date)
            fetch_and_save_tile(day, tile, tile_index, day_end, day_index)

            time.sleep(2)

        except Exception as e:
            print("Error:", e)
            raise