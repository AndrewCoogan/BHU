import os
import pickle
from sklearn.preprocessing import StandardScaler

class Scaler():
    def load_model(self, model_name) -> StandardScaler:
        model_file_path = self.file_path(model_name)
        if os.path.isfile(model_file_path):
            with open(model_file_path, 'rb') as f:
                model = pickle.load(f)
        else:
            raise Exception('No Scaler Model Present')
        return model
    
    def save_model(self, model, model_name) -> None:
        model_file_path = self.file_path(model_name)
        with open(model_file_path, 'wb') as f:
                pickle.dump(model, f)
        return
    
    def generate_model(self) -> StandardScaler:
         return StandardScaler()
    
    def file_path(self, model_name) -> str:
         return f'BHU/Saved Results/StandardScaler/{model_name}.pkl'
