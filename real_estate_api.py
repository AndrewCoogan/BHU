# This is going to be where I keep all the API endpoints.

# type: ignore

from retrying import retry
from ediblepickle import checkpoint
from beartype._decor.decormain import beartype
from beartype.typing import Tuple, Union
from typing import Literal, List
from datetime import datetime
from urllib.parse import quote

import requests
import html
import string

from sklearn.base import TransformerMixin, BaseEstimator
from math import radians, cos, sin, asin, sqrt, atan2

import keys as k

DISABLE_WALKSCORE = False
RESULTS_PER_REQUEST_LIMIT = 42
USREALESTATE_API_HEADERS = {
    "X-RapidAPI-Key": k.getKeys()['USRealEstate'],
    "X-RapidAPI-Host": "us-real-estate.p.rapidapi.com"
}

@beartype
@retry(stop_max_attempt_number=5)
@checkpoint(key=lambda args, kwargs: quote(args[0]) + '.pkl', work_dir='Saved Results/LocationSuggest/')
def get_LocationSuggest(
        search_keyword : str, 
        return_all     : bool = False
    ) -> dict:

    url = "https://us-real-estate.p.rapidapi.com/location/suggest"

    querystring = {
        "input":search_keyword
    }

    response = requests.request("GET", url, headers=USREALESTATE_API_HEADERS, params=querystring)
    response_json = response.json()

    return response_json if return_all else response_json['data'][0]

@beartype
@retry(stop_max_attempt_number=5)
@checkpoint(key=lambda args, kwargs: quote(args[0]) + '.pkl', work_dir='Saved Results/PropertyDetail/')
def get_PropertyDetail(
        property_id : str
    ) -> dict:

    url = "https://us-real-estate.p.rapidapi.com/v2/property-detail"

    querystring = {
        "property_id":property_id
    }

    response = requests.request("GET", url, headers=USREALESTATE_API_HEADERS, params=querystring)
    return response.json()

@beartype
@retry(stop_max_attempt_number=5)
@checkpoint(key=lambda args, kwargs: quote(args[0]) + '.pkl', work_dir='Saved Results/PropertyValue/')
def get_PropertyValue(
        property_id : str
    ) -> dict:

    url = "https://us-real-estate.p.rapidapi.com/for-sale/home-estimate-value"

    querystring = {
        "property_id":property_id
    }

    response = requests.request("GET", url, headers=USREALESTATE_API_HEADERS, params=querystring)
    return response.json()

def get_Properties(
        parent_pid    : str,
        market_status : Literal['for_sale','sold'],
        city_state    : Tuple[None, Tuple[str, str]] = None,
        zip_code      : Tuple[None, str] = None,
        n_results     : int = 1000,
        property_type : str = 'single_family',
        offset        : int = 0,
        verbose       : bool = False
    ) -> dict:
    
    '''
    This function will return properties, either recently sold or currently on the market, 
    within a specific city and state or zip code.
    Required fields: market_status, EITHER city_state or zip_code.

    There is something strange about the way this is setup where checkpointing fails, 
    and am not sure why that is happening.
    For now, I will be checkpointing the parent function.

    Although offset might seem a bit strange to pass in here,I will be checking that there is enough samples requested.
    The first round of outputs will dictate if we need to query more sold/for sale homes.
    '''

    if city_state is None and zip_code is None:
        raise Exception('Either city_state or zip_code is required.')

    if city_state is not None and zip_code is not None:
        raise Exception('Both city_state and zip_code can not be populated.')

    '''
    Other query string parameters:
    sort = (default: relevant)|newest|lowest_price|highest_price|open_house_date|
                                price_reduced_date|largest_sqft|lot_size|sold_date
    price_min/max = $ USD
    beds_min/max = #
    bath_min/max = #
    property_type = multi_family|single_family|mobile|land|farm (I think we should just use : 'single_family')
    '''

    querystring = {
        "offset":str(offset),
        "limit":str(RESULTS_PER_REQUEST_LIMIT),
        "sort":"sold_date" if market_status == 'sold' else "newest",
        "property_type":property_type,
        "min_price":100
    }

    # This will be looking at city, state
    if zip_code is None:
        if market_status == 'sold': # Sold city, state
            url = "https://us-real-estate.p.rapidapi.com/sold-homes"
        else: # For sale city, state
            url = "https://us-real-estate.p.rapidapi.com/v2/for-sale"

        querystring.update({
            "state_code":city_state[1],
            "city":city_state[0]
        }) 
    else:
        if market_status == 'sold': # Sold zip code
            url = "https://us-real-estate.p.rapidapi.com/v2/sold-homes-by-zipcode"
            del querystring['min_price']
        else: # For sale zip code
            url = "https://us-real-estate.p.rapidapi.com/v2/for-sale-by-zipcode"

        querystring.update({
            "zipcode":zip_code,
        })

    geo_to_return, houses_to_return = query_url(
        n_results, 
        verbose, 
        querystring, 
        url, 
        zzzparent_pid = parent_pid,
        zzzzipcode = querystring.get('zipcode', '00000'),
        zzzcity = querystring.get('city', 'XXXXX'),
        zzzsort = querystring.get('sort')
    )

    return {
        'houses' : houses_to_return,
        'geo' : geo_to_return
    }

