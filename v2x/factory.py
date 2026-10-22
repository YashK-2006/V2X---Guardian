"""

Fast dict-based V2X message construction used by the live pipeline.



Message dict schema (public fields are what receivers see):

    msg_id, type ("CAM" | "DENM"), sender_id, cert_id, pseudonym, timestamp, nonce,

    x, y, speed, accel, heading, lane, claimed_type, emergency_flag, event, signature

Hidden ground-truth fields (prefixed with "_", never shown to detectors):

    _tx       physical transmitter vehicle id

    _tx_pos   physical transmitter position

    _attack   attack type that produced/modified the message (None if honest)

"""



import random

import secrets

from typing import Dict, Optional, Tuple



from v2x.identity import Certificate



_counter = 0





def _next_id(prefix: str) -> str:

    global _counter

    _counter += 1

    return f"{prefix}-{_counter:08d}"





def make_cam(vehicle_id: str, state: Dict, now: float, cert: Optional[Certificate],

             rng: random.Random, gps_std: float = 1.5) -> Dict:

    x, y = state["position"]

    emergency = state.get("vehicle_type") in ("ambulance", "firetruck", "police")

    return {

        "msg_id": _next_id("CAM"),

        "type": "CAM",

        "sender_id": vehicle_id,

        "cert_id": cert.cert_id if cert else "",

        "pseudonym": cert.pseudonym if cert else "",

        "timestamp": round(now, 2),

        "nonce": secrets.token_hex(6),

        "x": round(x + rng.gauss(0, gps_std), 2),

        "y": round(y + rng.gauss(0, gps_std), 2),

        "speed": round(max(0.0, state.get("speed", 0.0) + rng.gauss(0, 0.3)), 2),

        "accel": round(state.get("acceleration", 0.0), 2),

        "heading": round((state.get("heading", 0.0) + rng.gauss(0, 1.0)) % 360, 1),

        "lane": state.get("lane_id", ""),

        "claimed_type": state.get("vehicle_type", "car"),

        "emergency_flag": emergency,

        "event": None,

        "signature": "",

        "_tx": vehicle_id,

        "_tx_pos": (x, y),

        "_attack": None,

    }





def make_denm(base_cam: Dict, event_type: str, event_pos: Tuple[float, float],

              severity: int, description: str, now: float) -> Dict:

    msg = dict(base_cam)

    msg.update({

        "msg_id": _next_id("DENM"),

        "type": "DENM",

        "nonce": secrets.token_hex(6),

        "timestamp": round(now, 2),

        "event": {

            "event_type": event_type,

            "x": round(event_pos[0], 1),

            "y": round(event_pos[1], 1),

            "severity": severity,

            "description": description,

        },

    })

    return msg





def public_view(msg: Dict) -> Dict:

    """Strip hidden ground-truth fields."""

    return {k: v for k, v in msg.items() if not k.startswith("_")}





def summarize(msg: Dict) -> str:

    """Short human-readable content string for tables."""

    if msg["type"] == "DENM" and msg.get("event"):

        ev = msg["event"]

        return f"{ev['event_type']} @({ev['x']:.0f},{ev['y']:.0f})"

    tag = f" [{msg['claimed_type']}]" if msg.get("emergency_flag") else ""

    return f"Speed {msg['speed'] * 3.6:.0f} km/h, hdg {msg['heading']:.0f}°{tag}"
