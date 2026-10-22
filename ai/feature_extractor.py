import numpy as np

import sys

import math

import logging

from dataclasses import dataclass, fields

from typing import List, Dict, Optional, Any



from config import get_config



logger = logging.getLogger(__name__)



@dataclass

class FeatureVector:

    # Kinematic (5)

    position_error: float

    speed_error: float

    acceleration_error: float

    heading_error: float

    lane_consistency: float



    # Communication (5)

    message_frequency: float

    inter_message_interval: float

    message_frequency_std: float

    event_frequency: float

    message_consistency: float



    # Spatial (4)

    avg_distance_to_neighbors: float

    min_distance_to_neighbors: float

    position_jump_distance: float

    trajectory_consistency: float



    # Temporal (5)

    historical_trust: float

    behavior_change_rate: float

    previous_anomaly_count: int

    recent_misbehavior_count: int

    time_since_last_anomaly: float



    # Social/Neighbor (6)

    num_agreeing_vehicles: int

    num_disagreeing_vehicles: int

    agreement_ratio: float

    neighbor_count: int

    neighbor_trust_weighted_agreement: float

    is_isolated: float





def get_attr(obj: Any, attr_name: str, default: Any = None) -> Any:

    """Helper to get attributes from dicts or objects."""

    if isinstance(obj, dict):

        return obj.get(attr_name, default)

    return getattr(obj, attr_name, default)





