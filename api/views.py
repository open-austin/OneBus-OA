import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from api.apps import get_data
from api.bus_models import three_stops_finder, all_stop_finder
from api.poi_models import poi_getter

# TODO: Figure out how to refactor into different directories without hitting this error:
# ImportError: attempted relative import beyond top-level package

@csrf_exempt # Disable CSRF verification. Since we're not dealing with users or authentication yet, this should be safe.
def test(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'HTTP method not supported.'}, status=400)
    
    # Get and validate the latitude and longitude values from the request
    try:
        data = json.loads(request.body.decode('utf-8'))
        latitude_input = data.get('latitude')
        longitude_input = data.get('longitude')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)

    if latitude_input is None or longitude_input is None:
        return JsonResponse({'error': 'Latitude and longitude values are required.'}, status=400)
    
    try:
        latitude = float(latitude_input)
        longitude = float(longitude_input)
    except ValueError:
        return JsonResponse({'error': 'Latitude and longitude must be valid numbers.'}, status=400)
    
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
    for index, row in all_stops.iterrows():        
        bus_stop = {
            'latitude': row['stop_lat'],
            'longitude': row['stop_lon'],
            'stop_name': row['stop_name'],
            'headsign': row['trip_headsign'],
        }

        response['stops'].append(bus_stop)

    # TODO: Add POI data to response
    # for index, row in poi_df.iterrows():
    #     poi_lat = row.geometry.y
    #     poi_lon = row.geometry.x
    #     poi_busstop = str(row['stop_name'])
    #     poi_bus = row['route_id']
    #     poi_name = row['name']
    #     first_stop_number = poi_df[(poi_df['origin stop'] == True) & (poi_df['route_id'] == poi_bus)]['stop_sequence']
    #     # print(first_stop_number)
    #     # num_stops = row['stop_sequence'] - row['first_stop_number']
    #     poi_amenity = row['amenity']
    #     icon_name = row['icon']
    #     icon_color = row['color']
        
    #     popup_text = folium.Html(f"Take bus {poi_bus} for stops <br> Closest bus stop: {poi_busstop}.<br>Name of POI: {poi_name}.<br>Type of POI: {poi_amenity}.<br>.", script = True)

    #     # Add a marker for each row to the map
    #     folium.Marker(
    #         location = [poi_lat, poi_lon], 
    #         popup=folium.Popup(popup_text, parse_html=True, max_width=300),
    #         icon=folium.Icon(color=icon_color ,icon=icon_name, prefix='fa')).add_to(map)

    return JsonResponse(response)
