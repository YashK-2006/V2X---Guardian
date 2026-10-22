import time

import math

from typing import List, Dict, Any, Optional

from pydantic import BaseModel



from .message import V2XMessage

import sys

from config import get_config



class ValidationResult(BaseModel):

    is_valid: bool

    errors: List[str]

    warnings: List[str]

    checks_passed: Dict[str, bool]



class MessageValidator:

    """Message validation pipeline for V2X messages."""



    def __init__(self):

        self.config = get_config()

        # History tracks the last message from each vehicle for consistency checks

        self.vehicle_history: Dict[str, V2XMessage] = {}



    def validate(self, message: V2XMessage, vehicle_state: Optional[Dict[str, Any]] = None) -> ValidationResult:

        """Run all validation checks on the message."""

        errors = []

        warnings = []

        checks_passed = {}



        # Check 1: Schema

        passed_schema, err_schema = self.check_schema(message)

        checks_passed["schema"] = passed_schema

        if not passed_schema:

            errors.append(err_schema)



        # Check 2: Timestamp Freshness

        passed_fresh, err_fresh = self.check_timestamp_freshness(message, max_age=10.0)

        checks_passed["freshness"] = passed_fresh

        if not passed_fresh:

            errors.append(err_fresh)



        # Check 3: Position Plausibility

        passed_pos, err_pos = self.check_position_plausibility(message)

        checks_passed["position_plausibility"] = passed_pos

        if not passed_pos:

            errors.append(err_pos)



        # Check 4: Speed Bounds

        max_speed = self.config.vehicle.max_speed

        passed_speed, err_speed = self.check_speed_bounds(message, max_speed)

        checks_passed["speed_bounds"] = passed_speed

        if not passed_speed:

            errors.append(err_speed)



        # Check 5: Acceleration Bounds

        max_accel = self.config.vehicle.max_acceleration

        max_decel = self.config.vehicle.max_deceleration

        passed_accel, err_accel = self.check_acceleration_bounds(message, max_accel, max_decel)

        checks_passed["acceleration_bounds"] = passed_accel

        if not passed_accel:

            errors.append(err_accel)



        # Check 6: Heading Range

        passed_head, err_head = self.check_heading_range(message)

        checks_passed["heading_range"] = passed_head

        if not passed_head:

            errors.append(err_head)



        # Check 7: Position Speed Consistency & Frequency

        previous_message = self.vehicle_history.get(message.vehicle_id)

        if previous_message:

            dt = message.timestamp - previous_message.timestamp



            # Rate limiting

            max_freq = self.config.vehicle.cam_frequency * 2.0 # Allow some jitter

            passed_freq, err_freq = self.check_message_frequency(dt, max_freq)

            checks_passed["frequency"] = passed_freq

            if not passed_freq:

                warnings.append(err_freq)



            if dt > 0:

                passed_cons, err_cons = self.check_position_speed_consistency(message, previous_message, dt)

                checks_passed["consistency"] = passed_cons

                if not passed_cons:

                    errors.append(err_cons)

        else:

            checks_passed["frequency"] = True

            checks_passed["consistency"] = True



        # Update history

        self.vehicle_history[message.vehicle_id] = message



        is_valid = len(errors) == 0

        return ValidationResult(

            is_valid=is_valid,

            errors=errors,

            warnings=warnings,

            checks_passed=checks_passed

        )



    def check_schema(self, message: V2XMessage) -> tuple[bool, str]:

        """Check if all required fields are present (handled mostly by Pydantic)."""

        if not message.vehicle_id or not message.message_id:

            return False, "Missing critical identifiers in message."

        return True, ""



    def check_timestamp_freshness(self, message: V2XMessage, max_age: float = 10.0) -> tuple[bool, str]:

        """Check if message is too old."""

        age = time.time() - message.timestamp

        if age > max_age or age < -2.0: # allow slight clock skew

            return False, f"Message timestamp {message.timestamp} is stale or from future (age: {age:.2f}s)."

        return True, ""



    def check_position_plausibility(self, message: V2XMessage) -> tuple[bool, str]:

        """Check if coordinates are within plausible simulation bounds."""

        # Just simple bounds check assuming a generic grid for now

        max_dim = self.config.simulation.grid_size * self.config.simulation.grid_length + 1000

        if not (-1000 <= message.position_x <= max_dim and -1000 <= message.position_y <= max_dim):

            return False, f"Position ({message.position_x}, {message.position_y}) is out of reasonable bounds."

        return True, ""



    def check_speed_bounds(self, message: V2XMessage, max_speed: float) -> tuple[bool, str]:

        """Check if speed is within physical limits."""

        # Allow small buffer for sensor noise

        if message.speed < -5.0 or message.speed > max_speed + 15.0:

            return False, f"Speed {message.speed:.2f} exceeds bounds [-5.0, {max_speed+15.0}]."

        return True, ""



    def check_acceleration_bounds(self, message: V2XMessage, max_accel: float, max_decel: float) -> tuple[bool, str]:

        """Check if acceleration is physically possible."""

        # Buffer for noise

        if message.acceleration > max_accel + 5.0 or message.acceleration < -max_decel - 5.0:

            return False, f"Acceleration {message.acceleration:.2f} outside bounds [-{max_decel+5.0}, {max_accel+5.0}]."

        return True, ""



    def check_heading_range(self, message: V2XMessage) -> tuple[bool, str]:

        """Check if heading is valid [0, 360)."""

        if not (0.0 <= message.heading < 360.1): # allow small float imprecision

            return False, f"Heading {message.heading} is out of bounds [0, 360)."

        return True, ""



    def check_position_speed_consistency(self, message: V2XMessage, previous_message: V2XMessage, dt: float) -> tuple[bool, str]:

        """Check if position change matches reported speed."""

        dist = math.hypot(message.position_x - previous_message.position_x,

                          message.position_y - previous_message.position_y)



        # Max possible distance covered in dt, given max possible speed in that window

        max_avg_speed = max(message.speed, previous_message.speed) + (self.config.vehicle.max_acceleration * dt) + 15.0 # buffer

        expected_max_dist = max_avg_speed * dt



        if dist > expected_max_dist:

            return False, f"Position change {dist:.2f}m is inconsistent with speed over {dt:.2f}s interval."

        return True, ""



    def check_message_frequency(self, dt: float, max_frequency: float) -> tuple[bool, str]:

        """Check if not exceeding rate limit."""

        if dt > 0:

            freq = 1.0 / dt

            if freq > max_frequency:

                return False, f"Message frequency {freq:.1f}Hz exceeds maximum {max_frequency}Hz."

        return True, ""