class FeatureExtractor:

    """Extracts machine learning features from V2X messages and context."""



    def __init__(self, config=None):

        self.config = config or get_config()

        self.window_size = self.config.ai.feature_window_size

        self.message_history = {}

        self.last_position = {}



    def extract_features(self, vehicle_id: str, current_message: Any,

                         vehicle_record: Any, neighbor_messages: List[Any],

                         neighbor_records: Dict[str, Any],

                         ground_truth_state: Any = None) -> FeatureVector:



        if vehicle_id not in self.message_history:

            self.message_history[vehicle_id] = []



        history = self.message_history[vehicle_id]

        history.append(current_message)

        if len(history) > self.window_size:

            history.pop(0)



        kinematic = self.extract_kinematic_features(current_message, ground_truth_state)

        communication = self.extract_communication_features(vehicle_id, history)

        spatial = self.extract_spatial_features(current_message, neighbor_messages)

        temporal = self.extract_temporal_features(vehicle_record)

        social = self.extract_social_features(current_message, neighbor_messages, neighbor_records)



        # update last position for jump distance

        pos = get_attr(current_message, 'position', (0.0, 0.0))

        self.last_position[vehicle_id] = pos



        return FeatureVector(

            **kinematic,

            **communication,

            **spatial,

            **temporal,

            **social

        )



    def extract_kinematic_features(self, message: Any, ground_truth: Any) -> Dict[str, float]:

        if ground_truth is None:

            return {

                'position_error': 0.0,

                'speed_error': 0.0,

                'acceleration_error': 0.0,

                'heading_error': 0.0,

                'lane_consistency': 1.0

            }



        m_pos = get_attr(message, 'position', (0.0, 0.0))

        g_pos = get_attr(ground_truth, 'position', (0.0, 0.0))

        position_error = self._euclidean_distance(m_pos, g_pos)



        m_speed = get_attr(message, 'speed', 0.0)

        g_speed = get_attr(ground_truth, 'speed', 0.0)

        speed_error = abs(float(m_speed) - float(g_speed))



        m_acc = get_attr(message, 'acceleration', 0.0)

        g_acc = get_attr(ground_truth, 'acceleration', 0.0)

        acc_error = abs(float(m_acc) - float(g_acc))



        m_head = get_attr(message, 'heading', 0.0)

        g_head = get_attr(ground_truth, 'heading', 0.0)

        heading_error = self._angular_difference(float(m_head), float(g_head))



        m_lane = str(get_attr(message, 'lane', ''))

        g_lane = str(get_attr(ground_truth, 'lane', ''))

        lane_consistency = 1.0 if m_lane == g_lane else 0.0



        return {

            'position_error': float(position_error),

            'speed_error': float(speed_error),

            'acceleration_error': float(acc_error),

            'heading_error': float(heading_error),

            'lane_consistency': float(lane_consistency)

        }



    def extract_communication_features(self, vehicle_id: str, message_history: List[Any]) -> Dict[str, float]:

        if len(message_history) <= 1:

            return {

                'message_frequency': 0.0,

                'inter_message_interval': 0.0,

                'message_frequency_std': 0.0,

                'event_frequency': 0.0,

                'message_consistency': 1.0

            }



        timestamps = [float(get_attr(m, 'timestamp', 0.0)) for m in message_history]

        timestamps.sort()



        intervals = np.diff(timestamps)

        mean_interval = float(np.mean(intervals)) if len(intervals) > 0 else 0.0

        std_interval = float(np.std(intervals)) if len(intervals) > 0 else 0.0

        freq = 1.0 / mean_interval if mean_interval > 0 else 0.0



        events = sum(1 for m in message_history if get_attr(m, 'events', []))

        total_time = timestamps[-1] - timestamps[0]

        event_freq = float(events / (total_time / 60.0)) if total_time > 0 else 0.0



        return {

            'message_frequency': float(freq),

            'inter_message_interval': float(mean_interval),

            'message_frequency_std': float(std_interval),

            'event_frequency': float(event_freq),

            'message_consistency': 1.0

        }



    def extract_spatial_features(self, message: Any, neighbor_messages: List[Any]) -> Dict[str, float]:

        m_pos = get_attr(message, 'position', (0.0, 0.0))

        vehicle_id = get_attr(message, 'vehicle_id', '')



        distances = []

        for nm in neighbor_messages:

            n_pos = get_attr(nm, 'position', (0.0, 0.0))

            distances.append(self._euclidean_distance(m_pos, n_pos))



        avg_dist = float(np.mean(distances)) if distances else 0.0

        min_dist = float(np.min(distances)) if distances else 0.0



        last_pos = self.last_position.get(vehicle_id, m_pos)

        jump_dist = self._euclidean_distance(m_pos, last_pos)



        trajectory_consistency = max(0.0, 1.0 - (jump_dist / 100.0))



        return {

            'avg_distance_to_neighbors': float(avg_dist),

            'min_distance_to_neighbors': float(min_dist),

            'position_jump_distance': float(jump_dist),

            'trajectory_consistency': float(trajectory_consistency)

        }



    def extract_temporal_features(self, vehicle_record: Any) -> Dict[str, float]:

        if vehicle_record is None:

            return {

                'historical_trust': 0.5,

                'behavior_change_rate': 0.0,

                'previous_anomaly_count': 0,

                'recent_misbehavior_count': 0,

                'time_since_last_anomaly': 9999.0

            }



        return {

            'historical_trust': float(get_attr(vehicle_record, 'trust_score', 0.5)),

            'behavior_change_rate': float(get_attr(vehicle_record, 'behavior_change_rate', 0.0)),

            'previous_anomaly_count': int(get_attr(vehicle_record, 'anomaly_count', 0)),

            'recent_misbehavior_count': int(get_attr(vehicle_record, 'recent_anomalies', 0)),

            'time_since_last_anomaly': float(get_attr(vehicle_record, 'time_since_anomaly', 9999.0))

        }



    def extract_social_features(self, message: Any, neighbor_messages: List[Any], neighbor_records: Dict[str, Any]) -> Dict[str, float]:

        agree = 0

        disagree = 0

        trust_weighted = 0.0



        m_pos = get_attr(message, 'position', (0.0, 0.0))

        m_speed = float(get_attr(message, 'speed', 0.0))



        for nm in neighbor_messages:

            n_id = get_attr(nm, 'vehicle_id', '')

            n_rec = neighbor_records.get(n_id)

            n_trust = get_attr(n_rec, 'trust_score', 0.5) if n_rec else 0.5



            # Simple heuristic for agreement based on reported positions/speeds from neighbors

            # If the neighbor is nearby, it agrees.

            n_pos = get_attr(nm, 'position', (0.0, 0.0))

            dist = self._euclidean_distance(m_pos, n_pos)



            if dist < 150.0:  # Arbitrary threshold for agreement

                agree += 1

                trust_weighted += n_trust

            else:

                disagree += 1



        total = agree + disagree

        ratio = agree / total if total > 0 else 0.0

        avg_trust = trust_weighted / agree if agree > 0 else 0.0



        return {

            'num_agreeing_vehicles': int(agree),

            'num_disagreeing_vehicles': int(disagree),

            'agreement_ratio': float(ratio),

            'neighbor_count': int(total),

            'neighbor_trust_weighted_agreement': float(avg_trust),

            'is_isolated': 1.0 if total == 0 else 0.0

        }



    def to_numpy(self, feature_vector: FeatureVector) -> np.ndarray:

        return np.array([getattr(feature_vector, name) for name in self.get_feature_names()], dtype=np.float32)



    def get_feature_names(self) -> List[str]:

        return [f.name for f in fields(FeatureVector)]



    def _angular_difference(self, a: float, b: float) -> float:

        diff = abs(a - b) % 360

        return min(diff, 360 - diff)



    def _euclidean_distance(self, p1, p2) -> float:

        if not p1 or not p2: return 0.0

        return math.sqrt(sum((a - b) ** 2 for a, b in zip(p1, p2)))