@beartype
@retry(stop_max_attempt_number=5)
@checkpoint(key=string.Template('${zzzparent_pid}_${zzzzipcode}_${zzzcity}_${zzzsort}.pkl'), \
    work_dir='Saved Results/Properties/')
def query_url(
        n_results : int, 
        verbose : bool, 
        querystring : dict, 
        url : str,
        zzzparent_pid : str,
        zzzzipcode : str,
        zzzcity : str,
        zzzsort : str
    ) -> Tuple[dict, List[dict]]:
    '''
    Honestly, this was just made the make the get_Properties function just a little less busy.
    When looking at pulling houses at the API level, we need a url, query string, the number of results, and a 
    header for the request. This takes all of that and can return properties as expected for the remsinder of the 
    program.
    '''

    v2 : bool = 'v2' in url

    response = requests.request("GET", url, headers=USREALESTATE_API_HEADERS, params=querystring).json()
    total_houses_available = response['data']['home_search']['total'] if v2 else response['data']['total']
    total_houses_in_request = response['data']['home_search']['count'] if v2 else response['data']['count'] 

    total_houses_available = int(total_houses_available)
    total_houses_in_request = int(total_houses_in_request)

    if n_results is None:
        n_results = total_houses_available

    if verbose:
        print(f'Returning {str(min(total_houses_available, n_results))} \
                out of a possible {str(total_houses_available)}.')

    geo_to_return = response['data']['geo'] if v2 else {}
    houses_to_return = response['data']['home_search']['results'] if v2 else response['data']['results']

    houses_remaining = min(total_houses_available, n_results) - len(houses_to_return)

    while houses_remaining > 0:
        querystring['offset'] = str(int(querystring['offset']) + RESULTS_PER_REQUEST_LIMIT)
        querystring['limit'] = str(min(RESULTS_PER_REQUEST_LIMIT, houses_remaining))

        response = requests.request("GET", url, headers=USREALESTATE_API_HEADERS, params=querystring).json()
        if v2:
            houses_to_return.extend(response['data']['home_search']['results'])
            houses_remaining -= len(response['data']['home_search']['results'])
        else:
            houses_to_return.extend(response['data']['results'])
            houses_remaining -= len(response['data']['results'])

    return geo_to_return, houses_to_return

@beartype
def get_UserHome(
        user_input : str
    ) -> dict[dict, dict]:

    location_suggest = get_LocationSuggest(user_input, return_all=True)
    locations = location_suggest.get('data')

    if locations is None:
        raise Exception('Nothing returned based on query.')

    filtered_locations = [l for l in locations if l.get('_score', 0) > 20 and l.get('full_address') is not None]

    if len(filtered_locations) > 1:
        print(f'We have found {len(filtered_locations)} plausible locations for your entry:')
        
        for i, e in enumerate(filtered_locations):
            print(f'#{i+1} : {e["full_address"][0]}')
        
        house_choice : str = html.escape(
            input('Do any of these look good? If yes, enter the # or enter "no":')
        )

        if house_choice == 'no':
            raise Exception('No valid house located.')

        try:
            return filtered_locations[int(house_choice.strip()) - 1]
        except:
            raise Exception(f'Your selection was not acceptable: {house_choice}')
    
    return filtered_locations[0]

