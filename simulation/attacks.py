"""

Live attack injection.



AttackManager holds the attacks launched against the running simulation. Each

attack transforms the honest messages a vehicle would send (it never touches

SUMO ground truth) and may emit extra messages (fake DENMs, sybil ghosts,

replays, floods). Every produced message is tagged with the hidden `_attack`

ground-truth label used for online detection metrics.

"""



import math

import random

import secrets

from collections import deque

from dataclasses import dataclass, field

from typing import Callable, Deque, Dict, List, Optional



from v2x.factory import make_denm, _next_id





ATTACK_TYPES: Dict[str, Dict[str, str]] = {

    "emergency_spoofing": {"label": "Emergency Vehicle Spoofing", "family": "identity",

                           "description": "Claims to be an ambulance/police/fire truck and broadcasts fake emergency priority"},

    "false_position":     {"label": "False Position", "family": "falsification",

                           "description": "Reports a position offset by 80-250 m"},

    "gps_spoofing":       {"label": "GPS Spoofing", "family": "falsification",

                           "description": "Reported position drifts away gradually from the real one"},

    "false_speed":        {"label": "False Speed", "family": "falsification",

                           "description": "Reports a speed far from the real one"},

    "false_acceleration": {"label": "False Acceleration", "family": "falsification",

                           "description": "Reports physically implausible acceleration"},

    "false_heading":      {"label": "False Heading", "family": "falsification",

                           "description": "Reports a heading inconsistent with its movement"},

    "fake_accident":      {"label": "Fake Accident", "family": "false_event",

                           "description": "Broadcasts DENM accident warnings where no accident exists"},

    "message_flooding":   {"label": "Message Flooding", "family": "dos",

                           "description": "Broadcasts beacons at 10x the normal rate"},

    "replay":             {"label": "Replay Attack", "family": "replay",

                           "description": "Re-broadcasts previously captured messages of other vehicles"},

    "sybil":              {"label": "Sybil Attack", "family": "identity",

                           "description": "Fabricates ghost vehicles with forged identities"},

    "message_injection":  {"label": "Message Injection", "family": "integrity",

                           "description": "Injects tampered DENMs whose signature does not verify"},

    "collusion":          {"label": "Collusion (multi-vehicle)", "family": "collusion",

                           "description": "3 attackers corroborate the same fake accident, claim to be stuck at it and vouch for each other"},

}





@dataclass

class ActiveAttack:

    vehicle_id: str

    attack_type: str

    started_at: float

    params: Dict = field(default_factory=dict)

    messages_sent: int = 0

    last_extra: float = -999.0



    def to_dict(self) -> Dict:

        return {"vehicle_id": self.vehicle_id, "attack_type": self.attack_type,

                "label": ATTACK_TYPES[self.attack_type]["label"], "started_at": self.started_at,

                "params": {k: v for k, v in self.params.items() if not k.startswith("_")},

                "messages_sent": self.messages_sent}





