"""

XGBoost / Gradient Boosting classifier wrapper for V2X Misbehavior Detection.



Tries XGBoost first; falls back to scikit-learn GradientBoostingClassifier

if XGBoost is not installed.

"""



import os

import sys

import logging

from typing import Dict, List, Optional, Tuple



import numpy as np

import joblib



sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import get_config



logger = logging.getLogger(__name__)



# Check XGBoost availability at module level

_HAS_XGBOOST = False

try:

    from xgboost import XGBClassifier

    _HAS_XGBOOST = True

except ImportError:

    from sklearn.ensemble import GradientBoostingClassifier

    logger.info("XGBoost not installed — using GradientBoostingClassifier fallback")





class V2XXGBoost:

    """

    XGBoost / GradientBoosting classifier for V2X misbehavior detection.



    Automatically selects XGBoost if available, otherwise uses scikit-learn's

    GradientBoostingClassifier with equivalent hyperparameters.

    """



    def __init__(self, config=None, **kwargs):

        self.ai_config = config or get_config().ai

        self.feature_names: Optional[List[str]] = None

        self.is_fitted: bool = False

        self.backend: str = "xgboost" if _HAS_XGBOOST else "sklearn"



        base_params = {

            "n_estimators": self.ai_config.xgb_n_estimators,

            "max_depth": self.ai_config.xgb_max_depth,

            "learning_rate": self.ai_config.xgb_learning_rate,

            "random_state": self.ai_config.random_seed,

        }

        base_params.update(kwargs)



        if _HAS_XGBOOST:

            self.model = XGBClassifier(

                **base_params,

                use_label_encoder=False,

                eval_metric="logloss",

                verbosity=0,

            )

        else:

            # GradientBoosting doesn't support use_label_encoder etc.

            self.model = GradientBoostingClassifier(**base_params)



        logger.info(

            f"V2XXGBoost initialized (backend={self.backend}): "

            f"n_estimators={base_params['n_estimators']}, "

            f"max_depth={base_params['max_depth']}, "

            f"lr={base_params['learning_rate']}"

        )



    def fit(self, X: np.ndarray, y: np.ndarray, feature_names: Optional[List[str]] = None) -> "V2XXGBoost":

        """Train the model."""

        self.feature_names = feature_names

        logger.info(f"Training {self.backend} on {X.shape[0]} samples, {X.shape[1]} features...")

        self.model.fit(X, y)

        self.is_fitted = True

        logger.info(f"{self.backend} training complete.")

        return self



    def predict(self, X: np.ndarray) -> np.ndarray:

        """Predict class labels."""

        self._check_fitted()

        return self.model.predict(X)



    def predict_proba(self, X: np.ndarray) -> np.ndarray:

        """Predict class probabilities."""

        self._check_fitted()

        return self.model.predict_proba(X)



    def predict_misbehavior_score(self, X: np.ndarray) -> np.ndarray:

        """Misbehavior probability score (higher = more suspicious)."""

        proba = self.predict_proba(X)

        return proba[:, 1]



    def predict_single(self, features: np.ndarray) -> Tuple[int, float, Dict[str, float]]:

        """

        Predict for a single vehicle.



        Returns:

            (label, confidence, feature_contributions)

        """

        self._check_fitted()

        X = features.reshape(1, -1)

        label = int(self.model.predict(X)[0])

        proba = self.model.predict_proba(X)[0]

        confidence = float(proba[label])



        contributions = {}

        if self.feature_names and hasattr(self.model, "feature_importances_"):

            for name, importance, value in zip(

                self.feature_names, self.model.feature_importances_, features

            ):

                contributions[name] = float(importance * abs(value))

            total = sum(contributions.values())

            if total > 0:

                contributions = {k: v / total for k, v in contributions.items()}



        return label, confidence, contributions



    def get_feature_importances(self) -> Dict[str, float]:

        """Feature importances sorted by value."""

        self._check_fitted()

        importances = self.model.feature_importances_



        if self.feature_names:

            result = {name: float(imp) for name, imp in zip(self.feature_names, importances)}

        else:

            result = {f"feature_{i}": float(imp) for i, imp in enumerate(importances)}



        return dict(sorted(result.items(), key=lambda x: x[1], reverse=True))



    def get_top_features(self, n: int = 10) -> List[Tuple[str, float]]:

        """Top N most important features."""

        return list(self.get_feature_importances().items())[:n]



    def save(self, filepath: Optional[str] = None) -> str:

        """Save model to disk."""

        self._check_fitted()

        if filepath is None:

            filepath = os.path.join(self.ai_config.model_dir, f"{self.backend}_model.joblib")

        os.makedirs(os.path.dirname(filepath), exist_ok=True)



        save_data = {

            "model": self.model,

            "feature_names": self.feature_names,

            "backend": self.backend,

            "model_type": "V2XXGBoost",

        }

        joblib.dump(save_data, filepath)

        logger.info(f"Model saved to {filepath}")

        return filepath



    @classmethod

    def load(cls, filepath: str) -> "V2XXGBoost":

        """Load model from disk."""

        save_data = joblib.load(filepath)

        instance = cls.__new__(cls)

        instance.model = save_data["model"]

        instance.feature_names = save_data.get("feature_names")

        instance.backend = save_data.get("backend", "unknown")

        instance.is_fitted = True

        instance.ai_config = get_config().ai

        logger.info(f"Model loaded from {filepath} (backend={instance.backend})")

        return instance



    def _check_fitted(self):

        if not self.is_fitted:

            raise RuntimeError("Model has not been fitted. Call fit() first.")
