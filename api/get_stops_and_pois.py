import numpy as np
import os
import sqlite3
from pathlib import Path
from shapely.geometry import Point
import math
import geopandas as gpd
from shapely import wkt
from math import radians, sin, cos, sqrt, atan2

import pandas as pd


DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "db.one-bus"


def _extract_coordinates(event):
	"""Extract latitude/longitude from a direct Lambda invocation payload."""
	if not isinstance(event, dict):
		raise ValueError("Event payload must be a JSON object")

	latitude_input = event.get("latitude")
	longitude_input = event.get("longitude")

	if latitude_input is None or longitude_input is None:
		raise ValueError("Latitude and longitude values are required.")

	try:
		latitude = float(latitude_input)
		longitude = float(longitude_input)
	except (TypeError, ValueError) as exc:
		raise ValueError("Latitude and longitude must be valid numbers") from exc

	return latitude, longitude


def _coerce_bool_column(df, column_name):
	if column_name in df.columns:
		df[column_name] = df[column_name].astype(bool)


def load_data_from_sqlite(db_path):
	"""Load data from SQLite using CSV basename table names."""
	with sqlite3.connect(db_path) as conn:
		all_unique_stops_df = pd.read_sql_query("SELECT * FROM all_unique_stops", conn)
		filtered_poi_df = pd.read_sql_query("SELECT * FROM one_bus_filtered_pois", conn)
		stop_times_df = pd.read_sql_query("SELECT * FROM stop_times", conn)
		trips_df = pd.read_sql_query("SELECT * FROM e_trips", conn)
		stops_df = pd.read_sql_query("SELECT * FROM stops", conn)

	_coerce_bool_column(all_unique_stops_df, "is_express")

	return DataHolder(
		stops_df=stops_df,
		trips_df=trips_df,
		stop_times_df=stop_times_df,
		filtered_poi_df=filtered_poi_df,
		all_unique_stops_df=all_unique_stops_df,
	)


def compute_stops_and_pois(latitude, longitude, db_path):
	data_holder = load_data_from_sqlite(db_path)

	three_stops_df = closest_stops_finder(
		data_holder.all_unique_stops_df,
		latitude,
		longitude,
	)

	all_stops = all_stop_finder(three_stops_df, data_holder.all_unique_stops_df)
	poi_df = poi_getter(latitude, longitude, data_holder.filtered_poi_df, all_stops)

	response = {"stops": [], "pois": []}

	for _, row in all_stops.iterrows():
		response["stops"].append(
			{
				"latitude": row["stop_lat"],
				"longitude": row["stop_lon"],
				"stop_name": row["stop_name"],
				"headsign": row["trip_headsign"],
				"origin_stop": bool(row["origin_stop"]),
			}
		)

	for _, row in poi_df.iterrows():
		lat = row.geometry.y
		lon = row.geometry.x
		response["pois"].append(
			{
				"latitude": lat,
				"longitude": lon,
				"map_url": f"https://www.google.com/maps/search/?api=1&query={lat}%2C{lon}",
				"stop_name": row["stop_name"],
				"route_id": row["route_id"],
				"num_stops_away": row["num_stops_away"],
				"name": row["name"],
				"amenity": row["amenity"],
				"amenity_category": row["amenity_category"],
				"icon": row["icon"],
				"color": row["color"],
			}
		)

	return response


def lambda_handler(event, context):
	del context
	latitude, longitude = _extract_coordinates(event)

	db_path = os.getenv("SQLITE_DB_PATH", str(DEFAULT_DB_PATH))
	if not os.path.exists(db_path):
		raise FileNotFoundError(f"SQLite database not found at {db_path}")

	return compute_stops_and_pois(latitude, longitude, db_path)


