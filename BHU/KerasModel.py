#ignore:type
from sklearn.base import BaseEstimator, RegressorMixin
from keras.models import Sequential
from keras.layers import Dense, Dropout
from keras.callbacks import EarlyStopping
from scikeras.wrappers import KerasRegressor

import pickle
import os

class KerasModel(BaseEstimator, RegressorMixin):
    def __init__(self, 
                 user_home,
                 target_transformer,
                 load_model_if_available : bool = True, 
                 update_model : bool = False, 
                 save_model : bool = False):
        # Interesting note, this instance is created before paramters are passed into the step of the pipeline.
        self.user_home = user_home
        self.target_transformer = target_transformer
        self.load_model_if_available = load_model_if_available
        self.update_model = update_model
        self.save_model = save_model

        self.earlystopping = EarlyStopping(patience=5, verbose=1, min_delta=0.05)

        if update_model and not self.load_model_if_available:
            raise Exception('Can not update a model not loaded.')

        self.model_name = f'{user_home.get("city")}_{user_home.get("state_code")}'

    def _keras_model(self, n_cols):
        km = Sequential()
        km.add(Dense(256, input_shape=(n_cols,), activation='relu', kernel_initializer='normal', name='dense_1'))
        km.add(Dense(128, activation='relu', kernel_initializer='normal', name='dense_2'))
        km.add(Dropout(0.20, name='dropout'))
        km.add(Dense(64, activation='relu', kernel_initializer='normal', name='dense_3'))
        km.add(Dense(1, activation='linear', kernel_initializer='normal', name='output'))
        km.compile(optimizer='adam', loss='mean_squared_error', metrics=['mean_squared_error', 'mean_absolute_error'])
        return KerasRegressor(model=km)

    def _generate_model(self, X, y):
            if not self.update_model: 
                self.model = self._keras_model(n_cols=X.shape[1])
            self.model.fit(X, y, epochs=100, batch_size = 50, callbacks = self.earlystopping)

    def fit(self, X, y=None):
        model_file_path = f'BHU/Saved Results/KerasModel/{self.model_name}.pkl'

        if self.load_model_if_available:
            if os.path.isfile(model_file_path):
                with open(model_file_path, 'rb') as f:
                    self.model = pickle.load(f)
                if self.update_model:
                    self._generate_model(X, y)
            else:
                print(f'No model found, generating {self.model_name}.')
                self._generate_model(X, y)
        else:
            self._generate_model(X, y)

        if self.update_model or self.save_model:
            with open(model_file_path, 'wb') as f:
                pickle.dump(self.model, f)
        
        return self

    def predict(self, X):
        return self.target_transformer.inverse_transform(self.model.predict(X))