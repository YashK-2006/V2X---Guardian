import threading

import math

from typing import List, Dict, Optional, Tuple, Any



from .message import V2XMessage, MessageType

import sys

from config import get_config



class V2XMessageBus:

    """V2X Message Bus with publish/subscribe mechanism."""



    def __init__(self):

        self.config = get_config()

        self.messages: List[V2XMessage] = []

        self._lock = threading.Lock()

        self.max_history = 10000



    def publish(self, message: V2XMessage) -> None:

        """Add a message to the bus."""

        with self._lock:

            self.messages.append(message)

            if len(self.messages) > self.max_history:

                self.messages.pop(0)



    def get_messages_for_vehicle(self, vehicle_id: str, position: Tuple[float, float], comm_range: float) -> List[V2XMessage]:

        """Return messages from other vehicles within communication range."""

        result = []

        px, py = position

        with self._lock:

            for msg in self.messages:

                if msg.vehicle_id == vehicle_id:

                    continue

                dist = math.hypot(msg.position_x - px, msg.position_y - py)

                if dist <= comm_range:

                    result.append(msg)

        return result



    def get_all_messages(self, since_timestamp: Optional[float] = None) -> List[V2XMessage]:

        """Return all messages, optionally filtering by timestamp."""

        with self._lock:

            if since_timestamp is None:

                return list(self.messages)

            return [msg for msg in self.messages if msg.timestamp >= since_timestamp]



    def get_messages_by_type(self, msg_type: MessageType) -> List[V2XMessage]:

        """Filter messages by type."""

        with self._lock:

            return [msg for msg in self.messages if msg.message_type == msg_type]



    def get_messages_from_vehicle(self, vehicle_id: str) -> List[V2XMessage]:

        """Get all messages originating from a specific vehicle."""

        with self._lock:

            return [msg for msg in self.messages if msg.vehicle_id == vehicle_id]



    def clear_old_messages(self, max_age_seconds: float, current_time: float) -> None:

        """Remove messages older than max_age_seconds."""

        cutoff_time = current_time - max_age_seconds

        with self._lock:

            self.messages = [msg for msg in self.messages if msg.timestamp >= cutoff_time]



    def get_statistics(self) -> Dict[str, Any]:

        """Get message statistics."""

        with self._lock:

            total = len(self.messages)

            counts = {msg_type.value: 0 for msg_type in MessageType}

            for msg in self.messages:

                counts[msg.message_type.value] = counts.get(msg.message_type.value, 0) + 1



        return {

            "total_messages": total,

            "type_counts": counts,

        }



class RSU:

    """Road Side Unit."""



    def __init__(self, rsu_id: str, position: Tuple[float, float], coverage_range: float = 500.0):

        self.rsu_id = rsu_id

        self.position = position

        self.coverage_range = coverage_range

        self.received_messages: List[V2XMessage] = []



    def receive_messages(self, message_bus: V2XMessageBus, current_time: float) -> None:

        """Collect messages within coverage range from the bus."""

        # Simple implementation: we get all messages in range over the last short window (e.g., 1 sec)

        recent_msgs = message_bus.get_all_messages(since_timestamp=current_time - 1.0)

        px, py = self.position



        in_range_msgs = []

        for msg in recent_msgs:

            dist = math.hypot(msg.position_x - px, msg.position_y - py)

            if dist <= self.coverage_range:

                in_range_msgs.append(msg)



        self.received_messages.extend(in_range_msgs)



    def get_vehicles_in_range(self, vehicle_positions: Dict[str, Tuple[float, float]]) -> List[str]:

        """Identify which vehicles are currently within range."""

        in_range = []

        px, py = self.position

        for v_id, (vx, vy) in vehicle_positions.items():

            dist = math.hypot(vx - px, vy - py)

            if dist <= self.coverage_range:

                in_range.append(v_id)

        return in_range
