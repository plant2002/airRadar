import os
import requests

# -------------------------------
# Configuration
# -------------------------------

WMS_URL = "REAL_WMS_URL_FROM_GetCapabilities"   # e.g. https://…/wms?
LAYER = "REAL_LAYER_NAME"                       # e.g. DOF050
WMS_VERSION = "1.3.0"
CRS = "EPSG:3794"   # D96/TM

TILE_SIZE = 256

EXTENT = [
    1502813.125709193, 5700582.732404123,
    1836771.598089014, 5860839.829947802
]

OUTPUT_DIR = "tiles_real_ortho"
os.makedirs(OUTPUT_DIR, exist_ok=True)

ZOOM_LEVELS = [6, 7, 8, 9]

def download_wms_tile(bbox):
    params = {
        "SERVICE": "WMS",
        "VERSION": WMS_VERSION,
        "REQUEST": "GetMap",
        "LAYERS": LAYER,
        "CRS": CRS,
        "BBOX": ",".join(map(str, bbox)),
        "WIDTH": TILE_SIZE,
        "HEIGHT": TILE_SIZE,
        "FORMAT": "image/png"
    }
    r = requests.get(WMS_URL, params=params)
    if "image" not in r.headers.get("Content-Type", ""):
        print(f"Warning: non-image returned for bbox {bbox}")
        print(r.text[:500])
        return None
    return r.content

for z in ZOOM_LEVELS:
    tiles_per_side = 2 ** (z - 6)
    dx = (EXTENT[2] - EXTENT[0]) / tiles_per_side
    dy = (EXTENT[3] - EXTENT[1]) / tiles_per_side

    print(f"Zoom {z}, {tiles_per_side}x{tiles_per_side} tiles")
    for ix in range(tiles_per_side):
        for iy in range(tiles_per_side):
            minx = EXTENT[0] + ix * dx
            maxx = EXTENT[0] + (ix + 1) * dx
            miny = EXTENT[1] + iy * dy
            maxy = EXTENT[1] + (iy + 1) * dy

            bbox = (minx, miny, maxx, maxy)
            data = download_wms_tile(bbox)
            if data:
                out_dir = os.path.join(OUTPUT_DIR, str(z))
                os.makedirs(out_dir, exist_ok=True)
                out_path = os.path.join(out_dir, f"{ix}_{iy}.png")
                with open(out_path, "wb") as f:
                    f.write(data)
                print(f"Saved tile {out_path}")