def all_stop_finder(origin_stops, all_unique_stops):
	'''
    Find the closest 3 bus stops and their corresponding bus numbers (note a bus stop can have more than 1 bus going through it!)

    Arguments:
    all_unique_stops: all unique routes from the GTFS data
    origin_stops: The 3 origin bus stops near the user

    Returns:
    all_possible_stops: Dataframe of all possible stops that the user can go to based off the 3 bus stops
    '''
	# initialize subsequent stops dataframe
	subsequent_stops = pd.DataFrame()

	for _, row in origin_stops.iterrows():
		# take the stop name and the stop sequence in order to find out which are the subsequent stops
		current_sequence = row['stop_sequence']
		headsign = row['trip_headsign']
		subsequent_stops_add = all_unique_stops[
			(all_unique_stops['stop_sequence'] > current_sequence) & (all_unique_stops['trip_headsign'] == headsign)]

		subsequent_stops = pd.concat([subsequent_stops, subsequent_stops_add])

	subsequent_stops['origin_stop'] = False

	all_possible_stops = pd.concat([origin_stops, subsequent_stops])

	return all_possible_stops


def closest_stops_finder(all_unique_stops, user_latitude, user_longitude):
	'''
    Find the closest 5 bus stops and their corresponding bus numbers (note a bus stop can have more than 1 bus going through it!)
    Since some bus stops might be in the next sequence, this function will only return the bus stop that is the closest
    and provides unique bus lines going through it

    Arguments:
    all_unique_stops: all unique routes from the GTFS data
    user_latitude: get this by prompting for user's location from the front end
    user_longitude: get this by prompting for user's location from the front end

    Returns:
    origin_stops: Dataframe of the 3 closest bus stops and all corresponding bus stops
    '''

	# Calculate distances for each bus stop
	all_unique_stops['distance'] = all_unique_stops.apply(
		lambda row: haversine(user_latitude, user_longitude, row['stop_lat'], row['stop_lon']),
		axis=1
	)

	# Get 10 closest stops
	closest_stops = (all_unique_stops
	.sort_values(['distance', 'direction_id'])  # Sort by distance then direction
	.drop_duplicates(['stop_name'], keep='first')  # Keep closest of each stop name
	.head(10)
	[['stop_name', 'stop_lat', 'stop_lon', 'distance']]
	)

	# Filter and process origin stops
	origin_stops = (all_unique_stops[
		all_unique_stops['stop_name'].isin(closest_stops['stop_name'])
	]
	.sort_values('route_id')  # Sort by route_id
	.assign(**{'distance (m)': lambda x: np.ceil(x['distance']).astype(int)})  # Rename and process distance
	.loc[lambda x: x.groupby(['route_id', 'direction_id'])['distance (m)'].idxmin()]  # Keep closest stop per route
	)

	# set True to all stops gathered here for origin stops

	origin_stops['origin_stop'] = True
	# TODO: Add a check here to enforce a maximum distance from the user's location to the origin stops. Maybe something like 10 miles?
	# That would effectively filter out users who aren't even close to Austin.

	return origin_stops

class DataHolder:
    """
    This class holds the dataframes used in the application.
    """
    def __init__(self, stops_df, trips_df, stop_times_df, filtered_poi_df, all_unique_stops_df):
        self.stops_df = stops_df
        self.trips_df = trips_df
        self.stop_times_df = stop_times_df
        self.filtered_poi_df = filtered_poi_df
        self.all_unique_stops_df = all_unique_stops_df


# Define a function to convert each polygon to its centroid point
def get_centroid(geom):
	return Point(geom.centroid)


