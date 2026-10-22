import time

import random

from typing import Dict, Any, Optional



from .message import V2XMessage, MessageType

import sys

from config import get_config



class CAMMessage(V2XMessage):

    message_type: MessageType = MessageType.CAM

    vehicle_length: float = 5.0

    vehicle_width: float = 2.0

    vehicle_type_class: str = "passenger"



class CAMGenerator:

    """Generator for Cooperative Awareness Messages (CAM)."""



    def __init__(self):

        self.config = get_config()



    def generate(self, vehicle_id: str, vehicle_hash: str, vehicle_state: Dict[str, Any], noise_config: Optional[Dict[str, float]] = None) -> CAMMessage:

        """Generate a CAM from vehicle state, applying optional noise."""



        pos_x = vehicle_state.get("position_x", 0.0)

        pos_y = vehicle_state.get("position_y", 0.0)

        lat = vehicle_state.get("latitude", 0.0)

        lon = vehicle_state.get("longitude", 0.0)

        speed = vehicle_state.get("speed", 0.0)

        heading = vehicle_state.get("heading", 0.0)



        if noise_config:

            pos_x += random.gauss(0, noise_config.get("position_noise_std", 0.0))

            pos_y += random.gauss(0, noise_config.get("position_noise_std", 0.0))

            speed += random.gauss(0, noise_config.get("speed_noise_std", 0.0))

            heading += random.gauss(0, noise_config.get("heading_noise_std", 0.0))

            # Heading should be within 0-360

            heading = heading % 360.0



        return CAMMessage(

            vehicle_id=vehicle_id,

            vehicle_hash=vehicle_hash,

            latitude=lat,

            longitude=lon,

            position_x=pos_x,

            position_y=pos_y,

            speed=speed,

            acceleration=vehicle_state.get("acceleration", 0.0),

            heading=heading,

            lane_id=vehicle_state.get("lane_id", "unknown"),

            vehicle_length=vehicle_state.get("length", 5.0),

            vehicle_width=vehicle_state.get("width", 2.0),

            vehicle_type_class=vehicle_state.get("type", "passenger"),

            timestamp=time.time()

        )



    def generate_batch(self, vehicle_states_dict: Dict[str, Dict[str, Any]]) -> Dict[str, CAMMessage]:

        """Generate CAMs for multiple vehicles."""

        noise_cfg = {

            "position_noise_std": self.config.vehicle.position_noise_std,

            "speed_noise_std": self.config.vehicle.speed_noise_std,

            "heading_noise_std": self.config.vehicle.heading_noise_std,

        }



        cams = {}

        for v_id, state in vehicle_states_dict.items():

            v_hash = state.get("vehicle_hash", "default_hash")

            cams[v_id] = self.generate(v_id, v_hash, state, noise_config=noise_cfg)

        return cams