def get_HousesOfInterest(
    address              : dict, 
    n                    : int = 84, 
    listed_to_sold_ratio : float = 0.3,
    verbose              : bool = False
) -> dict:
    '''
    This function is going to take an address and retrun a dictionary of geo / results. This is going to be a gloified 
    wrapper of the API call functions, aggregating the outputs.

    address - This is a valid address, expected to be sourced from the get_UserHome.

    n - How many overall results are there going to be.
    
    listed_to_sold_ratio - This model will be a combination of listed and sold houses. T
        his will be dictated by overall reasults, this may or may not be removed based on how it works 
        when were futher down the line.

    This function is currently implemented to only look at the city_state queries. 
    This might be ammended in future iterations to get some focus on the strictly local samples,
    but as of right now, zip_codes are not utilized.
    '''
    n_listed = int(n * listed_to_sold_ratio)
    n_sold = int(n) - n_listed

    parent_pid = address.get('property_id')

    if not parent_pid:
        raise Exception('User house does not have a valid property id.')
    
    # I am just going to go with city (for now)
    # TODO: Future enhancement, be able to pass a ratio of zip code and city, but not sure given I measure distance later.

    listed_homes = get_Properties(
        parent_pid=parent_pid,
        market_status='for_sale',
        city_state=(address.get('city'), address.get('state_code')),
        n_results=n_listed
    )

    sold_homes = get_Properties(
        parent_pid=parent_pid,
        market_status='sold',
        city_state=(address.get('city'), address.get('state_code')),
        n_results=n_sold
    )

    if len(listed_homes['houses']) < n_listed:
        new_n_results = n_listed-len(listed_homes['houses']) 
        if verbose:
            print(f'Shortfall in listed houses detected, appending {str(new_n_results)} of current listing to results.')

        sold_homes_v2 = get_Properties(
            parent_pid=parent_pid,
            market_status='sold',
            city_state=(address.get('city'), address.get('state_code')),
            n_results=n_listed - len(listed_homes['houses']),
            offset=new_n_results
        )

        sold_homes['houses'].extend(sold_homes_v2['houses'])

    if len(sold_homes['houses']) < n_sold:
        new_n_results = n_sold-len(sold_homes['houses'])
        if verbose:
            print(f'Shortfall in listed houses detected, appending {str(new_n_results)} of current listing to results.')

        listed_homes_v2 = get_Properties(
            parent_pid=parent_pid,
            market_status='for_sale',
            city_state=(address.get('city'), address.get('state_code')),
            n_results=n_listed,
            offset=new_n_results
        )
        
        listed_homes['houses'].extend(listed_homes_v2['houses'])

    # Geo will be the same for both unless one returns a zip_code not in the other, but if that happens 
    # it will be a small population.
    
    # NOTE: Listed home always goes first as long as there is a non zero listed home query, which are both v2, so the 
    # Geo not available in v1 issue should not be an problem.
    listed_homes['houses'].extend(sold_homes['houses'].copy())

    return listed_homes

@beartype
@retry(stop_max_attempt_number=5)
@checkpoint(key=string.Template('${lat}_${lon}.pkl'), work_dir='Saved Results/WalkScore/')
def get_WalkScore(
    address : str,
    lat : float,
    lon : float
    ) -> dict:

    querystring = {
        "format":'json',
        "address":quote(address),
        "lat":lat,
        "lon":lon,
        "transit":1,
        "bike":1,
        "wsapikey" : k.getKeys()['WalkscoreKey']
    }

    url = "https://api.walkscore.com/score"

    response = requests.request("GET", url, params=querystring)
    return response.json()
    
class geo_data():
    '''
    This is going to be used to organize the meta information about each query.
    I need to think where it is most appropriate to do this.
    '''
    def __init__(self, 
            stats : dict
        ):
        
        self.zip_info = self._parse_areas(stats.get('recommended_zips', {}).get('geos'))
        self.city_info = self._parse_areas(stats.get('recommended_cities', {}).get('geos'))
        self.county_info = self._parse_areas(stats.get('recommended_counties', {}).get('geos'))
        self.neighborhood_info = self._parse_areas(stats.get('recommended_neighborhoods', {}).get('geos'))
        self.market_stats = self._parse_statistics(stats.get('geo_statistics', {}).get('housing_market'))

    def __repr__(self) -> str:
        return f'Looking in {self.city_info}.'

    def _parse_areas(self, geos : dict) -> dict:
        return None if geos is None else {
            v.get(v.get('geo_type', 'slug_id'), '_parse_areas_FAILED') : {
                'slug_id' : v.get('slug_id'),
                'median_listing_price' : v.get('geo_statistics', {}).\
                    get('housing_market', {}).\
                    get('median_listing_price'),
                'state_code' : v.get('state_code'),
                'city_code' : v.get('city'),
                'geo_type' : v.get('geo_type')
            } for v in geos
        }
    
    def _parse_statistics(self, geo_stats : dict) -> dict:
        return None if geo_stats is None else {
            'median_days_on_market' : geo_stats.get('median_days_on_market'),
            'median_sold_price' : geo_stats.get('median_sold_price'),
            'median_price_per_sqft' : geo_stats.get('median_price_per_sqft'),
            'median_listing_price' : geo_stats.get('median_listing_price'),
            'month_to_month_metrics' : geo_stats.get('month_to_month'),
            'by_prop_type' : {
                ht.get('type') : {
                    k : v for k, v in ht.get('attributes', {}).items()
                } for ht in geo_stats.get('by_prop_type', {})
            }
        }

