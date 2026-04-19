import json
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt

from api.apps import get_data
from api.util.bus_functions import closest_stops_finder, all_stop_finder
from api.util.poi_functions import poi_getter

@csrf_exempt # Disable CSRF verification. Since we're not dealing with users or authentication yet, this should be safe.
def determine_stops_and_pois(request):
    """
    Endpoint to determine the closest bus stops and points of interest (POI) based on user's location.
    Expects a POST request with JSON body containing latitude and longitude.
    Returns a JSON response with the closest bus stops and POIs.

    Sample request body:
    {
	    "latitude": "30.31431458225797",
        "longitude": "-97.73587186057428123"
    }
    """
    if request.method == 'OPTIONS':
        response = HttpResponse()
        response['Allow'] = 'POST,OPTIONS'
        add_cors_headers(response)
        return response

    if request.method != 'POST':
        return JsonResponse({'error': 'HTTP method not supported.'}, status=405)
    
    # Get and validate the latitude and longitude values from the request
    try:
        input_body = json.loads(request.body.decode('utf-8'))
        latitude_input = input_body.get('latitude')
        longitude_input = input_body.get('longitude')
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
    
    data_holder = get_data()

    # Get three closest bus stops with user location
    three_stops_df = closest_stops_finder(data_holder.all_unique_stops_df, latitude, longitude)
    
    # Get all possible stops from origin stops
    all_stops = all_stop_finder(three_stops_df, data_holder.all_unique_stops_df)

    # Get all possible POI from all stops
    poi_df = poi_getter(latitude, longitude, data_holder.filtered_poi_df, all_stops)

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
            'origin_stop': row['origin_stop']
        }

        response['stops'].append(stop)

    for _, row in poi_df.iterrows():
        poi = {
            'latitude': row.geometry.y,
            'longitude': row.geometry.x,
            # URL to easily open POI location in Google Maps. Reference: https://developers.google.com/maps/documentation/urls/get-started
            "map_url": f"https://www.google.com/maps/search/?api=1&query={row.geometry.y}%2C{row.geometry.x}",
            'stop_name': row['stop_name'],
            'route_id': row['route_id'],
            'num_stops_away': row['num_stops_away'],
            'name': row['name'],
            'amenity': row['amenity'],
            'amenity_category': row['amenity_category'],
            'icon': row['icon'],
            'color': row['color'],
        }
        response['pois'].append(poi)

    jsonResponse = JsonResponse(response)
    add_cors_headers(jsonResponse)

    return jsonResponse

def add_cors_headers(response):
    """
    Helper function to set CORS headers for the response.
    """
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Methods'] = 'POST,OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Content-Type'
    response['Access-Control-Allow-Credentials'] = 'false'
