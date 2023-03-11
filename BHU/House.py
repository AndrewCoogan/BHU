#type:ignore
from typing import Literal, Tuple
from datetime import datetime
import numpy as np

class House():
    '''
    This is going to be the class that houses (hehe) all the house data. Each house will have its own instance.
    When we use the API, there is a lot of data reutned nested in a number of dictionaries. This will take the 'juicy' bit.
    The idea for this class is that it will hold all the needed info for:
         1) the GUI, address, google street view, other photos. This will probably be a flask application to start, but we are 
            far from even thinking about that.
         2) the MODEL, tags, list_prices, other flags. What if we created a word cloud and have the user select key words for 
            their house until they have selected some flat number or % contribution to model from the tags TBD. There will be 
            dates there, we will use days old (or something similar) for the model training, while the actual took will use zero, 
            as the user is entering 100% correct info. This may or may not be a good idea, as it might have unintended 
            implications within the model.

    Interior functions:
        Date Cleaning
        Location Cleaning
        Description Cleaning
    '''
    def __init__(self, 
            listing : dict,
            user_house : bool = False
        ):

        self.user_house : bool = user_house
        self.user_home_stats : dict = {}
        self.walk_score = np.nan

        if user_house:
            # Convert this to what we need for the feature generation and anything below.
            self._convert_user_home(listing)
            return

        self.reference_info = { # This is stuff not going into the model
            'id' : listing.get('property_id', ''),
            'photos' : 'to be added'
        }

        self.raw_listing : dict = listing
        self.raw_last_update : str = listing.get('last_update_date')
        self.raw_list_date : str = listing.get('list_date') or listing.get('sold_date')
        self.tags : list = listing.get('tags', [])
        self.status : Literal['sold', 'for_sale', 'NO_STATUS'] = listing.get('status', 'NO_STATUS')

        self.price : Tuple[int, float] = max(
            (listing.get('list_price') or 0), (listing.get('description', {}).get('list_price') or 0)
            ) if self.status == 'for_sale' else max(        
            (listing.get('sold_price') or 0), (listing.get('description', {}).get('sold_price') or 0)
            )

        self.new_construction : bool = listing.get('flags', {}).get('is_new_construction', False) or False

        self.raw_location : dict = listing['location']
        self.raw_description : dict = listing['description']

        self._clean_dates()
        self._clean_location()
        self._clean_description()

        # This is going to be used to store stuff in the future.
        self.future_stats = {}
        self.features = {}

    def __repr__(self) -> str:
        if self.user_house:
            return f'This is your home silly, {self.address}.' 
        return f'{self.reference_info["address"]}, {self.reference_info["city"]} {self.reference_info["state"]}'
        
    def _query_price_API(self, id : Tuple[int, str]) -> dict:
        property_value = get_PropertyValue(property_id = id)

        try:        
            estimate = pv['data']['current_values'][0]['estimate']
        except:
            estimate = None

        # We are going to get this into a shape that will be rendered in Chart.js
        output = {'estimate' : estimate}

        for metric in ['historical_values', 'forecasted_values']:
            values = property_value.get('data', {}).get(metric)
            metric_dict = {}

            if not values:
                for source in values:
                    data_source = source.get('source', {}).get('name') or 'UNKNOWN'
                    metric_dict[data_source] = [
                        (d.get('date') or '12-31-2000', d['estimate'] or 0) for d in source.get('estimates')
                    ]

            output.update({
                metric : metric_dict
            })

        '''
        This is going to be a big part of the Flask graphs, so want to be clear on what this is.
        output = {
            'estimate' = some number,
            'historical_values' = dict {
                    data_source_n = (date, value) for n in data_sources (usually three)
            },
            'forecasted_values' = dict {
                    data_source_n = (date, value) for n in data_sources (usually three)
            }
        }
        '''

        return output

    def _convert_user_home(self, user_home) -> None:
        '''
        So, the objective of this is just get the user home in a spot that we can feed it into our model.
        If we end up adding features, this is where we need to do that.
        '''
        property_details = user_home.get('data', {}).get('property_detail')

        if property_details is None:
            raise Exception('User home data is empty.')
        
        user_home_id = property_details.get('forwarded_mpr_ids')
        if isinstance(user_home_id, list):
            user_home_id = user_home_id[0]

        user_home_id_str = str(user_home_id)
        
        if user_home_id_str != 'None':
            self.user_home_stats.update(
                self._query_price_API(user_home_id_str)
            )

        prop_common = property_details.get('prop_common', {})
        features = property_details.get('features',{})
        public_records = property_details.get('public_records', [{}])[0]
        address = property_details['address']
        price_history = property_details['price_history']
        neighborhoods = property_details.get('neighborhoods', [{}])[0]

        num_garage = 0
        garage_details = list(filter(lambda l: l['category'].startswith('Garage'), features))
        if len(garage_details) > 0:
            for gd in garage_details[0]['text']:
                g_split = gd.split(':')
                if 'garage space' in g_split[0].lower():
                    num_garage = int(g_split[1])

        non_zero_price_history = [p for p in price_history if (p.get('price', 0) or 0) != 0]

        if not len(non_zero_price_history):
            most_recent_price = 0
        else:
            most_recent_price = max(non_zero_price_history, key=lambda d: d.get('date', '0')).get('price')

        self.reference_info = {'id' : property_details.get('id', 'USER_PID_MISSING')}
        self.status = 'sold'
        self.list_date_delta = 0
        self.last_update_delta = 0
        self.baths_full = int(prop_common.get('bath_full', 0) or 0)
        self.baths_3qtr = int(prop_common.get('bath_3qtr', 0) or 0)
        self.baths_half = int(prop_common.get('bath_half', 0) or 0)
        self.baths_1qtr = int(prop_common.get('bath_1qtr', 0) or 0)
        self.year_built = int(prop_common.get('year_built') or 1950)
        self.lot_sqft = int(prop_common.get('lot_sqft') or 0)
        self.sqft = int(prop_common.get('sqft') or 0)
        self.garage = num_garage or 0
        self.stories = public_records.get('stories', 1) or 1
        self.beds = public_records.get('beds') or 1
        self.bath = prop_common.get('bath') or 1
        self.tags = property_details.get('search_tags') or []
        self.new_construction = False
        self.future_stats = {'distance_from_user_home' : 0}
        self.lat_long = (address.get('location', {}).get('lat', 0), address.get('location', {}).get('lon', 0))
        self.lat_long_winz = self.lat_long
        self.address = address.get('line')
        self.price = most_recent_price

        if 'city' not in neighborhoods.keys():
            raise Exception('User home is missing a City, and maybe a state.')
        
        if 'state_code' not in neighborhoods.keys():
            raise Exception('User home is missing a State')

        self.city = neighborhoods['city'].upper()
        self.state = neighborhoods['state_code'].upper()
        #self.neighborhoods = neighborhoods.get('name', '').upper()

        total_baths = self.baths_full + \
            0.75*self.baths_3qtr + \
            0.5 * self.baths_half + \
            0.25 * self.baths_1qtr

        if self.bath > total_baths:
            missing = self.bath - total_baths
            # We are going to make educated guesses here
            if missing >= 1:
                n_full = missing // 1
                self.baths_full += n_full
                missing -= n_full
            if missing >= 0.75:
                n_3qtr = missing // 0.75
                self.baths_3qtr += n_3qtr
                missing -= 0.75 * n_3qtr
            if missing  >= 0.5:
                n_half = missing // 0.5
                self.baths_half += n_half
                missing -= 0.5 * n_half
            if missing >= 0.25:
                self.baths_1qtr += missing // 0.25

        return
    
    def _convert_date(self, date : str) -> datetime:
        return datetime.strptime(date, '%Y-%m-%d')
    
    def _clean_dates(self) -> None:
        last_update_date_parsed = self.raw_last_update.split('T')
        list_date_parsed = '' if self.status == 'sold' else self.raw_list_date.split('T')
        self.last_update = self._convert_date(last_update_date_parsed[0]) if len(last_update_date_parsed) == 2 else None
        self.list_date = self._convert_date(list_date_parsed[0]) if len(list_date_parsed) == 2 else None
        self.last_update_delta = None if self.last_update is None else max((datetime.now() - self.last_update).days, 0)
        self.list_date_delta = None if self.list_date is None else max((datetime.now() - self.list_date).days, 0)
        return
        
    def _clean_location(self) -> None:
        self.reference_info.update({
            'address' : self.raw_location.get('address', {}).get('line') or 'No Address Provided by API',
            'zip_code' : self.raw_location.get('address', {}).get('postal_code') or '00000',
            'google_map_street_view' : self.raw_location.get('street_view_url'),
            'fips_code' : self.raw_location.get('county', {}).get('fips_code'),
            'county' : self.raw_location.get('county', {}).get('name'),
        })

        self.city = (self.raw_location.get('address', {}).get('city', '') or '').upper()
        self.state = (self.raw_location.get('address', {}).get('state_code', '') or '').upper()

        lat_long = self.raw_location.get('address', {}).get('coordinate')
        self.lat_long = (None, None) if lat_long in [None, {}] else (lat_long.get('lat'), lat_long.get('lon')) 
        self.address = self.reference_info['address'] + ' ' +\
            self.city + ' ' +\
            self.state + ' ' +\
            self.reference_info['zip_code']
        return
    

    def _clean_description(self) -> None:
        self.baths_full = self.raw_description.get('baths_full') or 0
        self.baths_3qtr = self.raw_description.get('baths_3qtr') or 0
        self.baths_half = self.raw_description.get('baths_half') or 0
        self.baths_1qtr = self.raw_description.get('baths_1qtr') or 0
        self.year_built = self.raw_description.get('year_built') or 0
        self.lot_sqft = self.raw_description.get('lot_sqft') or 0
        self.sqft = self.raw_description.get('sqft') or 0
        self.garage = self.raw_description.get('garage') or 0
        self.stories = self.raw_description.get('stories') or 1
        self.beds = self.raw_description.get('beds') or 0
        self.type = self.raw_description.get('type') or 'NONE'
        return