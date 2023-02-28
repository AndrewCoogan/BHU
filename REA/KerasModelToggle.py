from FeatureGenerator import FeatureGenerator
from sklearn.pipeline import Pipeline

class KerasModelToggle():
    def __init__(self, 
                 model : Pipeline, 
                 fg : FeatureGenerator):
        self.model = model
        self.fg = fg

        self.model_predicted_user_price = model.predict(fg.user_features)[0][0]
        self.user_price = fg.user_target
        self.predicted_new_value = fg.user_target
        self.price_ratio = self.user_price / self.model_predicted_user_price
        self.user_features_mod = self.fg.user_features.copy()
        self._attributes = self.fg.user_features.keys()

    def __repr__(self):
        return f'This is a pricing model for {self.fg.user_home_formatted.address}.'
    
    def get_current_user_house_attributes(self):
        '''
        This returns a copy of the user_features dictionary that feeds the NN
        '''
        return self.fg.user_features.copy()
    
    def get_proposed_user_house_attributes(self):
        '''
        This returns a copy of the modified user_features that will feed the NN
        '''
        return self.user_features_mod.copy()
    
    def modify_attributes(self, **kwargs):
        '''
        Expected input is going to be in the shape {attribute : +/- 1}
        So the attribute will need to match up with the key of the model input

        THOUGHT: This might be easier if we do it as a value entry rather that an iteration (ie +/-1)
        This should be easy to change though.
        '''
        for k, v in kwargs.items():
            if k in self._attributes:
                self.user_features_mod[k] += v
                continue
            print(f'{k} is not a valid item to change.')

    def predit_new_value(self) -> dict:
        '''
        This will take whatever the current orientation is 
        '''

        try:
            self.predicted_new_value = self.model.predict(self.user_features_mod)
        except:
            return {
                'error' : 'Failed to predict a value for the submitted house!'
            }

        return {
            'predicted_new_value' : self.predicted_new_value,
            'scaled_new_value' : self.predicted_new_value * self.price_ratio, # This is the value we show
            'pct_increase' : self.predicted_new_value / self.model_predicted_user_price,
            'error' : None # Not sure if I need this or how it will interact with the front end.
        }
        