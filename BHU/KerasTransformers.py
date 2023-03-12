import pandas as pd
import numpy as np

from collections import Counter
from itertools import chain

from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.base import TransformerMixin, BaseEstimator
from sklearn.preprocessing import MinMaxScaler, KBinsDiscretizer, StandardScaler, OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.feature_extraction import DictVectorizer

from BHU.KerasModel import KerasModel
from BHU.FeatureGenerator import FeatureGenerator

'''
Days Listed - Linear
Days Updated - Linear
*baths - Normalize
year_built - I want to bucketize these, then keep the dummies.
lot_sqft - Normalize
    Feature generation, multiply lot_sqft normalized and the inverse_distance
        More questions, can you do this?
sqft - Normalize
garage / stories / beds - Normalize
Tags - Do what we did in the nlp homework
'''

class ToDataFrame(BaseEstimator, TransformerMixin):
    def fit(self, X, y=None):
        return self
    
    def transform(self, X):
        return pd.DataFrame(X).drop_duplicates(subset=['Property_ID'])

class DictEncoder(BaseEstimator, TransformerMixin):
    def fit(self, X, y=None):
        tag_frequency = Counter(chain(*X))
        self.tags_to_keep = [k for k, v in tag_frequency.items() if v > 1]
        return self
    
    def transform(self, X):
        return pd.Series(map(lambda l : {k : 1 for k in l if l in self.tags_to_keep}, X))

preprocess_min_max_cols = Pipeline(
    [
        ('impute', SimpleImputer(missing_values=np.nan, strategy="mean")),
        ('min_max_scale', MinMaxScaler())
    ]
)

preprocess_standard_scaler_cols = Pipeline(
    [
        ('impute', SimpleImputer(missing_values=np.nan, strategy="mean")),
        ('min_max_scale', StandardScaler())
    ]
)

preprocess_tags_col = Pipeline(
    [
        ('dict_encode', DictEncoder()),
        ('dict_vectorize', DictVectorizer())
    ]
)

preprocess_bucketize_col = Pipeline(
    [
        ('impute', SimpleImputer(missing_values=np.nan, strategy="mean")),
        ('bucketize', KBinsDiscretizer(n_bins=20, strategy='uniform'))
    ]
)

def generate_keras_pipeline(fg : FeatureGenerator):
    target_transformer = StandardScaler()
    targets = target_transformer.fit_transform(np.array(fg.targets).reshape(-1,1))

    normalize_cols = ['lot_sqft', 'sqft']
    bucketize_cols = ['year_built', 'distance_to_home', 'lat_winz', 'long_winz']
    walk_score = ['walk_score']
    dummy_cols = ['baths_full', 'baths_3qtr', 'baths_half', 'baths_1qtr', 'garage', 'stories', 'beds']

    preprocess_data = ColumnTransformer(
        [
            ('normalize', StandardScaler(), normalize_cols),
            ('bucketize', preprocess_bucketize_col, bucketize_cols),
            ('dummy', OneHotEncoder(sparse_output=False, handle_unknown='ignore'), dummy_cols),
            ('walkscore_mm', preprocess_min_max_cols, walk_score),
            ('walkscore_ss', preprocess_standard_scaler_cols, walk_score)
        ]
    )

    keras_pipeline = Pipeline(
        [
            ('to_data_frame', ToDataFrame()),
            ('preprocess', preprocess_data),
            ('keras_model', KerasModel(fg.user_home_formatted, target_transformer))
        ]
    )
    return keras_pipeline, targets