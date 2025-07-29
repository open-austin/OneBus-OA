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
