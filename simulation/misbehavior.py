import sys

import numpy as np

from abc import ABC, abstractmethod

from typing import Dict, Any



from config import AppConfig

from simulation.vehicle_manager import VehicleState

from simulation.behavior import NormalBehavior





class MisbehaviorProfile(ABC):

    """Base class for all synthetic misbehavior profiles."""



    def __init__(self, config: AppConfig, seed: int = 42):

        self.config = config

        self.rng = np.random.default_rng(seed)

        self.history = []



    @abstractmethod

    def apply(self, vehicle_state: VehicleState) -> Dict[str, Any]:

        """Applies the misbehavior to the vehicle state and returns modified message data."""

        pass



    @abstractmethod

    def get_type(self) -> str:

        """Returns the identifier string of the misbehavior."""

        pass



    def get_severity(self) -> float:

        """Returns the severity of the misbehavior from [0.0 to 1.0]."""

        return 0.5



    def is_active(self, current_step: int) -> bool:

        """Returns whether the misbehavior is active at the current step."""

        return True





class PositionInconsistency(MisbehaviorProfile):

    def apply(self, vehicle_state: VehicleState) -> Dict[str, Any]:

        data = NormalBehavior.generate_message_data(vehicle_state, self.config)

        offset = self.rng.uniform(

            self.config.misbehavior.position_offset_min,

            self.config.misbehavior.position_offset_max

        )

        angle = self.rng.uniform(0, 2 * np.pi)



        px, py = data["position"]

        data["position"] = (px + offset * np.cos(angle), py + offset * np.sin(angle))



        self.history.append(data)

        return data



    def get_type(self) -> str:

        return "PositionInconsistency"





class SpeedInconsistency(MisbehaviorProfile):

    def apply(self, vehicle_state: VehicleState) -> Dict[str, Any]:

        data = NormalBehavior.generate_message_data(vehicle_state, self.config)

        offset = self.rng.uniform(

            self.config.misbehavior.speed_offset_min,

            self.config.misbehavior.speed_offset_max

        )

        sign = self.rng.choice([-1, 1])

        data["speed"] = max(0.0, data["speed"] + sign * offset)



        self.history.append(data)

        return data



    def get_type(self) -> str:

        return "SpeedInconsistency"





class AccelerationInconsistency(MisbehaviorProfile):

    def apply(self, vehicle_state: VehicleState) -> Dict[str, Any]:

        data = NormalBehavior.generate_message_data(vehicle_state, self.config)

        # Apply physically impossible acceleration

        offset = self.config.misbehavior.acceleration_offset

        sign = self.rng.choice([-1, 1])

        data["acceleration"] += sign * offset



        self.history.append(data)

        return data



    def get_type(self) -> str:

        return "AccelerationInconsistency"





class FalseEventReporting(MisbehaviorProfile):

    def apply(self, vehicle_state: VehicleState) -> Dict[str, Any]:

        data = NormalBehavior.generate_message_data(vehicle_state, self.config)



        # Inject false DENM event data occasionally

        if self.rng.random() < self.config.misbehavior.false_event_probability:

            event_type = self.rng.choice(self.config.misbehavior.false_event_types)

            data["false_event"] = event_type



        self.history.append(data)

        return data



    def get_type(self) -> str:

        return "FalseEventReporting"





class MessageFrequencyAnomaly(MisbehaviorProfile):

    def apply(self, vehicle_state: VehicleState) -> Dict[str, Any]:

        data = NormalBehavior.generate_message_data(vehicle_state, self.config)

        # Represents higher message frequency via metadata.

        # Actual message dispatch frequency should be handled by the caller.

        data["frequency_multiplier"] = self.config.misbehavior.frequency_multiplier

        self.history.append(data)

        return data



    def get_type(self) -> str:

        return "MessageFrequencyAnomaly"





class SuddenBehavioralChange(MisbehaviorProfile):

    def is_active(self, current_step: int) -> bool:

        return current_step >= self.config.misbehavior.change_trigger_step



    def apply(self, vehicle_state: VehicleState) -> Dict[str, Any]:

        # For simplicity, applies position and speed inconsistency when active

        data = NormalBehavior.generate_message_data(vehicle_state, self.config)



        pos_offset = self.rng.uniform(50, 100)

        speed_offset = self.rng.uniform(10, 20)



        px, py = data["position"]

        data["position"] = (px + pos_offset, py + pos_offset)

        data["speed"] += speed_offset



        self.history.append(data)

        return data



    def get_type(self) -> str:

        return "SuddenBehavioralChange"





class SybilIdentity(MisbehaviorProfile):

    def apply(self, vehicle_state: VehicleState) -> Dict[str, Any]:

        data = NormalBehavior.generate_message_data(vehicle_state, self.config)

        # Generate multiple messages with fake identities

        sybil_messages = []

        for i in range(self.config.misbehavior.sybil_count):

            syb_data = data.copy()

            syb_data["vehicle_id"] = f"{data['vehicle_id']}_sybil_{i}"

            # Slightly shift position

            px, py = syb_data["position"]

            syb_data["position"] = (px + self.rng.uniform(-10, 10), py + self.rng.uniform(-10, 10))

            sybil_messages.append(syb_data)



        data["sybil_clones"] = sybil_messages

        self.history.append(data)

        return data



    def get_type(self) -> str:

        return "SybilIdentity"
