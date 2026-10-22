import time

import uuid

import random

from typing import Dict, Any, Optional, Tuple



from .message import V2XMessage, MessageType, EventType

import sys

from config import get_config



class DENMMessage(V2XMessage):

    message_type: MessageType = MessageType.DENM

    event_type: EventType

    event_id: str

    event_position_x: float

    event_position_y: float

    event_radius: float

    event_severity: int

    event_description: str

    is_active: bool = True

    expiry_time: Optional[float] = None



class DENMGenerator:

    """Generator for Decentralized Environmental Notification Messages (DENM)."""



    def __init__(self):

        self.config = get_config()



    def generate_event(self, vehicle_id: str, vehicle_hash: str, event_type: EventType, position: Tuple[float, float], severity: int, description: str) -> DENMMessage:

        """Create a DENM for a real event."""

        pos_x, pos_y = position



        return DENMMessage(

            vehicle_id=vehicle_id,

            vehicle_hash=vehicle_hash,

            latitude=0.0,

            longitude=0.0,

            position_x=pos_x,

            position_y=pos_y,

            speed=0.0,

            acceleration=0.0,

            heading=0.0,

            lane_id="unknown",

            event_type=event_type,

            event_id=str(uuid.uuid4()),

            event_position_x=pos_x,

            event_position_y=pos_y,

            event_radius=50.0,

            event_severity=severity,

            event_description=description,

            timestamp=time.time(),

            expiry_time=time.time() + 60.0 # Active for 60 seconds

        )



    def generate_false_event(self, vehicle_id: str, vehicle_hash: str, vehicle_state: Dict[str, Any]) -> DENMMessage:

        """Generate a fake DENM for misbehavior simulation."""

        false_event_types = self.config.misbehavior.false_event_types

        event_str = random.choice(false_event_types)

        event_type = EventType(event_str)



        # Slightly offset position for the fake event

        pos_x = vehicle_state.get("position_x", 0.0) + random.uniform(10.0, 100.0)

        pos_y = vehicle_state.get("position_y", 0.0) + random.uniform(10.0, 100.0)



        return DENMMessage(

            vehicle_id=vehicle_id,

            vehicle_hash=vehicle_hash,

            latitude=vehicle_state.get("latitude", 0.0),

            longitude=vehicle_state.get("longitude", 0.0),

            position_x=vehicle_state.get("position_x", 0.0),

            position_y=vehicle_state.get("position_y", 0.0),

            speed=vehicle_state.get("speed", 0.0),

            acceleration=vehicle_state.get("acceleration", 0.0),

            heading=vehicle_state.get("heading", 0.0),

            lane_id=vehicle_state.get("lane_id", "unknown"),

            event_type=event_type,

            event_id=str(uuid.uuid4()),

            event_position_x=pos_x,

            event_position_y=pos_y,

            event_radius=100.0,

            event_severity=random.randint(1, 5),

            event_description=f"False {event_type.value} reported by {vehicle_id}",

            timestamp=time.time(),

            expiry_time=time.time() + 120.0

        )
