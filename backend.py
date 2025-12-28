# backend.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opensky_client import get_circular_radar

app = FastAPI()

# Allow all origins for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

CENTER_LAT = 46.0569   # Ljubljana
CENTER_LON = 14.5058
RADIUS_KM = 100

@app.get("/aircraft")
def aircraft():
    aircraft_list = get_circular_radar(CENTER_LAT, CENTER_LON, RADIUS_KM)
    return [
        {
            "icao24": s[0],
            "callsign": s[1].strip() if s[1] else "N/A",
            "lat": s[6],
            "lon": s[5],
            "altitude": s[7],
            "velocity": s[9],
            "heading": s[10],
        }
        for s in aircraft_list
    ]
