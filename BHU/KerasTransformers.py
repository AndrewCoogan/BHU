import pandas as pd
import numpy as np
from collections import Counter
from itertools import chain

from sklearn.base import TransformerMixin, BaseEstimator
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MinMaxScaler, KBinsDiscretizer
from sklearn.impute import SimpleImputer
from sklearn.feature_extraction import DictVectorizer

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
    def __init__(self):
        self.tags_to_keep = None

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

preprocess_tags_col = Pipeline(
    [
        ('dict_encode', DictEncoder()),
        ('dict_vectorize', DictVectorizer())
    ]
)

preprocess_bucketize_col = Pipeline(
    [
        ('impute', SimpleImputer(missing_values=np.nan, strategy="median")),
        ('bucketize', KBinsDiscretizer(n_bins=20, strategy='uniform'))
    ]
)