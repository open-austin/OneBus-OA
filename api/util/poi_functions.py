import pandas as pd
import pandas as pd
from shapely.geometry import Point
import math
import geopandas as gpd
from shapely import wkt
from api.util.formulas import haversine

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
    pois_within_500m_points = gpd.sjoin(points_gdf,bus_stops_buffered_gdf,how='inner',predicate='within')
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