class house():
    '''
    This is going to be the class that houses (hehe) all the house data. Each house will have its own instance.
    When we use the API, there is a lot of data reutned nested in a number of dictionaries. This will take the 'juicy' bit.
    The idea for this class is that it will hold all the needed info for:
         1) the GUI, address, google street view, other photos. This will probably be a flask application to start, but we are 
            far from even thinking about that.
         2) the MODEL, tags, list_prices, other flags. What if we created a word cloud and have the user select key words for 
            their house until they have selected some flat number or % contribution to model from the tags TBD. There will be 
            dates there, we will use days old (or something similar) for the model training, while the actual took will use zero, 
            as the user is entering 100% correct info. This may or may not be a good idea, as it might have unintended implications
            within the model.

    Interior functions:
        Date Cleaning
        Location Cleaning
        Description Cleaning
    '''
    def __init__(self, 
            listing : dict,
            user_house : bool = False
        ):

        if user_house:
            # Convert this to what we need for the feature generation and anything below.
            listing = self._convert_user_home(listing)
            return None

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

        self.walk_score_raw = {}
        if not DISABLE_WALKSCORE:
            self.walk_score_raw = get_WalkScore(
                address=self.address,
                lat=self.lat_long[0],
                lon=self.lat_long[1]
            )

        self.walk_score = self.walk_score_raw.get('walkscore')
        self.transit_score = self.walk_score_raw.get('transit', {}).get('score')
        self.bike_score = self.walk_score_raw.get('bike', {}).get('score')

        # This is going to be used to store stuff in the future.
        self.future_stats = {}
        self.features = {}

    def __repr__(self) -> str:
        return f'{self.reference_info["address"]}, {self.reference_info["city"]} {self.reference_info["state"]}'
        
    def _query_price_API(self, id : Tuple[int, str]) -> dict:
        pv = get_PropertyValue(str(id[0]))
        pv = pv.get('data', False)

        if not pv:
            return {}
        
        pass
        ### I need to parse this.

    def _convert_user_home(self, user_home) -> dict:
        '''
        This is going to be sort of obnoxous. The structure of the direct query for a property id is a different
        structure than if you query a list of sold/listed properties. I am going to convert it here to get what
        needs in the form thats expected for the rest of the class processing.

        ^^^ This guy was an idiot. We are just going to get whatever the feature generator is expecting and punt 
        the rest. I will just make the processing stop once this returns.
        '''
        details = user_home['data']['property_detail']
        transformed_user_home = {}

        id = details.get('forwarded_mpr_ids', ['']) or ['']
        transformed_user_home['property_id'] = id[0] # Is this safe?
        transformed_user_home['tags'] = details.get('search_tags', []) or []
        transformed_user_home['sold_price'] = None # FIX THIS
        transformed_user_home['new_construction'] = details.get('new_construction', False) or False
        transformed_user_home['status'] = 'sold'

        '''
        _clean_location is expecting a few things:
            ['last_update_date']
            ['sold_date'], this is just a choice to make.
        '''
        today = datetime.now().strftime("%Y-%m-%d")
        transformed_user_home['last_update_date'] = details.get('prop_common', {}).get('last_update', today)
        transformed_user_home['sold_date'] = details.get('sold_date')

        '''
        _clean_location is expecting a few things:
            ['location'] is a dict that contains:
                ['address'] - line, postal_code, state, city
                ['county'] - fips_code, name
                ['street_view_url'] - list of url's? Idk, leving placeholder there.
        '''

        transformed_user_home['location'] = {
            'address' : details.get('address', {}),
            'county' : {
                'county' : details.get('address', {}).get('county')
            },
            'street_view_url' : []
        }

        # Renaming b/c im lazy.
        transformed_user_home['location']['address']['coordinate'] = \
            transformed_user_home['location']['address']['location']


        '''
        _clean_description is expecting a few things:
            a bunch of stats about the house.
            I need to convert bed -> beds
            garage from string to int

        '''

        desc = details.get('public_records', [{}])[0]
        desc.update(details.get('prop_common', {}))

        for k, v in desc.items():
            if k == 'bed':
                desc['beds'] = v
            if k.startswith('bed_'):
                parsed = k.split('_')
                if len(parsed) == 1:
                    raise Exception(f'Error in translating user home to house class: {desc}')
                else:
                    desc[f'beds_{parsed[1]}'] = v
            if k == 'garage':
                desc['garage'] = 1 if int(v) > 1 else 0

        transformed_user_home['description'] = desc
        return transformed_user_home

    def _convert_date(self, date : str) -> datetime:
        return datetime.strptime(date, '%Y-%m-%d')
    
    def _clean_dates(self) -> None:
        last_update_date_parsed = self.raw_last_update.split('T')
        list_date_parsed = '' if self.status == 'sold' else self.raw_list_date.split('T')
        self.last_update = self._convert_date(last_update_date_parsed[0]) if len(last_update_date_parsed) == 2 else None
        self.list_date = self._convert_date(list_date_parsed[0]) if len(list_date_parsed) == 2 else None
        self.last_update_delta = None if self.last_update is None else max((datetime.now() - self.last_update).days, 0)
        self.list_date_delta = None if self.list_date is None else max((datetime.now() - self.list_date).days, 0)
        
    def _clean_location(self) -> None:
        self.reference_info.update({
            'address' : self.raw_location.get('address', {}).get('line'),
            'zip_code' : self.raw_location.get('address', {}).get('postal_code'),
            'state' : self.raw_location.get('address', {}).get('state'),
            'state_code' : self.raw_location.get('address', {}).get('state_code'),
            'google_map_street_view' : self.raw_location.get('street_view_url'),
            'fips_code' : self.raw_location.get('county', {}).get('fips_code'),
            'county' : self.raw_location.get('county', {}).get('name'),
            'city' : self.raw_location.get('address', {}).get('city'),
        })

        lat_long = self.raw_location.get('address', {}).get('coordinate')
        self.lat_long = (None, None) if lat_long in [None, {}] else (lat_long.get('lat'), lat_long.get('lon')) 
        self.address = self.reference_info['address'] + ' ' +\
            self.reference_info['city'] + ' ' +\
            self.reference_info['state_code'] + ' ' +\
            self.reference_info['zip_code']
    

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

