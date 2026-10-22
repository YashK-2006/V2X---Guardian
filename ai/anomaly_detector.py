"""

Anomaly Detection using Isolation Forest for V2X Misbehavior Detection.



Provides unsupervised anomaly detection to catch previously unseen

behavioral patterns that supervised models may miss.

"""



import os

import sys

import logging

from typing import Dict, List, Optional, Tuple



import numpy as np

import joblib

from sklearn.ensemble import IsolationForest



sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import get_config



logger = logging.getLogger(__name__)





class V2XAnomalyDetector:

    """

    Isolation Forest-based anomaly detector for V2X vehicles.



    Operates in unsupervised mode to detect behavioral anomalies

    without requiring labeled training data.

    """



    def __init__(self, config=None, **kwargs):

        self.ai_config = config or get_config().ai

        self.feature_names: Optional[List[str]] = None

        self.is_fitted: bool = False



        model_params = {

            "n_estimators": self.ai_config.if_n_estimators,

            "contamination": self.ai_config.if_contamination,

            "random_state": self.ai_config.random_seed,

            "n_jobs": -1,

        }

        model_params.update(kwargs)



        self.model = IsolationForest(**model_params)

        self.threshold = self.ai_config.anomaly_threshold



        logger.info(

            f"V2XAnomalyDetector initialized: n_estimators={model_params['n_estimators']}, "

            f"contamination={model_params['contamination']}"

        )



    def fit(self, X: np.ndarray, feature_names: Optional[List[str]] = None) -> "V2XAnomalyDetector":

        """

        Fit the Isolation Forest on normal-behavior data.



        Args:

            X: Feature matrix (ideally from normal vehicles only, or mixed).

            feature_names: Optional feature names for reporting.

        """

        self.feature_names = feature_names

        logger.info(f"Fitting Isolation Forest on {X.shape[0]} samples, {X.shape[1]} features...")

        self.model.fit(X)

        self.is_fitted = True

        logger.info("Isolation Forest fitting complete.")

        return self



    def predict(self, X: np.ndarray) -> np.ndarray:

        """

        Predict anomaly labels.



        Returns:

            Array where 1=normal (inlier), -1=anomaly (outlier).

            Converted to 0=normal, 1=misbehavior for consistency with supervised models.

        """

        self._check_fitted()

        raw_predictions = self.model.predict(X)

        # Convert: 1 (inlier) -> 0 (normal), -1 (outlier) -> 1 (misbehavior)

        return (raw_predictions == -1).astype(int)



    def score_samples(self, X: np.ndarray) -> np.ndarray:

        """

        Compute anomaly scores for each sample.



        Returns:

            Array of anomaly scores. Lower (more negative) = more anomalous.

        """

        self._check_fitted()

        return self.model.score_samples(X)



    def predict_anomaly_score(self, X: np.ndarray) -> np.ndarray:

        """

        Compute normalized anomaly scores in [0, 1].



        Higher values indicate more anomalous behavior.

        """

        raw_scores = self.score_samples(X)

        # Invert and normalize: most anomalous (most negative) -> highest score

        min_score = raw_scores.min()

        max_score = raw_scores.max()

        if max_score - min_score == 0:

            return np.zeros(len(raw_scores))

        normalized = (max_score - raw_scores) / (max_score - min_score)

        return normalized



    def predict_single(self, features: np.ndarray) -> Tuple[int, float]:

        """

        Predict for a single vehicle.



        Args:

            features: 1D feature array.



        Returns:

            (label, anomaly_score) where label is 0=normal, 1=anomaly,

            and anomaly_score is in [0, 1] (higher = more anomalous).

        """

        self._check_fitted()

        X = features.reshape(1, -1)

        label = int(self.predict(X)[0])

        anomaly_score = float(self.predict_anomaly_score(X)[0])

        return label, anomaly_score



    def evaluate(

        self, X: np.ndarray, y_true: np.ndarray

    ) -> Dict[str, float]:

        """

        Evaluate anomaly detector against ground truth labels.



        Args:

            X: Feature matrix.

            y_true: True labels (0=normal, 1=misbehavior).



        Returns:

            Dict with accuracy, precision, recall, F1, and detection rate.

        """

        from sklearn.metrics import (

            accuracy_score,

            precision_score,

            recall_score,

            f1_score,

        )



        y_pred = self.predict(X)



        metrics = {

            "accuracy": float(accuracy_score(y_true, y_pred)),

            "precision": float(precision_score(y_true, y_pred, zero_division=0)),

            "recall": float(recall_score(y_true, y_pred, zero_division=0)),

            "f1": float(f1_score(y_true, y_pred, zero_division=0)),

            "detection_rate": float(np.sum((y_pred == 1) & (y_true == 1)) / max(np.sum(y_true == 1), 1)),

            "false_alarm_rate": float(np.sum((y_pred == 1) & (y_true == 0)) / max(np.sum(y_true == 0), 1)),

            "total_anomalies_detected": int(np.sum(y_pred == 1)),

            "total_actual_anomalies": int(np.sum(y_true == 1)),

        }

        return metrics



    def get_anomaly_feature_analysis(self, X: np.ndarray) -> Dict[str, Dict[str, float]]:

        """

        Analyze which features contribute most to anomaly detection.



        Compares feature distributions between detected normal and anomaly groups.

        """

        self._check_fitted()

        labels = self.predict(X)

        normal_mask = labels == 0

        anomaly_mask = labels == 1



        analysis = {}

        n_features = X.shape[1]

        names = self.feature_names or [f"feature_{i}" for i in range(n_features)]



        for i, name in enumerate(names):

            normal_vals = X[normal_mask, i] if normal_mask.any() else np.array([0])

            anomaly_vals = X[anomaly_mask, i] if anomaly_mask.any() else np.array([0])



            analysis[name] = {

                "normal_mean": float(np.mean(normal_vals)),

                "normal_std": float(np.std(normal_vals)),

                "anomaly_mean": float(np.mean(anomaly_vals)),

                "anomaly_std": float(np.std(anomaly_vals)),

                "mean_difference": float(abs(np.mean(anomaly_vals) - np.mean(normal_vals))),

            }



        # Sort by mean difference (most discriminative first)

        analysis = dict(sorted(

            analysis.items(),

            key=lambda x: x[1]["mean_difference"],

            reverse=True,

        ))

        return analysis



    def save(self, filepath: Optional[str] = None) -> str:

        """Save model to disk."""

        self._check_fitted()

        if filepath is None:

            filepath = os.path.join(self.ai_config.model_dir, "isolation_forest_model.joblib")

        os.makedirs(os.path.dirname(filepath), exist_ok=True)



        save_data = {

            "model": self.model,

            "feature_names": self.feature_names,

            "threshold": self.threshold,

            "model_type": "V2XAnomalyDetector",

        }

        joblib.dump(save_data, filepath)

        logger.info(f"Anomaly detector saved to {filepath}")

        return filepath



    @classmethod

    def load(cls, filepath: str) -> "V2XAnomalyDetector":

        """Load model from disk."""

        save_data = joblib.load(filepath)

        instance = cls.__new__(cls)

        instance.model = save_data["model"]

        instance.feature_names = save_data.get("feature_names")

        instance.threshold = save_data.get("threshold", -0.5)

        instance.is_fitted = True

        instance.ai_config = get_config().ai

        logger.info(f"Anomaly detector loaded from {filepath}")

        return instance



    def _check_fitted(self):

        if not self.is_fitted:

            raise RuntimeError("Model has not been fitted. Call fit() first.")
