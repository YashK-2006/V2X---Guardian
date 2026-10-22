import os

import numpy as np

import pandas as pd

from typing import List, Dict, Tuple, Any, Optional

import sys

from config import get_config

from ai.feature_extractor import FeatureExtractor, FeatureVector



class DatasetGenerator:

    """Manages generation, storage, and preprocessing of V2X datasets."""



    def __init__(self, feature_extractor: FeatureExtractor, output_dir: str):

        self.feature_extractor = feature_extractor

        self.output_dir = output_dir

        self.features: List[np.ndarray] = []

        self.labels: List[int] = []

        self.metadata: List[Dict[str, Any]] = []

        os.makedirs(output_dir, exist_ok=True)



    def add_sample(self, feature_vector: FeatureVector, label: int, vehicle_id: str, timestamp: float):

        """Add a single labeled sample."""

        self.features.append(self.feature_extractor.to_numpy(feature_vector))

        self.labels.append(label)

        self.metadata.append({"vehicle_id": vehicle_id, "timestamp": timestamp})



    def add_batch(self, features_list: List[FeatureVector], labels_list: List[int]):

        """Add a batch of labeled samples."""

        for feat, label in zip(features_list, labels_list):

            self.features.append(self.feature_extractor.to_numpy(feat))

            self.labels.append(label)

            # Dummy metadata for batch add without specific ids/timestamps

            self.metadata.append({"vehicle_id": "unknown", "timestamp": 0.0})



    def get_dataset(self) -> Tuple[np.ndarray, np.ndarray]:

        """Return the complete dataset as numpy arrays."""

        if not self.features:

            return np.array([]), np.array([])

        return np.vstack(self.features), np.array(self.labels)



    def split_dataset(self, test_ratio: float = 0.2, val_ratio: float = 0.1, random_seed: int = 42) -> Dict[str, np.ndarray]:

        """Split dataset into train, validation, and test sets."""

        X, y = self.get_dataset()

        if len(X) == 0:

            return {}



        np.random.seed(random_seed)

        indices = np.random.permutation(len(X))

        X_shuffled = X[indices]

        y_shuffled = y[indices]



        test_size = int(len(X) * test_ratio)

        val_size = int(len(X) * val_ratio)



        test_end = test_size

        val_end = test_size + val_size



        X_test = X_shuffled[:test_end]

        y_test = y_shuffled[:test_end]



        X_val = X_shuffled[test_end:val_end]

        y_val = y_shuffled[test_end:val_end]



        X_train = X_shuffled[val_end:]

        y_train = y_shuffled[val_end:]



        return {

            'X_train': X_train,

            'y_train': y_train,

            'X_val': X_val,

            'y_val': y_val,

            'X_test': X_test,

            'y_test': y_test

        }



    def normalize(self, X_train: np.ndarray, X_test: np.ndarray, X_val: Optional[np.ndarray] = None) -> Tuple[Any, ...]:

        """Normalize dataset using standard scaling (mean 0, std 1)."""

        mean = np.mean(X_train, axis=0)

        std = np.std(X_train, axis=0)

        std[std == 0] = 1.0  # Prevent division by zero



        X_train_norm = (X_train - mean) / std

        X_test_norm = (X_test - mean) / std



        class Scaler:

            def __init__(self, mean, std):

                self.mean = mean

                self.std = std

            def transform(self, X):

                return (X - self.mean) / self.std



        scaler = Scaler(mean, std)



        if X_val is not None:

            X_val_norm = (X_val - mean) / std

            return X_train_norm, X_test_norm, X_val_norm, scaler



        return X_train_norm, X_test_norm, scaler



    def save_dataset(self, filepath: str):

        """Save the dataset to a CSV file."""

        if not self.features:

            return



        X, y = self.get_dataset()

        df = pd.DataFrame(X, columns=self.feature_extractor.get_feature_names())

        df['label'] = y



        meta_df = pd.DataFrame(self.metadata)

        df['vehicle_id'] = meta_df['vehicle_id']

        df['timestamp'] = meta_df['timestamp']



        df.to_csv(filepath, index=False)



    def load_dataset(self, filepath: str) -> Tuple[np.ndarray, np.ndarray]:

        """Load dataset from a CSV file."""

        df = pd.read_csv(filepath)

        y = df['label'].values



        feature_names = self.feature_extractor.get_feature_names()

        X = df[feature_names].values



        # Populate internal state

        self.features = [row for row in X]

        self.labels = y.tolist()



        if 'vehicle_id' in df.columns and 'timestamp' in df.columns:

            self.metadata = [{'vehicle_id': row['vehicle_id'], 'timestamp': row['timestamp']}

                             for _, row in df.iterrows()]



        return X, y



    def get_statistics(self) -> Dict[str, Any]:

        """Return dataset statistics."""

        X, y = self.get_dataset()

        if len(y) == 0:

            return {"sample_count": 0}



        normal_count = np.sum(y == 0)

        anomaly_count = np.sum(y == 1)



        feature_stats = {}

        names = self.feature_extractor.get_feature_names()



        for i, name in enumerate(names):

            feature_stats[name] = {

                'mean': float(np.mean(X[:, i])),

                'std': float(np.std(X[:, i])),

                'min': float(np.min(X[:, i])),

                'max': float(np.max(X[:, i]))

            }



        return {

            'sample_count': len(y),

            'normal_samples': int(normal_count),

            'anomalous_samples': int(anomaly_count),

            'class_balance': float(anomaly_count / max(1, len(y))),

            'feature_statistics': feature_stats

        }



    def get_feature_importance_data(self) -> Dict[str, Any]:

        """Format feature names and basic stats for visualization."""

        stats = self.get_statistics()

        if stats['sample_count'] == 0:

            return {}



        return {

            'features': list(stats['feature_statistics'].keys()),

            'importance_scores': [1.0] * len(stats['feature_statistics'])  # Placeholder until model is trained

        }





