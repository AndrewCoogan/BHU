# This is going to be where I keep all the API endpoints.
from beartype import beartype
import requests
from retrying import retry
from ediblepickle import checkpoint
from urllib.parse import quote
import html
from typing import Literal
from beartype.typing import Tuple
from datetime import datetime

import keys
keys = keys.getKeys()

RESULTS_PER_REQUEST_LIMIT = 42

USREALESTATE_API_HEADERS = {
    "X-RapidAPI-Key": keys['USRealEstate'],
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
    
    if not isinstance(property_id, str):
        try:
            property_id = str(property_id)
        except:
            raise Exception('Could not convert input to string.')

    url = "https://us-real-estate.p.rapidapi.com/v2/property-detail"

    querystring = {
        "property_id":property_id
    }

    response = requests.request("GET", url, headers=USREALESTATE_API_HEADERS, params=querystring)
    return response.json()

@beartype
@retry(stop_max_attempt_number=5)
@checkpoint(key=lambda args, kwargs: quote(args[0]) + '.pkl', work_dir='Saved Results/PropertyValue/')
def get_PropertyValue(propoerty_id : str) -> dict:
    url = "https://us-real-estate.p.rapidapi.com/for-sale/home-estimate-value"

    querystring = {
        "property_id":propoerty_id
    }

    response = requests.request("GET", url, headers=USREALESTATE_API_HEADERS, params=querystring)
    return response.json()

@beartype
def get_Properties(
        market_status : Literal['for_sale','sold'],
        city_state    : Tuple[str, str] = None,
        zip_code      : str = None,
        n_results     : int = None,
        property_type : str = 'single_family',
        offset        : int = 0,
        verbose       : Literal[0,1] = 0
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

    geo_to_return, houses_to_return = query_url(n_results, verbose, querystring, url)

    return {
        'houses' : houses_to_return,
        'geo' : geo_to_return
    }

@beartype
@retry(stop_max_attempt_number=5)
def query_url(
    n_results : int, 
    verbose : bool, 
    querystring : dict, 
    url : str
    ) -> Tuple[dict, dict]:
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

def get_UserHome(
        user_input : str
    ) -> str:

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

@beartype
@checkpoint(key=lambda args, kwargs: quote(args[0]['full_address'][0]) + '.pkl', work_dir='Saved Results/Properties/')
def get_HousesOfInterest(
    address              : dict, 
    n                    : int = 84, 
    listed_to_sold_ratio : float = 0.3,
    verbose              : Literal[0,1] = 0
) -> dict:
    '''
    This function is going to take an address and retrun a dictionary of geo / results. This is going to be a gloified 
    wrapper of the API call functions, aggregating the outputs.

    address - This is a valid address, expected to be sourced from the get_UserHome.

    n - How many overall results are there going to be.
    
    listed_to_sold_ratio - This model will be a combination of listed and sold houses. T
        his will be dictated by overall reasults, this may or may not be removed based on how it works 
        when were futher down the line.

    This function is currently implemented to only look at the city_state queries. This might be ammended in future iterations
    to get some focus on the strictly local samples, but as of right now, zip_codes are not utilized.
    '''
    n_listed = int(n * listed_to_sold_ratio)
    n_sold = int(n) - n_listed
    
    # I am just going to go with city (for now)
    # TODO: Future enhancement, be able to pass a ratio of zip code and city, but not sure given I measure distance later.
    # 

    listed_homes = get_Properties(
        market_status='for_sale',
        city_state=(address.get('city'), address.get('state_code')),
        n_results=n_listed
    )

    sold_homes = get_Properties(
        market_status='sold',
        city_state=(address.get('city'), address.get('state_code')),
        n_results=n_sold
    )

    if len(listed_homes['houses']) < n_listed:
        new_n_results = n_listed-len(listed_homes['houses']) 
        if verbose:
            print(f'Shortfall in listed houses detected, appending {str(new_n_results)} of current listing to results.')

        sold_homes_v2 = get_Properties(
            market_status='sold',
            city_state=(address.get('city'), address.get('state_code')),
            n_results=n_listed - len(listed_homes['houses']),
            offset=new_n_results
        )

        sold_homes['houses'].append(sold_homes_v2['houses'])

    if len(sold_homes['houses']) < n_sold:
        new_n_results = n_sold-len(sold_homes['houses'])
        if verbose:
            print(f'Shortfall in listed houses detected, appending {str(new_n_results)} of current listing to results.')

        listed_homes_v2 = get_Properties(
            market_status='for_sale',
            city_state=(address.get('city'), address.get('state_code')),
            n_results=n_listed,
            offset=new_n_results
        )
        
        listed_homes['houses'].extend(listed_homes_v2['houes'])

    # Geo will be the same for both unless one returns a zip_code not in the other, but if that happens 
    # it will be a small population.
    
    # NOTE: Listed home always goes first as long as there is a non zero listed home query, which are both v2, so the 
    # Geo not available in v1 issue should not be an problem.
    listed_homes['houses'].extend(sold_homes['houses'].copy())

    return listed_homes

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
        pass

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
            listing : dict
        ):
        
        self.reference_info = { # This is stuff not going into the model
            'id' : listing.get('property_id', ''),
            'photos' : 'to be added'
        }

        self.raw_last_update : str = listing['last_update_date']
        self.raw_list_date : str = listing['list_date']
        self.tags : list = listing.get('tags', [])
        self.list_price : Tuple[int, float] = listing.get('list_price', 0)
        self.new_construction : bool = listing.get('flags', {}).get('is_new_construction', False) or False
        self.status : Literal['sold', 'for_sale', 'NO_STATUS'] = listing.get('status', 'NO_STATUS')

        self.raw_location : dict = listing['location']
        self.raw_description : dict = listing['description']

        self._clean_dates()
        self._clean_location()
        self._clean_description()

        # This is going to be used to store stuff in the future.
        self.future_stats = {}
        self.features = {}

    def __repr__(self) -> str:
        pass
        
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
            'zip_code' : self.raw_location.get('address', {}).get('postal_code'),
            'state' : self.raw_location.get('address', {}).get('state'),
            'google_map_street_view' : self.raw_location.get('street_view_url'),
            'fips_code' : self.raw_location.get('county', {}).get('fips_code'),
            'county' : self.raw_location.get('county', {}).get('name'),
            'city' : self.raw_location.get('address', {}).get('city')
        })

        lat_long = self.raw_location.get('address', {}).get('coordinate')
        self.lat_long = (None, None) if lat_long is None else (lat_long.get('lat'), lat_long.get('lon'))     

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

    def validate(self) -> None:
        '''
        This is just going to look at the data we will need at the next step and see if its mostly good.
        '''
        validation_dict = {
            'Days_listed' : self.list_date_delta,
            'Days_updated' : self.last_update_delta,
            'baths_full' : self.baths_full,
            'baths_3qtr' : self.baths_3qtr,
            'baths_half' : self.baths_half,
            'baths_1qtr' : self.baths_1qtr,
            'year_built' : self.year_built,
            'lot_sqft' : self.lot_sqft,
            'sqft' : self.sqft,
            'garage' : self.garage,
            'stories' : self.stories,
            'beds' : self.beds,
            'type' : self.type,
            'tags' : self.tags,
            'new_construction' : self.new_construction
        }

        for k, v in validation_dict.items():
            if v is None:
                print(f'{k} missing value for house {self.reference_info.id}')

if __name__ == '__main__':
    pass