"""

Random Forest classifier wrapper for V2X Misbehavior Detection.



Provides a clean interface around scikit-learn's RandomForestClassifier

with feature importance extraction and configurable hyperparameters.

"""



import os

import sys

import logging

from typing import Dict, List, Optional, Tuple



import numpy as np

import joblib

from sklearn.ensemble import RandomForestClassifier

from sklearn.metrics import f1_score



sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import get_config



logger = logging.getLogger(__name__)





class V2XRandomForest:

    """

    Random Forest classifier tailored for V2X misbehavior detection.



    Wraps scikit-learn's RandomForestClassifier with project-specific

    defaults, feature importance analysis, and serialization support.

    """



    def __init__(self, config=None, **kwargs):

        """

        Initialize Random Forest with project configuration.



        Args:

            config: AIConfig instance. Uses global config if None.

            **kwargs: Override any RandomForestClassifier parameter.

        """

        self.ai_config = config or get_config().ai

        self.feature_names: Optional[List[str]] = None

        self.is_fitted: bool = False



        # Build model parameters from config, allowing overrides

        model_params = {

            "n_estimators": self.ai_config.rf_n_estimators,

            "max_depth": self.ai_config.rf_max_depth,

            "min_samples_split": self.ai_config.rf_min_samples_split,

            "min_samples_leaf": self.ai_config.rf_min_samples_leaf,

            "random_state": self.ai_config.random_seed,

            "n_jobs": -1,

            "class_weight": "balanced",

        }

        model_params.update(kwargs)



        self.model = RandomForestClassifier(**model_params)

        logger.info(

            f"V2XRandomForest initialized: n_estimators={model_params['n_estimators']}, "

            f"max_depth={model_params['max_depth']}"

        )



    def fit(self, X: np.ndarray, y: np.ndarray, feature_names: Optional[List[str]] = None) -> "V2XRandomForest":

        """

        Train the Random Forest model.



        Args:

            X: Training feature matrix (n_samples, n_features).

            y: Training labels (0=normal, 1=misbehavior).

            feature_names: Optional list of feature names for importance analysis.



        Returns:

            self for method chaining.

        """

        self.feature_names = feature_names

        logger.info(f"Training Random Forest on {X.shape[0]} samples, {X.shape[1]} features...")

        self.model.fit(X, y)

        self.is_fitted = True

        logger.info("Random Forest training complete.")

        return self



    def predict(self, X: np.ndarray) -> np.ndarray:

        """Predict class labels (0 or 1)."""

        self._check_fitted()

        return self.model.predict(X)



    def predict_proba(self, X: np.ndarray) -> np.ndarray:

        """Predict class probabilities. Returns (n_samples, 2) array."""

        self._check_fitted()

        return self.model.predict_proba(X)



    def predict_misbehavior_score(self, X: np.ndarray) -> np.ndarray:

        """

        Get misbehavior probability score for each sample.



        Returns array of floats in [0, 1] where higher = more likely misbehaving.

        """

        proba = self.predict_proba(X)

        return proba[:, 1]



    def predict_single(self, features: np.ndarray) -> Tuple[int, float, Dict[str, float]]:

        """

        Predict for a single vehicle with detailed output.



        Args:

            features: 1D feature array for one vehicle.



        Returns:

            Tuple of (label, confidence, feature_contributions).

        """

        self._check_fitted()

        X = features.reshape(1, -1)

        label = int(self.model.predict(X)[0])

        proba = self.model.predict_proba(X)[0]

        confidence = float(proba[label])



        # Feature contributions (approximated by feature importance * feature value)

        contributions = {}

        if self.feature_names and hasattr(self.model, "feature_importances_"):

            for name, importance, value in zip(

                self.feature_names, self.model.feature_importances_, features

            ):

                contributions[name] = float(importance * abs(value))



            # Normalize contributions

            total = sum(contributions.values())

            if total > 0:

                contributions = {k: v / total for k, v in contributions.items()}



        return label, confidence, contributions



    def get_feature_importances(self) -> Dict[str, float]:

        """

        Get feature importance scores, sorted by importance.



        Returns:

            Dict mapping feature name to importance score.

        """

        self._check_fitted()

        importances = self.model.feature_importances_



        if self.feature_names:

            result = {

                name: float(imp)

                for name, imp in zip(self.feature_names, importances)

            }

        else:

            result = {

                f"feature_{i}": float(imp)

                for i, imp in enumerate(importances)

            }



        return dict(sorted(result.items(), key=lambda x: x[1], reverse=True))



    def get_top_features(self, n: int = 10) -> List[Tuple[str, float]]:

        """Get the top N most important features."""

        importances = self.get_feature_importances()

        return list(importances.items())[:n]



    def save(self, filepath: Optional[str] = None) -> str:

        """Save model to disk."""

        self._check_fitted()

        if filepath is None:

            filepath = os.path.join(self.ai_config.model_dir, "random_forest_model.joblib")

        os.makedirs(os.path.dirname(filepath), exist_ok=True)



        save_data = {

            "model": self.model,

            "feature_names": self.feature_names,

            "model_type": "V2XRandomForest",

        }

        joblib.dump(save_data, filepath)

        logger.info(f"Model saved to {filepath}")

        return filepath



    @classmethod

    def load(cls, filepath: str) -> "V2XRandomForest":

        """Load model from disk."""

        save_data = joblib.load(filepath)

        instance = cls.__new__(cls)

        instance.model = save_data["model"]

        instance.feature_names = save_data.get("feature_names")

        instance.is_fitted = True

        instance.ai_config = get_config().ai

        logger.info(f"Model loaded from {filepath}")

        return instance



    def _check_fitted(self):

        """Raise if model hasn't been trained."""

        if not self.is_fitted:

            raise RuntimeError("Model has not been fitted. Call fit() first.")
