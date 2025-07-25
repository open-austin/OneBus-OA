import folium
import os
from pathlib import Path


def map_maker(lat,lon,all_possible_stops, poi_df):
    '''
    Helper function to create the folium make, deletes current map made and re makes it with new data
    map will automatically be zoomed into the users location

    Arguments:
        - origin_stop: bus stop name of the origin bus stop
        - lat: current latitude of the user 
        - lon: current longitude of the user
        - all_busstops: all bus stops that user can get to given that bus number
        - poi_df: dataframe of POIs retrieved from OSMNX
        - stop_times_df: dataframe of stops_times.txt from GTFS data

    Returns:
        - map.html: folium map that is zoomed in
    '''


    # 1. Get the project root path (assuming mapping.py is in utils/)
    current_dir = Path(__file__).parent  # Gets utils/ folder
    project_root = current_dir.parent    # Goes up one level to project_root
    print(project_root)
    
    # 2. Define the full template path
    template_path = project_root / "templates" / "map.html"
    print(template_path)
    

    # Clear existing map HTML file if it exists
    if os.path.exists(template_path):
        os.remove(template_path)  # This is more direct than writing an empty file

    map = folium.Map(location=[lat, lon], zoom_start=12)
    print("map just got created")

    for index, row in all_possible_stops.iterrows():
        bus_stop_lat = row['stop_lat']
        bus_stop_lon = row['stop_lon']
        stop = row['stop_name']
        headsign = row['trip_headsign']
        
        popup_text = folium.Html(f"Bus Station: {stop} heading towards {headsign}", script = True)
        
        # Add a marker for each row to the map
        folium.Marker(
            location = [bus_stop_lat, bus_stop_lon], 
            popup=folium.Popup(popup_text, parse_html=True, max_width=300),
            icon=folium.Icon(color='black' ,icon='bus', prefix='fa')).add_to(map)

    # map.save(str(template_path))  # Test saving to known location    print("map has been saved")
    print(poi_df)
    # Iterate over the rows of the DataFrame
    for index, row in poi_df.iterrows():
        poi_lat = row.geometry.y
        poi_lon = row.geometry.x
        poi_busstop = str(row['stop_name'])
        poi_bus = row['route_id']
        poi_name = row['name']
        first_stop_number = poi_df[(poi_df['origin stop'] == True) & (poi_df['route_id'] == poi_bus)]['stop_sequence']
        # print(first_stop_number)
        # num_stops = row['stop_sequence'] - row['first_stop_number']
        poi_amenity = row['amenity']
        icon_name = row['icon']
        icon_color = row['color']
        
        popup_text = folium.Html(f"Take bus {poi_bus} for stops <br> Closest bus stop: {poi_busstop}.<br>Name of POI: {poi_name}.<br>Type of POI: {poi_amenity}.<br>.", script = True)

        # Add a marker for each row to the map
        folium.Marker(
            location = [poi_lat, poi_lon], 
            popup=folium.Popup(popup_text, parse_html=True, max_width=300),
            icon=folium.Icon(color=icon_color ,icon=icon_name, prefix='fa')).add_to(map)
    
    try:
        map.save(str(template_path))
        print("Map saved successfully.")
    except Exception as e:
        print("Error saving map:", e)

    # folium.Marker(
    # location = [lat, lon], 
    # popup='Home',
    # icon=folium.Icon(color='green' ,icon='home', prefix='fa')).add_to(map)
    

    # 3. Ensure directory exists
    template_path.parent.mkdir(exist_ok=True)
    print("Temp save successful:", Path(template_path).exists())

    # Check final save path
    print(f"Target path exists: {template_path.exists()}")
    print(f"Parent writable: {os.access(template_path.parent, os.W_OK)}")

    # 4. Save the file
