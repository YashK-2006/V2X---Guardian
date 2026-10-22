import time

import uuid

import hmac

import hashlib

from enum import Enum

from typing import Optional, Dict, Any

from pydantic import BaseModel, Field



class MessageType(str, Enum):

    CAM = "CAM"

    DENM = "DENM"

    BSM = "BSM"



class EventType(str, Enum):

    ACCIDENT = "ACCIDENT"

    ROAD_HAZARD = "ROAD_HAZARD"

    CONGESTION = "CONGESTION"

    EMERGENCY = "EMERGENCY"

    ICE_ON_ROAD = "ICE_ON_ROAD"

    WRONG_WAY_DRIVER = "WRONG_WAY_DRIVER"



class V2XMessage(BaseModel):

    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    vehicle_id: str

    vehicle_hash: str

    timestamp: float = Field(default_factory=time.time)

    latitude: float

    longitude: float

    position_x: float

    position_y: float

    speed: float

    acceleration: float

    heading: float

    lane_id: str

    message_type: MessageType

    signature: Optional[str] = None

    metadata: Dict[str, Any] = Field(default_factory=dict)



    def to_dict(self) -> Dict[str, Any]:

        """Convert message to dictionary."""

        return self.model_dump()



    @classmethod

    def from_dict(cls, data: Dict[str, Any]) -> "V2XMessage":

        """Create a message from dictionary."""

        return cls(**data)



    def _get_signature_payload(self) -> bytes:

        """Get the payload string for signature generation."""

        # Excluding signature and metadata for hashing

        payload = f"{self.message_id}:{self.vehicle_id}:{self.timestamp}:{self.position_x}:{self.position_y}:{self.speed}:{self.heading}:{self.message_type}"

        return payload.encode('utf-8')



    def compute_signature(self, private_key: str) -> str:

        """Compute HMAC-SHA256 signature and set it."""

        payload = self._get_signature_payload()

        sig = hmac.new(private_key.encode('utf-8'), payload, hashlib.sha256).hexdigest()

        self.signature = sig

        return sig



    def verify_signature(self, public_key: str) -> bool:

        """Verify the signature using the given key (symmetric key logic for HMAC)."""

        if not self.signature:

            return False

        payload = self._get_signature_payload()

        expected_sig = hmac.new(public_key.encode('utf-8'), payload, hashlib.sha256).hexdigest()

        return hmac.compare_digest(self.signature, expected_sig)



    def age(self, current_time: float) -> float:

        """Return the age of the message in seconds relative to current_time."""

        return max(0.0, current_time - self.timestamp)
