#type:ignore
import requests
import html
import string

from urllib.parse import quote
from retrying import retry
from ediblepickle import checkpoint
from beartype._decor.decormain import beartype
from beartype.typing import Tuple

from typing import Literal, Tuple, List

import keys as k

RESULTS_PER_REQUEST_LIMIT = 200
USREALESTATE_API_HEADERS = {
    "X-RapidAPI-Key": k.getKeys()['USRealEstate'],
    "X-RapidAPI-Host": "us-real-estate.p.rapidapi.com"
}

@beartype
@retry(stop_max_attempt_number=5)
@checkpoint(key=lambda args, kwargs: quote(args[0]) + '.pkl', work_dir='BHU/Saved Results/LocationSuggest/')
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
@checkpoint(key=lambda args, kwargs: quote(args[0]) + '.pkl', work_dir='BHU/Saved Results/PropertyDetail/')
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
@checkpoint(key=lambda args, kwargs: quote(args[0]) + '.pkl', work_dir='BHU/Saved Results/PropertyValue/')
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

    Although offset might seem a bit strange to pass in here,I will be checking that there is enough samples 
    requested. The first round of outputs will dictate if we need to query more sold/for sale homes.
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
    work_dir='BHU/Saved Results/Properties/')
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
@checkpoint(key=string.Template('${lat}_${lon}.pkl'), work_dir='BHU/Saved Results/WalkScore/')
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