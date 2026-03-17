import requests
import mysql.connector
import time

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
# OPENSKY CONFIG
# -----------------------------
OPENSKY_URL = "https://opensky-network.org/api/states/all"

# Slovenia / nearby region
BBOX = {
    "lamin": 47.0,
    "lamax": 48.0,
    "lomin": 11.0,
    "lomax": 19.0
}

# seconds between API calls
FETCH_INTERVAL = 20


# -----------------------------
# CONNECT DATABASE
# -----------------------------
db = mysql.connector.connect(**DB_CONFIG)
cursor = db.cursor()

insert_sql = """
INSERT INTO aircraft
(ICAO24, CALLSIGN, LAT, LON, ALTITUDE, VELOCITY, HEADING)
VALUES (%s,%s,%s,%s,%s,%s,%s)
ON DUPLICATE KEY UPDATE
CALLSIGN=VALUES(CALLSIGN),
LAT=VALUES(LAT),
LON=VALUES(LON),
ALTITUDE=VALUES(ALTITUDE),
VELOCITY=VALUES(VELOCITY),
HEADING=VALUES(HEADING)
"""


# -----------------------------
# FETCH DATA FROM OPENSKY
# -----------------------------
def fetch_aircraft():
    response = requests.get(OPENSKY_URL, params=BBOX)

    if response.status_code != 200:
        print("OpenSky error:", response.status_code)
        return []

    data = response.json()

    if not data or "states" not in data:
        return []

    rows = []

    for s in data["states"]:
        if s is None:
            continue

        icao24 = s[0]
        callsign = (s[1] or "").strip()

        lon = s[5]
        lat = s[6]

        altitude = s[7]
        velocity = s[9]
        heading = s[10]

        # skip aircraft with no position
        if lat is None or lon is None:
            continue

        rows.append((
            icao24,
            callsign,
            float(lat),
            float(lon),
            float(altitude or 0),
            float(velocity or 0),
            float(heading or 0)
        ))

    return rows


# -----------------------------
# SAVE TO DATABASE
# -----------------------------
def save_to_db(rows):

    if not rows:
        return

    try:
        cursor.executemany(insert_sql, rows)
        db.commit()
        print(f"Inserted/updated {cursor.rowcount} aircraft")

    except Exception as e:
        print("Database error:", e)


# -----------------------------
# MAIN LOOP
# -----------------------------
def main():

    print("AirRadar data collector started")

    while True:

        try:
            rows = fetch_aircraft()
            save_to_db(rows)

        except Exception as e:
            print("Error:", e)

        time.sleep(FETCH_INTERVAL)


# -----------------------------
# START
# -----------------------------
if __name__ == "__main__":
    main()