'''
This is not being used right now.
''' 

# type: ignore 
from BHU.API_Calls import get_WalkScore
from BHU.House import House
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.base import BaseEstimator, RegressorMixin
import pickle
import os
import numpy as np

class WalkScoreModel(BaseEstimator, RegressorMixin):
    '''
    This is going to be everything WalkScore, very similar to how we have the pipeline.
    The end game of this is to be smart, if there is no model available then hit the API and download the walkscores.
    If there is a model - we load the model
    If there is no model - 
        1) Hit the API
        2) Generate the model with the newly downloaded walkscores
        3) Save it
    Have model assigned to .model
    FeatureGenerator will use the .predict

    This is going to be somewhat annoying, I am
    '''
    def __init__(self, 
                 user_home,
                 load_model_if_available : bool = True,
                 save_model : bool = True
                 ):
        self.user_home = user_home
        self.load_model_if_available = load_model_if_available
        self.save_model = save_model
        self.model_name = f'{user_home.get("city")}_{user_home.get("state_code")}'

        def clean_values(score):
            try:
                score_min = max([score, 0])
                score_max = min([score, 100])
                clean_score = min([score_min, score_max])
            except:
                clean_score = np.nan
            return clean_score
        
        self.clean_scores = clean_values

    def _get_walk_scores(self, h : House) -> dict:
        '''
        Here is the API call to get all the numbers.
        '''
        walk_score_raw = get_WalkScore(
            address=f'{h.reference_info.get("city")} {h.reference_info.get("state_code")}',
            lat=h.lat_long[0],
            lon=h.lat_long[1]
        )

        return {
            'walk_score' : self.clean_scores(walk_score_raw.get('walkscore')),
            'transit_score' : self.clean_scores(walk_score_raw.get('transit', {}).get('score')),
            'bike_score' : self.clean_scores(walk_score_raw.get('bike', {}).get('score'))
        }

    def _GBR_model(self):
        return GradientBoostingRegressor(n_estimators=250, 
                                         min_samples_split=5, 
                                         min_samples_leaf=5, 
                                         max_depth=12)

    def _generate_model(self, X, y):
        self._GBR_model().fit(X, y)

    def fit(self, X, y=None):
        model_file_path = f'BHU/Saved Results/WalkScoreModel/{self.model_name}.pkl'

        if self.load_model_if_available:
            if os.path.isfile(model_file_path):
                with open(model_file_path, 'rb') as f:
                    self.model = pickle.load(f)
            else:
                print(f'No model found, generating {self.model_name}.')
                self._generate_model(X, y)
        else:
            self._generate_model(X, y)

        if self.save_model:
            with open(model_file_path, 'wb') as f:
                pickle.dump(self.model, f)
        
        return self

    def predict(self, X):
        return self.model.predict(X)