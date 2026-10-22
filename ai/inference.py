"""

Real-time AI inference engine for V2X misbehavior detection.

"""



import sys

import time

import logging

from dataclasses import dataclass

from typing import Dict, Any, Optional



import numpy as np



from config import get_config

from ai.random_forest import V2XRandomForest

from ai.anomaly_detector import V2XAnomalyDetector



try:

    from ai.xgboost_model import V2XXGBoost

except ImportError:

    # Stub for xgboost if not available

    class V2XXGBoost:

        def __init__(self, config=None, **kwargs):

            self.is_fitted = False

        @classmethod

        def load(cls, filepath):

            return cls()

        def predict_single(self, features):

            return 0, 0.0, {}



logger = logging.getLogger(__name__)





@dataclass

class InferenceResult:

    vehicle_id: str

    label: int

    confidence: float

    anomaly_score: float

    misbehavior_probability: float

    feature_contributions: Dict[str, float]

    model_used: str

    inference_time_ms: float

    timestamp: float

    severity: str





class InferenceEngine:

    def __init__(self, config=None):

        self.config = config or get_config()

        self.supervised_model = None

        self.anomaly_detector = None

        self.model_used = ""

        self.stats = {

            "total_inferences": 0,

            "total_latency_ms": 0.0,

            "anomalies_detected": 0,

            "misbehaviors_detected": 0,

            "avg_latency_ms": 0.0

        }



    def load_models(self, model_dir: str):

        import os

        primary = self.config.ai.primary_model

        rf_path = os.path.join(model_dir, "random_forest_model.joblib")

        xgb_path = os.path.join(model_dir, "xgboost_model.joblib")

        if_path = os.path.join(model_dir, "isolation_forest_model.joblib")



        try:

            if primary == "xgboost" and os.path.exists(xgb_path):

                self.supervised_model = V2XXGBoost.load(xgb_path)

                self.model_used = "xgboost"

            elif os.path.exists(rf_path):

                self.supervised_model = V2XRandomForest.load(rf_path)

                self.model_used = "random_forest"

            else:

                logger.warning(f"No supervised model found in {model_dir}")

        except Exception as e:

            logger.error(f"Error loading supervised model: {e}")



        try:

            if os.path.exists(if_path):

                self.anomaly_detector = V2XAnomalyDetector.load(if_path)

            else:

                logger.warning(f"No anomaly detector found in {model_dir}")

        except Exception as e:

            logger.error(f"Error loading anomaly detector: {e}")



    def get_severity(self, misbehavior_probability: float, anomaly_score: float) -> str:

        prob = max(misbehavior_probability, anomaly_score)

        if prob < 0.3:

            return 'NORMAL'

        elif prob < 0.5:

            return 'LOW'

        elif prob < 0.7:

            return 'MEDIUM'

        elif prob < 0.9:

            return 'HIGH'

        else:

            return 'CRITICAL'



    def infer_single(self, vehicle_id: str, features: np.ndarray) -> InferenceResult:

        start_time = time.time()



        label = 0

        confidence = 0.0

        contributions = {}

        misbehavior_prob = 0.0



        if self.supervised_model and getattr(self.supervised_model, 'is_fitted', False):

            label, confidence, contributions = self.supervised_model.predict_single(features)

            misbehavior_prob = confidence if label == 1 else (1.0 - confidence)



        anomaly_label = 0

        anomaly_score = 0.0

        if self.anomaly_detector and getattr(self.anomaly_detector, 'is_fitted', False):

            anomaly_label, anomaly_score = self.anomaly_detector.predict_single(features)



        if anomaly_label == 1 and label == 0:

            misbehavior_prob = max(misbehavior_prob, anomaly_score)

            label = 1 if misbehavior_prob >= 0.5 else 0



        end_time = time.time()

        latency_ms = (end_time - start_time) * 1000.0



        severity = self.get_severity(misbehavior_prob, anomaly_score)



        result = InferenceResult(

            vehicle_id=vehicle_id,

            label=label,

            confidence=confidence,

            anomaly_score=anomaly_score,

            misbehavior_probability=misbehavior_prob,

            feature_contributions=contributions,

            model_used=self.model_used or "none",

            inference_time_ms=latency_ms,

            timestamp=time.time(),

            severity=severity

        )



        self.stats["total_inferences"] += 1

        self.stats["total_latency_ms"] += latency_ms

        self.stats["avg_latency_ms"] = self.stats["total_latency_ms"] / self.stats["total_inferences"]

        if anomaly_label == 1:

            self.stats["anomalies_detected"] += 1

        if label == 1:

            self.stats["misbehaviors_detected"] += 1



        return result



    def infer_batch(self, vehicle_features: Dict[str, np.ndarray]) -> Dict[str, InferenceResult]:

        results = {}

        for vid, feats in vehicle_features.items():

            results[vid] = self.infer_single(vid, feats)

        return results



    def get_model_info(self) -> Dict[str, Any]:

        return {

            "supervised_model": self.model_used if self.supervised_model else None,

            "anomaly_detector_loaded": self.anomaly_detector is not None,

            "supervised_fitted": getattr(self.supervised_model, 'is_fitted', False) if self.supervised_model else False,

            "anomaly_fitted": getattr(self.anomaly_detector, 'is_fitted', False) if self.anomaly_detector else False

        }



    def get_inference_statistics(self) -> Dict[str, Any]:

        return dict(self.stats)