class AttackManager:

    def __init__(self, seed: Optional[int] = None):

        self.rng = random.Random(seed)

        self.active: Dict[str, ActiveAttack] = {}

        self.history: List[Dict] = []

        # Captured honest messages available to replay attackers.

        self.captured: Deque[Dict] = deque(maxlen=400)



    # ------------------------------------------------------------------ control

    def launch(self, vehicle_id: str, attack_type: str, now: float, params: Optional[Dict] = None) -> ActiveAttack:

        if attack_type not in ATTACK_TYPES:

            raise ValueError(f"Unknown attack type {attack_type}")

        p = dict(params or {})

        r = self.rng

        if attack_type == "false_position":

            ang = r.uniform(0, 2 * math.pi)

            dist = p.get("offset", r.uniform(80, 250))

            p.update(dx=dist * math.cos(ang), dy=dist * math.sin(ang), offset=round(dist, 1))

        elif attack_type == "gps_spoofing":

            ang = r.uniform(0, 2 * math.pi)

            p.update(drift_rate=p.get("drift_rate", 4.0), ux=math.cos(ang), uy=math.sin(ang))

        elif attack_type == "false_speed":

            p.setdefault("speed_offset", r.uniform(18, 35))

        elif attack_type == "false_acceleration":

            p.setdefault("fake_accel", r.choice([-1, 1]) * r.uniform(9, 14))

        elif attack_type == "false_heading":

            p.setdefault("heading_offset", r.uniform(110, 180))

        elif attack_type == "emergency_spoofing":

            p.setdefault("claimed_type", r.choice(["ambulance", "ambulance", "police", "firetruck"]))

        elif attack_type == "collusion":

            if "event_x" not in p:

                raise ValueError("collusion needs a shared event location (launched through the orchestrator)")

            p.setdefault("ox", r.uniform(-12, 12))

            p.setdefault("oy", r.uniform(-12, 12))

        elif attack_type == "sybil":

            n = int(p.get("ghosts", 3))

            p["ghosts"] = n

            p["_ghost_ids"] = [f"G{vehicle_id}_{i}" for i in range(n)]

            p["_ghost_certs"] = ["CERT-" + secrets.token_hex(6).upper() for _ in range(n)]

            p["_ghost_offsets"] = [(r.uniform(-25, 25), r.uniform(-25, 25)) for _ in range(n)]

        attack = ActiveAttack(vehicle_id, attack_type, now, p)

        self.active[vehicle_id] = attack

        self.history.append({"event": "launch", "time": now, **attack.to_dict()})

        return attack



    def stop(self, vehicle_id: str, now: float) -> Optional[ActiveAttack]:

        attack = self.active.pop(vehicle_id, None)

        if attack:

            self.history.append({"event": "stop", "time": now, **attack.to_dict()})

        return attack



    def stop_all(self, now: float):

        for vid in list(self.active):

            self.stop(vid, now)



    def is_attacker(self, vehicle_id: str) -> bool:

        return vehicle_id in self.active



    def colluders(self, vehicle_id: str) -> List[str]:

        """Members of the same collusion group (empty if not colluding)."""

        a = self.active.get(vehicle_id)

        if not a or a.attack_type != "collusion":

            return []

        return [v for v, x in self.active.items() if x.attack_type == "collusion" and x.params.get("group") == a.params.get("group")]



    def list_active(self) -> List[Dict]:

        return [a.to_dict() for a in self.active.values()]



    def reset(self):

        self.active.clear()

        self.history.clear()

        self.captured.clear()



    # ---------------------------------------------------------------- transform

    def beacon_due(self, vehicle_id: str, normally_due: bool) -> bool:

        attack = self.active.get(vehicle_id)

        if attack and attack.attack_type == "message_flooding":

            return True

        return normally_due



    def capture(self, msg: Dict):

        if msg.get("_attack") is None and msg["type"] == "CAM":

            self.captured.append(msg)



    def transform(self, msg: Dict, state: Dict, now: float,

                  sign: Callable[[str, Dict], str]) -> List[Dict]:

        """Apply the vehicle's active attack to an honest CAM. Returns messages to transmit."""

        attack = self.active.get(msg["sender_id"])

        if attack is None:

            msg["signature"] = sign(msg["sender_id"], msg)

            return [msg]



        t = attack.attack_type

        p = attack.params

        out = [msg]

        tag = True  # whether the primary CAM itself is malicious



        if t == "false_position":

            msg["x"] = round(msg["x"] + p["dx"], 2)

            msg["y"] = round(msg["y"] + p["dy"], 2)

        elif t == "gps_spoofing":

            drift = min(400.0, p["drift_rate"] * (now - attack.started_at))

            msg["x"] = round(msg["x"] + p["ux"] * drift, 2)

            msg["y"] = round(msg["y"] + p["uy"] * drift, 2)

        elif t == "false_speed":

            msg["speed"] = round(msg["speed"] + p["speed_offset"], 2)

        elif t == "false_acceleration":

            msg["accel"] = round(p["fake_accel"], 2)

        elif t == "false_heading":

            msg["heading"] = round((msg["heading"] + p["heading_offset"]) % 360, 1)

        elif t == "emergency_spoofing":

            msg["claimed_type"] = p["claimed_type"]

            msg["emergency_flag"] = True

            if now - attack.last_extra >= 2.0:

                attack.last_extra = now

                denm = make_denm(msg, "EMERGENCY_VEHICLE_APPROACH", (msg["x"], msg["y"]), 5,

                                 f"{p['claimed_type'].title()} approaching - clear the lane", now)

                out.append(denm)

        elif t == "fake_accident":

            tag = False

            if now - attack.last_extra >= 2.0:

                attack.last_extra = now

                rad = math.radians(msg["heading"])

                ahead = (msg["x"] + 90 * math.sin(rad), msg["y"] + 90 * math.cos(rad))

                out.append(make_denm(msg, "ACCIDENT", ahead, 4, "Collision ahead - lanes blocked", now))

        elif t == "collusion":

            # claim to be stuck at the (fake) accident and keep reporting it, like the other group members

            msg["x"] = round(p["event_x"] + p["ox"], 2)

            msg["y"] = round(p["event_y"] + p["oy"], 2)

            msg["speed"], msg["accel"] = 0.0, 0.0

            if now - attack.last_extra >= 2.0:

                attack.last_extra = now

                out.append(make_denm(msg, "ACCIDENT", (p["event_x"], p["event_y"]), 5,

                                     "Multi-vehicle collision - road blocked", now))

        elif t == "message_flooding":

            pass  # beacon_due() forces a CAM every step

        elif t == "replay":

            tag = False

            if now - attack.last_extra >= 0.5:

                attack.last_extra = now

                old = [m for m in self.captured if now - m["timestamp"] >= 3.0 and m["sender_id"] != msg["sender_id"]]

                for victim_msg in self.rng.sample(old, min(2, len(old))):

                    replayed = dict(victim_msg)  # identical payload, nonce and signature

                    replayed["_tx"] = msg["_tx"]

                    replayed["_tx_pos"] = msg["_tx_pos"]

                    replayed["_attack"] = "replay"

                    out.append(replayed)

        elif t == "sybil":

            tag = False

            for gid, gcert, (ox, oy) in zip(p["_ghost_ids"], p["_ghost_certs"], p["_ghost_offsets"]):

                ghost = dict(msg)

                ghost.update({

                    "msg_id": _next_id("CAM"), "sender_id": gid, "cert_id": gcert,

                    "pseudonym": "PS-" + gid[-6:].upper(), "nonce": secrets.token_hex(6),

                    "x": round(msg["x"] + ox, 2), "y": round(msg["y"] + oy, 2),

                    "claimed_type": "car", "emergency_flag": False,

                    "signature": secrets.token_hex(32), "_attack": "sybil",

                })

                out.append(ghost)

        elif t == "message_injection":

            tag = False

            if now - attack.last_extra >= 1.5:

                attack.last_extra = now

                ev = self.rng.choice(["ROAD_HAZARD", "ICE_ON_ROAD", "WRONG_WAY_DRIVER"])

                inj = make_denm(msg, ev, (msg["x"] + self.rng.uniform(-60, 60), msg["y"] + self.rng.uniform(-60, 60)),

                                3, f"{ev.replace('_', ' ').title()} reported", now)

                inj["signature"] = sign(msg["sender_id"], inj)

                inj["event"] = dict(inj["event"], severity=5)  # tampered after signing

                inj["x"] = round(inj["x"] + 0.5, 2)

                inj["_attack"] = "message_injection"

                out.append(inj)



        if tag:

            msg["_attack"] = t

        for m in out:

            if m.get("_attack") is None and m is not msg:

                m["_attack"] = t

            if not m.get("signature"):

                m["signature"] = sign(m["sender_id"], m)

        attack.messages_sent += sum(1 for m in out if m.get("_attack"))

        return out
