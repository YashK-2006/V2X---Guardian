import sys

import pytest

import numpy as np



from ai.feature_extractor import FeatureExtractor



def test_kinematic_features():

    ext = FeatureExtractor()

    msg = {"position": (10, 10), "speed": 15, "acceleration": 1, "heading": 90, "lane": "l1"}

    gt = {"position": (10, 10), "speed": 15, "acceleration": 1, "heading": 90, "lane": "l1"}

    feats = ext.extract_kinematic_features(msg, gt)

    assert feats["position_error"] == 0.0



def test_communication_features():

    ext = FeatureExtractor()

    hist = [{"timestamp": 1}, {"timestamp": 2}, {"timestamp": 3}]

    feats = ext.extract_communication_features("V1", hist)

    assert feats["inter_message_interval"] == 1.0

    assert feats["message_frequency"] == 1.0



def test_spatial_features():

    ext = FeatureExtractor()

    msg = {"position": (0, 0), "vehicle_id": "V1"}

    nm = [{"position": (3, 4)}, {"position": (6, 8)}]

    feats = ext.extract_spatial_features(msg, nm)

    assert feats["avg_distance_to_neighbors"] == 7.5

    assert feats["min_distance_to_neighbors"] == 5.0



def test_feature_vector_to_numpy():

    ext = FeatureExtractor()

    vec = ext.extract_features("V1", {"position": (0,0)}, None, [], {})

    arr = ext.to_numpy(vec)

    assert isinstance(arr, np.ndarray)

    assert len(arr) == len(ext.get_feature_names())



def test_feature_names_count():

    ext = FeatureExtractor()

    names = ext.get_feature_names()

    assert len(names) == 25



def test_feature_extraction_with_misbehavior():

    ext = FeatureExtractor()

    msg = {"position": (100, 100), "speed": 50, "acceleration": 1, "heading": 90, "lane": "l1"}

    gt = {"position": (10, 10), "speed": 15, "acceleration": 1, "heading": 90, "lane": "l1"}

    feats = ext.extract_kinematic_features(msg, gt)

    assert feats["position_error"] > 0

    assert feats["speed_error"] == 35.0
