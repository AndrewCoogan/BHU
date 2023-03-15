#ignore:type
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.preprocessing import StandardScaler
from keras.models import Sequential
from keras.layers import Dense, Dropout
from keras.callbacks import EarlyStopping
from keras.initializers import TruncatedNormal
from scikeras.wrappers import KerasRegressor

import pickle
import pandas as pd
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '1'

class KerasModel(BaseEstimator, RegressorMixin):
    '''
    This is the powerhouse of the cell, the model!
    This is the final step of the pipeline. I am actually very pleased with this. It was a really good learning
    experience to see how much you can push and do within one of these. In prior iterations of this, I was able
    to do a GridSearchCV with this, by having the parameter in the __init__ statement and that feeding into
    whatever you are GridSearching. As I write this, alhtough I did not do this, I could have grid searched on any
    element of the Pipeline, which could be sick for later applications.
    '''

    '''
    THIS IS BEING CHANGED QUITE A BIT TO GET IT TO WORK IN FLASK.
    I WILL NEED TO REFACTOR A GOOD CHUNK OF THIS TRIMMING FAT FOR TRAINING ON THE FLY.
    THIS WILL BE REWRITTEN TO ASSUME INPUTS ARE A PRETRAINED. I WILL NEED TO RETHINK HOW TO APPROACH TRAINING.
    '''
    def __init__(self, 
                 model_name : str,
                 target_transformer,
                 load_model_if_available : bool = True, 
                 update_model : bool = False, 
                 save_model : bool = False):
        # Interesting note, this instance is created before paramters are passed into the step of the pipeline.
        self.model_name = model_name
        self.load_model_if_available = load_model_if_available
        self.update_model = update_model
        self.save_model = save_model
        self.target_transformer = target_transformer

        self.earlystopping = EarlyStopping(patience=5, verbose=1, min_delta=0.05)

        if update_model and not load_model_if_available:
            raise Exception('Can not update a model not loaded.')

    def _keras_model(self, n_cols):
        km = Sequential()
        km.add(Dense(256, 
                     input_shape=(n_cols,), 
                     activation='relu',
                     kernel_initializer=TruncatedNormal(stddev=n_cols**-0.5), 
                     name='dense_1'))
        km.add(Dense(128, 
                     activation='relu', 
                     kernel_initializer=TruncatedNormal(stddev=128**-0.5), 
                     name='dense_2'))
        km.add(Dense(64, 
                     activation='relu', 
                     kernel_initializer=TruncatedNormal(stddev=64**-0.5), 
                     name='dense_3'))
        km.add(Dense(1, 
                     activation='linear', 
                     kernel_initializer='normal', 
                     name='output'))
        km.compile(optimizer='adam', loss='mean_squared_error', metrics=['mean_squared_error', 'mean_absolute_error'])
        return KerasRegressor(model=km)

    def _generate_model(self, X, y):
            if not self.update_model: 
                self.model = self._keras_model(n_cols=X.shape[1])
            self.model.fit(X, y, epochs=200, batch_size = 50, callbacks = self.earlystopping)

    def fit(self, X=None, y=None):
        # This will never be hit in production.
        model_file_path = f'BHU/Saved Results/KerasModel/{self.model_name}.pkl'
        if X is None and y is None:
            if os.path.isfile(model_file_path):
                with open(model_file_path, 'rb') as f:
                    self.model = pickle.load(f)
                return self
            else:
                raise Exception('This is not going to generate any new models. (Yet)')

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