"""

Deterministic plausibility detectors for V2X misbehavior.



Each detector inspects a feature dict (see ai.misbehavior_detector.FEATURE_NAMES)

and returns RuleHit records that explain *why* a message is suspicious: the

attack type, a score in [0, 1], and the expected vs observed values used as

evidence.

"""



from dataclasses import dataclass, asdict

from typing import Dict, List





@dataclass

class RuleHit:

    rule: str

    attack_type: str

    score: float

    expected: str

    observed: str



    def to_dict(self) -> Dict:

        return asdict(self)





def _clip(v: float) -> float:

    return max(0.0, min(0.99, v))





def evaluate_rules(f: Dict[str, float], ctx: Dict) -> List[RuleHit]:

    """Run all rule detectors. `ctx` carries non-numeric context (types, event names, sticky labels)."""

    hits: List[RuleHit] = []



    # --- Authentication / identity -------------------------------------------------

    if f["bad_signature"]:

        hits.append(RuleHit("signature_check", "message_injection", 0.97,

                            "valid ECDSA/HMAC signature", "signature verification failed"))

    if f["unknown_cert"]:

        if f["colocated_ids"] >= 1:

            hits.append(RuleHit("sybil_colocation", "sybil", _clip(0.9 + 0.03 * f["colocated_ids"]),

                                "one identity per radio source",

                                f"{int(f['colocated_ids']) + 1} identities from the same transmitter"))

        else:

            hits.append(RuleHit("certificate_check", "sybil", 0.85,

                                "certificate issued by registry", "unknown certificate"))

    if f["revoked"]:

        hits.append(RuleHit("revocation_check", "revoked_identity", 0.88,

                            "non-revoked certificate", "certificate on revocation list"))



    # --- Emergency vehicle spoofing -----------------------------------------------

    if f["claimed_emergency"] and f["type_mismatch"]:

        score = 0.95 + (0.02 if f["event_emergency"] else 0.0)

        hits.append(RuleHit("type_consistency", "emergency_spoofing", _clip(score),

                            f"registered type: {ctx.get('registered_type')}",

                            f"claimed type: {ctx.get('claimed_type')} (emergency flag set)"))

    elif f["type_mismatch"]:

        hits.append(RuleHit("type_consistency", "emergency_spoofing", 0.7,

                            f"registered type: {ctx.get('registered_type')}",

                            f"claimed type: {ctx.get('claimed_type')}"))



    # --- Replay --------------------------------------------------------------------

    if f["duplicate_nonce"]:

        hits.append(RuleHit("nonce_freshness", "replay", 0.96, "unique nonce", "nonce already seen"))

    elif f["msg_age"] > 2.0:

        hits.append(RuleHit("timestamp_freshness", "replay", _clip(0.7 + f["msg_age"] / 30),

                            "message age < 2.0 s", f"message age {f['msg_age']:.1f} s"))



    # --- Position ------------------------------------------------------------------

    replayed = f["duplicate_nonce"] or f["msg_age"] > 2.0

    if f["has_localization"] and f["loc_error"] > 25 and not replayed and not f["unknown_cert"]:

        attack = ctx.get("position_label") or ("false_position" if f["loc_error"] > 60 else "gps_spoofing")

        if f["sender_in_event_group"] or ctx.get("at_own_event"):

            # falsified presence at a (contested / self-reported) accident: colluding witness

            attack = "collusion"

        hits.append(RuleHit("rsu_localization", attack, _clip(0.55 + f["loc_error"] / 150),

                            "claimed position within 25 m of RSU-localized transmitter",

                            f"deviation {f['loc_error']:.0f} m"))



    # --- Kinematics ----------------------------------------------------------------

    if f["dt"] >= 0.5 and f["speed_mismatch"] > 8 and f["loc_error"] <= 25:

        hits.append(RuleHit("speed_plausibility", "false_speed", _clip(0.55 + f["speed_mismatch"] / 50),

                            f"≈{f['implied_speed'] * 3.6:.0f} km/h (from positions)",

                            f"{f['claimed_speed'] * 3.6:.0f} km/h claimed"))

    if f["accel_abs"] > 7 and f["accel_mismatch"] > 5:

        hits.append(RuleHit("acceleration_plausibility", "false_acceleration", _clip(0.55 + f["accel_mismatch"] / 25),

                            f"≈{f['implied_accel']:.1f} m/s² (from speeds)", f"{f['claimed_accel']:.1f} m/s² claimed"))

    if f["moved"] > 5 and f["heading_motion_diff"] > 75 and ctx.get("heading_violations", 0) >= 3:

        hits.append(RuleHit("heading_consistency", "false_heading", _clip(0.5 + f["heading_motion_diff"] / 360),

                            "heading aligned with direction of travel",

                            f"{f['heading_motion_diff']:.0f}° off direction of travel"))



    # --- Frequency -----------------------------------------------------------------

    if f["msg_rate"] > 4:

        hits.append(RuleHit("rate_limit", "message_flooding", _clip(0.55 + f["msg_rate"] / 25),

                            "≤ 2 msgs/s per station", f"{f['msg_rate']:.0f} msgs/s"))



    # --- Event plausibility (DENM) -------------------------------------------------

    event_type = ctx.get("event_type")

    if f["is_denm"] and event_type in ("ACCIDENT", "ROAD_HAZARD", "CONGESTION"):

        near, slowed, fast = f["denm_near_count"], f["denm_support"], f["denm_contradict"]

        # a slow/stopped reporter at the event location is describing its own situation

        reporter_on_scene = f["denm_distance"] < 25 and f["claimed_speed"] < 3

        if f["event_reporters"] >= 2 and event_type != "CONGESTION" and fast >= 1 and slowed < 0.2:

            hits.append(RuleHit("collusion_detection", "collusion", _clip(0.88 + 0.03 * f["event_reporters"]),

                                "independent vehicles near the event confirm it",

                                f"{int(f['event_reporters'])} stations report the same {event_type.lower()}, "

                                f"{int(fast)} independent vehicles pass at speed"))

        if f["event_drift"] > 15 and event_type != "CONGESTION":  # queues move; accidents/hazards do not

            hits.append(RuleHit("event_stationarity", "fake_accident", _clip(0.85 + f["event_drift"] / 400),

                                "static event location across repeated reports",

                                f"reported {event_type.lower()} moved {f['event_drift']:.0f} m between reports"))

        if fast >= (3 if reporter_on_scene else 1) and slowed == 0 and event_type != "CONGESTION" \

                and f["event_reporters"] < 2:

            hits.append(RuleHit("event_corroboration", "fake_accident", _clip(0.82 + 0.04 * fast),

                                "vehicles near the event slow down / stop",

                                f"{int(fast)} vehicles pass the event location at speed, none slowed"))

        elif event_type == "CONGESTION" and not reporter_on_scene and fast >= 2 and slowed == 0:

            hits.append(RuleHit("event_corroboration", "fake_accident", _clip(0.6 + 0.04 * fast),

                                "congestion reported by vehicles inside the queue",

                                f"reporter moving at {f['claimed_speed'] * 3.6:.0f} km/h, {int(fast)} vehicles flowing freely"))

        elif near == 0 and event_type == "ACCIDENT" and not reporter_on_scene:

            score = 0.8 if f["denm_distance"] > 50 and f["claimed_speed"] > 6 else 0.55

            hits.append(RuleHit("event_corroboration", "fake_accident", score,

                                "accident observed by nearby vehicles or reporter at the scene",

                                f"no vehicle within 80 m, reporter {f['denm_distance']:.0f} m away at {f['claimed_speed'] * 3.6:.0f} km/h"))

    if f["event_emergency"] and not f["registered_emergency"] and not f["type_mismatch"]:

        hits.append(RuleHit("emergency_authorization", "emergency_spoofing", 0.9,

                            "emergency DENM from registered emergency vehicle",

                            f"sent by registered {ctx.get('registered_type')}"))



    return hits
