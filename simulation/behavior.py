import sys

import random

from typing import Dict, Any, Optional



from config import AppConfig

from simulation.vehicle_manager import VehicleState





class NormalBehavior:

    """Generates realistic normal vehicle behavior and sensor noise."""



    @staticmethod

    def generate_message_data(vehicle_state: VehicleState, config: AppConfig) -> Dict[str, Any]:

        """Applies Gaussian noise to actual vehicle state to simulate sensors."""

        v_cfg = config.vehicle



        # Add noise to position

        px, py = vehicle_state.position

        px_noisy = px + random.gauss(0, v_cfg.position_noise_std)

        py_noisy = py + random.gauss(0, v_cfg.position_noise_std)



        # Add noise to speed

        speed_noisy = max(0.0, vehicle_state.speed + random.gauss(0, v_cfg.speed_noise_std))



        # Add noise to heading

        heading_noisy = (vehicle_state.heading + random.gauss(0, v_cfg.heading_noise_std)) % 360.0



        return {

            "vehicle_id": vehicle_state.vehicle_id,

            "position": (px_noisy, py_noisy),

            "speed": speed_noisy,

            "acceleration": vehicle_state.acceleration,

            "heading": heading_noisy,

            "lane_id": vehicle_state.lane_id,

            "road_id": vehicle_state.road_id,

            "timestamp": vehicle_state.timestamp

        }



    @staticmethod

    def should_send_cam(last_cam_time: float, current_time: float, frequency: float) -> bool:

        """Determines if a CAM message should be sent based on frequency."""

        return (current_time - last_cam_time) >= (1.0 / frequency)



    @staticmethod

    def should_send_denm(vehicle_state: VehicleState, environment: Dict[str, Any]) -> bool:

        """Determines if a DENM message should be sent for an event."""

        # E.g. hard braking, accident detection, hazard in environment

        if vehicle_state.acceleration < -5.0:  # Hard braking

            return True



        # Add other actual environmental triggers here

        return False