def poi_getter(user_latitude, user_longitude, filtered_pois_df, possible_locations):
	'''
    Gets specific list of POIs that are within walking distance of the bus stops and produces a dataframe of POIs that user can go to
    Uses a pre downloaded POI list loaded from GCS

    If there are overlapping POIs, algorithm will select whichever is closest to the bus stop

    Arguments:
        - filtered_pois_df: list of amenities that I think might be interesting to go to/visit
        - possible_locations: dataframe of bus_stops that user is able to go to

    Returns:
        - combined_poi: dataframe of all POIs that user can go to
    '''

	# Step 1: Add a geometry column to the bus stop DataFrame
	possible_locations = possible_locations.copy()
	possible_locations.loc[:, 'geometry'] = possible_locations.apply(
		lambda row: Point(row['stop_lon'], row['stop_lat']),
		axis=1
	)

	# First ensure the geometry column is string type
	filtered_pois_df['geometry'] = filtered_pois_df['geometry'].astype(str)

	# Step 2: Convert both DataFrames to GeoDataFrames
	# Set the CRS to WGS84 (EPSG:4326) for latitude/longitude
	filtered_pois_df['geometry'] = filtered_pois_df['geometry'].apply(wkt.loads)

	bus_stops_gdf = gpd.GeoDataFrame(possible_locations, geometry='geometry', crs='EPSG:4326')
	pois_gdf = gpd.GeoDataFrame(filtered_pois_df, geometry='geometry', crs='EPSG:4326')

	# Separate points and polygons
	points_gdf = pois_gdf[pois_gdf.geometry.type == 'Point']
	polygons_gdf = pois_gdf[pois_gdf.geometry.type == 'Polygon']

	# Step 3: Create a copy for buffered bus stops
	bus_stops_buffered_gdf = bus_stops_gdf.copy()

	# Step 4: Calculate buffer distance in degrees
	def meters_to_degrees(meters, latitude):
		return meters / (111320 * math.cos(math.radians(latitude)))

	buffer_distance_degrees = meters_to_degrees(500, 30.26562)  # 500 meters at latitude 30.26562

	# Step 5: Apply buffer to create circular areas around bus stops
	bus_stops_buffered_gdf['geometry'] = bus_stops_buffered_gdf.geometry.buffer(buffer_distance_degrees)

	# Step 6: Perform a spatial join to find POIs within the buffered area
	pois_within_500m_points = gpd.sjoin(points_gdf, bus_stops_buffered_gdf, how='inner', predicate='within')
	pois_within_500m_poly = gpd.sjoin(polygons_gdf, bus_stops_buffered_gdf, how='inner', predicate='intersects')

	# Calculate for centroid
	pois_within_500m_poly['geometry'] = pois_within_500m_poly['geometry'].centroid

	combined_poi = pd.concat([pois_within_500m_poly, pois_within_500m_points], ignore_index=True)

	# Removing duplicate POIs

	# Extract coordinates from geometry and stop_lat/stop_lon
	combined_poi['distance'] = combined_poi.apply(
		lambda row: haversine(
			row.geometry.x, row.geometry.y,  # POI coordinates (lon, lat)
			row['stop_lon'], row['stop_lat']  # Bus stop coordinates
		),
		axis=1
	)

	# Calculate distance from user to each POI
	combined_poi['distance_from_user'] = combined_poi.apply(
		lambda row: haversine(
			row.geometry.x, row.geometry.y,  # POI coordinates (lon, lat)
			user_longitude, user_latitude  # User's coordinates
		),
		axis=1
	)
	origin_stops = possible_locations[possible_locations['origin_stop'] == True]

	# Create a mapping dictionary of origin stops and their trip desqience
	origin_stop_seq_dict = origin_stops.set_index(['trip_headsign'])['stop_sequence'].to_dict()

	# Apply to main DataFrame
	combined_poi['origin_stop_sequence'] = combined_poi['trip_headsign'].map(origin_stop_seq_dict)

	# calculate POI number of stops away
	combined_poi['num_stops_away'] = abs(combined_poi['origin_stop_sequence'] - combined_poi['stop_sequence'])

	# Drop POIs that are less than 500m from the user since that is walking distance

	# Drop duplicates, keeping the closest POI per geometry
	# Sort by distance (ascending) to prioritize shortest distances
	combined_poi = combined_poi.sort_values(['num_stops_away', 'distance'], ascending=[True, True])
	combined_poi = combined_poi.drop_duplicates(subset=['geometry'], keep='first')
	combined_poi = combined_poi[(combined_poi['num_stops_away'] > 0)]

	# TODO: Consider adding a max distance threshold as well. We'd also want to similarly filter
	# bus stops to avoid showing a map with far away stops and no POIs nearby.

	return combined_poi


def haversine(lat1, lon1, lat2, lon2):
	# Convert degrees to radians
	lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

	# Haversine formula
	dlon = lon2 - lon1
	dlat = lat2 - lat1
	a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
	c = 2 * atan2(sqrt(a), sqrt(1 - a))
	distance = 6371 * c * 1000  # Earth radius in km, convert to meters
	return distance


if __name__ == "__main__":
	sample_event = {
		"latitude": "30.31431458225797",
		"longitude": "-97.73587186057428",
	}
	print(lambda_handler(sample_event, None))