class DataCollector:

    """Collects training data during simulation."""



    def __init__(self, output_dir: str):

        self.config = get_config()

        self.feature_extractor = FeatureExtractor(self.config)

        self.dataset_generator = DatasetGenerator(self.feature_extractor, output_dir)



    def collect_step(self, vehicles: Dict[str, Any], messages: List[Any],

                     ground_truth: Dict[str, Any], feature_extractor: FeatureExtractor):

        """Process one simulation step and extract features for all vehicles."""



        # Organize messages by sender

        msg_by_sender = {}

        for m in messages:

            vid = getattr(m, 'vehicle_id', m.get('vehicle_id', ''))

            if vid not in msg_by_sender:

                msg_by_sender[vid] = []

            msg_by_sender[vid].append(m)



        for vid, vehicle in vehicles.items():

            if vid not in msg_by_sender or not msg_by_sender[vid]:

                continue



            current_message = msg_by_sender[vid][-1]

            vehicle_record = getattr(vehicle, 'record', vehicle.get('record', {})) if isinstance(vehicle, dict) else getattr(vehicle, 'record', None)



            # Simple assumption: neighbor messages are just all other messages

            # In a real scenario, we'd filter by range

            neighbor_messages = [m for m in messages if getattr(m, 'vehicle_id', m.get('vehicle_id', '')) != vid]

            neighbor_records = {v: getattr(vehicles[v], 'record', None) for v in vehicles if v != vid}



            gt_state = ground_truth.get(vid)



            feat_vector = feature_extractor.extract_features(

                vid, current_message, vehicle_record,

                neighbor_messages, neighbor_records, gt_state

            )



            # Determine label based on vehicle type

            v_type = getattr(vehicle, 'type', vehicle.get('type', 'normal')) if isinstance(vehicle, dict) else getattr(vehicle, 'type', 'normal')

            label = 1 if v_type == 'misbehaving' else 0



            timestamp = float(getattr(current_message, 'timestamp', current_message.get('timestamp', 0.0))) if isinstance(current_message, dict) else getattr(current_message, 'timestamp', 0.0)

            self.dataset_generator.add_sample(feat_vector, label, vid, timestamp)



    def finalize(self) -> DatasetGenerator:

        """Return the populated dataset generator."""

        return self.dataset_generator
