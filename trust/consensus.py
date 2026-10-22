import sys

import math

from dataclasses import dataclass, field

from typing import Dict, List, Tuple



from config import get_config, TrustConfig



@dataclass

class ConsensusResult:

    vehicle_id: str

    consensus_score: float

    supporting_count: int

    opposing_count: int

    total_neighbors: int

    details: List[dict] = field(default_factory=list)



def _xy(msg: dict) -> Tuple[float, float]:

    """Accepts both V2XMessage.to_dict() (position_x/position_y) and plain x/y dicts."""

    return (msg.get("position_x", msg.get("x", 0.0)), msg.get("position_y", msg.get("y", 0.0)))





class NeighborConsensus:

    def __init__(self, config: TrustConfig = None):

        self.config = config or get_config().trust



    def compute_consensus(self, target_vehicle_id: str, target_message: dict,

                          neighbor_messages: List[dict], neighbor_trust_scores: Dict[str, float]) -> ConsensusResult:

        if not neighbor_messages:

            return ConsensusResult(

                vehicle_id=target_vehicle_id,

                consensus_score=0.5, # Neutral if no neighbors

                supporting_count=0,

                opposing_count=0,

                total_neighbors=0

            )



        supporting_weight = 0.0

        total_weight = 0.0

        supporting_count = 0

        opposing_count = 0

        details = []



        is_event = "event_type" in target_message



        for msg in neighbor_messages:

            n_id = msg.get("vehicle_id")

            if not n_id or n_id not in neighbor_trust_scores:

                continue



            n_trust = neighbor_trust_scores[n_id]

            total_weight += n_trust



            supports = False

            if is_event:

                # Target is reporting an event, check if neighbor corroborates

                # If neighbor reports the same event, it supports

                n_event = msg.get("event_type")

                if n_event == target_message.get("event_type"):

                    supports = True

            else:

                # Target is reporting position. We check if neighbor's view of target's position aligns (simplified)

                # In real scenario, neighbor would report where it thinks target is, or its own position to check distance.

                # Assuming `check_position_agreement` does something reasonable here

                supports = self.check_position_agreement(target_message, msg, threshold=50.0)



            if supports:

                supporting_weight += n_trust

                supporting_count += 1

            else:

                opposing_count += 1



            details.append({

                "neighbor_id": n_id,

                "trust_score": n_trust,

                "supports": supports

            })



        if total_weight > 0:

            consensus_score = supporting_weight / total_weight

        else:

            consensus_score = 0.5



        return ConsensusResult(

            vehicle_id=target_vehicle_id,

            consensus_score=consensus_score,

            supporting_count=supporting_count,

            opposing_count=opposing_count,

            total_neighbors=len(neighbor_messages),

            details=details

        )



    def check_position_agreement(self, target_pos: dict, neighbor_pos: dict, threshold: float) -> bool:

        # Simplistic check: If neighbors are within comm range and reporting close timestamps

        t_x, t_y = _xy(target_pos)

        n_x, n_y = _xy(neighbor_pos)



        distance = math.sqrt((t_x - n_x)**2 + (t_y - n_y)**2)

        # Assuming if neighbor is within comm range, it supports the position claim conceptually

        # In reality, this requires sensor data matching.

        return distance <= get_config().vehicle.communication_range



    def check_event_agreement(self, target_event: dict, neighbor_messages: List[dict]) -> Tuple[int, int]:

        supporting = 0

        opposing = 0

        t_type = target_event.get("event_type")

        for msg in neighbor_messages:

            if msg.get("event_type") == t_type:

                supporting += 1

            else:

                opposing += 1

        return supporting, opposing



    def get_neighbors(self, vehicle_id: str, all_vehicles: Dict[str, dict], comm_range: float) -> List[str]:

        if vehicle_id not in all_vehicles:

            return []



        target = all_vehicles[vehicle_id]

        t_x, t_y = target.get("x", 0.0), target.get("y", 0.0)

        neighbors = []



        for v_id, v_data in all_vehicles.items():

            if v_id == vehicle_id:

                continue

            v_x, v_y = v_data.get("x", 0.0), v_data.get("y", 0.0)

            dist = math.sqrt((t_x - v_x)**2 + (t_y - v_y)**2)

            if dist <= comm_range:

                neighbors.append(v_id)



        return neighbors
