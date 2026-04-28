import os
os.environ["OPENSKY_USERNAME"] = "ms68672"
os.environ["OPENSKY_PASSWORD"] = "8LPq04Wq9hA6e4QMGb87vz5JC80a2CMm"
os.environ["TRINO_CONFIG_DIR"] = os.path.expanduser("~/.trino")
os.makedirs(os.environ["TRINO_CONFIG_DIR"], exist_ok=True)
import logging
logging.basicConfig(level=logging.DEBUG)

from traffic.data import opensky

df = opensky.history(
    start="2024-01-01 12:00:00",
    stop="2024-01-01 13:00:00",
    lat=(48.5, 49.2),  # latitude min/max
    lon=(2.0, 2.5)     # longitude min/max
)
print(df)