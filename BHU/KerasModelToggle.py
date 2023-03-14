from sklearn.pipeline import Pipeline
import pandas as pd

class KerasModelToggle():
    def __init__(self, 
                 model : Pipeline, 
                 user_features,
                 user_price,
                 address
                 ):
        '''
        This needs to be changed into taking parameters that are serializeable, ie not FeatureGenerator
        '''
        self.model = model
        self.user_features = user_features # This is the user confirmed features
        self.user_price = float(user_price) # This is the user confirmed price
        self.address = address # This is the address

        self.model_predicted_user_price = float(self.model.predict([self.user_features])[0][0])
        self.predicted_new_value = self.user_price
        self.price_ratio = float(self.user_price / self.model_predicted_user_price)
        self.user_features_mod = user_features.copy()
        self._attributes = user_features.keys()

    def __repr__(self):
        return f'This is a pricing model for {self.address}.'
    
    def get_current_user_house_attributes(self):
        '''
        This returns a copy of the user_features dictionary that feeds the NN
        '''
        return self.user_features
    
    def get_proposed_user_house_attributes(self):
        '''
        This returns a copy of the modified user_features that will feed the NN
        '''
        return self.user_features_mod
    
    def reset_user_mod(self):
        '''
        This just resets the user mod to the original state.
        '''
        self.user_features_mod = self.user_features
    
    def modify_attributes(self, **kwargs):
        for k, v in kwargs.items():
            if k in self._attributes:
                self.user_features_mod[k] = v
            else:
                print(f'{k} is not a valid item to change.')

    def predit_new_value(self) -> dict:
        '''
        This will take whatever the current orientation is.
        '''
        self.predicted_new_value = float(self.model.predict([self.user_features_mod])[0][0])

        scaled_new_value = self.predicted_new_value * self.price_ratio
        dollar_delta = scaled_new_value - self.user_price
        pct_delta = float(self.predicted_new_value / self.model_predicted_user_price)

        return {
            'scaled_new_value' : scaled_new_value,
            '_new_value' : self.predicted_new_value,
            'dollar_delta' : dollar_delta,
            'pct_delta' : pct_delta,
            '_user_price_ratio' : self.price_ratio,
            '_model_predicted_price' : self.model_predicted_user_price
        }