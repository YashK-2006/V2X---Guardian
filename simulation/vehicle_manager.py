import sys

import hashlib

import time

import math

from dataclasses import dataclass, field

from typing import Dict, List, Optional



from config import get_config





@dataclass

class VehicleState:

    vehicle_id: str

    position: tuple  # (x, y)

    latitude: float

    longitude: float

    speed: float

    acceleration: float

    heading: float

    lane_id: str

    road_id: str

    vehicle_type: str

    timestamp: float

    is_active: bool = True





@dataclass

class VehicleIdentity:

    vehicle_id: str

    identity_hash: str

    public_key_hash: str

    registration_timestamp: float





@dataclass

class VehicleRecord:

    identity: VehicleIdentity

    current_state: Optional[VehicleState] = None

    behavior_type: str = 'normal'

    misbehavior_profile: Optional[str] = None

    trust_score: float = 0.5

    reputation_score: float = 0.5

    message_count: int = 0

    misbehavior_count: int = 0

    behavior_history: List[VehicleState] = field(default_factory=list)





class VehicleManager:

    """Manages vehicle identities, states, and historical data."""



    def __init__(self, history_size: int = 50):

        self.cfg = get_config()

        self.history_size = history_size

        self._vehicles: Dict[str, VehicleRecord] = {}



    def generate_identity_hash(self, vehicle_id: str) -> str:

        """Generates a SHA-256 hash for the vehicle identity."""

        salt = str(time.time())

        data = f"{vehicle_id}:{salt}".encode('utf-8')

        return hashlib.sha256(data).hexdigest()



    def register_vehicle(self, vehicle_id: str, behavior_type: str = 'normal', misbehavior_profile: Optional[str] = None) -> VehicleRecord:

        """Registers a new vehicle and assigns it an identity."""

        identity_hash = self.generate_identity_hash(vehicle_id)

        # Dummy public key hash for simulation purposes

        pk_hash = hashlib.sha256(f"pk_{vehicle_id}".encode('utf-8')).hexdigest()



        identity = VehicleIdentity(

            vehicle_id=vehicle_id,

            identity_hash=identity_hash,

            public_key_hash=pk_hash,

            registration_timestamp=time.time()

        )



        record = VehicleRecord(

            identity=identity,

            behavior_type=behavior_type,

            misbehavior_profile=misbehavior_profile,

            trust_score=self.cfg.trust.initial_trust

        )



        self._vehicles[vehicle_id] = record

        return record



    def update_vehicle_state(self, vehicle_id: str, state: VehicleState):

        """Updates the state and history for a vehicle."""

        if vehicle_id not in self._vehicles:

            # Auto-register if not found

            self.register_vehicle(vehicle_id)



        record = self._vehicles[vehicle_id]

        record.current_state = state



        record.behavior_history.append(state)

        if len(record.behavior_history) > self.history_size:

            record.behavior_history.pop(0)



    def get_vehicle(self, vehicle_id: str) -> Optional[VehicleRecord]:

        """Retrieves a vehicle record by ID."""

        return self._vehicles.get(vehicle_id)



    def get_all_vehicles(self) -> Dict[str, VehicleRecord]:

        """Returns all registered vehicles."""

        return self._vehicles



    def get_vehicles_by_type(self, behavior_type: str) -> List[VehicleRecord]:

        """Filters vehicles by their behavior type."""

        return [v for v in self._vehicles.values() if v.behavior_type == behavior_type]



    def get_vehicles_in_range(self, position: tuple, range_meters: float) -> List[VehicleRecord]:

        """Finds all active vehicles within a given radius."""

        in_range = []

        for record in self._vehicles.values():

            if record.current_state and record.current_state.is_active:

                v_pos = record.current_state.position

                dist = math.sqrt((v_pos[0] - position[0])**2 + (v_pos[1] - position[1])**2)

                if dist <= range_meters:

                    in_range.append(record)

        return in_range



    def assign_behavior_types(self, vehicle_ids: List[str], misbehavior_ratio: float):

        """Randomly assigns behavior types to a list of vehicles based on ratio."""

        import random



        num_misbehaving = int(len(vehicle_ids) * misbehavior_ratio)

        misbehaving_ids = set(random.sample(vehicle_ids, num_misbehaving))



        profiles = [

            "PositionInconsistency", "SpeedInconsistency", "AccelerationInconsistency",

            "FalseEventReporting", "MessageFrequencyAnomaly", "SuddenBehavioralChange", "SybilIdentity"

        ]



        for vid in vehicle_ids:

            if vid in misbehaving_ids:

                prof = random.choice(profiles)

                if vid in self._vehicles:

                    self._vehicles[vid].behavior_type = 'misbehaving'

                    self._vehicles[vid].misbehavior_profile = prof

                else:

                    self.register_vehicle(vid, 'misbehaving', prof)

            else:

                if vid in self._vehicles:

                    self._vehicles[vid].behavior_type = 'normal'

                    self._vehicles[vid].misbehavior_profile = None

                else:

                    self.register_vehicle(vid, 'normal')
