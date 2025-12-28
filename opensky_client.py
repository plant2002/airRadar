# opensky_client.py
import requests
import math

OPENSKY_URL = "https://opensky-network.org/api/states/all"

def get_aircraft_states(bbox=None):
    params = {}
    if bbox:
        params = {
            "lamin": bbox[0],
            "lamax": bbox[1],
            "lomin": bbox[2],
            "lomax": bbox[3],
        }
    response = requests.get(OPENSKY_URL, params=params, timeout=10)
    response.raise_for_status()
    return response.json()

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def get_circular_radar(center_lat, center_lon, radius_km):
    lat_deg = radius_km / 111
    lon_deg = radius_km / (111 * math.cos(math.radians(center_lat)))
    bbox = (
        center_lat - lat_deg,
        center_lat + lat_deg,
        center_lon - lon_deg,
        center_lon + lon_deg
    )
    data = get_aircraft_states(bbox=bbox)
    return [
        s for s in data["states"]
        if haversine(center_lat, center_lon, s[6], s[5]) <= radius_km
    ]
