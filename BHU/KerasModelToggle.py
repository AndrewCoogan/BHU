from BHU.FeatureGenerator import FeatureGenerator
from sklearn.pipeline import Pipeline

class KerasModelToggle():
    def __init__(self, 
                 model : Pipeline, 
                 user_features,
                 user_price,
                 address
                 ):
        self.model = model
        self.fg__user_features = user_features
        self.fg__user_price = user_price
        self.fg__user_home_formatted__address = address

        '''
        This needs to be changed into taking parameters that are serializeable, ie not FeatureGenerator
        '''

        self.model_predicted_user_price = self.model.predict(self.fg__user_price)[0][0]
        self.user_price = self.fg__user_price
        self.predicted_new_value = self.fg__user_price
        self.price_ratio = self.user_price / self.model_predicted_user_price
        self.user_features_mod = self.fg__user_features.copy()
        self._attributes = self.fg__user_features.keys()

    def __repr__(self):
        return f'This is a pricing model for {self.fg__user_home_formatted__address.address}.'
    
    def get_current_user_house_attributes(self):
        '''
        This returns a copy of the user_features dictionary that feeds the NN
        '''
        return self.fg__user_features.copy()
    
    def get_proposed_user_house_attributes(self):
        '''
        This returns a copy of the modified user_features that will feed the NN
        '''
        return self.user_features_mod.copy()
    
    def reset_user_mod(self):
        '''
        This just resets the user mod to the original state.
        '''
        self.user_features_mod = self.fg__user_features
    
    def modify_attributes(self, **kwargs):
        '''
        THOUGHT: This might be easier if we do it as a value (2 or 3 half bath)
        entry rather that an iteration (ie +/-1)
        This should be easy to change though.
        '''
        for k, v in kwargs.items():
            if k in self._attributes:
                self.user_features_mod[k] = v
            else:
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
        