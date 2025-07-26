import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from api.apps import get_data
from api.util.bus_functions import three_stops_finder, all_stop_finder
from api.util.poi_functions import poi_getter

@csrf_exempt # Disable CSRF verification. Since we're not dealing with users or authentication yet, this should be safe.
def determine_stops_and_pois(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'HTTP method not supported.'}, status=400)
    
    # Get and validate the latitude and longitude values from the request
    try:
        data = json.loads(request.body.decode('utf-8'))
        latitude_input = data.get('latitude')
        longitude_input = data.get('longitude')
    except json.JSONDecodeError as e:
        print(f"JSON decoding error: {e}")
        return JsonResponse({'error': f'Invalid JSON data'}, status=400)

    if latitude_input is None or longitude_input is None:
        return JsonResponse({'error': 'Latitude and longitude values are required.'}, status=400)
    
    try:
        latitude = float(latitude_input)
        longitude = float(longitude_input)
    except ValueError as e:
        print(f"Coordinate conversion error: {e}")
        return JsonResponse({'error': f'Latitude and longitude must be valid numbers'}, status=400)
    
    data = get_data()

    # Get three closest bus stops with user location
    three_stops_df = three_stops_finder(data['all_unique_stops_df'], latitude, longitude)
    
    # Get all possible stops from origin stops
    all_stops = all_stop_finder(three_stops_df, data['all_unique_stops_df'])

    # Get all possible POI from all stops
    poi_df = poi_getter(data['filtered_poi_df'], all_stops)

    # Format the response
    response = {
        "stops": [],
        "pois": [],
    }
    for _, row in all_stops.iterrows():        
        stop = {
            'latitude': row['stop_lat'],
            'longitude': row['stop_lon'],
            'stop_name': row['stop_name'],
            'headsign': row['trip_headsign'],
        }

        response['stops'].append(stop)

    for _, row in poi_df.iterrows():
        poi = {
            'latitude': row.geometry.y,
            'longitude': row.geometry.x,
            'stop_name': row['stop_name'],
            'route_id': row['route_id'],
            'name': row['name'],
            'amenity': row['amenity'],
            'icon': row['icon'],
            'color': row['color'],
        }
        response['pois'].append(poi)

    return JsonResponse(response)
