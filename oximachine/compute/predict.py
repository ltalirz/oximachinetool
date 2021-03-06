import os

THIS_DIR = os.path.dirname(os.path.realpath(__file__))
from glob import glob
from pathlib import Path
from collections import defaultdict
from functools import partial
import concurrent.futures
import warnings

warnings.simplefilter("ignore")
import numpy as np
from numeral import int2roman
import joblib

from pymatgen import Structure
from mine_mof_oxstate.featurize import GetFeatures, FeatureCollector
from joblib import load
from .utils import string_to_pymatgen
import shap
import logging

log = logging.getLogger("shap")
log.setLevel(logging.ERROR)

from learnmofox import utils
import sys

sys.modules["utils"] = utils

# adjust these features according to model
METAL_CENTER_FEATURES = [
    "column",
    "row",
    "valenceelectrons",
    "diffto18electrons",
    "sunfilled",
    "punfilled",
    "dunfilled",
]
GEOMETRY_FEATURES = ["crystal_nn_fingerprint", "behler_parinello"]
CHEMISTRY_FEATURES = ["local_property_stats"]
FEATURES = CHEMISTRY_FEATURES + METAL_CENTER_FEATURES + ["crystal_nn_no_steinhardt"]


MODEL = joblib.load(os.path.join(THIS_DIR, "votingclassifier.joblib"))
SCALER = joblib.load(os.path.join(THIS_DIR, "scaler_0.joblib"))
EXPLAINER = joblib.load(os.path.join(THIS_DIR, "explainer.joblib"))


def get_explanations(
    X: np.array, prediction_labels: list, feature_names: list, nsamples: int = 50
) -> dict:
    """[summary]
    
    Arguments:
        X {np.array} -- feature matrix, already unscaled (!, to be easier compatible with the current API)
        prediction_labels {list} -- list of keys that will be used for the dictionary
        feature_names {list} -- list of strings containing the feature names 
        
    Keyword Arguments:
        nsamples {int} -- how often the feature importance calculation is performed, 
            larger value leads to smaller variance but is more expensive (default: {1})
    
    Returns:
        dict -- [description]
    """
    result_dict = {}
    X = SCALER.transform(X)
    shap_values = EXPLAINER.shap_values(X, nsamples=nsamples)
    for i, row in enumerate(X):
        html = shap.force_plot(
            EXPLAINER.expected_value,
            shap_values[i, :],
            row,
            feature_names=feature_names,
        )
        html_data = html.data

        result_dict[prediction_labels[i]] = html_data

    print(result_dict)

    return result_dict


def predictions(X, site_names):
    X_scaled = SCALER.transform(X)
    prediction = MODEL.predict(X_scaled)

    max_probas = np.max(MODEL.predict_proba(X_scaled), axis=1)
    base_predictions = MODEL._predict(X_scaled)

    print(prediction, site_names, max_probas, base_predictions)
    prediction_output = []
    for i, pred in enumerate(prediction):
        agreement = (
            [MODEL.classes[j] for j in base_predictions[i]].count(pred)
            / len(base_predictions[i])
            * 100
        )
        if agreement > 80:
            bartype = "progress-bar bg-success"
        elif agreement < 60:
            bartype = "progress-bar bg-danger"
        else:
            bartype = "progress-bar bg-warning"
        prediction_output.append(
            [
                site_names[i],
                int2roman(pred),
                max_probas[i],
                ", ".join([int2roman(MODEL.classes[j]) for j in base_predictions[i]]),
                agreement,
                bartype,
            ],
        )

    prediction_labels = []
    for i, pred in enumerate(prediction):
        prediction_labels.append("{} ({})".format(site_names[i], int2roman(pred)))

    return prediction_output, prediction_labels
