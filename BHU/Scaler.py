import os
import pickle
from sklearn.preprocessing import StandardScaler

class Scaler():
    def load_scaler(self, model_name) -> StandardScaler:
        model_file_path = f'BHU/Saved Results/StandardScaler/{model_name}.pkl'
        if os.path.isfile(model_file_path):
            with open(model_file_path, 'rb') as f:
                model = pickle.load(f)
        else:
            raise Exception('No Scaler Model Present')
        return model
    
    def save_scaler(self, model, model_name) -> None:
        model_file_path = f'BHU/Saved Results/StandardScaler/{model_name}.pkl'
        with open(model_file_path, 'wb') as f:
                pickle.dump(model, f)
        return