# This will take in house and geo, and generate stats based on what is fed, and then can output a dictionary that 
# can easily be converted into a pd.Dataframe for the pipeline.
class FeatureGenerator(BaseEstimator, TransformerMixin):
    def __init__(self, 
        houses    : List[dict], 
        gd        : geo_data,
        user_home : house
        ):

        '''
        This is the first step in the pipeline.
        This will import a list of houses, the geo data, and the user house

         - Look at distances between coordinates, NOT ZIPCODES
        '''
        self.houses = []
        self._unique_property_ids = []

        for h in houses:
            if h['property_id'] not in self._unique_property_ids:
                self._unique_property_ids.append(h['property_id'])
                self.houses.append(house(h))

        self.gd = gd
        self.user_home = user_home

        self.user_home_lat_lon  = (
            self.user_home.get('centroid', {}).get('lat', 0),
            self.user_home.get('centroid', {}).get('lon', 0)
        )

        # I need to keep in mind here that this is a list of houses
        self.houses = list(map(self._generate_distance_between_coordinates, self.houses))
        self.houses = list(filter(self._remove_bad_listings, self.houses))
        self.features = list(map(self._generate_features, self.houses))
        self.targets = list(map(self._generate_targets, self.houses))

    def __repr__(self) -> str:
        pass

    def _generate_distance_between_coordinates(self, h : house) -> house:
        user_loc : Tuple[float, float] = self.user_home_lat_lon
        query_loc : Tuple[float, float] = h.lat_long

        if None in query_loc:
            h.future_stats['distance_from_user_home'] =  None
            h.future_stats['angle_from_user_home'] = None
            return h

        lat1, lon1 = radians(user_loc[0]), radians(user_loc[1])
        lat2, lon2 = radians(query_loc[0]), radians(query_loc[1])

        # Haversine formula
        dlon, dlat = lon2 - lon1, lat2 - lat1
        a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2

        c = 2 * asin(sqrt(a))
        r = 3956 # Radius of earth: 6371 kilometers / 3956 miles
        h.future_stats['distance_from_user_home'] =  c * r
        h.future_stats['angle_from_user_home'] = atan2((lat2 - lat1), (lon2 - lon1))
        return h

    def _remove_bad_listings(self, h : house) -> bool:
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

    def _generate_features(self, h) -> dict:
        h.features = {
            'Property_ID' : h.reference_info.get('id'),
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
            'lat' : h.lat_long[0],
            'long' : h.lat_long[1]
        }
        
        return h.features
    
    def _generate_targets(self, h) -> int:
        return int(h.price or 0)
