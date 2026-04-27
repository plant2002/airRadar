import mysql.connector
from datetime import datetime, timedelta
import trino
import time
import random
import pandas as pd
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
INSERT INTO aircraft
(ICAO24, CALLSIGN, LAT, LON, ALTITUDE, VELOCITY, HEADING, TIME)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
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
# TRINO CONNECTION
# -----------------------------
conn = trino.dbapi.connect(
    host = "trino.opensky-netowrk.org",
    port= 443,
    user = "ms68672",
    http_scheme = "https",
    catalog = "opensky",
    schema = "default"
)
cursor = conn.cursor()

def fetch_trino(day, tile):
    start = day.strftime("%Y-%m-%d 00:00:00")
    end = (day + timedelta(days=1)).strftime("%Y-%m-%d 00:00:00")

    query = f"""
        SELECT icao24, callsign, lat, lon, geo_altitude, velocity, heading, time
        FROM state_vectors_data4
        WHERE time >= TIMESTAMP '{start}'
        AND time < TIMESTAMP '{end}'
        AND lon BETWEEN {tile['lomin']} AND {tile['lomax']}
        AND lat BETWEEN {tile['lamin']} AND {tile['lamax']}
        """

    cursor.execute(query)
    return cursor.fetchall()

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
def polite_sleep():
    time.sleep(2 + random.random())  # 2–3 seconds
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
        if r[2] is None or r[3] is None:  # lat/lon
            continue
        cleaned.append(tuple(x if x is not None else 0 for x in r))
    return cleaned
# -----------------------------
# MAIN LOOP
# -----------------------------
tiles = generate_tiles(44.12, 47.68, 11.05, 19.07, step=0.5)

start_date = datetime(2023, 1, 1)
end_date   = datetime(2025, 1, 1)

for day_index, day in enumerate(generate_days(start_date, end_date)):

    print("Processing day:", day.date())

    for tile_index, tile in enumerate(tiles):
        try:
            print("Tile:", tile)

            rows = clean_rows(fetch_trino(day, tile))
            save_to_db(rows)

            # SAVE PROGRESS HERE
            with open("progress.txt", "w") as f:
                f.write(f"{day_index},{tile_index}")

            polite_sleep()

        except Exception as e:
            print("Error:", e)
            time.sleep(10)