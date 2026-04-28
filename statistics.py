from pyproj import Transformer, CRS
from sqlalchemy import create_engine
import pandas as pd
from sklearn.neighbors import KernelDensity
import numpy as np


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
# GET SPECIFIED DATA FROM DB
# -----------------------------
def get_data(params):
    
    engine = create_engine("mysql+mysqlconnector://root:@localhost/airradar")

    query = """SELECT * FROM `archive_new` WHERE 
            TIME1 BETWEEN %s AND %s 
            AND ALTITUDE BETWEEN %s AND %s;
            """
    
    rows = pd.read_sql(query, engine, params=params)

    rows["TIME1"] = pd.to_datetime(rows["TIME1"])
    return rows

# -----------------------------
# CREATE TRAJECTORIES FOR AIRCRAFTS (FROM POINTS)
# -----------------------------
def trajectories(rows):
    #creating lines/trajectories from saved points
    rows = rows.sort_values(['ICAO24', 'TIME1']).copy()

    #time difference
    rows['TIME_diff'] = rows.groupby('ICAO24')['TIME1'].diff().dt.total_seconds()

    #new trajectory if TIME_diff too big
    rows['new_traj'] = (rows['TIME_diff'] > 60) | (rows['TIME_diff'].isna())
    rows['traj_ID']= rows.groupby('ICAO24')['new_traj'].cumsum()

    #create next point only if it's the same trajectory
    group_cols = ["ICAO24", "traj_ID"]

    #save all data for trajectory
    rows['LAT_next'] = rows.groupby(group_cols)['LAT'].shift(-1)
    rows['LON_next'] = rows.groupby(group_cols)['LON'].shift(-1)
    rows['ALTITUDE_next'] = rows.groupby(group_cols)['ALTITUDE'].shift(-1)
    rows['HEADING_next'] = rows.groupby(group_cols)['HEADING'].shift(-1)
    rows['VELOCITY_next'] = rows.groupby(group_cols)['VELOCITY'].shift(-1)
    rows['TIME_next'] = rows.groupby(group_cols)['TIME1'].shift(-1)

    #last point (no next point possible)
    segments = rows.dropna(subset=['LAT_next', 'LON_next']).copy()

    return segments

# -----------------------------
# MIDPOINTS - SMOOTHING
# -----------------------------
#create midpoints between coordinates for KDE later
def midpoint_smoothing(segments):
    segments["LAT_mid"] = (segments["LAT"] + segments["LAT_next"]) / 2
    segments["LON_mid"] = (segments["LON"] + segments["LON_next"]) / 2

    return segments

# -----------------------------
# COORDINATE SYSTEM TRANSFOMATION
# FROM WGS (PHI/LAMBDA) TO WGS(E, N)
# -----------------------------
#using local coordinate system for this one
def make_local_tm():
    lon_0 =(11 + 19) / 2
    lat_0 = (44 + 48) / 2
    
    return CRS.from_proj4(
        f"+proj=tmerc +lat_0={lat_0} +lon_0={lon_0} "
        f"+k=0.9999 +x_0=500000 +y_0=0 "
        f"+ellps=WGS84 +units=m +no_defs"
    )

def transform_coordinates(segments):

    local_crs = make_local_tm()

    transformer = Transformer.from_crs("EPSG:4326", local_crs, always_xy= True)
    e, n = transformer.transform(segments["LON_mid"].values, segments["LAT_mid"].values)

    segments["e"] = e
    segments["n"] = n

    return segments
    
# -----------------------------
# KERNEL DENSITY
# -----------------------------
def kernel_density(segments):
    #points used for KDE
    valid_points = segments[["e", "n"]].dropna()
    points = valid_points.values

    #KDE model
    #change bandwidth for different smoothing size
    #it's in meters. so 5000 --> 5 km smoothing
    kde = KernelDensity(kernel = "gaussian", bandwidth = 5000)
    #fit KDE to points
    kde.fit(points)

    #density at the points
    log_density = kde.score_samples(points)
    density = np.exp(log_density)

    segments = segments.copy()
    segments.loc[valid_points.index, "density"] = density

    if segments["density"].max() > segments["density"].min():
        segments["density_norm"] = (
        (segments["density"] - segments["density"].min()) /
            (segments["density"].max() - segments["density"].min())
        )
    else:
        segments["density_norm"] = 0

    return segments

def run_kde(segments, bandwidth = 5000, grid_size = 300):
    points = segments[["e", "n"]].dropna().values

    kde = KernelDensity(kernel="gaussian", bandwidth=bandwidth)
    kde.fit(points)

    e_min, e_max = points[:, 0].min(), points[:, 0].max()
    n_min, n_max = points[:, 1].min(), points[:, 1].max()

    e_grid = np.linspace(e_min, e_max, grid_size)
    n_grid = np.linspace(n_min, n_max, grid_size)

    E, N = np.meshgrid(e_grid, n_grid)

    grid_points = np.column_stack([
        E.ravel(),
        N.ravel()
    ])

    log_density = kde.score_samples(grid_points)
    density = np.exp(log_density).reshape(E.shape)

    return E, N, density
# -----------------------------
# MAIN CALL FUNCTION
# -----------------------------
def main(time_from = None, time_to = None, altitude_from = None, altitude_to = None):
    #check arguments, if None, assign value
    time_from = "2024-01-01 00:00:00" if time_from is None else time_from
    time_to = "2024-01-01 01:00:00" if time_to is None else time_to
    altitude_from = 0 if altitude_from is None else altitude_from
    altitude_to = 38000 if altitude_to is None else altitude_to

    params = (time_from, time_to, altitude_from, altitude_to)

    #DB 
    rows = get_data(params)

    #from points create segments
    segments = trajectories(rows)

    #smoothing of segments
    segments = midpoint_smoothing(segments)

    segments = transform_coordinates(segments)

    segments = kernel_density(segments)
    E, N, density_grid = run_kde(segments, bandwidth = 5000, grid_size = 300)

    return segments, E, N, density_grid


data, E, N, density_grid = main()
print(data.head())
