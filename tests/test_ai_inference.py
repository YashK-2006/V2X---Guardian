import sys

import pytest

import numpy as np



from ai.inference import InferenceEngine



class MockSupervisedModel:

    def __init__(self):

        self.is_fitted = True

    def predict_single(self, features):

        return (1, 0.9, {"speed_error": 0.8})



class MockAnomalyDetector:

    def __init__(self):

        self.is_fitted = True

    def predict_single(self, features):

        return (1, 0.85)



def test_random_forest_fit_predict():

    engine = InferenceEngine()

    engine.supervised_model = MockSupervisedModel()

    engine.model_used = "random_forest"

    feats = np.zeros(25)

    res = engine.infer_single("V1", feats)

    assert res.label == 1

    assert res.confidence == 0.9

    assert res.model_used == "random_forest"



def test_xgboost_fit_predict():

    engine = InferenceEngine()

    engine.supervised_model = MockSupervisedModel()

    engine.model_used = "xgboost"

    feats = np.zeros(25)

    res = engine.infer_single("V1", feats)

    assert res.label == 1

    assert res.model_used == "xgboost"



def test_anomaly_detector_fit_predict():

    engine = InferenceEngine()

    engine.anomaly_detector = MockAnomalyDetector()

    feats = np.zeros(25)

    res = engine.infer_single("V1", feats)

    assert res.anomaly_score == 0.85



def test_model_save_load():

    engine = InferenceEngine()

    assert hasattr(engine, "load_models")



def test_inference_result_structure():

    engine = InferenceEngine()

    engine.supervised_model = MockSupervisedModel()

    res = engine.infer_single("V1", np.zeros(25))

    assert hasattr(res, "vehicle_id")

    assert hasattr(res, "label")

    assert hasattr(res, "confidence")

    assert hasattr(res, "severity")



def test_severity_classification():

    engine = InferenceEngine()

    assert engine.get_severity(0.1, 0.1) == 'NORMAL'

    assert engine.get_severity(0.4, 0.2) == 'LOW'

    assert engine.get_severity(0.6, 0.3) == 'MEDIUM'

    assert engine.get_severity(0.8, 0.1) == 'HIGH'

    assert engine.get_severity(0.95, 0.95) == 'CRITICAL'
