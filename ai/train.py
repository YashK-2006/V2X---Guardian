"""

AI Model Training Pipeline for V2X Misbehavior Detection.



Supports Random Forest, XGBoost (with GradientBoosting fallback),

cross-validation, hyperparameter search, and comprehensive metric evaluation.

"""



import os

import sys

import json

import time

import logging

from typing import Dict, List, Optional, Tuple, Any

from dataclasses import dataclass, field, asdict



import numpy as np

import pandas as pd

import joblib

from sklearn.model_selection import (

    cross_val_score,

    StratifiedKFold,

    GridSearchCV,

)

from sklearn.metrics import (

    accuracy_score,

    precision_score,

    recall_score,

    f1_score,

    roc_auc_score,

    confusion_matrix,

    classification_report,

    roc_curve,

)



sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import get_config



logger = logging.getLogger(__name__)





@dataclass

class ModelMetrics:

    """Comprehensive metrics for a trained model."""

    model_name: str

    accuracy: float = 0.0

    precision: float = 0.0

    recall: float = 0.0

    f1: float = 0.0

    roc_auc: float = 0.0

    false_positive_rate: float = 0.0

    false_negative_rate: float = 0.0

    inference_time_ms: float = 0.0

    training_time_s: float = 0.0

    confusion_matrix: Optional[List[List[int]]] = None

    feature_importances: Optional[Dict[str, float]] = None

    cross_val_scores: Optional[List[float]] = None

    cross_val_mean: float = 0.0

    cross_val_std: float = 0.0

    roc_curve_fpr: Optional[List[float]] = None

    roc_curve_tpr: Optional[List[float]] = None

    classification_report_dict: Optional[Dict] = None

    best_params: Optional[Dict] = None



    def to_dict(self) -> Dict:

        """Convert metrics to dictionary."""

        d = asdict(self)

        # Convert numpy arrays to lists if needed

        for key, val in d.items():

            if isinstance(val, np.ndarray):

                d[key] = val.tolist()

        return d



    def summary(self) -> str:

        """Human-readable summary."""

        return (

            f"Model: {self.model_name}\n"

            f"  Accuracy:  {self.accuracy:.4f}\n"

            f"  Precision: {self.precision:.4f}\n"

            f"  Recall:    {self.recall:.4f}\n"

            f"  F1 Score:  {self.f1:.4f}\n"

            f"  ROC-AUC:   {self.roc_auc:.4f}\n"

            f"  FPR:       {self.false_positive_rate:.4f}\n"

            f"  FNR:       {self.false_negative_rate:.4f}\n"

            f"  Inference: {self.inference_time_ms:.2f} ms\n"

            f"  CV Mean:   {self.cross_val_mean:.4f} ± {self.cross_val_std:.4f}"

        )





@dataclass

class TrainingResult:

    """Result of a complete training run."""

    model_name: str

    model: Any  # The trained sklearn model

    metrics: ModelMetrics

    scaler: Any = None  # Fitted StandardScaler

    feature_names: Optional[List[str]] = None

    model_path: Optional[str] = None

    timestamp: float = field(default_factory=time.time)





