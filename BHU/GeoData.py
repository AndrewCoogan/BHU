#type: ignore
class GeoData():
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