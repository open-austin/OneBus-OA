import pandas as pd
from datetime import datetime
import pandas as pd
import numpy as np
from math import radians, sin, cos, sqrt, atan2
from api.util.formulas import haversine



def three_stops_finder(all_unique_stops, user_latitude, user_longitude):
    '''
    Find the closest 3 bus stops and their corresponding bus numbers (note a bus stop can have more than 1 bus going through it!)

    Arguments: 
    all_unique_stops: all unique routes from the GTFS data
    user_latitude: get this by prompting for user's location from the front end
    user_longitude: get this by prompting for user's location from the front end

    Returns:
    origin_stops: Dataframe of the 3 closest bus stops and all corresponding bus stops 
    '''
 
    
    # Calculate distances for each bus stop
    all_unique_stops['distance'] = all_unique_stops.apply(lambda row: haversine(user_latitude, user_longitude, row['stop_lat'], row['stop_lon']), axis=1)

    # Sort bus stops by distance and get the closest stops
    closest_stops = all_unique_stops.nsmallest(3, 'distance')[[ 'stop_name', 'stop_lat', 'stop_lon', 'distance']]

    # Sort by distance (ascending) to prioritize closer stops
    sorted_stops = all_unique_stops.sort_values('distance')

    # Drop duplicates, keeping the first (closest) occurrence of each stop_name
    unique_sorted_stops = sorted_stops.drop_duplicates(subset=['stop_name'], keep='first')

    # Take the top 3 closest unique stops
    closest_stops = unique_sorted_stops.head(3)[['stop_name', 'stop_lat', 'stop_lon', 'distance']]

    # select the 3 closest bus stops
    origin_stops = all_unique_stops[all_unique_stops['stop_name'].isin(closest_stops['stop_name'])]

    origin_stops = origin_stops.sort_values(by='route_id')
    origin_stops['distance'] = (np.ceil(origin_stops['distance']*100 ) * 10).astype(int)
    origin_stops = origin_stops.rename(columns={'distance': 'distance (m)'})

    # tag the closest stops to be origin stops
    origin_stops['origin stop'] = True 

    # TODO: Add a check here to enforce a maximum distance from the user's location to the origin stops. Maybe something like 10 miles?
    # That would effectively filter out users who aren't even close to Austin.
    
    return origin_stops

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
        subsequent_stops_add = all_unique_stops[(all_unique_stops['stop_sequence'] > current_sequence) & (all_unique_stops['trip_headsign'] == headsign)]
        
        subsequent_stops = pd.concat([subsequent_stops,subsequent_stops_add])
        
    subsequent_stops['origin stop'] = False
    
    all_possible_stops = pd.concat([origin_stops,subsequent_stops])
    
    return all_possible_stops

def transit_duration(origin, destination, stop_times_df):
    '''
    Helper function to caluclate the duration of the bus journey

    Arguments:
        - origin: bus stop name of the origin bus stop
        - destination: bus stop name of the destination bus stop
        - stop_times_df: dataframe of stops_times.txt from GTFS data

    Returns:
        - time_diff_mins: rounded up number of time difference
    '''

    # get the bus timings
    get_on = stop_times_df[stop_times_df['stop_name'] == origin]['departure_time'].values[0]
    get_off = stop_times_df[stop_times_df['stop_name'] == destination]['departure_time'].values[0]

    # calculate the time difference
    start_time = datetime.strptime(get_on, '%H:%M:%S')
    user_time = datetime.strptime(get_off, '%H:%M:%S')
    time_diff = user_time - start_time
    time_diff_mins = round(time_diff.total_seconds() / 60)

    return time_diff_mins