class ModelTrainer:

    """

    Training pipeline for V2X misbehavior detection models.



    Supports Random Forest, XGBoost/GradientBoosting, and model comparison.

    """



    def __init__(self, config=None):

        self.config = config or get_config().ai

        self.results: Dict[str, TrainingResult] = {}

        os.makedirs(self.config.model_dir, exist_ok=True)



    def train_random_forest(

        self,

        X_train: np.ndarray,

        y_train: np.ndarray,

        X_test: np.ndarray,

        y_test: np.ndarray,

        feature_names: Optional[List[str]] = None,

        hyperparameter_search: bool = False,

    ) -> TrainingResult:

        """Train a Random Forest classifier."""

        from sklearn.ensemble import RandomForestClassifier



        logger.info("Training Random Forest classifier...")



        if hyperparameter_search:

            param_grid = {

                "n_estimators": [50, 100, 200],

                "max_depth": [5, 10, 15, None],

                "min_samples_split": [2, 5, 10],

                "min_samples_leaf": [1, 2, 4],

            }

            base_model = RandomForestClassifier(random_state=self.config.random_seed)

            grid_search = GridSearchCV(

                base_model,

                param_grid,

                cv=3,

                scoring="f1",

                n_jobs=-1,

                verbose=0,

            )

            start_time = time.time()

            grid_search.fit(X_train, y_train)

            training_time = time.time() - start_time

            model = grid_search.best_estimator_

            best_params = grid_search.best_params_

            logger.info(f"Best RF params: {best_params}")

        else:

            model = RandomForestClassifier(

                n_estimators=self.config.rf_n_estimators,

                max_depth=self.config.rf_max_depth,

                min_samples_split=self.config.rf_min_samples_split,

                min_samples_leaf=self.config.rf_min_samples_leaf,

                random_state=self.config.random_seed,

                n_jobs=-1,

            )

            start_time = time.time()

            model.fit(X_train, y_train)

            training_time = time.time() - start_time

            best_params = None



        metrics = self._evaluate_model(

            model, X_train, y_train, X_test, y_test, "RandomForest",

            feature_names, training_time, best_params,

        )



        result = TrainingResult(

            model_name="RandomForest",

            model=model,

            metrics=metrics,

            feature_names=feature_names,

        )

        self.results["RandomForest"] = result



        logger.info(f"Random Forest training complete:\n{metrics.summary()}")

        return result



    def train_xgboost(

        self,

        X_train: np.ndarray,

        y_train: np.ndarray,

        X_test: np.ndarray,

        y_test: np.ndarray,

        feature_names: Optional[List[str]] = None,

        hyperparameter_search: bool = False,

    ) -> TrainingResult:

        """Train XGBoost or fall back to GradientBoosting."""

        try:

            from xgboost import XGBClassifier



            logger.info("Training XGBoost classifier...")

            model_name = "XGBoost"



            if hyperparameter_search:

                param_grid = {

                    "n_estimators": [50, 100, 200],

                    "max_depth": [3, 6, 9],

                    "learning_rate": [0.01, 0.1, 0.3],

                }

                base_model = XGBClassifier(

                    random_state=self.config.random_seed,

                    use_label_encoder=False,

                    eval_metric="logloss",

                )

                grid_search = GridSearchCV(

                    base_model, param_grid, cv=3, scoring="f1",

                    n_jobs=-1, verbose=0,

                )

                start_time = time.time()

                grid_search.fit(X_train, y_train)

                training_time = time.time() - start_time

                model = grid_search.best_estimator_

                best_params = grid_search.best_params_

            else:

                model = XGBClassifier(

                    n_estimators=self.config.xgb_n_estimators,

                    max_depth=self.config.xgb_max_depth,

                    learning_rate=self.config.xgb_learning_rate,

                    random_state=self.config.random_seed,

                    use_label_encoder=False,

                    eval_metric="logloss",

                )

                start_time = time.time()

                model.fit(X_train, y_train)

                training_time = time.time() - start_time

                best_params = None



        except ImportError:

            from sklearn.ensemble import GradientBoostingClassifier



            logger.warning("XGBoost not available, falling back to GradientBoosting")

            model_name = "GradientBoosting"



            model = GradientBoostingClassifier(

                n_estimators=self.config.xgb_n_estimators,

                max_depth=self.config.xgb_max_depth,

                learning_rate=self.config.xgb_learning_rate,

                random_state=self.config.random_seed,

            )

            start_time = time.time()

            model.fit(X_train, y_train)

            training_time = time.time() - start_time

            best_params = None



        metrics = self._evaluate_model(

            model, X_train, y_train, X_test, y_test, model_name,

            feature_names, training_time, best_params,

        )



        result = TrainingResult(

            model_name=model_name,

            model=model,

            metrics=metrics,

            feature_names=feature_names,

        )

        self.results[model_name] = result



        logger.info(f"{model_name} training complete:\n{metrics.summary()}")

        return result



    def train_all(

        self,

        X_train: np.ndarray,

        y_train: np.ndarray,

        X_test: np.ndarray,

        y_test: np.ndarray,

        feature_names: Optional[List[str]] = None,

        hyperparameter_search: bool = False,

    ) -> Dict[str, TrainingResult]:

        """Train all supported models and return comparison."""

        self.train_random_forest(

            X_train, y_train, X_test, y_test, feature_names, hyperparameter_search,

        )

        self.train_xgboost(

            X_train, y_train, X_test, y_test, feature_names, hyperparameter_search,

        )

        return self.results



    def _evaluate_model(

        self,

        model,

        X_train: np.ndarray,

        y_train: np.ndarray,

        X_test: np.ndarray,

        y_test: np.ndarray,

        model_name: str,

        feature_names: Optional[List[str]],

        training_time: float,

        best_params: Optional[Dict],

    ) -> ModelMetrics:

        """Comprehensive model evaluation."""

        # Predictions

        y_pred = model.predict(X_test)

        y_proba = model.predict_proba(X_test)[:, 1] if hasattr(model, "predict_proba") else y_pred.astype(float)



        # Inference time measurement

        start = time.time()

        for _ in range(100):

            model.predict(X_test[:1])

        inference_time = (time.time() - start) / 100 * 1000  # ms per sample



        # Confusion matrix

        cm = confusion_matrix(y_test, y_pred)

        tn, fp, fn, tp = cm.ravel()

        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0

        fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0



        # ROC curve

        fpr_curve, tpr_curve, _ = roc_curve(y_test, y_proba)



        # Cross-validation

        cv = StratifiedKFold(n_splits=self.config.cross_validation_folds, shuffle=True, random_state=self.config.random_seed)

        cv_scores = cross_val_score(model, X_train, y_train, cv=cv, scoring="f1")



        # Feature importances

        importances = {}

        if hasattr(model, "feature_importances_") and feature_names:

            for name, imp in zip(feature_names, model.feature_importances_):

                importances[name] = float(imp)

            importances = dict(sorted(importances.items(), key=lambda x: x[1], reverse=True))



        # Classification report

        report = classification_report(y_test, y_pred, output_dict=True)



        metrics = ModelMetrics(

            model_name=model_name,

            accuracy=float(accuracy_score(y_test, y_pred)),

            precision=float(precision_score(y_test, y_pred, zero_division=0)),

            recall=float(recall_score(y_test, y_pred, zero_division=0)),

            f1=float(f1_score(y_test, y_pred, zero_division=0)),

            roc_auc=float(roc_auc_score(y_test, y_proba)),

            false_positive_rate=float(fpr),

            false_negative_rate=float(fnr),

            inference_time_ms=float(inference_time),

            training_time_s=float(training_time),

            confusion_matrix=cm.tolist(),

            feature_importances=importances if importances else None,

            cross_val_scores=cv_scores.tolist(),

            cross_val_mean=float(cv_scores.mean()),

            cross_val_std=float(cv_scores.std()),

            roc_curve_fpr=fpr_curve.tolist(),

            roc_curve_tpr=tpr_curve.tolist(),

            classification_report_dict=report,

            best_params=best_params,

        )

        return metrics



    def save_model(self, model_name: str, filepath: Optional[str] = None) -> str:

        """Save a trained model to disk."""

        if model_name not in self.results:

            raise ValueError(f"Model '{model_name}' not found. Available: {list(self.results.keys())}")



        result = self.results[model_name]

        if filepath is None:

            filepath = os.path.join(self.config.model_dir, f"{model_name.lower()}_model.joblib")



        os.makedirs(os.path.dirname(filepath), exist_ok=True)



        save_data = {

            "model": result.model,

            "scaler": result.scaler,

            "feature_names": result.feature_names,

            "metrics": result.metrics.to_dict(),

            "timestamp": result.timestamp,

        }

        joblib.dump(save_data, filepath)

        result.model_path = filepath

        logger.info(f"Model saved to {filepath}")

        return filepath



    def load_model(self, filepath: str) -> TrainingResult:

        """Load a model from disk."""

        save_data = joblib.load(filepath)

        metrics = ModelMetrics(**{

            k: v for k, v in save_data["metrics"].items()

            if k in ModelMetrics.__dataclass_fields__

        })

        result = TrainingResult(

            model_name=metrics.model_name,

            model=save_data["model"],

            metrics=metrics,

            scaler=save_data.get("scaler"),

            feature_names=save_data.get("feature_names"),

            model_path=filepath,

            timestamp=save_data.get("timestamp", time.time()),

        )

        self.results[result.model_name] = result

        logger.info(f"Model loaded from {filepath}")

        return result



    def save_all_models(self) -> Dict[str, str]:

        """Save all trained models."""

        paths = {}

        for name in self.results:

            paths[name] = self.save_model(name)

        return paths



    def compare_models(self) -> pd.DataFrame:

        """Generate a comparison table of all trained models."""

        if not self.results:

            return pd.DataFrame()



        rows = []

        for name, result in self.results.items():

            m = result.metrics

            rows.append({

                "Model": name,

                "Accuracy": m.accuracy,

                "Precision": m.precision,

                "Recall": m.recall,

                "F1": m.f1,

                "ROC-AUC": m.roc_auc,

                "FPR": m.false_positive_rate,

                "FNR": m.false_negative_rate,

                "Inference (ms)": m.inference_time_ms,

                "Training (s)": m.training_time_s,

                "CV Mean": m.cross_val_mean,

                "CV Std": m.cross_val_std,

            })



        df = pd.DataFrame(rows)

        df = df.set_index("Model")

        return df



    def get_best_model(self, metric: str = "f1") -> TrainingResult:

        """Get the best model based on a specified metric."""

        if not self.results:

            raise ValueError("No models trained yet")



        best_name = None

        best_val = -1.0

        for name, result in self.results.items():

            val = getattr(result.metrics, metric, 0.0)

            if val > best_val:

                best_val = val

                best_name = name



        return self.results[best_name]



    def save_metrics_report(self, output_dir: Optional[str] = None) -> str:

        """Save a comprehensive metrics report as JSON."""

        if output_dir is None:

            output_dir = self.config.model_dir



        os.makedirs(output_dir, exist_ok=True)

        report_path = os.path.join(output_dir, "training_report.json")



        report = {

            "timestamp": time.time(),

            "models": {},

            "comparison": self.compare_models().to_dict() if self.results else {},

        }



        for name, result in self.results.items():

            report["models"][name] = result.metrics.to_dict()



        with open(report_path, "w") as f:

            json.dump(report, f, indent=2, default=str)



        logger.info(f"Metrics report saved to {report_path}")

        return report_path





if __name__ == "__main__":

    # The live multi-class detector is trained by ai.train_detector

    from ai.train_detector import main

    main()
