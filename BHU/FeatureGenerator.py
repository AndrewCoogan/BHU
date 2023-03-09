#type:ignore

from BHU.House import House
from BHU.GeoData import GeoData
from BHU.API_Calls import *
from BHU.WalkScoreModel import WalkScoreModel
from typing import Tuple, List
from math import radians, cos, sin, asin, sqrt, atan2
from scipy.stats.mstats import winsorize
from sklearn.impute import SimpleImputer
import numpy as np

# This will take in house and geo, and generate stats based on what is fed, and then can output a dictionary that 
# can easily be converted into a pd.Dataframe for the pipeline.
class FeatureGenerator():
    def __init__(self, 
        houses    : List[dict], 
        gd        : GeoData,
        user_home : dict
        ):

        '''
        This is the first step in the pipeline.
        This will import a list of houses, the geo data, and the user house
        '''
        
        self.houses = []
        self._unique_property_ids = []

        for h in houses:
            if h['property_id'] not in self._unique_property_ids:
                self._unique_property_ids.append(h['property_id'])
                self.houses.append(House(h))

        self.gd = gd
        self.user_home = user_home

        # I need to convert user house to the right format.
        self.user_home_formatted = House(self.user_home, user_house = True)

        # I need to keep in mind here that this is a list of houses
        self.houses = list(map(self._generate_distance_between_coordinates, self.houses))
        self.houses = list(filter(self._remove_bad_listings, self.houses))
        self._generate_winsorized_coordinates()

        self.features = list(map(self._generate_features, self.houses))
        self.targets = list(map(self._generate_targets, self.houses))
        self.user_features = self._generate_features(self.user_home_formatted)
        self.user_target = self._generate_targets(self.user_home_formatted)

    def __repr__(self) -> str:
        return "This is a feature generator."
    
    def _clean_walk_score_value(self, score : int) -> int:
        try:
            score_min = max([score, 0])
            score_max = min([score, 100])
            clean_score = min([score_min, score_max])
        except:
            clean_score = np.nan
        return clean_score

    def _get_walk_score(self, h) -> House:
        # If this is tripped, we know we do not have a model, so generate it.
        walk_score_raw = get_WalkScore(
            address=f'{h.city} {h.state}',
            lat=h.lat_long[0],
            lon=h.lat_long[1]
        )

        return {
            'walk_score' : self._clean_walk_score_value(walk_score_raw.get('walkscore')),
            'transit_score' : self._clean_walk_score_value(walk_score_raw.get('transit', {}).get('score')),
            'bike_score' : self._clean_walk_score_value(walk_score_raw.get('bike', {}).get('score'))
        }

    def _sync_walk_score(self) -> None:
        # If I want to multithread, this is where we need to do it.
        # If I do this, I am going to lose order, so maybe return the property id?

        user_ws = self._get_walk_score(self.user_home_formatted)
        self.user_home_formatted.walk_score = user_ws.get('walk_score') or 50

        for h in self.houses:
            ws = self._get_walk_score(h)
            h.walk_score = ws.get('walk_score') or 50

        return

    def _generate_distance_between_coordinates(self, h : House) -> House:
        query_loc : Tuple[float, float] = h.lat_long

        if None in query_loc:
            h.future_stats['distance_from_user_home'] =  None
            h.future_stats['angle_from_user_home'] = None
            return h

        lat1 = radians(self.user_home_formatted.lat_long[0])
        lon1 = radians(self.user_home_formatted.lat_long[1])
        lat2, lon2 = radians(query_loc[0]), radians(query_loc[1])

        # Haversine formula
        dlon, dlat = lon2 - lon1, lat2 - lat1
        a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2

        c = 2 * asin(sqrt(a))
        r = 3956 # Radius of earth: 6371 kilometers / 3956 miles
        h.future_stats['distance_from_user_home'] =  c * r
        h.future_stats['angle_from_user_home'] = atan2((lat2 - lat1), (lon2 - lon1))
        return h

    def _remove_bad_listings(self, h : House) -> bool:
        if h.lot_sqft > 1_000_000:
            return False
        if sum([int(h.baths_full), int(h.baths_3qtr), int(h.baths_half), int(h.baths_1qtr)]) == 0:
            return False
        if int(h.beds) == 0:
            return False
        if int(h.price or 0) > 5_000_000:
            return False
        if int(h.lot_sqft or 0) > 15_000:
            return False
        return True

    def _generate_winsorized_coordinates(self) -> None:
        '''
        This is going to take some of the lifting off of the pipelines, and get good data here.
        Step 1: Winsorise
        Step 2: Impute
        '''
        lat_list = [h.lat_long[0] for h in self.houses]
        long_list = [h.lat_long[1] for h in self.houses]

        lat_list = np.array(lat_list, dtype=np.float32)
        long_list = np.array(long_list, dtype=np.float32)

        lat_list_winsorized = winsorize(lat_list, (0.05, 0.05), nan_policy='omit')
        long_list_winsorized = winsorize(long_list, (0.05, 0.05), nan_policy='omit')

        si = SimpleImputer(strategy="mean")
        lat_list_winsorized = si.fit_transform(np.array(lat_list_winsorized).reshape(-1,1))
        long_list_winsorized = si.fit_transform(np.array(long_list_winsorized).reshape(-1,1))
        
        for h, lat, long in zip(self.houses, lat_list_winsorized, long_list_winsorized):
            h.lat_long_winz = (lat, long)

        return


    def _generate_features(self, h : House) -> dict:
        h.features = {
            'Property_ID' : h.reference_info.get('id'),
            'Address' : h.reference_info.get('address'),
            'Status' : h.status,
            'Days_listed' : int(h.list_date_delta or 0),
            'Days_updated' : int(h.last_update_delta or 0),
            'baths_full' : int(h.baths_full),
            'baths_3qtr' : int(h.baths_3qtr),
            'baths_half' : int(h.baths_half),
            'baths_1qtr' : int(h.baths_1qtr),
            'year_built' : int(h.year_built),
            'lot_sqft' : int(h.lot_sqft),
            'sqft' : int(h.sqft),
            'garage' : int(h.garage),
            'stories' : int(h.stories),
            'beds' : int(h.beds),
            'tags' : h.tags or [],
            'new_construction' : bool(h.new_construction),
            'distance_to_home' : h.future_stats.get('distance_from_user_home'),
            'lat_winz' : h.lat_long_winz[0],
            'long_winz' : h.lat_long_winz[1],
            'lat' : h.lat_long[0],
            'long' : h.lat_long[1],
        }
        
        return h.features
    
    def _generate_targets(self, h) -> int:
        return int(h.price or 0)